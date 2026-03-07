import json
import logging
import requests
import uuid
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import StreamingHttpResponse
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import PointsUsageLog
from apps.ai_customer.models import (
    AICustomerSetting,
    ChatMessage,
    HumanHandoverTicket,
    HumanReplyClearState,
    ResumeAssistantTask,
)
from apps.ai_customer.memory_services import (
    activate_session,
    create_session,
    get_memory_prompt_parts,
    get_or_create_active_session,
    get_recent_messages,
    get_session_for_user,
    list_sessions,
    maybe_update_session_title,
    schedule_memory_update,
)
from apps.ai_customer.services import (
    build_system_prompt,
    search_context,
    has_reliable_context,
    web_search,
    stream_llm_answer,
    has_image_generation_intent,
    optimize_image_prompt,
    generate_image_with_ark,
)
from apps.ai_customer.resume_services import (
    ResumeAssistantError,
    build_resume_download_url,
    run_resume_assistant,
    resume_points_cost,
)
from apps.ai_customer.resume_tasks import dispatch_resume_task
from apps.ai_memory.models import AIConversationSummary, AIUserFact
from apps.ai_memory.services import MemoryOrchestrator

logger = logging.getLogger(__name__)
User = get_user_model()


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _consume_user_points(user_id: int, required_points: Decimal, usage_type: str, description: str):
    with transaction.atomic():
        user = User.objects.select_for_update().get(id=user_id)
        balance = Decimal(user.points or 0)
        if balance < required_points:
            return None, f"积分不足（当前 {balance:.2f}，需 {required_points:.2f}）"
        user.points = balance - required_points
        user.save(update_fields=["points"])
        PointsUsageLog.objects.create(
            user=user,
            usage_type=usage_type,
            amount=required_points,
            balance_after=user.points,
            description=description[:255],
        )
        return Decimal(user.points), None


def _refund_user_points(user_id: int, points: Decimal, description: str):
    with transaction.atomic():
        user = User.objects.select_for_update().get(id=user_id)
        user.points = Decimal(user.points or 0) + points
        user.save(update_fields=["points"])
        PointsUsageLog.objects.create(
            user=user,
            usage_type=PointsUsageLog.TYPE_REFUND,
            amount=-points,
            balance_after=user.points,
            description=description[:255],
        )


def _sse_error(message: str, status: int = 400):
    body = "data: " + json.dumps({"type": "error", "message": message}, ensure_ascii=False) + "\n\n"
    return StreamingHttpResponse(body, status=status, content_type="text/event-stream")


def _serialize_resume_task(task: ResumeAssistantTask):
    pdf_url = build_resume_download_url(task.pdf_url or "")
    return {
        "task_id": task.id,
        "request_id": task.request_id,
        "status": task.status,
        "progress": int(task.progress or 0),
        "cost_points": float(task.cost_points or 0),
        "result": {
            "pdf_url": pdf_url,
            "ocr_text": task.ocr_text or "",
            "skill_points": task.skill_points or [],
            "resume_text": task.resume_text or "",
        },
        "error": task.error_message or "",
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


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
    session_id = request.query_params.get("session_id")
    try:
        sid = int(session_id) if session_id is not None else None
    except (TypeError, ValueError):
        sid = None
    session = get_session_for_user(request.user, sid)
    rows = ChatMessage.objects.filter(user=request.user, session=session).order_by("-id")[:30]
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
            "sessions": list_sessions(request.user),
            "messages": items,
        }
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def chat_sessions(request):
    if request.method == "GET":
        return ok({"active_session_id": get_or_create_active_session(request.user).id, "items": list_sessions(request.user)})
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
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_assistant_task_create(request):
    payload = request.data or {}
    job_title = str(payload.get("job_title", "")).strip()
    image_urls = payload.get("image_urls") or []
    rois = payload.get("rois") or []
    request_id = str(payload.get("request_id", "")).strip() or uuid.uuid4().hex

    if not job_title:
        return bad("请输入职位名称")
    if not isinstance(image_urls, list) or not image_urls:
        return bad("请上传职位要求截图")
    if len(image_urls) > 6:
        return bad("职位要求截图最多6张")
    if len(job_title) > 120:
        return bad("职位名称不能超过120字")

    old = ResumeAssistantTask.objects.filter(user=request.user, request_id=request_id).first()
    if old:
        return ok(_serialize_resume_task(old))

    task = ResumeAssistantTask.objects.create(
        user=request.user,
        request_id=request_id,
        job_title=job_title,
        image_urls=image_urls,
        rois=rois if isinstance(rois, list) else [],
        status=ResumeAssistantTask.STATUS_CREATED,
        progress=0,
        cost_points=resume_points_cost(),
    )
    dispatch_resume_task(task.id)
    return ok(_serialize_resume_task(task))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def resume_assistant_task_detail(request, task_id: int):
    task = ResumeAssistantTask.objects.filter(id=task_id, user=request.user).first()
    if not task:
        return bad("任务不存在", 404)
    data = _serialize_resume_task(task)
    data["remaining_points"] = float(request.user.points or 0)
    return ok(data)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def resume_assistant_generate(request):
    payload = request.data or {}
    job_title = str(payload.get("job_title", "")).strip()
    image_urls = payload.get("image_urls") or []
    if not job_title:
        return bad("请输入职位名称")
    if not isinstance(image_urls, list) or not image_urls:
        return bad("请上传职位要求截图")

    cost_points = resume_points_cost()
    remaining_points, err = _consume_user_points(
        request.user.id,
        cost_points,
        PointsUsageLog.TYPE_RESUME_ASSISTANT,
        f"简历助手消耗，职位：{job_title}",
    )
    if err:
        return bad(err, 402)

    try:
        setting = AICustomerSetting.singleton()
        result = run_resume_assistant(
            user=request.user,
            setting=setting,
            job_title=job_title,
            image_urls=image_urls,
            rois=payload.get("rois") or [],
        )
        return ok(
            {
                **result,
                "cost_points": float(cost_points),
                "remaining_points": float(remaining_points),
            }
        )
    except ResumeAssistantError as exc:
        _refund_user_points(request.user.id, cost_points, "简历助手生成失败自动退款")
        return bad(f"简历助手失败：{exc}", exc.status)
    except Exception:
        logger.exception("resume assistant fatal error")
        _refund_user_points(request.user.id, cost_points, "简历助手生成失败自动退款")
        return bad("简历助手失败：服务暂时不可用，请稍后重试", 500)


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
