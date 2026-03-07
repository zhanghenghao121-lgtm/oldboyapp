import uuid
from datetime import datetime
from typing import List, Tuple

from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from apps.ai_customer.services import embed_texts


def _qdrant_client() -> QdrantClient:
    url = (settings.QDRANT_URL or "").strip()
    if not url:
        raise RuntimeError("QDRANT_URL 未配置")
    api_key = (settings.QDRANT_API_KEY or "").strip()
    return QdrantClient(url=url, api_key=api_key or None, timeout=30)


class VectorMemoryService:
    def __init__(self):
        self.collection = (getattr(settings, "AI_MEMORY_QDRANT_COLLECTION", "ai_memory_cases") or "ai_memory_cases").strip()
        self.top_k = max(int(getattr(settings, "AI_MEMORY_VECTOR_TOP_K", 8)), 1)
        self.score_min = float(getattr(settings, "AI_MEMORY_SCORE_MIN", 0.15))
        self.project = (getattr(settings, "AI_MEMORY_PROJECT_NAME", "oldboyapp") or "oldboyapp").strip()

    def ensure_collection(self, vector_size: int):
        client = _qdrant_client()
        if client.collection_exists(self.collection):
            return
        client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def maybe_write_case(
        self,
        *,
        user_id: int,
        session_uuid: str,
        user_message: str,
        assistant_message: str,
        memory_type: str = "solution_case",
    ):
        title = (user_message or "").strip()[:90]
        content = (
            f"标题：{title}\n"
            f"类型：{memory_type}\n"
            f"摘要：{(assistant_message or '').strip()[:240]}\n"
            f"正文：用户问题：{(user_message or '').strip()}\n回答：{(assistant_message or '').strip()}"
        ).strip()
        if len(content) < 120:
            return None
        vector = embed_texts([content])[0]
        self.ensure_collection(len(vector))
        point_id = uuid.uuid4().hex
        payload = {
            "memory_id": point_id,
            "user_id": int(user_id),
            "session_uuid": session_uuid,
            "project": self.project,
            "memory_type": memory_type,
            "title": title,
            "quality_score": 0.85,
            "text": content,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "is_active": True,
        }
        client = _qdrant_client()
        client.upsert(collection_name=self.collection, points=[PointStruct(id=point_id, vector=vector, payload=payload)])
        return point_id

    def search_cases(self, *, user_id: int, query: str, final_k: int = 4) -> List[Tuple[str, float]]:
        text = (query or "").strip()
        if not text:
            return []
        vector = embed_texts([text])[0]
        client = _qdrant_client()
        result = client.search(
            collection_name=self.collection,
            query_vector=vector,
            query_filter=Filter(
                must=[
                    FieldCondition(key="user_id", match=MatchValue(value=int(user_id))),
                    FieldCondition(key="project", match=MatchValue(value=self.project)),
                    FieldCondition(key="is_active", match=MatchValue(value=True)),
                ]
            ),
            limit=self.top_k,
            with_payload=True,
        )
        rows: List[Tuple[str, float]] = []
        for item in result:
            score = float(getattr(item, "score", 0.0) or 0.0)
            if score < self.score_min:
                continue
            payload = item.payload or {}
            text_value = str(payload.get("text") or "").strip()
            if text_value:
                rows.append((text_value, score))
        return rows[: max(int(final_k or 1), 1)]

