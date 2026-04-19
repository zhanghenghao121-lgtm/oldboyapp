import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import timedelta
from datetime import datetime
from pathlib import Path
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.conf import settings
from django.utils import timezone
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.models import (
    AICustomerSetting,
    HumanHandoverTicket,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeUploadSession,
)
from apps.ai_customer.services import embed_texts, upsert_chunks, split_texts_for_embedding, delete_vector_ids
from apps.ai_customer.knowledge_tasks import dispatch_knowledge_vectorize
from apps.ai_customer.memory_services import get_recent_messages
from apps.ai_customer.models import ChatSession
from apps.ai_memory.models import AIConversationSummary, AIUserFact
from apps.ai_memory.services.summary_memory import SummaryMemoryService
from apps.ai_memory.services.memory_orchestrator import MemoryOrchestrator
from apps.console.permissions import IsConsoleAdmin

logger = logging.getLogger(__name__)
ALLOWED_KNOWLEDGE_EXTS = {".json", ".jsonl", ".csv", ".xlsx", ".txt", ".md"}


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _to_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _validate_knowledge_file_name(file_name: str):
    ext = Path(file_name or "").suffix.lower()
    if ext not in ALLOWED_KNOWLEDGE_EXTS:
        raise ValueError("仅支持 json/jsonl/csv/xlsx/txt/md 文件")
    return ext


def _knowledge_upload_dir(upload_id: str) -> str:
    base = (getattr(settings, "AI_CS_KNOWLEDGE_TMP_DIR", "") or "").strip()
    root = base or os.path.join(tempfile.gettempdir(), "oldboyapp_ai_knowledge")
    return os.path.join(root, upload_id)


def _cleanup_knowledge_upload(upload_id: str):
    path = _knowledge_upload_dir(upload_id)
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def _upload_knowledge_source(file_name: str, raw: bytes = None, local_path: str = ""):
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise RuntimeError("COS配置不完整")
    ext = ""
    if "." in (file_name or ""):
        ext = "." + file_name.split(".")[-1].lower()
    key = f"ai-customer/knowledge/raw/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}{ext}"
    timeout_s = max(int(getattr(settings, "AI_CS_KNOWLEDGE_COS_TIMEOUT", 900)), 60)
    multipart_threshold_mb = max(int(getattr(settings, "AI_CS_KNOWLEDGE_MULTIPART_THRESHOLD_MB", 8)), 1)
    part_size_mb = max(int(getattr(settings, "AI_CS_KNOWLEDGE_PART_SIZE_MB", 8)), 1)
    max_threads = max(int(getattr(settings, "AI_CS_KNOWLEDGE_UPLOAD_THREADS", 3)), 1)
    max_retries = max(int(getattr(settings, "AI_CS_KNOWLEDGE_COS_RETRIES", 2)), 0)

    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
        Timeout=timeout_s,
    )
    client = CosS3Client(config)
    if local_path:
        size_mb = max(float(os.path.getsize(local_path)) / (1024 * 1024), 0)
    else:
        size_mb = len(raw or b"") / (1024 * 1024)
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            if size_mb >= multipart_threshold_mb:
                if local_path:
                    tmp_path = local_path
                    clean_tmp = False
                else:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext or ".bin") as tmp:
                        tmp.write(raw or b"")
                        tmp_path = tmp.name
                    clean_tmp = True
                try:
                    client.upload_file(
                        Bucket=settings.COS_BUCKET,
                        Key=key,
                        LocalFilePath=tmp_path,
                        PartSize=part_size_mb,
                        MAXThread=max_threads,
                    )
                finally:
                    if clean_tmp:
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
            else:
                if local_path:
                    with open(local_path, "rb") as f:
                        body = f.read()
                else:
                    body = raw or b""
                client.put_object(
                    Bucket=settings.COS_BUCKET,
                    Body=body,
                    Key=key,
                    ContentType="application/octet-stream",
                )
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            time.sleep(min(2 ** attempt, 3))
    if last_exc:
        raise last_exc
    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    return key, url


