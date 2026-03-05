import threading

from django.conf import settings
from django.db import close_old_connections

from apps.ai_customer.blogger_services import BloggerError, process_post_generation, process_video_generation
from apps.ai_customer.models import AiBloggerPost, AiBloggerVideoTask


def _run_safe(fn, task_id: int, kind: str):
    close_old_connections()
    try:
        fn(task_id)
    except BloggerError as exc:
        if kind == "post":
            AiBloggerPost.objects.filter(id=task_id).update(
                status_text=AiBloggerPost.STATUS_FAILED,
                error_text=str(exc)[:500],
            )
        else:
            AiBloggerVideoTask.objects.filter(id=task_id).update(
                status_video=AiBloggerVideoTask.STATUS_FAILED,
                error_text=str(exc)[:500],
            )
    except Exception:
        if kind == "post":
            AiBloggerPost.objects.filter(id=task_id).update(
                status_text=AiBloggerPost.STATUS_FAILED,
                error_text="图文生成失败，请稍后重试",
            )
        else:
            AiBloggerVideoTask.objects.filter(id=task_id).update(
                status_video=AiBloggerVideoTask.STATUS_FAILED,
                error_text="视频生成失败，请稍后重试",
            )
    finally:
        close_old_connections()


def dispatch_post_generation(post_id: int):
    if not bool(getattr(settings, "AI_BLOGGER_INPROCESS_QUEUE", True)):
        return
    t = threading.Thread(target=_run_safe, args=(process_post_generation, post_id, "post"), daemon=True)
    t.start()


def dispatch_video_generation(video_task_id: int):
    if not bool(getattr(settings, "AI_BLOGGER_INPROCESS_QUEUE", True)):
        return
    t = threading.Thread(target=_run_safe, args=(process_video_generation, video_task_id, "video"), daemon=True)
    t.start()
