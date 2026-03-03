import threading
import time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db import close_old_connections

from apps.accounts.models import PointsUsageLog
from apps.ai_customer.models import AICustomerSetting, ResumeAssistantTask
from apps.ai_customer.resume_services import ResumeAssistantError, run_resume_assistant

User = get_user_model()


class ResumeTaskRunnerError(Exception):
    pass


def _consume_user_points(user_id: int, required_points: Decimal, description: str):
    with transaction.atomic():
        user = User.objects.select_for_update().get(id=user_id)
        balance = Decimal(user.points or 0)
        if balance < required_points:
            return None, f"积分不足（当前 {balance:.2f}，需 {required_points:.2f}）"
        user.points = balance - required_points
        user.save(update_fields=["points"])
        PointsUsageLog.objects.create(
            user=user,
            usage_type=PointsUsageLog.TYPE_RESUME_ASSISTANT,
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


def _set_task_progress(task_id: int, status: str = None, progress: int = None, **fields):
    payload = {}
    if status is not None:
        payload["status"] = status
    if progress is not None:
        payload["progress"] = max(0, min(int(progress), 100))
    payload.update(fields)
    payload["updated_at"] = timezone.now()
    ResumeAssistantTask.objects.filter(id=task_id).update(**payload)


def process_resume_task(task_id: int, claimed: bool = False):
    close_old_connections()
    if not claimed:
        with transaction.atomic():
            row = ResumeAssistantTask.objects.select_for_update().filter(id=task_id).first()
            if not row:
                return
            if row.status != ResumeAssistantTask.STATUS_CREATED:
                return
            row.status = ResumeAssistantTask.STATUS_RUNNING
            row.progress = 10
            row.error_message = ""
            row.save(update_fields=["status", "progress", "error_message", "updated_at"])
    else:
        _set_task_progress(task_id, progress=10, error_message="")

    task = ResumeAssistantTask.objects.select_related("user").filter(id=task_id).first()
    if not task:
        return

    cost_points = Decimal(task.cost_points or 0)
    if cost_points <= 0:
        _set_task_progress(task_id, status=ResumeAssistantTask.STATUS_FAILED, progress=100, error_message="任务积分配置异常")
        return

    remaining_points, err = _consume_user_points(task.user_id, cost_points, f"简历助手消耗，职位：{task.job_title}")
    if err:
        _set_task_progress(task_id, status=ResumeAssistantTask.STATUS_FAILED, progress=100, error_message=err)
        return

    try:
        _set_task_progress(task_id, progress=25)
        setting = AICustomerSetting.singleton()
        _set_task_progress(task_id, progress=45)
        result = run_resume_assistant(
            user=task.user,
            setting=setting,
            job_title=task.job_title,
            image_urls=task.image_urls or [],
            rois=task.rois or [],
        )
        _set_task_progress(
            task_id,
            status=ResumeAssistantTask.STATUS_SUCCEEDED,
            progress=100,
            ocr_text=(result.get("ocr_text") or "")[:5000],
            skill_points=result.get("skill_points") or [],
            resume_text=(result.get("resume_text") or "")[:12000],
            pdf_url=result.get("pdf_url") or "",
            error_message="",
        )
    except ResumeAssistantError as exc:
        if not task.refunded:
            _refund_user_points(task.user_id, cost_points, "简历助手生成失败自动退款")
            ResumeAssistantTask.objects.filter(id=task_id).update(refunded=True)
        _set_task_progress(task_id, status=ResumeAssistantTask.STATUS_FAILED, progress=100, error_message=str(exc)[:255])
    except Exception:
        if not task.refunded:
            _refund_user_points(task.user_id, cost_points, "简历助手生成失败自动退款")
            ResumeAssistantTask.objects.filter(id=task_id).update(refunded=True)
        _set_task_progress(task_id, status=ResumeAssistantTask.STATUS_FAILED, progress=100, error_message="服务暂时不可用，请稍后重试")
    finally:
        close_old_connections()


def _run_in_thread(task_id: int):
    try:
        process_resume_task(task_id, claimed=False)
    except Exception:
        pass


def dispatch_resume_task(task_id: int):
    in_process = bool(getattr(settings, "AI_RESUME_INPROCESS_QUEUE", True))
    if not in_process:
        return
    t = threading.Thread(target=_run_in_thread, args=(task_id,), daemon=True)
    t.start()


def consume_one_pending_task():
    with transaction.atomic():
        row = (
            ResumeAssistantTask.objects.select_for_update(skip_locked=True)
            .filter(status=ResumeAssistantTask.STATUS_CREATED)
            .order_by("id")
            .first()
        )
        if not row:
            return None
        row.status = ResumeAssistantTask.STATUS_RUNNING
        row.progress = 5
        row.error_message = ""
        row.save(update_fields=["status", "progress", "error_message", "updated_at"])
        return row.id


def run_worker_loop(poll_interval: float = 1.0):
    while True:
        task_id = consume_one_pending_task()
        if task_id is None:
            time.sleep(max(poll_interval, 0.3))
            continue
        process_resume_task(task_id, claimed=True)
