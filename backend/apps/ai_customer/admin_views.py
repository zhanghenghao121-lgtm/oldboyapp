import logging
import uuid
from datetime import datetime
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.models import (
    AICustomerSetting,
    HumanHandoverTicket,
    KnowledgeChunk,
    KnowledgeDocument,
)
from apps.ai_customer.services import embed_texts, upsert_chunks, split_texts_for_embedding, delete_vector_ids
from apps.ai_customer.knowledge_tasks import dispatch_knowledge_vectorize
from apps.console.permissions import IsConsoleAdmin

logger = logging.getLogger(__name__)


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


def _upload_knowledge_source(file_name: str, raw: bytes):
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise RuntimeError("COS配置不完整")
    ext = ""
    if "." in (file_name or ""):
        ext = "." + file_name.split(".")[-1].lower()
    key = f"ai-customer/knowledge/raw/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}{ext}"
    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Body=raw,
        Key=key,
        ContentType="application/octet-stream",
    )
    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    return key, url


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
                "resume_system_prompt": setting.resume_system_prompt,
                "no_answer_text": setting.no_answer_text,
                "feishu_bot_config_url": setting.feishu_bot_config_url,
                "feishu_webhook_url": setting.feishu_webhook_url,
            }
        )

    payload = request.data or {}
    setting.enabled = _to_bool(payload.get("enabled"), setting.enabled)
    setting.tone_style = str(payload.get("tone_style", setting.tone_style)).strip() or setting.tone_style
    setting.base_prompt = str(payload.get("base_prompt", setting.base_prompt)).strip() or setting.base_prompt
    setting.resume_system_prompt = (
        str(payload.get("resume_system_prompt", setting.resume_system_prompt)).strip() or setting.resume_system_prompt
    )
    setting.no_answer_text = str(payload.get("no_answer_text", setting.no_answer_text)).strip() or setting.no_answer_text
    setting.feishu_bot_config_url = str(payload.get("feishu_bot_config_url", setting.feishu_bot_config_url)).strip()
    setting.feishu_webhook_url = str(payload.get("feishu_webhook_url", setting.feishu_webhook_url)).strip()
    setting.save()
    return ok({"updated": True})


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_cs_docs(request):
    rows = KnowledgeDocument.objects.all().order_by("-id")[:200]
    return ok(
        [
            {
                "id": row.id,
                "title": row.title,
                "source_name": row.source_name,
                "status": row.status,
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
    max_upload_size = max(int(getattr(settings, "AI_CS_KNOWLEDGE_MAX_UPLOAD_SIZE", 100 * 1024 * 1024)), 1)
    if file_obj.size > max_upload_size:
        return bad(f"知识库文件不能超过{max_upload_size // (1024 * 1024)}MB")

    doc = KnowledgeDocument.objects.create(
        title=title or file_obj.name,
        source_name=file_obj.name,
        created_by=getattr(request, "console_user", None),
        status=KnowledgeDocument.STATUS_PENDING,
    )

    try:
        raw = file_obj.read()
        source_key, source_url = _upload_knowledge_source(file_obj.name, raw)
        doc.source_key = source_key
        doc.source_url = source_url
        doc.status = KnowledgeDocument.STATUS_PENDING
        doc.error_message = ""
        doc.save(update_fields=["source_key", "source_url", "status", "error_message", "updated_at"])
        dispatch_knowledge_vectorize(doc.id)
        return ok({"id": doc.id, "chunk_count": 0, "status": doc.status, "queued": True})
    except Exception as exc:
        logger.exception("ai_cs_upload_knowledge failed: %s", exc)
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = str(exc)[:255]
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return bad(f"向量化失败：{exc}", 500)


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

        for row in valid_rows:
            row.synced_to_knowledge = True
            row.save(update_fields=["synced_to_knowledge", "updated_at"])

        return ok({"doc_id": doc.id, "count": total})
    except Exception as exc:
        logger.exception("ai_cs_ticket_sync_knowledge failed: %s", exc)
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = str(exc)[:255]
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return bad(f"入库失败：{exc}", 500)
