import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.ai_customer.models import (
    AICustomerSetting,
    HumanHandoverTicket,
    KnowledgeChunk,
    KnowledgeDocument,
)
from apps.ai_customer.services import chunk_text, embed_texts, parse_text_file, upsert_chunks
from apps.console.permissions import IsConsoleAdmin


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


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
    setting.enabled = bool(payload.get("enabled", setting.enabled))
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
    if file_obj.size > 10 * 1024 * 1024:
        return bad("知识库文件不能超过10MB")

    doc = KnowledgeDocument.objects.create(
        title=title or file_obj.name,
        source_name=file_obj.name,
        created_by=getattr(request, "console_user", None),
        status=KnowledgeDocument.STATUS_PENDING,
    )

    try:
        raw = file_obj.read()
        text = parse_text_file(file_obj.name, raw)
        chunks = chunk_text(text)
        if not chunks:
            raise RuntimeError("解析后内容为空")
        vectors = embed_texts(chunks)
        vector_ids = upsert_chunks(doc.id, chunks, vectors)
        objs = [
            KnowledgeChunk(document=doc, chunk_index=i, text=chunk, vector_id=vector_ids[i])
            for i, chunk in enumerate(chunks)
        ]
        KnowledgeChunk.objects.bulk_create(objs)
        doc.status = KnowledgeDocument.STATUS_SUCCESS
        doc.chunk_count = len(chunks)
        doc.error_message = ""
        doc.save(update_fields=["status", "chunk_count", "error_message", "updated_at"])
        return ok({"id": doc.id, "chunk_count": len(chunks), "status": doc.status})
    except Exception as exc:
        doc.status = KnowledgeDocument.STATUS_FAILED
        doc.error_message = str(exc)[:255]
        doc.save(update_fields=["status", "error_message", "updated_at"])
        return bad(f"向量化失败：{exc}", 500)


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def ai_cs_tickets(request):
    rows = HumanHandoverTicket.objects.select_related("user").all()[:200]
    return ok(
        [
            {
                "id": row.id,
                "username": row.user.username,
                "question": row.question,
                "ai_reply": row.ai_reply,
                "attachments": row.attachments,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    )


@api_view(["PATCH"])
@permission_classes([IsConsoleAdmin])
@csrf_exempt
def ai_cs_ticket_update(request, ticket_id: int):
    row = HumanHandoverTicket.objects.filter(id=ticket_id).first()
    if not row:
        return bad("工单不存在", 404)
    status = str(request.data.get("status", "")).strip()
    if status not in [HumanHandoverTicket.STATUS_OPEN, HumanHandoverTicket.STATUS_RESOLVED]:
        return bad("状态不支持")
    row.status = status
    row.save(update_fields=["status", "updated_at"])
    return ok({"id": row.id, "status": row.status})
