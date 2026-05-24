import json
import logging
from pathlib import Path

from apps.ai_customer.llm_clients import LLMClientError, chat_completion
from apps.ai_customer.manga_services import MangaScriptError, _extract_json_value, _prepare_uploaded_image
from apps.ai_customer.runtime_config import (
    get_position_agent_llm_config,
    get_position_vision_llm_config,
)


logger = logging.getLogger(__name__)
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(name: str) -> str:
    try:
        return (PROMPT_DIR / name).read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.exception("站位功能 prompt 读取失败: %s", name)
        raise MangaScriptError("站位识别配置缺失，请联系管理员", 500) from exc


def _chat_text(body: dict, service_name: str) -> str:
    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise MangaScriptError(f"{service_name}未返回有效内容", 502)
    return content


def _call_chat(runtime: dict, payload: dict, service_name: str) -> dict:
    try:
        return chat_completion(runtime, payload, service_name=service_name)
    except LLMClientError as exc:
        raise MangaScriptError(str(exc), exc.status) from exc


def _json_dumps(value) -> str:
    return json.dumps(value or {}, ensure_ascii=False, indent=2)


def recognize_position_image(image_files) -> dict:
    image = _prepare_uploaded_image(image_files, "position_image", "人物站位图")
    if not image:
        raise MangaScriptError("请先上传人物站位图")

    runtime = get_position_vision_llm_config()
    model = str(runtime.get("model") or "").strip()
    if not model:
        raise MangaScriptError("站位识图模型配置不完整，请联系管理员", 500)

    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": _load_prompt("position_recognition_system.txt")},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请识别这张人物站位图并严格按要求输出 JSON。"},
                    {"type": "image_url", "image_url": {"url": image["data_url"]}},
                ],
            },
        ],
    }
    body = _call_chat(runtime, payload, "站位识图模型")
    raw_text = _chat_text(body, "站位识图模型")
    data = _extract_json_value(raw_text)
    if not isinstance(data, dict) or not data:
        logger.error("站位识图模型返回无法解析 JSON: %s", raw_text[:500])
        raise MangaScriptError("站位识图模型未返回可解析的结构化结果", 502)
    description = build_position_description(data)
    return {
        "recognition": data,
        "description": description,
        "subjects": _extract_subjects(data),
        "image": {"name": image["name"], "label": image["label"]},
    }


def _extract_subjects(data: dict) -> list[dict]:
    subjects = []
    for group_key, subject_type in (("characters", "角色"), ("objects", "物品")):
        items = data.get(group_key) if isinstance(data.get(group_key), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("id") or "").strip()
            if not label:
                continue
            subjects.append(
                {
                    "id": str(item.get("id") or f"{group_key}_{len(subjects) + 1}"),
                    "type": subject_type,
                    "label": label,
                    "binding": label,
                    "summary": str(item.get("appearance") or item.get("image_position") or ""),
                }
            )
    return subjects


def build_position_description(recognition: dict) -> str:
    runtime = get_position_agent_llm_config()
    payload = {
        "model": runtime["model"],
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _load_prompt("position_description_agent.txt")},
            {"role": "user", "content": f"识图 JSON：\n{_json_dumps(recognition)}"},
        ],
    }
    body = _call_chat(runtime, payload, "站位描述模型")
    return _chat_text(body, "站位描述模型")


def generate_reverse_prompt(position_description: str, bindings: list[dict] | None = None, recognition: dict | None = None) -> dict:
    description = str(position_description or "").strip()
    if len(description) < 10:
        raise MangaScriptError("请先确认或填写更完整的站位描述")
    runtime = get_position_agent_llm_config()
    payload = {
        "model": runtime["model"],
        "stream": False,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": _load_prompt("reverse_prompt_agent.txt")},
            {
                "role": "user",
                "content": (
                    f"用户确认后的正面镜头站位描述：\n{description[:4000]}\n\n"
                    f"角色/物品绑定关系：\n{_json_dumps(bindings or [])}\n\n"
                    f"识图 JSON：\n{_json_dumps(recognition or {})[:6000]}"
                ),
            },
        ],
    }
    body = _call_chat(runtime, payload, "反打提示词模型")
    prompt = _chat_text(body, "反打提示词模型")
    return {"prompt": prompt, "model": runtime["model"], "bindings": bindings or []}
