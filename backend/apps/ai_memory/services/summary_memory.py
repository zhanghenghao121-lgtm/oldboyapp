from typing import Dict, List

from django.conf import settings

from apps.ai_memory.models import AIConversationSummary


class SummaryMemoryService:
    def __init__(self):
        self.trigger_rounds = max(int(getattr(settings, "AI_MEMORY_SUMMARY_TRIGGER_ROUNDS", 10)), 4)

    def get_active_summary_text(self, ai_session) -> str:
        row = (
            AIConversationSummary.objects.filter(session=ai_session, is_active=True)
            .order_by("-version", "-id")
            .first()
        )
        if not row:
            return ""
        parts = []
        if row.current_goal:
            parts.append(f"当前目标：{row.current_goal}")
        if row.task_stage:
            parts.append(f"阶段：{row.task_stage}")
        if row.recent_decisions:
            parts.append("近期决策：" + "；".join([str(x) for x in row.recent_decisions[:5] if str(x).strip()]))
        if row.open_questions:
            parts.append("待解决：" + "；".join([str(x) for x in row.open_questions[:5] if str(x).strip()]))
        if row.next_action:
            parts.append(f"下一步：{row.next_action}")
        return "\n".join(parts).strip()

    def maybe_update_summary(self, ai_session, recent_messages: List[Dict[str, str]]):
        rounds = len(recent_messages or [])
        if rounds < self.trigger_rounds:
            return None
        if rounds % self.trigger_rounds != 0:
            return None
        return self.force_update_summary(ai_session, recent_messages)

    def force_update_summary(self, ai_session, recent_messages: List[Dict[str, str]]):
        prev = (
            AIConversationSummary.objects.filter(session=ai_session, is_active=True)
            .order_by("-version", "-id")
            .first()
        )
        if prev:
            prev.is_active = False
            prev.save(update_fields=["is_active", "updated_at"])
        version = (prev.version + 1) if prev else 1
        payload = self._build_summary_payload(recent_messages)
        return AIConversationSummary.objects.create(
            session=ai_session,
            user=ai_session.user,
            summary_type=AIConversationSummary.TYPE_RECENT,
            task_stage=payload.get("task_stage", ""),
            current_goal=payload.get("current_goal", ""),
            recent_decisions=payload.get("recent_decisions", []),
            open_questions=payload.get("open_questions", []),
            important_entities=payload.get("important_entities", []),
            next_action=payload.get("next_action", ""),
            version=version,
            is_active=True,
        )

    def _build_summary_payload(self, messages: List[Dict[str, str]]) -> Dict:
        user_msgs = [str(m.get("content", "")).strip() for m in messages if m.get("role") == "user"]
        assistant_msgs = [str(m.get("content", "")).strip() for m in messages if m.get("role") == "assistant"]
        current_goal = user_msgs[-1][:200] if user_msgs else ""
        decisions = [text[:180] for text in assistant_msgs[-3:] if text]
        open_questions = [text[:180] for text in user_msgs[-2:] if text and ("?" in text or "？" in text)]
        entities = []
        for text in user_msgs[-4:]:
            for token in ["Django", "Redis", "Qdrant", "DeepSeek", "智谱", "向量化", "部署", "工单", "知识库"]:
                if token in text and token not in entities:
                    entities.append(token)
        return {
            "task_stage": "in_progress",
            "current_goal": current_goal,
            "recent_decisions": decisions[:5],
            "open_questions": open_questions[:5],
            "important_entities": entities[:8],
            "next_action": "继续处理当前用户需求并给出可执行结果",
        }

