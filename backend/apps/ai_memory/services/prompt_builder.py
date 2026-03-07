from typing import List, Tuple


class PromptBuilder:
    def build(
        self,
        *,
        fact_lines: List[str],
        summary_text: str,
        vector_hits: List[Tuple[str, float]],
    ) -> Tuple[List[str], str, List[Tuple[str, float]]]:
        facts = [str(x).strip() for x in (fact_lines or []) if str(x).strip()]
        summary = (summary_text or "").strip()
        hits = [(str(text).strip(), float(score)) for text, score in (vector_hits or []) if str(text).strip()]
        return facts, summary, hits

