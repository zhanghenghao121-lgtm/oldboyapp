from django.conf import settings
from django.db import close_old_connections
from celery import shared_task

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


@shared_task(bind=True, name="ai_blogger.generate_post")
def generate_post_task(self, post_id: int):
    _run_safe(process_post_generation, post_id, "post")


@shared_task(bind=True, name="ai_blogger.generate_video")
def generate_video_task(self, video_task_id: int):
    _run_safe(process_video_generation, video_task_id, "video")


def dispatch_post_generation(post_id: int):
    if bool(getattr(settings, "AI_BLOGGER_USE_CELERY", True)):
        generate_post_task.delay(post_id)
        return
    _run_safe(process_post_generation, post_id, "post")


def dispatch_video_generation(video_task_id: int):
    if bool(getattr(settings, "AI_BLOGGER_USE_CELERY", True)):
        generate_video_task.delay(video_task_id)
        return
    _run_safe(process_video_generation, video_task_id, "video")
