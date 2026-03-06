import re
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.db import close_old_connections
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from apps.ai_customer.models import ChatMessage, ChatSession, MemoryChunk, UserProfileMemory
from apps.ai_customer.services import embed_texts


def _memory_enabled() -> bool:
    return bool(getattr(settings, "AI_MEMORY_ENABLED", True))


def get_or_create_active_session(user) -> ChatSession:
    row = ChatSession.objects.filter(user=user, is_active=True).order_by("-updated_at", "-id").first()
    if row:
        return row
    return ChatSession.objects.create(user=user, title="新的对话", scene_type="general", is_active=True)


def get_session_for_user(user, session_id: Optional[int]) -> ChatSession:
    if session_id:
        row = ChatSession.objects.filter(id=session_id, user=user).first()
        if row:
            if not row.is_active:
                row.is_active = True
                row.save(update_fields=["is_active", "updated_at"])
            return row
    return get_or_create_active_session(user)


def list_sessions(user, limit: int = 30) -> List[Dict]:
    rows = ChatSession.objects.filter(user=user).order_by("-updated_at", "-id")[: max(int(limit or 1), 1)]
    return [
        {
            "id": row.id,
            "title": row.title,
            "scene_type": row.scene_type,
            "summary": row.summary,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]


def create_session(user, title: str = "", scene_type: str = "general") -> ChatSession:
    title = (title or "").strip() or "新的对话"
    scene = (scene_type or "general").strip() or "general"
    ChatSession.objects.filter(user=user, is_active=True).update(is_active=False)
    return ChatSession.objects.create(user=user, title=title[:120], scene_type=scene[:32], is_active=True)


def activate_session(user, session_id: int) -> Optional[ChatSession]:
    row = ChatSession.objects.filter(id=session_id, user=user).first()
    if not row:
        return None
    ChatSession.objects.filter(user=user, is_active=True).exclude(id=row.id).update(is_active=False)
    if not row.is_active:
        row.is_active = True
        row.save(update_fields=["is_active", "updated_at"])
    return row


def maybe_update_session_title(session: ChatSession, user_message: str):
    if not session:
        return
    if (session.title or "").strip() not in {"", "新的对话"}:
        return
    text = re.sub(r"\s+", " ", str(user_message or "").strip())
    if not text:
        return
    session.title = text[:24]
    session.save(update_fields=["title", "updated_at"])


def get_recent_messages(session: ChatSession, limit: int = 8) -> List[Dict[str, str]]:
    rows = ChatMessage.objects.filter(session=session).order_by("-id")[: max(int(limit or 1), 1)]
    output = []
    for row in reversed(list(rows)):
        output.append({"role": row.role, "content": row.content})
    return output


def extract_profile_memory_candidates(text: str) -> Dict[str, str]:
    msg = (text or "").strip()
    if not msg:
        return {}

    pairs: Dict[str, str] = {}
    patterns = [
        (r"(?:我叫|叫我)\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{1,24})", "preferred_name"),
        (r"(?:我的项目|项目名)\s*(?:是|叫)\s*([^，。\n]{2,60})", "project_name"),
        (r"(?:我喜欢|偏好)\s*([^，。\n]{2,60})", "preference"),
        (r"(?:请用|以后都用)\s*([^，。\n]{2,40})(?:语气|风格)", "response_style"),
        (r"(?:请称呼我|你可以叫我)\s*([^，。\n]{1,24})", "preferred_name"),
    ]
    for pattern, key in patterns:
        m = re.search(pattern, msg)
        if not m:
            continue
        value = (m.group(1) or "").strip(" ：:，,。.")
        if value:
            pairs[key] = value[:120]
    return pairs


def upsert_profile_memories(user, text: str):
    if not _memory_enabled():
        return
    pairs = extract_profile_memory_candidates(text)
    for key, value in pairs.items():
        UserProfileMemory.objects.update_or_create(
            user=user,
            mem_key=key,
            defaults={"mem_value": value, "confidence": Decimal("0.82")},
        )


def get_profile_memory_lines(user, limit: int = 10) -> List[str]:
    if not _memory_enabled():
        return []
    rows = UserProfileMemory.objects.filter(user=user).order_by("-updated_at")[: max(int(limit or 1), 1)]
    lines = []
    for row in rows:
        key = (row.mem_key or "").strip()
        value = (row.mem_value or "").strip()
        if key and value:
            lines.append(f"{key}: {value}")
    return lines


def _qdrant_client() -> QdrantClient:
    url = (settings.QDRANT_URL or "").strip()
    if not url:
        raise RuntimeError("QDRANT_URL 未配置")
    key = (settings.QDRANT_API_KEY or "").strip()
    return QdrantClient(url=url, api_key=key or None, timeout=30)


def _memory_collection() -> str:
    return (getattr(settings, "AI_MEMORY_COLLECTION", "ai_customer_memory") or "ai_customer_memory").strip()


def ensure_memory_collection(vector_size: int):
    client = _qdrant_client()
    collection = _memory_collection()
    if client.collection_exists(collection):
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def store_semantic_memory(user_id: int, session_id: Optional[int], content: str, source: str = "chat"):
    if not _memory_enabled():
        return
    text = (content or "").strip()
    min_chars = max(int(getattr(settings, "AI_MEMORY_CHUNK_MIN_CHARS", 20)), 1)
    if len(text) < min_chars:
        return

    vectors = embed_texts([text])
    vec = vectors[0]
    ensure_memory_collection(len(vec))
    vector_id = uuid.uuid4().hex
    payload = {
        "user_id": int(user_id),
        "session_id": int(session_id) if session_id else 0,
        "text": text,
        "source": source,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    client = _qdrant_client()
    client.upsert(collection_name=_memory_collection(), points=[PointStruct(id=vector_id, vector=vec, payload=payload)])
    MemoryChunk.objects.create(
        user_id=user_id,
        session_id=session_id,
        content=text,
        vector_id=vector_id,
        source=source[:32],
    )


def search_semantic_memories(user_id: int, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
    if not _memory_enabled():
        return []
    text = (query or "").strip()
    if not text:
        return []
    vectors = embed_texts([text])
    vec = vectors[0]
    client = _qdrant_client()
    flt = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=int(user_id)))])
    result = client.search(
        collection_name=_memory_collection(),
        query_vector=vec,
        query_filter=flt,
        limit=max(int(top_k or 1), 1),
        with_payload=True,
    )
    score_min = float(getattr(settings, "AI_MEMORY_SCORE_MIN", 0.15))
    output: List[Tuple[str, float]] = []
    for item in result:
        score = float(getattr(item, "score", 0.0) or 0.0)
        payload = item.payload or {}
        content = str(payload.get("text") or "").strip()
        if content and score >= score_min:
            output.append((content, score))
    return output


