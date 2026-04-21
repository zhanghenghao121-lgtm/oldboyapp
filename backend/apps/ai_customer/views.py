import json
import logging
import requests
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.models import (
    AICustomerSetting,
    ChatMessage,
    HumanHandoverTicket,
    HumanReplyClearState,
)
from apps.ai_customer.memory_services import (
    activate_session,
    create_session,
    get_memory_prompt_parts,
    get_or_create_active_session,
    get_recent_messages,
    prune_expired_chat_records,
    get_session_for_user,
    list_sessions,
    maybe_update_session_title,
    schedule_memory_update,
)
from apps.ai_customer.manga_services import (
    MangaScriptError,
    extract_story_source_text,
    generate_manga_storyboard_image,
    generate_manga_storyboard,
    prepare_storyboard_image_sections,
)
from apps.ai_customer.runtime_config import (
    get_assistant_llm_config,
    get_manga_image_prompt,
    get_manga_llm_config,
    get_manga_storyboard_prompt,
)
from apps.ai_customer.services import (
    build_system_prompt,
    generate_image_with_ark,
    has_image_generation_intent,
    has_reliable_context,
    optimize_image_prompt,
    search_context,
    stream_llm_answer,
    web_search,
)
from apps.ai_memory.models import AIConversationSummary, AIUserFact
from apps.ai_memory.services import MemoryOrchestrator

logger = logging.getLogger(__name__)
User = get_user_model()


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _parse_window_days(raw, default=3, minimum=1, maximum=7):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(min(value, maximum), minimum)


