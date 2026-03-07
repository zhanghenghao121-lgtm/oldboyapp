from dataclasses import dataclass
from typing import List, Optional, Tuple

from django.conf import settings

from apps.ai_customer.models import ChatMessage
from apps.ai_memory.models import AIMemoryWriteLog, AIMessage, AISession
from apps.ai_memory.services.fact_memory import FactMemoryService
from apps.ai_memory.services.prompt_builder import PromptBuilder
from apps.ai_memory.services.summary_memory import SummaryMemoryService
from apps.ai_memory.services.vector_memory import VectorMemoryService
from apps.ai_memory.services.window_memory import WindowMemoryService
from apps.ai_memory.services.write_classifier import WriteClassifier


def _session_uuid(chat_session_id: int) -> str:
    return f"chat_{int(chat_session_id)}"


@dataclass
class PromptMemoryContext:
    fact_lines: List[str]
    summary_text: str
    vector_hits: List[Tuple[str, float]]


class MemoryOrchestrator:
    def __init__(self):
        self.window = WindowMemoryService()
        self.facts = FactMemoryService()
        self.summary = SummaryMemoryService()
        self.vector = VectorMemoryService()
        self.classifier = WriteClassifier()
        self.builder = PromptBuilder()

    def ensure_ai_session(self, user, chat_session) -> AISession:
        session_uuid = _session_uuid(chat_session.id)
        row, created = AISession.objects.get_or_create(
            session_uuid=session_uuid,
            defaults={
                "user": user,
                "title": (chat_session.title or "新的对话")[:255],
                "scene": (chat_session.scene_type or "general")[:64],
                "status": AISession.STATUS_ACTIVE,
            },
        )
        if not created:
            changed = False
            if row.user_id != user.id:
                row.user = user
                changed = True
            title = (chat_session.title or "新的对话")[:255]
            scene = (chat_session.scene_type or "general")[:64]
            if row.title != title:
                row.title = title
                changed = True
            if row.scene != scene:
                row.scene = scene
                changed = True
            if row.status != AISession.STATUS_ACTIVE:
                row.status = AISession.STATUS_ACTIVE
                changed = True
            if changed:
                row.save(update_fields=["user", "title", "scene", "status", "last_active_at"])
        return row

    def get_recent_messages(self, chat_session, limit: int) -> List[dict]:
        sid = _session_uuid(chat_session.id)
        from_window = self.window.get_messages(sid)
        if from_window:
            return from_window[-max(int(limit or 1), 1):]
        rows = ChatMessage.objects.filter(session=chat_session).order_by("-id")[: max(int(limit or 1), 1)]
        output = []
        for row in reversed(list(rows)):
            output.append({"role": row.role, "content": row.content})
        return output

    def build_prompt_context(self, user, chat_session, query: str) -> PromptMemoryContext:
        ai_session = self.ensure_ai_session(user, chat_session)
        facts = self.facts.render_fact_lines(user, limit=max(int(getattr(settings, "AI_MEMORY_PROFILE_MAX_ITEMS", 10)), 1))
        summary = self.summary.get_active_summary_text(ai_session)
        final_k = max(int(getattr(settings, "AI_MEMORY_VECTOR_FINAL_K", 4)), 1)
        try:
            vector_hits = self.vector.search_cases(user_id=user.id, query=query, final_k=final_k)
        except Exception:
            vector_hits = []
        fact_lines, summary_text, semantic_hits = self.builder.build(
            fact_lines=facts,
            summary_text=summary,
            vector_hits=vector_hits,
        )
        return PromptMemoryContext(
            fact_lines=fact_lines,
            summary_text=summary_text,
            vector_hits=semantic_hits,
        )

    def schedule_postprocess(self, user, chat_session, user_message: str, assistant_message: str):
        if not bool(getattr(settings, "AI_MEMORY_ENABLED", True)):
            return
        ai_session = self.ensure_ai_session(user, chat_session)
        from apps.ai_memory.tasks import dispatch_memory_postprocess
        dispatch_memory_postprocess(
            user_id=user.id,
            chat_session_id=chat_session.id,
            ai_session_id=ai_session.id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    def run_postprocess(
        self,
        *,
        user,
        chat_session,
        ai_session: AISession,
        user_message: str,
        assistant_message: str,
    ):
        sid = _session_uuid(chat_session.id)
        self.window.append_pair(sid, user_message, assistant_message)

        token_user = max(1, len((user_message or "").strip()) // 4)
        token_assistant = max(1, len((assistant_message or "").strip()) // 4)
        AIMessage.objects.bulk_create(
            [
                AIMessage(session=ai_session, user=user, role="user", content=user_message or "", token_estimate=token_user),
                AIMessage(
                    session=ai_session,
                    user=user,
                    role="assistant",
                    content=assistant_message or "",
                    token_estimate=token_assistant,
                ),
            ]
        )

        decisions = self.classifier.classify(user_message, assistant_message)
        write_log_enabled = bool(getattr(settings, "AI_MEMORY_WRITE_LOG_ENABLED", True))
        for decision in decisions:
            if write_log_enabled:
                AIMemoryWriteLog.objects.create(
                    user=user,
                    session=ai_session,
                    decision=decision.get("decision", "window_only"),
                    target_layer=decision.get("target_layer", "window"),
                    reason=decision.get("reason", ""),
                    payload=decision.get("payload") or {},
                )
            d = decision.get("decision")
            if d == "write_fact":
                self.facts.maybe_extract_and_upsert(user, user_message)
            elif d == "write_summary":
                recent = self.get_recent_messages(chat_session, limit=max(int(getattr(settings, "AI_MEMORY_SUMMARY_WINDOW", 16)), 4))
                self.summary.maybe_update_summary(ai_session, recent)
            elif d == "write_vector":
                memory_type = (decision.get("payload") or {}).get("memory_type") or "solution_case"
                self.vector.maybe_write_case(
                    user_id=user.id,
                    session_uuid=ai_session.session_uuid,
                    user_message=user_message,
                    assistant_message=assistant_message,
                    memory_type=memory_type,
                )
