import threading

from django.conf import settings
from django.db import close_old_connections
from celery import shared_task
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.models import KnowledgeDocument, KnowledgeChunk
from apps.ai_customer.services import (
    delete_vector_ids,
    parse_text_file,
    chunk_text,
    split_texts_for_embedding,
    embed_texts,
    upsert_chunks,
)


def _download_source_bytes(source_key: str) -> bytes:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise RuntimeError("COS配置不完整")
    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    obj = client.get_object(Bucket=settings.COS_BUCKET, Key=source_key)
    body = obj.get("Body")
    if body is None:
        raise RuntimeError("知识库源文件为空")
    if hasattr(body, "get_raw_stream"):
        raw = body.get_raw_stream().read()
    elif hasattr(body, "read"):
        raw = body.read()
    else:
        raw = b""
    if not raw:
        raise RuntimeError("知识库源文件为空")
    return raw


def _process_knowledge_document(doc_id: int):
    doc = KnowledgeDocument.objects.filter(id=doc_id).first()
    if not doc:
        return
    if doc.status == KnowledgeDocument.STATUS_CANCELED:
        return
    if doc.status == KnowledgeDocument.STATUS_SUCCESS:
        return
    if not doc.source_key:
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = "缺少源文件"
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return

    try:
        raw = _download_source_bytes(doc.source_key)
        doc.refresh_from_db(fields=["status"])
        if doc.status == KnowledgeDocument.STATUS_CANCELED:
            return
        text = parse_text_file(doc.source_name, raw)
        chunks = chunk_text(text)
        if not chunks:
            raise RuntimeError("解析后内容为空")
        batch_size = max(int(getattr(settings, "AI_CS_EMBED_BATCH_SIZE", 64)), 1)
        batch_max_chars = max(int(getattr(settings, "AI_CS_EMBED_BATCH_MAX_CHARS", 18000)), 1)
        total = 0
        inserted_vector_ids = []
        for batch in split_texts_for_embedding(chunks, max_items=batch_size, max_chars=batch_max_chars):
            doc.refresh_from_db(fields=["status"])
            if doc.status == KnowledgeDocument.STATUS_CANCELED:
                if inserted_vector_ids:
                    try:
                        delete_vector_ids(inserted_vector_ids)
                    except Exception:
                        pass
                    KnowledgeChunk.objects.filter(document_id=doc.id).delete()
                return
            vectors = embed_texts(batch)
            vector_ids = upsert_chunks(doc.id, batch, vectors, start_index=total)
            inserted_vector_ids.extend(vector_ids)
            rows = [
                KnowledgeChunk(document=doc, chunk_index=total + i, text=batch[i], vector_id=vector_ids[i])
                for i in range(len(batch))
            ]
            KnowledgeChunk.objects.bulk_create(rows, batch_size=200)
            total += len(batch)

        doc.refresh_from_db(fields=["status"])
        if doc.status == KnowledgeDocument.STATUS_CANCELED:
            if inserted_vector_ids:
                try:
                    delete_vector_ids(inserted_vector_ids)
                except Exception:
                    pass
                KnowledgeChunk.objects.filter(document_id=doc.id).delete()
            return
        doc.status = KnowledgeDocument.STATUS_SUCCESS
        doc.chunk_count = total
        doc.error_message = ""
        doc.save(update_fields=["status", "chunk_count", "error_message", "updated_at"])
    except Exception as exc:
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = str(exc)[:255]
        doc.save(update_fields=["status", "error_message", "updated_at"])


@shared_task(bind=True, name="ai_customer.knowledge_vectorize")
def knowledge_vectorize_task(self, doc_id: int):
    _process_knowledge_document(doc_id)


def _thread_run(doc_id: int):
    close_old_connections()
    try:
        _process_knowledge_document(doc_id)
    finally:
        close_old_connections()


def dispatch_knowledge_vectorize(doc_id: int):
    use_celery = bool(getattr(settings, "AI_CS_USE_CELERY", True))
    if use_celery:
        try:
            knowledge_vectorize_task.delay(doc_id)
            return
        except Exception:
            pass
    t = threading.Thread(target=_thread_run, args=(doc_id,), daemon=True)
    t.start()