def _create_knowledge_doc(title: str, source_name: str, source_key: str, source_url: str, user):
    doc = KnowledgeDocument.objects.create(
        title=title or source_name,
        source_name=source_name,
        source_key=source_key,
        source_url=source_url,
        created_by=user,
        status=KnowledgeDocument.STATUS_PENDING,
        error_message="",
    )
    dispatch_knowledge_vectorize(doc.id)
    return doc


@api_view(["GET", "PUT"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_settings(request):
    setting = AICustomerSetting.singleton()
    if request.method == "GET":
        return ok(
            {
                "enabled": setting.enabled,
                "tone_style": setting.tone_style,
                "base_prompt": setting.base_prompt,
                "no_answer_text": setting.no_answer_text,
                "feishu_bot_config_url": setting.feishu_bot_config_url,
                "feishu_webhook_url": setting.feishu_webhook_url,
            }
        )

    payload = request.data or {}
    setting.enabled = _to_bool(payload.get("enabled"), setting.enabled)
    setting.tone_style = str(payload.get("tone_style", setting.tone_style)).strip() or setting.tone_style
    setting.base_prompt = str(payload.get("base_prompt", setting.base_prompt)).strip() or setting.base_prompt
    setting.no_answer_text = str(payload.get("no_answer_text", setting.no_answer_text)).strip() or setting.no_answer_text
    setting.feishu_bot_config_url = str(payload.get("feishu_bot_config_url", setting.feishu_bot_config_url)).strip()
    setting.feishu_webhook_url = str(payload.get("feishu_webhook_url", setting.feishu_webhook_url)).strip()
    setting.save()
    return ok({"updated": True})


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_cs_docs(request):
    rows = KnowledgeDocument.objects.all().order_by("-id")[:200]
    status_text_map = {
        KnowledgeDocument.STATUS_PENDING: "排队中",
        KnowledgeDocument.STATUS_RUNNING: "处理中",
        KnowledgeDocument.STATUS_SUCCESS: "成功",
        KnowledgeDocument.STATUS_FAILED: "失败",
        KnowledgeDocument.STATUS_CANCELED: "取消上传",
    }
    return ok(
        [
            {
                "id": row.id,
                "title": row.title,
                "source_name": row.source_name,
                "status": row.status,
                "status_text": status_text_map.get(row.status, row.status),
                "chunk_count": row.chunk_count,
                "error_message": row.error_message,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    )


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_upload_knowledge(request):
    file_obj = request.FILES.get("file")
    title = str(request.data.get("title", "")).strip()
    if not file_obj:
        return bad("请上传文件")
    try:
        _validate_knowledge_file_name(file_obj.name)
    except Exception as exc:
        return bad(str(exc))
    max_upload_size = max(int(getattr(settings, "AI_CS_KNOWLEDGE_MAX_UPLOAD_SIZE", 100 * 1024 * 1024)), 1)
    if file_obj.size > max_upload_size:
        return bad(f"知识库文件不能超过{max_upload_size // (1024 * 1024)}MB")

    try:
        raw = file_obj.read()
        source_key, source_url = _upload_knowledge_source(file_obj.name, raw)
        doc = _create_knowledge_doc(
            title=title or file_obj.name,
            source_name=file_obj.name,
            source_key=source_key,
            source_url=source_url,
            user=getattr(request, "console_user", None),
        )
        return ok({"id": doc.id, "chunk_count": 0, "status": doc.status, "queued": True})
    except Exception as exc:
        logger.exception("ai_cs_upload_knowledge failed: %s", exc)
        return bad(f"向量化失败：{exc}", 500)


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_upload_knowledge_init(request):
    payload = request.data or {}
    file_name = str(payload.get("file_name", "")).strip()
    title = str(payload.get("title", "")).strip()
    fingerprint = str(payload.get("fingerprint", "")).strip()
    try:
        file_size = int(payload.get("file_size") or 0)
    except (TypeError, ValueError):
        file_size = 0
    if not file_name or file_size <= 0:
        return bad("文件参数不完整")
    try:
        _validate_knowledge_file_name(file_name)
    except Exception as exc:
        return bad(str(exc))
    max_upload_size = max(int(getattr(settings, "AI_CS_KNOWLEDGE_MAX_UPLOAD_SIZE", 100 * 1024 * 1024)), 1)
    if file_size > max_upload_size:
        return bad(f"知识库文件不能超过{max_upload_size // (1024 * 1024)}MB")

    chunk_size = max(int(getattr(settings, "AI_CS_KNOWLEDGE_CHUNK_SIZE", 2 * 1024 * 1024)), 256 * 1024)
    total_chunks = max((file_size + chunk_size - 1) // chunk_size, 1)
    now = timezone.now()
    expire_hours = max(int(getattr(settings, "AI_CS_KNOWLEDGE_UPLOAD_EXPIRE_HOURS", 24)), 1)
    user = getattr(request, "console_user", None)

    if fingerprint:
        existing = (
            KnowledgeUploadSession.objects.filter(
                created_by=user,
                file_fingerprint=fingerprint,
                file_name=file_name,
                file_size=file_size,
                status=KnowledgeUploadSession.STATUS_UPLOADING,
                expires_at__gt=now,
            )
            .order_by("-id")
            .first()
        )
        if existing:
            return ok(
                {
                    "upload_id": existing.upload_id,
                    "chunk_size": existing.chunk_size,
                    "total_chunks": existing.total_chunks,
                    "uploaded_chunks": existing.uploaded_chunks or [],
                    "progress": round(100 * len(existing.uploaded_chunks or []) / max(existing.total_chunks, 1), 2),
                }
            )

    upload_id = uuid.uuid4().hex
    os.makedirs(_knowledge_upload_dir(upload_id), exist_ok=True)
    session = KnowledgeUploadSession.objects.create(
        upload_id=upload_id,
        file_name=file_name,
        file_size=file_size,
        file_fingerprint=fingerprint,
        title=title[:200],
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        uploaded_chunks=[],
        created_by=user,
        status=KnowledgeUploadSession.STATUS_UPLOADING,
        expires_at=now + timedelta(hours=expire_hours),
    )
    return ok(
        {
            "upload_id": session.upload_id,
            "chunk_size": session.chunk_size,
            "total_chunks": session.total_chunks,
            "uploaded_chunks": [],
            "progress": 0,
        }
    )


def _get_upload_session(request, upload_id: str):
    user = getattr(request, "console_user", None)
    now = timezone.now()
    row = (
        KnowledgeUploadSession.objects.filter(
            upload_id=upload_id,
            created_by=user,
            expires_at__gt=now,
        )
        .order_by("-id")
        .first()
    )
    return row


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_cs_upload_knowledge_status(request):
    upload_id = str(request.query_params.get("upload_id", "")).strip()
    if not upload_id:
        return bad("缺少upload_id")
    row = _get_upload_session(request, upload_id)
    if not row:
        return bad("上传会话不存在或已过期", 404)
    uploaded_chunks = row.uploaded_chunks or []
    return ok(
        {
            "upload_id": row.upload_id,
            "status": row.status,
            "chunk_size": row.chunk_size,
            "total_chunks": row.total_chunks,
            "uploaded_chunks": uploaded_chunks,
            "progress": round(100 * len(uploaded_chunks) / max(row.total_chunks, 1), 2),
            "completed_doc_id": row.completed_doc_id,
        }
    )


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_upload_knowledge_chunk(request):
    upload_id = str(request.data.get("upload_id", "")).strip()
    file_obj = request.FILES.get("chunk")
    if not upload_id or not file_obj:
        return bad("缺少分片参数")
    row = _get_upload_session(request, upload_id)
    if not row:
        return bad("上传会话不存在或已过期", 404)
    if row.status != KnowledgeUploadSession.STATUS_UPLOADING:
        return bad("上传会话状态不可写入", 400)

    try:
        chunk_index = int(request.data.get("chunk_index"))
    except (TypeError, ValueError):
        return bad("chunk_index无效")
    if chunk_index < 0 or chunk_index >= row.total_chunks:
        return bad("chunk_index超出范围")

    uploaded = set(int(item) for item in (row.uploaded_chunks or []) if str(item).isdigit())
    if chunk_index in uploaded:
        return ok(
            {
                "upload_id": row.upload_id,
                "chunk_index": chunk_index,
                "progress": round(100 * len(uploaded) / max(row.total_chunks, 1), 2),
                "uploaded_count": len(uploaded),
                "total_chunks": row.total_chunks,
            }
        )

    upload_dir = _knowledge_upload_dir(upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    part_path = os.path.join(upload_dir, f"{chunk_index:06d}.part")
    with open(part_path, "wb") as f:
        for piece in file_obj.chunks():
            f.write(piece)

    uploaded.add(chunk_index)
    row.uploaded_chunks = sorted(uploaded)
    row.expires_at = timezone.now() + timedelta(
        hours=max(int(getattr(settings, "AI_CS_KNOWLEDGE_UPLOAD_EXPIRE_HOURS", 24)), 1)
    )
    row.save(update_fields=["uploaded_chunks", "expires_at", "updated_at"])
    return ok(
        {
            "upload_id": row.upload_id,
            "chunk_index": chunk_index,
            "progress": round(100 * len(row.uploaded_chunks) / max(row.total_chunks, 1), 2),
            "uploaded_count": len(row.uploaded_chunks),
            "total_chunks": row.total_chunks,
        }
    )


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_upload_knowledge_complete(request):
    upload_id = str(request.data.get("upload_id", "")).strip()
    title = str(request.data.get("title", "")).strip()
    if not upload_id:
        return bad("缺少upload_id")
    row = _get_upload_session(request, upload_id)
    if not row:
        return bad("上传会话不存在或已过期", 404)

    if row.status == KnowledgeUploadSession.STATUS_COMPLETED and row.completed_doc_id:
        return ok({"id": row.completed_doc_id, "chunk_count": 0, "status": "pending", "queued": True})

    uploaded = set(int(item) for item in (row.uploaded_chunks or []) if str(item).isdigit())
    if len(uploaded) < row.total_chunks:
        return bad("文件仍在上传中，请先完成全部分片")

    upload_dir = _knowledge_upload_dir(upload_id)
    if not os.path.isdir(upload_dir):
        return bad("分片文件不存在，请重新上传", 404)

    merged_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(row.file_name).suffix or ".bin") as tmp:
            merged_path = tmp.name
            for idx in range(row.total_chunks):
                part_path = os.path.join(upload_dir, f"{idx:06d}.part")
                if not os.path.exists(part_path):
                    raise RuntimeError(f"分片缺失: {idx}")
                with open(part_path, "rb") as part:
                    shutil.copyfileobj(part, tmp, length=1024 * 1024)

        source_key, source_url = _upload_knowledge_source(row.file_name, local_path=merged_path)
        doc = _create_knowledge_doc(
            title=title or row.title or row.file_name,
            source_name=row.file_name,
            source_key=source_key,
            source_url=source_url,
            user=getattr(request, "console_user", None),
        )
        row.status = KnowledgeUploadSession.STATUS_COMPLETED
        row.completed_doc_id = doc.id
        row.save(update_fields=["status", "completed_doc_id", "updated_at"])
        _cleanup_knowledge_upload(upload_id)
        return ok({"id": doc.id, "chunk_count": 0, "status": doc.status, "queued": True})
    except Exception as exc:
        logger.exception("ai_cs_upload_knowledge_complete failed: %s", exc)
        return bad(f"向量化失败：{exc}", 500)
    finally:
        if merged_path and os.path.exists(merged_path):
            try:
                os.remove(merged_path)
            except OSError:
                pass


@api_view(["DELETE"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_doc_delete(request, doc_id: int):
    doc = KnowledgeDocument.objects.filter(id=doc_id).first()
    if not doc:
        return bad("文档不存在", 404)

    try:
        vector_ids = list(KnowledgeChunk.objects.filter(document_id=doc.id).values_list("vector_id", flat=True))
        if vector_ids:
            delete_vector_ids(vector_ids)
    except Exception as exc:
        logger.exception("ai_cs_doc_delete vector delete failed: %s", exc)
        return bad(f"删除向量失败：{exc}", 500)

    try:
        doc.delete()
    except Exception as exc:
        logger.exception("ai_cs_doc_delete doc delete failed: %s", exc)
        return bad(f"删除文档失败：{exc}", 500)

    return ok({"deleted": True, "doc_id": doc_id})


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_doc_cancel(request, doc_id: int):
    doc = KnowledgeDocument.objects.filter(id=doc_id).first()
    if not doc:
        return bad("文档不存在", 404)
    if doc.status not in {KnowledgeDocument.STATUS_PENDING, KnowledgeDocument.STATUS_RUNNING}:
        return bad("仅支持取消排队中/处理中任务")

    is_running = doc.status == KnowledgeDocument.STATUS_RUNNING

    try:
        vector_ids = list(KnowledgeChunk.objects.filter(document_id=doc.id).values_list("vector_id", flat=True))
        if vector_ids:
            delete_vector_ids(vector_ids)
        KnowledgeChunk.objects.filter(document_id=doc.id).delete()
    except Exception as exc:
        logger.exception("ai_cs_doc_cancel cleanup failed: %s", exc)
        return bad(f"取消上传失败：{exc}", 500)

    doc.status = KnowledgeDocument.STATUS_CANCELED
    doc.chunk_count = 0
    doc.error_message = "停止向量化" if is_running else "取消上传"
    doc.save(update_fields=["status", "chunk_count", "error_message", "updated_at"])
    return ok({"id": doc.id, "status": doc.status})


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_cs_tickets(request):
    rows = HumanHandoverTicket.objects.select_related("user").all()[:200]
    unread_count = HumanHandoverTicket.objects.filter(status=HumanHandoverTicket.STATUS_UNREAD).count()
    return ok(
        {
            "list": [
                {
                    "id": row.id,
                    "username": row.user.username,
                    "question": row.question,
                    "ai_reply": row.ai_reply,
                    "admin_reply": row.admin_reply,
                    "synced_to_knowledge": row.synced_to_knowledge,
                    "attachments": row.attachments,
                    "status": row.status,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "unread_count": unread_count,
        }
    )


@api_view(["PATCH"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_ticket_update(request, ticket_id: int):
    row = HumanHandoverTicket.objects.filter(id=ticket_id).first()
    if not row:
        return bad("工单不存在", 404)
    action = str(request.data.get("action", "")).strip()
    if action == "read":
        row.status = HumanHandoverTicket.STATUS_READ
        row.save(update_fields=["status", "updated_at"])
        return ok({"id": row.id, "status": row.status})
    if action == "ignore":
        row.status = HumanHandoverTicket.STATUS_IGNORED
        row.save(update_fields=["status", "updated_at"])
        return ok({"id": row.id, "status": row.status})
    if action == "reply":
        reply = str(request.data.get("reply", "")).strip()
        if not reply:
            return bad("回复内容不能为空")
        row.admin_reply = reply
        row.status = HumanHandoverTicket.STATUS_READ
        row.synced_to_knowledge = False
        row.save(update_fields=["admin_reply", "status", "synced_to_knowledge", "updated_at"])
        return ok({"id": row.id, "status": row.status, "admin_reply": row.admin_reply})
    return bad("操作不支持")


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_ticket_sync_knowledge(request):
    raw_ids = request.data.get("ticket_ids") or []
    if not isinstance(raw_ids, list) or not raw_ids:
        return bad("请选择要入库的工单")

    ticket_ids = []
    for item in raw_ids:
        try:
            ticket_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    if not ticket_ids:
        return bad("工单参数无效")

    rows = list(HumanHandoverTicket.objects.filter(id__in=ticket_ids).order_by("id"))
    if not rows:
        return bad("工单不存在", 404)

    texts = []
    valid_rows = []
    for row in rows:
        question = (row.question or "").strip()
        answer = (row.admin_reply or "").strip()
        if not question or not answer:
            continue
        text = f"用户问题：{question}\n人工回复：{answer}\n来源工单ID：{row.id}"
        texts.append(text)
        valid_rows.append(row)

    if not texts:
        return bad("所选工单没有可入库的人工回复")

    doc = KnowledgeDocument.objects.create(
        title=f"人工客服回复入库（{len(valid_rows)}条）",
        source_name="human_service_tickets",
        created_by=getattr(request, "console_user", None),
        status=KnowledgeDocument.STATUS_PENDING,
    )

    try:
        batch_size = max(int(getattr(settings, "AI_CS_EMBED_BATCH_SIZE", 64)), 1)
        batch_max_chars = max(int(getattr(settings, "AI_CS_EMBED_BATCH_MAX_CHARS", 18000)), 1)
        total = 0
        for batch in split_texts_for_embedding(texts, max_items=batch_size, max_chars=batch_max_chars):
            vectors = embed_texts(batch)
            vector_ids = upsert_chunks(doc.id, batch, vectors, start_index=total)
            chunks = [
                KnowledgeChunk(document=doc, chunk_index=total + i, text=batch[i], vector_id=vector_ids[i])
                for i in range(len(batch))
            ]
            KnowledgeChunk.objects.bulk_create(chunks, batch_size=200)
            total += len(batch)
        doc.status = KnowledgeDocument.STATUS_SUCCESS
        doc.chunk_count = total
        doc.error_message = ""
        doc.save(update_fields=["status", "chunk_count", "error_message", "updated_at"])

        now = timezone.now()
        for row in valid_rows:
            row.synced_to_knowledge = True
            row.updated_at = now
        HumanHandoverTicket.objects.bulk_update(valid_rows, ["synced_to_knowledge", "updated_at"], batch_size=200)

        return ok({"doc_id": doc.id, "count": total})
    except Exception as exc:
        logger.exception("ai_cs_ticket_sync_knowledge failed: %s", exc)
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = str(exc)[:255]
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return bad(f"入库失败：{exc}", 500)


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_memory_admin_overview(request):
    keyword = str(request.query_params.get("keyword", "")).strip()
    summary_qs = AIConversationSummary.objects.select_related("user", "session").order_by("-updated_at", "-id")
    fact_qs = AIUserFact.objects.select_related("user").order_by("-updated_at", "-id")
    if keyword:
        summary_qs = summary_qs.filter(user__username__icontains=keyword)
        fact_qs = fact_qs.filter(user__username__icontains=keyword)
    summaries = summary_qs[:60]
    facts = fact_qs[:80]
    return ok(
        {
            "summaries": [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": row.user.username,
                    "session_id": row.session_id,
                    "task_stage": row.task_stage,
                    "current_goal": row.current_goal,
                    "recent_decisions": row.recent_decisions or [],
                    "open_questions": row.open_questions or [],
                    "important_entities": row.important_entities or [],
                    "next_action": row.next_action,
                    "version": row.version,
                    "is_active": row.is_active,
                    "updated_at": row.updated_at,
                }
                for row in summaries
            ],
            "facts": [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "username": row.user.username,
                    "fact_key": row.fact_key,
                    "fact_value": row.fact_value,
                    "fact_type": row.fact_type,
                    "confidence": float(row.confidence or 0),
                    "source": row.source,
                    "status": row.status,
                    "version": row.version,
                    "updated_at": row.updated_at,
                }
                for row in facts
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_memory_summary_rebuild(request, session_id: int):
    chat_session = ChatSession.objects.filter(id=session_id).first()
    if not chat_session:
        return bad("会话不存在", 404)
    orchestrator = MemoryOrchestrator()
    ai_session = orchestrator.ensure_ai_session(chat_session.user, chat_session)
    recent_messages = get_recent_messages(chat_session, limit=max(int(getattr(settings, "AI_MEMORY_SUMMARY_WINDOW", 16)), 4))
    if not recent_messages:
        return bad("最近对话为空，无法重建摘要")
    service = SummaryMemoryService()
    row = service.force_update_summary(ai_session, recent_messages)
    return ok(
        {
            "id": row.id,
            "session_id": row.session_id,
            "task_stage": row.task_stage,
            "current_goal": row.current_goal,
            "version": row.version,
            "updated_at": row.updated_at,
        }
    )


@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_memory_fact_inactivate(request, fact_id: int):
    row = AIUserFact.objects.filter(id=fact_id).first()
    if not row:
        return bad("事实不存在", 404)
    if row.status != AIUserFact.STATUS_ACTIVE:
        return bad("该事实已失效")
    row.status = AIUserFact.STATUS_INACTIVE
    row.save(update_fields=["status", "updated_at"])
    return ok({"id": row.id, "status": row.status})
