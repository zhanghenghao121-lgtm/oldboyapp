import json
import re
from typing import Dict, List

import requests

from django.conf import settings

from apps.ai_customer.runtime_config import get_runtime_llm_config
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
        llm_payload = self._build_summary_payload_with_llm(messages)
        if llm_payload:
            return llm_payload
        return self._build_summary_payload_with_rules(messages)

    def _build_summary_payload_with_llm(self, messages: List[Dict[str, str]]) -> Dict:
        runtime = get_runtime_llm_config("assistant")
        api_key = str(runtime.get("api_key") or "").strip()
        base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
        model = str(runtime.get("model") or "").strip()
        if not api_key or not base_url or not model:
            return {}

        dialogue_lines = []
        for item in messages[-max(self.trigger_rounds * 2, 8):]:
            role = "用户" if item.get("role") == "user" else "助手"
            content = str(item.get("content", "")).strip()
            if content:
                dialogue_lines.append(f"{role}: {content}")
        if not dialogue_lines:
            return {}

        prompt = (
            "请基于最近对话生成结构化近期摘要，只输出 JSON，不要输出 markdown。\n"
            "字段必须包含：current_goal, recent_decisions, open_questions, important_entities, task_stage, next_action。\n"
            "其中 recent_decisions/open_questions/important_entities 必须是数组。\n"
            "对话如下：\n"
            + "\n".join(dialogue_lines[-20:])
        )
        payload = {
            "model": model,
            "stream": False,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是对话记忆压缩助手。"
                        "只输出合法 JSON，内容必须简洁、可承接后续任务。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=max(int(getattr(settings, "AI_MEMORY_SUMMARY_TIMEOUT", 45)), 10),
            )
            if resp.status_code >= 400:
                return {}
            body = resp.json()
            content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
            return self._parse_summary_json(content)
        except Exception:
            return {}

    def _parse_summary_json(self, content: str) -> Dict:
        text = (content or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return {}
            try:
                data = json.loads(match.group(0))
            except Exception:
                return {}
        if not isinstance(data, dict):
            return {}
        return {
            "task_stage": str(data.get("task_stage", "")).strip()[:64],
            "current_goal": str(data.get("current_goal", "")).strip()[:500],
            "recent_decisions": [str(x).strip()[:240] for x in (data.get("recent_decisions") or []) if str(x).strip()][:5],
            "open_questions": [str(x).strip()[:240] for x in (data.get("open_questions") or []) if str(x).strip()][:5],
            "important_entities": [str(x).strip()[:120] for x in (data.get("important_entities") or []) if str(x).strip()][:8],
            "next_action": str(data.get("next_action", "")).strip()[:500],
        }

    def _build_summary_payload_with_rules(self, messages: List[Dict[str, str]]) -> Dict:
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