def _serialize_model_option(option_id: str, label: str, runtime: dict):
    return {
        "id": option_id,
        "label": label,
        "model": str(runtime.get("model") or "").strip(),
        "base_url": str(runtime.get("base_url") or "").strip(),
    }


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
    prune_expired_chat_records(request.user)
    session_id = request.query_params.get("session_id")
    window_days = _parse_window_days(request.query_params.get("window_days"), default=3)
    try:
        sid = int(session_id) if session_id is not None else None
    except (TypeError, ValueError):
        sid = None
    session = get_session_for_user(request.user, sid)
    cutoff = timezone.now() - timedelta(days=window_days)
    rows = (
        ChatMessage.objects.filter(user=request.user, session=session, created_at__gte=cutoff)
        .order_by("-id")[:100]
    )
    items = [
        {
            "id": row.id,
            "session_id": row.session_id,
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
            "active_session_id": session.id,
            "window_days": window_days,
            "sessions": list_sessions(request.user, days=7),
            "messages": items,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_sessions(request):
    prune_expired_chat_records(request.user)
    if request.method == "GET":
        return ok({"active_session_id": get_or_create_active_session(request.user).id, "items": list_sessions(request.user, days=7)})
    payload = request.data or {}
    title = str(payload.get("title", "")).strip()
    scene_type = str(payload.get("scene_type", "general")).strip() or "general"
    row = create_session(request.user, title=title, scene_type=scene_type)
    return ok(
        {
            "id": row.id,
            "title": row.title,
            "scene_type": row.scene_type,
            "summary": row.summary,
            "is_active": row.is_active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_session_activate(request, session_id: int):
    row = activate_session(request.user, session_id)
    if not row:
        return bad("会话不存在", 404)
    return ok({"id": row.id, "is_active": row.is_active})


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


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_manga_config(request):
    assistant = get_assistant_llm_config()
    manga = get_manga_llm_config()
    return ok(
        {
            "default_model_preset": "assistant",
            "storyboard_prompt": get_manga_storyboard_prompt(),
            "image_prompt": get_manga_image_prompt(),
            "model_options": [
                _serialize_model_option("assistant", "助手模型", assistant),
                _serialize_model_option("manga", "漫剧模型", manga),
            ],
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_storyboard(request):
    file_obj = request.FILES.get("file")
    text = str(request.data.get("text", "")).strip()
    model_preset = str(request.data.get("model_preset", "assistant")).strip().lower() or "assistant"
    if model_preset not in {"assistant", "manga"}:
        return bad("模型选项不支持")
    try:
        source_text = extract_story_source_text(file_obj=file_obj, text=text)
        result = generate_manga_storyboard(source_text, model_preset=model_preset)
        return ok(result)
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_storyboard_prepare(request):
    sections = request.data.get("sections") or []
    if not isinstance(sections, list):
        return bad("分镜段落格式错误")
    try:
        prepared = prepare_storyboard_image_sections(sections)
        return ok({"sections": prepared})
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_storyboard_image(request):
    prompt = str(request.data.get("prompt", "")).strip()
    section_id = request.data.get("section_id")
    reference_assets = request.data.get("reference_assets") or []
    try:
        result = generate_manga_storyboard_image(prompt, reference_assets=reference_assets)
        return ok(
            {
                **result,
                "section_id": section_id,
            }
        )
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def memory_summary(request):
    session = get_or_create_active_session(request.user)
    orchestrator = MemoryOrchestrator()
    ai_session = orchestrator.ensure_ai_session(request.user, session)
    row = (
        AIConversationSummary.objects.filter(session=ai_session, is_active=True)
        .order_by("-version", "-id")
        .first()
    )
    if not row:
        return ok({"summary": None})
    return ok(
        {
            "summary": {
                "id": row.id,
                "task_stage": row.task_stage,
                "current_goal": row.current_goal,
                "recent_decisions": row.recent_decisions or [],
                "open_questions": row.open_questions or [],
                "important_entities": row.important_entities or [],
                "next_action": row.next_action,
                "version": row.version,
                "updated_at": row.updated_at,
            }
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def memory_facts(request):
    rows = AIUserFact.objects.filter(user=request.user, status=AIUserFact.STATUS_ACTIVE).order_by("-updated_at", "-id")[:50]
    return ok(
        {
            "list": [
                {
                    "id": row.id,
                    "fact_key": row.fact_key,
                    "fact_value": row.fact_value,
                    "fact_type": row.fact_type,
                    "confidence": float(row.confidence or 0),
                    "version": row.version,
                    "updated_at": row.updated_at,
                }
                for row in rows
            ]
        }
    )


@csrf_exempt
def chat_stream(request):
    try:
        if not request.user.is_authenticated:
            return _sse_error("请先登录", 401)
        prune_expired_chat_records(request.user)

        if request.method != "POST":
            return _sse_error("Method not allowed", 405)

        try:
            payload = json.loads((request.body or b"{}").decode("utf-8"))
        except Exception:
            payload = {}

        message = str(payload.get("message", "")).strip()
        attachments = payload.get("attachments") or []
        session_id = payload.get("session_id")
        try:
            session_id = int(session_id) if session_id is not None else None
        except (TypeError, ValueError):
            session_id = None
        if not isinstance(attachments, list):
            attachments = []
        if not message:
            return _sse_error("消息不能为空", 400)

        setting = AICustomerSetting.singleton()
        if not setting.enabled:
            return _sse_error("AI客服已关闭", 403)

        session = get_session_for_user(request.user, session_id)
        maybe_update_session_title(session, message)

        ChatMessage.objects.create(
            user=request.user,
            session=session,
            role=ChatMessage.ROLE_USER,
            content=message,
            attachments=attachments,
        )
        session.save(update_fields=["updated_at"])

        image_mode = has_image_generation_intent(message)
        llm_messages = []
        if not image_mode:
            context_hits = []
            try:
                context_hits = search_context(message, top_k=settings.AI_CS_TOP_K)
            except Exception:
                context_hits = []
            web_hits = []
            if not has_reliable_context(context_hits):
                try:
                    web_hits = web_search(message)
                except Exception:
                    web_hits = []

            profile_lines, session_summary, semantic_hits = get_memory_prompt_parts(request.user, session, message)
            system_prompt = build_system_prompt(
                setting,
                context_hits,
                web_hits,
                profile_memory_lines=profile_lines,
                session_summary=session_summary,
                semantic_memory_hits=semantic_hits,
            )
            recent_messages = get_recent_messages(session, limit=max(int(getattr(settings, "AI_MEMORY_RECENT_LIMIT", 8)), 2))

            llm_messages = [{"role": "system", "content": system_prompt}, *recent_messages]
    except Exception as exc:
        logger.exception("chat_stream fatal error: %s", exc)
        return _sse_error("服务暂时不可用，请稍后重试", 500)

    def gen():
        if image_mode:
            try:
                optimized_prompt = optimize_image_prompt(message)
                image_attachment = generate_image_with_ark(optimized_prompt)
                final_text = "已根据你的需求生成图片。"
                ChatMessage.objects.create(
                    user=request.user,
                    session=session,
                    role=ChatMessage.ROLE_ASSISTANT,
                    content=final_text,
                    attachments=[image_attachment],
                )
                session.save(update_fields=["updated_at"])
                schedule_memory_update(request.user.id, session.id, message, final_text)
                yield "data: " + json.dumps(
                    {
                        "type": "done",
                        "content": final_text,
                        "handover": False,
                        "ticket_id": None,
                        "attachments": [image_attachment],
                        "meta": {"optimized_prompt": optimized_prompt},
                    },
                    ensure_ascii=False,
                ) + "\n\n"
            except Exception as exc:
                logger.exception("chat_stream image mode error: %s", exc)
                yield "data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n"
            return

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
                session=session,
                role=ChatMessage.ROLE_ASSISTANT,
                content=full,
                attachments=[],
            )
            session.save(update_fields=["updated_at"])
            schedule_memory_update(request.user.id, session.id, message, full)

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
                    "attachments": [],
                },
                ensure_ascii=False,
            ) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n"

    response = StreamingHttpResponse(gen(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
