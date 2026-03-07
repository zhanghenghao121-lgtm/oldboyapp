import math
from typing import Dict, List

from django.conf import settings
from django.core.cache import cache


def _window_key(session_uuid: str) -> str:
    return f"ai:mem:window:{session_uuid}"


def _state_key(session_uuid: str) -> str:
    return f"ai:mem:state:{session_uuid}"


def _estimate_tokens(text: str) -> int:
    content = str(text or "")
    if not content:
        return 0
    return max(1, math.ceil(len(content) / 4))


class WindowMemoryService:
    def __init__(self):
        self.max_tokens = max(int(getattr(settings, "AI_MEMORY_WINDOW_MAX_TOKENS", 4000)), 400)
        self.ttl = max(int(getattr(settings, "AI_MEMORY_WINDOW_TTL", 7 * 24 * 3600)), 600)

    def get_window(self, session_uuid: str) -> Dict:
        return cache.get(_window_key(session_uuid)) or {"session_uuid": session_uuid, "messages": [], "token_estimate": 0}

    def get_messages(self, session_uuid: str) -> List[Dict[str, str]]:
        row = self.get_window(session_uuid)
        messages = row.get("messages") or []
        return [msg for msg in messages if msg.get("role") and msg.get("content")]

    def set_state(self, session_uuid: str, state: Dict):
        cache.set(_state_key(session_uuid), state or {}, timeout=self.ttl)

    def get_state(self, session_uuid: str) -> Dict:
        return cache.get(_state_key(session_uuid)) or {}

    def append_pair(self, session_uuid: str, user_message: str, assistant_message: str):
        window = self.get_window(session_uuid)
        messages = window.get("messages") or []
        if user_message:
            messages.append({"role": "user", "content": str(user_message)})
        if assistant_message:
            messages.append({"role": "assistant", "content": str(assistant_message)})
        messages = self._trim(messages)
        total_tokens = sum(_estimate_tokens(item.get("content", "")) for item in messages)
        cache.set(
            _window_key(session_uuid),
            {
                "session_uuid": session_uuid,
                "messages": messages,
                "token_estimate": total_tokens,
            },
            timeout=self.ttl,
        )

    def _trim(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        total = 0
        kept: List[Dict[str, str]] = []
        for msg in reversed(messages):
            role = str(msg.get("role", "")).strip()
            content = str(msg.get("content", "")).strip()
            if not role or not content:
                continue
            token_estimate = _estimate_tokens(content)
            if total + token_estimate > self.max_tokens:
                break
            kept.append({"role": role, "content": content})
            total += token_estimate
        return list(reversed(kept))

