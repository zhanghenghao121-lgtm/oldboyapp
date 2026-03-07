import re
from typing import Dict, List


class WriteClassifier:
    def classify(self, user_message: str, assistant_message: str) -> List[Dict]:
        user_text = (user_message or "").strip()
        assistant_text = (assistant_message or "").strip()
        decisions = [{"decision": "window_only", "target_layer": "window", "reason": "默认写入滑动窗口", "payload": {}}]
        if not user_text and not assistant_text:
            decisions.append({"decision": "discard", "target_layer": "none", "reason": "空消息", "payload": {}})
            return decisions

        if self._looks_like_fact(user_text):
            decisions.append(
                {
                    "decision": "write_fact",
                    "target_layer": "long_term_fact",
                    "reason": "用户显式声明长期偏好或事实",
                    "payload": {},
                }
            )

        if len(user_text) + len(assistant_text) >= 140:
            decisions.append(
                {
                    "decision": "write_summary",
                    "target_layer": "recent_summary",
                    "reason": "对话信息量较大，写近期脉络摘要",
                    "payload": {},
                }
            )

        if self._looks_like_reusable_case(user_text, assistant_text):
            decisions.append(
                {
                    "decision": "write_vector",
                    "target_layer": "vector_case",
                    "reason": "包含可复用的问题-解法片段",
                    "payload": {"memory_type": "solution_case"},
                }
            )
        return decisions

    def _looks_like_fact(self, text: str) -> bool:
        if not text:
            return False
        patterns = [
            r"(?:我叫|叫我|请称呼我)",
            r"(?:我喜欢|偏好|以后都用)",
            r"(?:我的项目|项目名)",
            r"(?:技术栈|后端|前端|数据库|向量库)",
        ]
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    def _looks_like_reusable_case(self, user_text: str, assistant_text: str) -> bool:
        content = f"{user_text}\n{assistant_text}"
        if len(content) < 80:
            return False
        keywords = ["报错", "修复", "方案", "部署", "向量", "配置", "步骤", "接口"]
        hit = sum(1 for kw in keywords if kw in content)
        return hit >= 2

