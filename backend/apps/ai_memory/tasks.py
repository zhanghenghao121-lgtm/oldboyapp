import threading

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections

from apps.ai_customer.models import ChatSession
from apps.ai_memory.models import AISession
from apps.ai_memory.services.memory_orchestrator import MemoryOrchestrator

User = get_user_model()


def _run_postprocess(*, user_id: int, chat_session_id: int, ai_session_id: int, user_message: str, assistant_message: str):
    close_old_connections()
    try:
        user = User.objects.filter(id=user_id).first()
        chat_session = ChatSession.objects.filter(id=chat_session_id).first()
        ai_session = AISession.objects.filter(id=ai_session_id).first()
        if not user or not chat_session or not ai_session:
            return
        orchestrator = MemoryOrchestrator()
        orchestrator.run_postprocess(
            user=user,
            chat_session=chat_session,
            ai_session=ai_session,
            user_message=user_message,
            assistant_message=assistant_message,
        )
    finally:
        close_old_connections()


@shared_task(bind=True, name="ai_memory.postprocess")
def ai_memory_postprocess_task(self, user_id: int, chat_session_id: int, ai_session_id: int, user_message: str, assistant_message: str):
    _run_postprocess(
        user_id=user_id,
        chat_session_id=chat_session_id,
        ai_session_id=ai_session_id,
        user_message=user_message,
        assistant_message=assistant_message,
    )


def dispatch_memory_postprocess(*, user_id: int, chat_session_id: int, ai_session_id: int, user_message: str, assistant_message: str):
    use_celery = bool(getattr(settings, "AI_MEMORY_USE_CELERY", True))
    if use_celery:
        try:
            ai_memory_postprocess_task.delay(user_id, chat_session_id, ai_session_id, user_message, assistant_message)
            return
        except Exception:
            pass
    t = threading.Thread(
        target=_run_postprocess,
        kwargs={
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "ai_session_id": ai_session_id,
            "user_message": user_message,
            "assistant_message": assistant_message,
        },
        daemon=True,
    )
    t.start()

