import ast
import re

from apps.ai_customer.llm_clients import LLMClientError, image_generation, task_status
from apps.ai_customer.runtime_config import get_ai_image_config

MAX_AI_IMAGE_REFERENCES = 16
AI_IMAGE_SIZE_OPTIONS = {
    "auto", "1:1", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5",
    "16:9", "9:16", "2:1", "1:2", "3:1", "1:3", "21:9", "9:21",
}
AI_IMAGE_RESOLUTION_OPTIONS = {"1k", "2k", "4k"}


class AIImageError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").replace("\r\n", "\n").split("\n")).strip()


def _normalize_size(value: str) -> str:
    text = str(value or "16:9").strip().lower()
    return text if text in AI_IMAGE_SIZE_OPTIONS or re.fullmatch(r"\d{2,5}x\d{2,5}", text) else "16:9"


def _normalize_resolution(value: str) -> str:
    text = str(value or "1k").strip().lower()
    return text if text in AI_IMAGE_RESOLUTION_OPTIONS else "1k"


def _normalize_seedream_size(value: str) -> str:
    text = str(value or "2k").strip().lower()
    return text if text in {"2k", "3k", "4k"} or re.fullmatch(r"\d{2,5}x\d{2,5}", text) else "2k"


def _is_seedream(runtime: dict) -> bool:
    text = f"{runtime.get('provider')} {runtime.get('base_url')} {runtime.get('model')}".lower()
    return any(part in text for part in ("seedream", "doubao", "volcengine", "ark.cn"))


def _prompt(prompt: str) -> str:
    text = _normalize_text(prompt)
    if not text:
        raise AIImageError("请输入生图提示词")
    return text[:6000]


def _image_ref_values(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(_image_ref_values(item))
        return refs
    if isinstance(value, dict):
        if value.get("b64_json"):
            return [f"data:image/png;base64,{value['b64_json']}"]
        return _image_ref_values(value.get("url") or value.get("image_url"))
    text = str(value).strip()
    if not text:
        return []
    if text.startswith("[") and text.endswith("]"):
        try:
            return _image_ref_values(ast.literal_eval(text))
        except (ValueError, SyntaxError):
            pass
    urls = re.findall(r"https?://[^\s'\"\[\]]+", text)
    return urls or [text]


def _image_urls(body: dict) -> list[str]:
    urls = []
    data = body.get("data") or []
    for item in data if isinstance(data, list) else [data]:
        if not isinstance(item, dict):
            continue
        value = (item or {}).get("url") or (item or {}).get("image_url")
        urls.extend(_image_ref_values(value or item))
    return urls


def submit_ai_image_generation(*, prompt="", model="", size="16:9", resolution="1k", reference_images=None) -> dict:
    runtime = get_ai_image_config(model)
    if not runtime.get("api_key") or not runtime.get("base_url") or not runtime.get("model"):
        raise AIImageError("生图模型配置不完整，请先在后台模型设置中补全 API 地址、API Key 和模型名称", 500)
    images = reference_images or []
    if len(images) > MAX_AI_IMAGE_REFERENCES:
        raise AIImageError("参考图最多支持 16 张")
    if _is_seedream(runtime):
        payload = {
            "model": runtime["model"], "prompt": _prompt(prompt),
            "sequential_image_generation": "disabled", "response_format": "url",
            "size": _normalize_seedream_size(resolution), "stream": False, "watermark": True,
        }
        if images:
            image_urls = [item["data_url"] for item in images]
            payload["image"] = image_urls if len(image_urls) > 1 else image_urls[0]
    else:
        payload = {
            "model": runtime["model"], "prompt": _prompt(prompt), "n": 1,
            "size": _normalize_size(size), "resolution": _normalize_resolution(resolution),
        }
        if images:
            payload["image_urls"] = [item["data_url"] for item in images]
    try:
        body = image_generation(runtime["base_url"], runtime["api_key"], payload, service_name="生图模型")
    except LLMClientError as exc:
        raise AIImageError(str(exc), exc.status) from exc
    urls = _image_urls(body)
    data = body.get("data") or {}
    first_data = data[0] if isinstance(data, list) and data else data
    task_id = str(first_data.get("task_id") or first_data.get("id") or "").strip() if isinstance(first_data, dict) else ""
    if urls:
        return {"task_id": task_id, "status": "completed", "images": urls, "model": runtime["model"]}
    if not task_id:
        raise AIImageError("生图模型未返回任务ID", 502)
    return {"task_id": task_id, "status": "submitted", "model": runtime["model"]}


def _task_result_images(data: dict) -> list[str]:
    candidates = [
        ((data.get("result") or {}).get("images") if isinstance(data.get("result"), dict) else None),
        data.get("images"),
        data.get("image_urls"),
        data.get("url"),
        data.get("image_url"),
    ]
    images = []
    for candidate in candidates:
        images.extend(_image_ref_values(candidate))
    return images


def get_ai_image_task_result(task_id: str, model: str = "") -> dict:
    runtime = get_ai_image_config(model)
    if not task_id:
        raise AIImageError("缺少任务ID")
    if not runtime.get("api_key") or not runtime.get("base_url"):
        raise AIImageError("生图模型配置不完整，请先在后台模型设置中补全", 500)
    try:
        body = task_status(runtime["base_url"], runtime["api_key"], task_id, service_name="生图任务")
    except LLMClientError as exc:
        raise AIImageError(str(exc), exc.status) from exc
    raw_data = body.get("data")
    data = raw_data[0] if isinstance(raw_data, list) and raw_data else raw_data if isinstance(raw_data, dict) else {}
    images = _task_result_images(data) or _image_urls(body)
    return {
        "task_id": data.get("id") or task_id,
        "status": data.get("status") or body.get("status") or "",
        "progress": data.get("progress") or body.get("progress") or 0,
        "images": images,
        "error": ((data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else data.get("message") or body.get("message")) or "",
    }