def summarize_session_if_needed(session_id: int):
    if not _memory_enabled():
        return
    trigger_count = max(int(getattr(settings, "AI_MEMORY_SUMMARY_TRIGGER", 12)), 4)
    window = max(int(getattr(settings, "AI_MEMORY_SUMMARY_WINDOW", 16)), 4)
    row = ChatSession.objects.filter(id=session_id).first()
    if not row:
        return
    total = ChatMessage.objects.filter(session_id=session_id).count()
    if total < trigger_count or (total % trigger_count) != 0:
        return

    recent = ChatMessage.objects.filter(session_id=session_id).order_by("-id")[:window]
    lines = []
    for item in reversed(list(recent)):
        who = "用户" if item.role == ChatMessage.ROLE_USER else "助手"
        lines.append(f"{who}: {item.content}")
    dialogue = "\n".join(lines)
    old_summary = (row.summary or "").strip()
    prompt = (
        "请将以下对话压缩为可持续记忆的中文摘要，包含：用户目标、偏好、关键事实、未完成事项。"
        "输出纯文本，120字以内。\n"
        f"历史摘要：{old_summary or '无'}\n"
        f"最近对话：\n{dialogue[:4000]}"
    )

    api_key = (settings.AI_CS_LLM_API_KEY or "").strip()
    if not api_key:
        return
    url = f"{settings.AI_CS_LLM_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.AI_CS_LLM_MODEL,
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "你是记忆压缩助手，只输出摘要正文。"},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_MEMORY_SUMMARY_TIMEOUT", 45)), 10),
        )
        if resp.status_code >= 400:
            return
        body = resp.json()
        summary = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
        if summary:
            row.summary = summary[:1200]
            row.save(update_fields=["summary", "updated_at"])
    except Exception:
        return


def schedule_memory_update(user_id: int, session_id: int, user_message: str, assistant_message: str):
    if not _memory_enabled():
        return

    def _run():
        close_old_connections()
        try:
            session = ChatSession.objects.filter(id=session_id).first()
            if not session:
                return
            user = session.user
            upsert_profile_memories(user, user_message)
            try:
                store_semantic_memory(user_id, session_id, f"用户: {user_message}", source="user")
            except Exception:
                pass
            try:
                store_semantic_memory(user_id, session_id, f"助手: {assistant_message}", source="assistant")
            except Exception:
                pass
            summarize_session_if_needed(session_id)
        finally:
            close_old_connections()

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def get_memory_prompt_parts(user, session: ChatSession, query: str) -> Tuple[List[str], str, List[Tuple[str, float]]]:
    profile_lines = get_profile_memory_lines(user, limit=max(int(getattr(settings, "AI_MEMORY_PROFILE_MAX_ITEMS", 10)), 1))
    session_summary = (session.summary or "").strip() if session else ""
    semantic_hits: List[Tuple[str, float]] = []
    try:
        semantic_hits = search_semantic_memories(
            user.id,
            query,
            top_k=max(int(getattr(settings, "AI_MEMORY_TOP_K", 3)), 1),
        )
    except Exception:
        semantic_hits = []
    return profile_lines, session_summary, semantic_hits
