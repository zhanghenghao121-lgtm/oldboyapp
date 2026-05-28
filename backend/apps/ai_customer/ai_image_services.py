import ast
import base64
import io
import mimetypes
import re

from PIL import Image, ImageOps

from apps.ai_customer.llm_clients import LLMClientError, image_generation, task_status
from apps.ai_customer.runtime_config import get_ai_image_config, get_ai_image_reverse_prompt

MAX_REFERENCE_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AI_IMAGE_REFERENCES = 16
AI_IMAGE_REFERENCE_LABELS = {
    "front_scene_image": "参考图1：场景正面镜头背景",
    "reverse_scene_image": "参考图2：场景反打镜头背景",
}
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


def _compress_reference_image(raw: bytes, label: str) -> tuple[bytes, str]:
    if len(raw) <= int(MAX_REFERENCE_IMAGE_BYTES * 0.95):
        return raw, ""
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception as exc:
        raise AIImageError(f"{label}压缩失败：{exc}") from exc
    image.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
    quality = 88
    while True:
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=quality, optimize=True, progressive=True)
        result = stream.getvalue()
        if len(result) <= MAX_REFERENCE_IMAGE_BYTES or quality <= 45:
            break
        quality -= 8
    if len(result) > MAX_REFERENCE_IMAGE_BYTES:
        raise AIImageError(f"{label}压缩后仍超过 10MB，请换一张更小的图片")
    return result, "image/jpeg"


def _prepare_uploaded_image(image_files, field_name: str, label: str):
    file_obj = image_files.get(field_name) if image_files else None
    if not file_obj:
        return None
    content_type = str(getattr(file_obj, "content_type", "") or "").lower()
    if not content_type:
        content_type = str(mimetypes.guess_type(str(getattr(file_obj, "name", "") or ""))[0] or "").lower()
    if not content_type.startswith("image/"):
        raise AIImageError(f"{label}仅支持图片文件")
    raw = file_obj.read()
    file_obj.seek(0)
    if not raw:
        raise AIImageError(f"{label}不能为空")
    raw, compressed_type = _compress_reference_image(raw, label)
    content_type = compressed_type or content_type
    return {
        "field": field_name,
        "label": label,
        "name": str(getattr(file_obj, "name", "") or label),
        "data_url": f"data:{content_type};base64,{base64.b64encode(raw).decode('ascii')}",
    }


def prepare_ai_image_references(image_files, object_names: list[str] | None = None) -> list[dict]:
    images = []
    for field_name, label in AI_IMAGE_REFERENCE_LABELS.items():
        image = _prepare_uploaded_image(image_files, field_name, label)
        if image:
            images.append(image)
    object_files = list(image_files.getlist("object_images")) if image_files else []
    for index, file_obj in enumerate(object_files[: MAX_AI_IMAGE_REFERENCES - len(images)], start=1):
        name = str((object_names or [""])[index - 1] if index <= len(object_names or []) else "").strip()[:40] or f"对象{index}"
        image = _prepare_uploaded_image({"item": file_obj}, "item", f"@{name} 参考图")
        image["field"] = "object_images"
        image["label"] = f"@{name}"
        images.append(image)
    return images


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


def _prompt(mode: str, prompt: str) -> str:
    text = _normalize_text(prompt)
    if not text:
        raise AIImageError("请输入生图提示词")
    if str(mode).lower() != "reverse_shot":
        return text[:6000]
    return f"{get_ai_image_reverse_prompt()}\n\n用户站位描述：\n{text[:3000]}"


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


def submit_ai_image_generation(*, mode="text", prompt="", model="", size="16:9", resolution="1k", reference_images=None) -> dict:
    runtime = get_ai_image_config(model)
    if not runtime.get("api_key") or not runtime.get("base_url") or not runtime.get("model"):
        raise AIImageError("生图模型配置不完整，请先在后台模型设置中补全 API 地址、API Key 和模型名称", 500)
    images = reference_images or []
    if len(images) > MAX_AI_IMAGE_REFERENCES:
        raise AIImageError("参考图最多支持 16 张")
    if mode == "reverse_shot":
        fields = {item.get("field") for item in images}
        if not {"front_scene_image", "reverse_scene_image"}.issubset(fields):
            raise AIImageError("反打画面需要上传场景正面参考图和场景反打参考图")
        if not any(item.get("field") == "object_images" for item in images):
            raise AIImageError("请至少上传 1 张角色或物品参考图")
    if _is_seedream(runtime):
        payload = {
            "model": runtime["model"], "prompt": _prompt(mode, prompt),
            "sequential_image_generation": "disabled", "response_format": "url",
            "size": _normalize_seedream_size(resolution), "stream": False, "watermark": True,
        }
        if images:
            image_urls = [item["data_url"] for item in images]
            payload["image"] = image_urls if len(image_urls) > 1 else image_urls[0]
    else:
        payload = {
            "model": runtime["model"], "prompt": _prompt(mode, prompt), "n": 1,
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
        return {"task_id": task_id, "status": "completed", "images": urls, "model": runtime["model"], "mode": mode}
    if not task_id:
        raise AIImageError("生图模型未返回任务ID", 502)
    return {"task_id": task_id, "status": "submitted", "model": runtime["model"], "mode": mode}


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
