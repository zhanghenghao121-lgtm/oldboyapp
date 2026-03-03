import json
import logging
import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.models import AICustomerSetting, ChatMessage, HumanHandoverTicket, HumanReplyClearState
from apps.ai_customer.services import build_system_prompt, search_context, stream_llm_answer

logger = logging.getLogger(__name__)


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _sse_error(message: str, status: int = 400):
    body = "data: " + json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n\n"
    return StreamingHttpResponse(body, status=status, content_type="text/event-stream")


def _notify_feishu_if_needed(setting: AICustomerSetting, ticket: HumanHandoverTicket):
    webhook = (setting.feishu_webhook_url or "").strip()
    if not webhook:
        return
    payload = {
        "msg_type": "text",
        "content": {
            "text": (
                f"[AI客服转人工]\n"
                f"用户ID: {ticket.user_id}\n"
                f"问题: {ticket.question[:300]}\n"
                f"工单ID: {ticket.id}"
            )
        },
    }
    try:
        requests.post(webhook, json=payload, timeout=8)
    except Exception:
        pass


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def chat_history(request):
    rows = ChatMessage.objects.filter(user=request.user).order_by("-id")[:30]
    items = [
        {
            "id": row.id,
            "role": row.role,
            "content": row.content,
            "attachments": row.attachments or [],
            "created_at": row.created_at,
        }
        for row in reversed(list(rows))
    ]
    setting = AICustomerSetting.singleton()
    return ok(
        {
            "enabled": setting.enabled,
            "no_answer_text": setting.no_answer_text,
            "messages": items,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def human_replies(request):
    qs = HumanHandoverTicket.objects.filter(user=request.user).exclude(admin_reply="")
    clear_state = HumanReplyClearState.objects.filter(user=request.user).only("cleared_at").first()
    if clear_state and clear_state.cleared_at:
        qs = qs.filter(updated_at__gt=clear_state.cleared_at)
    rows = qs.order_by("-updated_at")[:100]
    return ok(
        {
            "list": [
                {
                    "id": row.id,
                    "question": row.question,
                    "admin_reply": row.admin_reply,
                    "status": row.status,
                    "replied_at": row.updated_at,
                }
                for row in rows
            ]
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def clear_human_replies(request):
    HumanReplyClearState.objects.update_or_create(
        user=request.user,
        defaults={"cleared_at": timezone.now()},
    )
    return ok({"cleared": True})


@csrf_exempt
def chat_stream(request):
    try:
        if not request.user.is_authenticated:
            return _sse_error("请先登录", 401)

        if request.method != "POST":
            return _sse_error("Method not allowed", 405)

        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        message = str(payload.get("message", "")).strip()
        attachments = payload.get("attachments") or []
        if not isinstance(attachments, list):
            attachments = []
        if not message:
            return _sse_error("消息不能为空", 400)

        setting = AICustomerSetting.singleton()
        if not setting.enabled:
            return _sse_error("AI客服已关闭", 403)

        ChatMessage.objects.create(
            user=request.user,
            role=ChatMessage.ROLE_USER,
            content=message,
            attachments=attachments,
        )

        context_hits = []
        try:
            context_hits = search_context(message, top_k=settings.AI_CS_TOP_K)
        except Exception:
            context_hits = []

        system_prompt = build_system_prompt(setting, context_hits)
        recent = ChatMessage.objects.filter(user=request.user).order_by("-id")[:8]
        recent_messages = []
        for row in reversed(list(recent)):
            recent_messages.append({"role": row.role, "content": row.content})

        llm_messages = [{"role": "system", "content": system_prompt}, *recent_messages]
    except Exception as exc:
        logger.exception("chat_stream fatal error: %s", exc)
        return _sse_error("服务暂时不可用，请稍后重试", 500)

    def gen():
        full = ""
        handover = False
        ticket_id = None
        try:
            for token in stream_llm_answer(llm_messages):
                full += token
                yield "data: " + json.dumps({"type": "delta", "content": token}, ensure_ascii=False) + "\n\n"

            if "[NEED_HUMAN]" in full:
                handover = True
                full = full.replace("[NEED_HUMAN]", "").strip()
            if not full:
                handover = True
                full = setting.no_answer_text

            ChatMessage.objects.create(
                user=request.user,
                role=ChatMessage.ROLE_ASSISTANT,
                content=full,
                attachments=[],
            )

            if handover:
                ticket = HumanHandoverTicket.objects.create(
                    user=request.user,
                    question=message,
                    ai_reply=full,
                    attachments=attachments,
                    status=HumanHandoverTicket.STATUS_UNREAD,
                )
                ticket_id = ticket.id
                _notify_feishu_if_needed(setting, ticket)

            yield "data: " + json.dumps(
                {
                    "type": "done",
                    "content": full,
                    "handover": handover,
                    "ticket_id": ticket_id,
                },
                ensure_ascii=False,
            ) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n"

    response = StreamingHttpResponse(gen(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
