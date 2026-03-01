import csv
import io
import json
import uuid
import requests
from decimal import Decimal
from typing import List, Tuple
from openpyxl import load_workbook
from django.conf import settings
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from apps.ai_customer.models import AICustomerSetting


def parse_text_file(file_name: str, raw: bytes) -> str:
    lower = file_name.lower()
    if lower.endswith(".json"):
        data = json.loads(raw.decode("utf-8"))
        if isinstance(data, list):
            return "\n".join(json.dumps(item, ensure_ascii=False) for item in data)
        if isinstance(data, dict):
            return json.dumps(data, ensure_ascii=False)
        return str(data)

    if lower.endswith(".csv"):
        rows = []
        with io.StringIO(raw.decode("utf-8", errors="ignore")) as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(rows)

    if lower.endswith(".xlsx"):
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        lines = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(values_only=True):
                values = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if values:
                    lines.append(" | ".join(values))
        return "\n".join(lines)

    if lower.endswith(".txt") or lower.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")

    raise ValueError("仅支持 json/csv/xlsx/txt/md 文件")


def chunk_text(text: str, size: int = 500, overlap: int = 80) -> List[str]:
    content = (text or "").strip()
    if not content:
        return []
    chunks = []
    start = 0
    total = len(content)
    while start < total:
        end = min(start + size, total)
        piece = content[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= total:
            break
        start = max(end - overlap, 0)
    return chunks


def embed_texts(texts: List[str]) -> List[List[float]]:
    api_key = settings.ARK_API_KEY.strip()
    if not api_key:
        raise RuntimeError("ARK_API_KEY 未配置")
    endpoint = (getattr(settings, "ARK_EMBEDDING_ENDPOINT", "/embeddings/multimodal") or "/embeddings/multimodal").strip()
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint
    url = settings.ARK_EMBEDDING_BASE_URL.rstrip("/") + endpoint
    payload = {"model": settings.ARK_EMBEDDING_MODEL, "input": texts}
    if "multimodal" in endpoint:
        payload = {
            "model": settings.ARK_EMBEDDING_MODEL,
            "instructions": settings.ARK_EMBEDDING_INSTRUCTIONS,
            "input": [{"type": "text", "text": text} for text in texts],
            "dimensions": settings.ARK_EMBEDDING_DIMENSIONS,
            "multi_embedding": {"type": "enabled"},
            "sparse_embedding": {"type": "enabled"},
            "encoding_format": "float",
        }
    timeout_s = max(int(getattr(settings, "ARK_EMBEDDING_TIMEOUT", 8)), 3)
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout_s,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Embedding 请求失败: {exc}")
    if resp.status_code >= 400:
        raise RuntimeError(f"Embedding 接口错误({resp.status_code})")
    data = resp.json()
    items = data.get("data") or []
    if not items:
        raise RuntimeError("Embedding 返回为空")
    items = sorted(items, key=lambda x: x.get("index", 0))

    def pick_dense_embedding(item):
        if item.get("embedding"):
            return item.get("embedding")
        if item.get("dense_embedding"):
            return item.get("dense_embedding")
        emb = item.get("embeddings") or {}
        if isinstance(emb, dict):
            if emb.get("dense_embedding"):
                return emb.get("dense_embedding")
            if emb.get("embedding"):
                return emb.get("embedding")
        return None

    vectors = [pick_dense_embedding(item) for item in items]
    vectors = [vec for vec in vectors if vec]
    if len(vectors) != len(texts):
        raise RuntimeError("Embedding 返回数量异常")
    return vectors


def _qdrant_client() -> QdrantClient:
    url = settings.QDRANT_URL.strip()
    if not url:
        raise RuntimeError("QDRANT_URL 未配置")
    key = settings.QDRANT_API_KEY.strip()
    return QdrantClient(url=url, api_key=key or None, timeout=30)


def ensure_collection(vector_size: int):
    client = _qdrant_client()
    collection = settings.QDRANT_COLLECTION
    exists = client.collection_exists(collection)
    if exists:
        return
    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )


def upsert_chunks(document_id: int, chunks: List[str], vectors: List[List[float]]) -> List[str]:
    if not chunks:
        return []
    ensure_collection(len(vectors[0]))
    client = _qdrant_client()
    collection = settings.QDRANT_COLLECTION
    points = []
    vector_ids = []
    for idx, (text, vec) in enumerate(zip(chunks, vectors)):
        vector_id = uuid.uuid4().hex
        vector_ids.append(vector_id)
        points.append(
            PointStruct(
                id=vector_id,
                vector=vec,
                payload={"document_id": document_id, "chunk_index": idx, "text": text},
            )
        )
    client.upsert(collection_name=collection, points=points)
    return vector_ids


def search_context(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
    if not getattr(settings, "AI_CS_ENABLE_RAG", True):
        return []
    query = (query or "").strip()
    if not query:
        return []
    vectors = embed_texts([query])
    query_vec = vectors[0]
    client = _qdrant_client()
    result = client.search(
        collection_name=settings.QDRANT_COLLECTION,
        query_vector=query_vec,
        limit=max(top_k, 1),
        with_payload=True,
    )
    output = []
    for item in result:
        text = (item.payload or {}).get("text") or ""
        score = float(getattr(item, "score", 0.0) or 0.0)
        if text:
            output.append((text, score))
    return output


def stream_llm_answer(messages):
    base_url = settings.AI_CS_LLM_BASE_URL.rstrip("/")
    model = settings.AI_CS_LLM_MODEL
    api_key = settings.AI_CS_LLM_API_KEY.strip()
    if not api_key:
        raise RuntimeError("AI_CS_LLM_API_KEY 未配置")
    url = f"{base_url}/chat/completions"
    headers = {"Content-Type": "application/json"}
    headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.5,
    }

    with requests.post(url, json=payload, headers=headers, stream=True, timeout=180) as resp:
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM 服务错误({resp.status_code})")
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                yield content


def build_system_prompt(setting: AICustomerSetting, context_blocks: List[Tuple[str, float]]) -> str:
    context_lines = []
    threshold = Decimal(str(settings.AI_CS_CONTEXT_MIN_SCORE))
    for idx, (text, score) in enumerate(context_blocks, start=1):
        if Decimal(str(score)) >= threshold:
            context_lines.append(f"[{idx}] score={score:.4f}\n{text}")
    context_text = "\n\n".join(context_lines) or "无可靠知识库命中"
    return (
        f"{setting.base_prompt}\n"
        f"你的语气风格：{setting.tone_style}\n"
        "请严格遵守：\n"
        "1) 优先依据知识库上下文回答，不得编造事实。\n"
        "2) 若上下文不足，先明确不确定，再给出可执行建议。\n"
        "3) 当无法可靠回答时，必须在回复最后追加 [NEED_HUMAN]。\n"
        f"\n知识库上下文:\n{context_text}\n"
    )
