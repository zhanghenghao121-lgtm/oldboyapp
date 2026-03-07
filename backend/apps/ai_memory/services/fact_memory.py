import re
from decimal import Decimal
from typing import Dict, List

from django.conf import settings

from apps.ai_memory.models import AIUserFact


class FactMemoryService:
    def __init__(self):
        self.min_confidence = Decimal(str(getattr(settings, "AI_MEMORY_FACT_MIN_CONFIDENCE", 0.85)))

    def get_active_facts(self, user, limit: int = 10) -> List[AIUserFact]:
        return list(
            AIUserFact.objects.filter(user=user, status=AIUserFact.STATUS_ACTIVE)
            .order_by("-updated_at", "-id")[: max(int(limit or 1), 1)]
        )

    def render_fact_lines(self, user, limit: int = 10) -> List[str]:
        return [f"{row.fact_key}: {row.fact_value}" for row in self.get_active_facts(user, limit=limit)]

    def maybe_extract_and_upsert(self, user, message: str):
        pairs = self._extract_fact_pairs(message)
        for pair in pairs:
            self.upsert_fact(
                user=user,
                fact_key=pair["fact_key"],
                fact_value=pair["fact_value"],
                fact_type=pair.get("fact_type", "general"),
                confidence=pair.get("confidence", Decimal("0.90")),
                source="rule_extract",
            )

    def upsert_fact(
        self,
        *,
        user,
        fact_key: str,
        fact_value: str,
        fact_type: str = "general",
        confidence: Decimal = Decimal("0.90"),
        source: str = "model_extract",
    ):
        if not fact_key or not fact_value:
            return None
        if Decimal(str(confidence)) < self.min_confidence:
            return None

        old = AIUserFact.objects.filter(user=user, fact_key=fact_key, status=AIUserFact.STATUS_ACTIVE).first()
        value = str(fact_value).strip()
        if old and (old.fact_value or "").strip() == value:
            return old

        if old:
            old.status = AIUserFact.STATUS_INACTIVE
            old.save(update_fields=["status", "updated_at"])
        version = (old.version + 1) if old else 1
        return AIUserFact.objects.create(
            user=user,
            fact_key=fact_key.strip()[:128],
            fact_value=value[:5000],
            fact_type=(fact_type or "general").strip()[:64],
            confidence=Decimal(str(confidence)),
            source=(source or "model_extract").strip()[:32],
            status=AIUserFact.STATUS_ACTIVE,
            version=version,
        )

    def _extract_fact_pairs(self, message: str) -> List[Dict]:
        text = (message or "").strip()
        if not text:
            return []
        output: List[Dict] = []
        patterns = [
            (r"(?:我叫|叫我|请称呼我)\s*([^\s，。,.]{1,24})", "preferred_name", "preference"),
            (r"(?:我喜欢|偏好)\s*([^，。\n]{2,60})", "reply_preference", "preference"),
            (r"(?:后端|backend)\s*(?:是|用)\s*([^，。\n]{2,40})", "backend_stack", "tech_stack"),
            (r"(?:前端|frontend)\s*(?:是|用)\s*([^，。\n]{2,40})", "frontend_stack", "tech_stack"),
            (r"(?:数据库|db)\s*(?:是|用)\s*([^，。\n]{2,40})", "database_stack", "infra"),
            (r"(?:向量库|vector db)\s*(?:是|用)\s*([^，。\n]{2,40})", "vector_db", "infra"),
        ]
        for pattern, key, fact_type in patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if not m:
                continue
            value = (m.group(1) or "").strip(" ：:，,。.")
            if not value:
                continue
            output.append({"fact_key": key, "fact_value": value, "fact_type": fact_type, "confidence": Decimal("0.90")})
        return output

