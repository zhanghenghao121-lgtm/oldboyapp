import base64
import io
import json
import mimetypes
import re
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from xml.etree import ElementTree

import requests
from django.conf import settings

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - optional runtime dependency
    Image = None
    ImageOps = None

from apps.ai_customer.runtime_config import (
    get_ai_image_config,
    get_ai_image_reverse_prompt,
    get_manga_vision_llm_config,
    get_manga_storyboard_prompt,
    get_manga_style_prompt,
    get_runtime_llm_config,
)

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional runtime dependency
    PdfReader = None


class MangaScriptError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


STORYBOARD_SPLIT_PATTERN = re.compile(
    r"(?=^(?:第\s*[0-9零一二三四五六七八九十百千]+\s*[镜幕格]|分镜\s*[0-9零一二三四五六七八九十百千]+))",
    re.MULTILINE,
)
STORYBOARD_MEANINGFUL_PATTERN = re.compile(r"[0-9A-Za-z\u4e00-\u9fff]")
MAX_GROUP_SECONDS = 15
DEFAULT_SHOT_SECONDS = 4
MAX_REFERENCE_IMAGE_BYTES = 10 * 1024 * 1024
TARGET_REFERENCE_IMAGE_BYTES = int(MAX_REFERENCE_IMAGE_BYTES * 0.95)
PROMPT_TEXT_KEYS = (
    "prompt",
    "text",
    "content",
    "description",
    "desc",
    "shot_description",
    "camera_prompt",
    "video_prompt",
    "shot",
    "scene",
    "提示词",
    "分镜词",
    "分镜提示词",
    "镜头描述",
    "画面描述",
    "画面",
)
DURATION_KEYS = ("duration_seconds", "duration", "seconds", "时长", "秒数")
PROMPT_CONTAINER_KEYS = (
    "groups",
    "shots",
    "sections",
    "items",
    "prompts",
    "storyboard",
    "result",
    "data",
    "分镜",
    "镜头",
    "段落",
    "提示词列表",
)
MILLION_TOKENS = Decimal("1000000")
TOKEN_PRICES_PER_MILLION = {
    "deepseek-v4-flash": {
        "input_cache_hit": Decimal("0.02"),
        "input_cache_miss": Decimal("1"),
        "output": Decimal("2"),
    },
    "deepseek-v4-pro": {
        "input_cache_hit": Decimal("0.025"),
        "input_cache_miss": Decimal("3"),
        "output": Decimal("6"),
    },
}
STYLE_LABELS = {
    "3d": "3D风格",
    "real": "真人风格",
}
REFERENCE_IMAGE_LABELS = {
    "character_position_image": "人物站位图",
}
AI_IMAGE_REFERENCE_LABELS = {
    "front_scene_image": "参考图1：场景正面镜头背景",
    "reverse_scene_image": "参考图2：场景反打镜头背景",
}
MAX_AI_IMAGE_REFERENCES = 16
AI_IMAGE_SIZE_OPTIONS = {
    "auto",
    "1:1",
    "3:2",
    "2:3",
    "4:3",
    "3:4",
    "5:4",
    "4:5",
    "16:9",
    "9:16",
    "2:1",
    "1:2",
    "3:1",
    "1:3",
    "21:9",
    "9:21",
}
AI_IMAGE_RESOLUTION_OPTIONS = {"1k", "2k", "4k"}


def _normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in str(text or "").replace("\r\n", "\n").split("\n")).strip()


def _extract_pdf_text(raw: bytes) -> str:
    if PdfReader is None:
        raise MangaScriptError("服务器暂未启用 PDF 解析依赖，请先安装 pypdf", 500)
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise MangaScriptError(f"PDF 读取失败：{exc}", 400)
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return _normalize_text("\n".join(parts))


def _extract_docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml = zf.read("word/document.xml")
    except KeyError:
        raise MangaScriptError("Word 文档结构异常，无法识别 document.xml")
    except Exception as exc:
        raise MangaScriptError(f"Word 文档读取失败：{exc}")

    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise MangaScriptError(f"Word 文档解析失败：{exc}")

    texts = []
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for paragraph in root.findall(".//w:p", namespace):
        paragraph_text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace))
        if paragraph_text.strip():
            texts.append(paragraph_text.strip())
    return _normalize_text("\n".join(texts))


def extract_story_source_text(file_obj=None, text: str = "") -> str:
    manual_text = _normalize_text(text)
    doc_text = ""
    if file_obj:
        name = str(getattr(file_obj, "name", "") or "").lower()
        raw = file_obj.read()
        try:
            file_obj.seek(0)
        except Exception:
            pass

        if name.endswith(".pdf"):
            doc_text = _extract_pdf_text(raw)
        elif name.endswith(".docx"):
            doc_text = _extract_docx_text(raw)
        elif name.endswith(".doc"):
            raise MangaScriptError("暂不支持旧版 .doc，请另存为 .docx 后再上传")
        else:
            raise MangaScriptError("仅支持 PDF 或 Word 文档（.docx）")

    merged = "\n\n".join(part for part in [manual_text, doc_text] if part)
    merged = _normalize_text(merged)
    if not merged:
        raise MangaScriptError("请输入文本或上传文档后再识别剧本")
    if len(merged) < 20:
        raise MangaScriptError("内容过短，请提供更完整的剧本文本")
    return merged


def _image_to_rgb(image):
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, "#ffffff")
        background.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
        return background
    return image.convert("RGB")


def _save_jpeg(image, quality: int) -> bytes:
    stream = io.BytesIO()
    image.save(stream, format="JPEG", quality=quality, optimize=True, progressive=True)
    return stream.getvalue()


def _image_resampling_filter():
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _compress_reference_image(raw: bytes, label: str) -> tuple[bytes, str]:
    if len(raw) <= TARGET_REFERENCE_IMAGE_BYTES:
        return raw, ""
    if Image is None or ImageOps is None:
        raise MangaScriptError(f"{label}超过 10MB，服务器暂未启用图片压缩依赖")

    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image = _image_to_rgb(image)
    except Exception as exc:
        raise MangaScriptError(f"{label}压缩失败：{exc}")

    max_side = 4096
    width, height = image.size
    if max(width, height) > max_side:
        ratio = max_side / max(width, height)
        image = image.resize((max(1, int(width * ratio)), max(1, int(height * ratio))), _image_resampling_filter())

    quality = 88
    compressed = _save_jpeg(image, quality)
    while len(compressed) > TARGET_REFERENCE_IMAGE_BYTES and quality > 45:
        quality -= 8
        compressed = _save_jpeg(image, quality)

    while len(compressed) > TARGET_REFERENCE_IMAGE_BYTES and max(image.size) > 1200:
        width, height = image.size
        image = image.resize((max(1, int(width * 0.85)), max(1, int(height * 0.85))), _image_resampling_filter())
        quality = 82
        compressed = _save_jpeg(image, quality)
        while len(compressed) > TARGET_REFERENCE_IMAGE_BYTES and quality > 45:
            quality -= 8
            compressed = _save_jpeg(image, quality)

    if len(compressed) > MAX_REFERENCE_IMAGE_BYTES:
        raise MangaScriptError(f"{label}压缩后仍超过 10MB，请换一张更小的图片")
    return compressed, "image/jpeg"


def _prepare_uploaded_image(image_files: dict, field_name: str, label: str) -> dict | None:
    file_obj = image_files.get(field_name) if image_files else None
    if not file_obj:
        return None

    content_type = str(getattr(file_obj, "content_type", "") or "").lower()
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(str(getattr(file_obj, "name", "") or ""))
        content_type = str(guessed_type or "").lower()
    if not content_type.startswith("image/"):
        raise MangaScriptError(f"{label}仅支持图片文件")

    raw = file_obj.read()
    try:
        file_obj.seek(0)
    except Exception:
        pass
    if not raw:
        raise MangaScriptError(f"{label}不能为空")
    compressed_raw, compressed_type = _compress_reference_image(raw, label)
    if compressed_type:
        raw = compressed_raw
        content_type = compressed_type

    return {
        "field": field_name,
        "label": label,
        "name": str(getattr(file_obj, "name", "") or label),
        "content_type": content_type,
        "data_url": f"data:{content_type};base64,{base64.b64encode(raw).decode('ascii')}",
    }


def prepare_reference_images(image_files: dict) -> list[dict]:
    images = []
    for field_name, label in REFERENCE_IMAGE_LABELS.items():
        image = _prepare_uploaded_image(image_files, field_name, label)
        if image:
            images.append(image)
    return images


def prepare_ai_image_references(image_files: dict, object_names: list[str] | None = None) -> list[dict]:
    images = []
    for field_name, label in AI_IMAGE_REFERENCE_LABELS.items():
        image = _prepare_uploaded_image(image_files, field_name, label)
        if image:
            images.append(image)
    names = object_names or []
    object_files = []
    if image_files:
        try:
            object_files = list(image_files.getlist("object_images"))
        except Exception:
            object_files = []
    for index, file_obj in enumerate(object_files[: max(0, MAX_AI_IMAGE_REFERENCES - len(images))], start=1):
        label = str(names[index - 1] if index - 1 < len(names) else "").strip()
        label = label[:40] or f"对象{index}"
        image = _prepare_uploaded_image({"object_image": file_obj}, "object_image", f"@{label} 参考图")
        if image:
            image["field"] = "object_images"
            image["label"] = f"@{label}"
            images.append(image)
    return images


def split_storyboard_sections(storyboard: str) -> list[dict]:
    text = _normalize_text(storyboard)
    if not text:
        return []

    parts = [item.strip() for item in STORYBOARD_SPLIT_PATTERN.split(text) if item.strip()]
    if len(parts) <= 1:
        blocks = [item.strip() for item in re.split(r"\n{2,}", text) if item.strip()]
        parts = blocks if len(blocks) > 1 else [text]

    sections = []
    for idx, part in enumerate(parts, start=1):
        normalized_part = _normalize_text(part)
        if not STORYBOARD_MEANINGFUL_PATTERN.search(normalized_part):
            continue
        first_line = next((line.strip() for line in part.splitlines() if line.strip()), "")
        if not STORYBOARD_MEANINGFUL_PATTERN.search(first_line):
            content_lines = [line.strip() for line in normalized_part.splitlines() if STORYBOARD_MEANINGFUL_PATTERN.search(line)]
            first_line = content_lines[0] if content_lines else ""
        title = first_line[:40] if first_line else f"分镜{idx}"
        sections.append(
            {
                "id": len(sections) + 1,
                "index": len(sections) + 1,
                "title": title,
                "prompt": normalized_part,
            }
        )
    return sections


def normalize_manga_style(style: str = "3d") -> str:
    text = str(style or "").strip().lower()
    if text in {"real", "live", "live_action", "真人", "真人风格", "写实真人"}:
        return "real"
    return "3d"


def _coerce_duration_seconds(value, default=DEFAULT_SHOT_SECONDS) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        duration = float(default)
    duration = max(1.0, min(float(MAX_GROUP_SECONDS), duration))
    return round(duration, 1)


def _clean_prompt_line(value: str) -> str:
    text = _normalize_text(value)
    text = re.sub(r"^\s*(?:第?\s*\d+\s*[镜条.]?|[-*•])\s*", "", text)
    return text.strip()


def _pick_first_text(item: dict, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            text = _normalize_text(value)
            if text:
                return text
    return ""


def _pick_duration(item: dict):
    for key in DURATION_KEYS:
        if key in item:
            return item.get(key)
    return DEFAULT_SHOT_SECONDS


def _append_group(groups: list[dict], shots: list[dict]) -> None:
    if not shots:
        return
    group_index = len(groups) + 1
    duration = round(sum(float(item.get("duration_seconds") or 0) for item in shots), 1)
    normalized_shots = []
    for item in shots:
        section_index = sum(len(group["shots"]) for group in groups) + len(normalized_shots) + 1
        normalized_shots.append(
            {
                "id": section_index,
                "index": section_index,
                "prompt": item["prompt"],
                "duration_seconds": _coerce_duration_seconds(item.get("duration_seconds")),
            }
        )
    groups.append(
        {
            "id": group_index,
            "index": group_index,
            "title": f"段落 {group_index}",
            "duration_seconds": duration,
            "shots": normalized_shots,
        }
    )


def _regroup_shots(shots: list[dict]) -> list[dict]:
    groups = []
    current = []
    current_seconds = 0.0
    for shot in shots:
        prompt = _clean_prompt_line(_pick_first_text(shot, PROMPT_TEXT_KEYS))
        if not prompt or not STORYBOARD_MEANINGFUL_PATTERN.search(prompt):
            continue
        duration = _coerce_duration_seconds(_pick_duration(shot))
        if current and current_seconds + duration > MAX_GROUP_SECONDS:
            _append_group(groups, current)
            current = []
            current_seconds = 0.0
        current.append({"prompt": prompt, "duration_seconds": duration})
        current_seconds += duration
    _append_group(groups, current)
    return groups


def _collect_prompt_shots(value) -> list[dict]:
    if isinstance(value, list):
        shots = []
        for item in value:
            shots.extend(_collect_prompt_shots(item))
        return shots

    if not isinstance(value, dict):
        return [{"prompt": value, "duration_seconds": DEFAULT_SHOT_SECONDS}] if isinstance(value, str) else []

    shots = []
    for key in PROMPT_CONTAINER_KEYS:
        if key in value:
            shots.extend(_collect_prompt_shots(value.get(key)))
    if shots:
        return shots

    prompt = _pick_first_text(value, PROMPT_TEXT_KEYS)
    if prompt:
        return [{"prompt": prompt, "duration_seconds": _pick_duration(value)}]
    return []


def _normalize_ai_prompt_groups(content: str) -> list[dict]:
    data = _extract_json_value(content)
    flattened = _collect_prompt_shots(data)
    if flattened:
        return _regroup_shots(flattened)

    fallback_sections = split_storyboard_sections(content)
    fallback_shots = [
        {"prompt": section.get("prompt", ""), "duration_seconds": DEFAULT_SHOT_SECONDS}
        for section in fallback_sections
    ]
    return _regroup_shots(fallback_shots)


def _flatten_groups(groups: list[dict]) -> list[dict]:
    sections = []
    for group in groups or []:
        for shot in group.get("shots") or []:
            sections.append(
                {
                    "id": len(sections) + 1,
                    "index": len(sections) + 1,
                    "group_id": group.get("id"),
                    "group_index": group.get("index"),
                    "title": f"提示词 {len(sections) + 1}",
                    "prompt": shot.get("prompt") or "",
                    "duration_seconds": _coerce_duration_seconds(shot.get("duration_seconds")),
                }
            )
    return sections


def _render_prompt_groups(groups: list[dict]) -> str:
    rendered = []
    for group in groups or []:
        rendered.append(f"段落 {group.get('index')} | 约 {group.get('duration_seconds')} 秒")
        for shot in group.get("shots") or []:
            rendered.append(f"{shot.get('index')}.（{shot.get('duration_seconds')}s）{shot.get('prompt')}")
        rendered.append("")
    return _normalize_text("\n".join(rendered))


def _extract_json_value(text: str):
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", raw)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def _as_int(value) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _resolve_pricing_model(model: str) -> str:
    normalized = str(model or "").strip().lower()
    if "flash" in normalized:
        return "deepseek-v4-flash"
    if "deepseek" not in normalized:
        return ""
    return "deepseek-v4-pro"


def _decimal_points(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _calculate_token_usage_cost(usage: dict, model: str) -> dict:
    usage = usage if isinstance(usage, dict) else {}
    prompt_tokens = _as_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    completion_tokens = _as_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    total_tokens = _as_int(usage.get("total_tokens")) or prompt_tokens + completion_tokens

    prompt_details = usage.get("prompt_tokens_details") if isinstance(usage.get("prompt_tokens_details"), dict) else {}
    cache_hit_tokens = _as_int(
        usage.get("prompt_cache_hit_tokens")
        or usage.get("input_cache_hit_tokens")
        or usage.get("cache_hit_tokens")
        or prompt_details.get("cached_tokens")
    )
    cache_miss_tokens = _as_int(
        usage.get("prompt_cache_miss_tokens")
        or usage.get("input_cache_miss_tokens")
        or usage.get("cache_miss_tokens")
    )
    if cache_miss_tokens <= 0 and prompt_tokens:
        cache_miss_tokens = max(prompt_tokens - cache_hit_tokens, 0)

    pricing_model = _resolve_pricing_model(model)
    if not pricing_model:
        return {
            "model": model,
            "pricing_model": "",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "input_cache_hit_tokens": cache_hit_tokens,
            "input_cache_miss_tokens": cache_miss_tokens,
            "input_cache_hit_points": 0,
            "input_cache_miss_points": 0,
            "output_points": 0,
            "total_points": 0,
            "prices_per_million": {},
        }
    prices = TOKEN_PRICES_PER_MILLION[pricing_model]
    hit_points = Decimal(cache_hit_tokens) * prices["input_cache_hit"] / MILLION_TOKENS
    miss_points = Decimal(cache_miss_tokens) * prices["input_cache_miss"] / MILLION_TOKENS
    output_points = Decimal(completion_tokens) * prices["output"] / MILLION_TOKENS
    total_points = hit_points + miss_points + output_points

    return {
        "model": model,
        "pricing_model": pricing_model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "input_cache_hit_tokens": cache_hit_tokens,
        "input_cache_miss_tokens": cache_miss_tokens,
        "input_cache_hit_points": _decimal_points(hit_points),
        "input_cache_miss_points": _decimal_points(miss_points),
        "output_points": _decimal_points(output_points),
        "total_points": _decimal_points(total_points),
        "prices_per_million": {key: float(value) for key, value in prices.items()},
    }


def _build_manga_user_content(
    source_text: str,
    style_label: str,
    reference_images: list[dict] | None = None,
    position_description: str = "",
    attach_images: bool = True,
):
    text_content = (
        f"请根据以下内容生成 {style_label} 视频提示词分组。\n"
        "如果原文已经包含分镜结构，请整理为更清晰的提示词组。\n"
        "每条提示词应可直接复制给视频生成模型使用。\n"
    )
    if position_description:
        text_content += f"人物站位描述：{position_description}\n"
    if reference_images:
        labels = "、".join(item["label"] for item in reference_images)
        text_content += (
            f"本次还上传了参考图片：{labels}。\n"
            "请结合图片中的人物位置、前后方向、空间关系、人物站位和镜头轴线来生成分镜提示词；"
            "没有在图片中明确出现的信息不要臆造。\n"
        )
    text_content += f"原始内容如下：\n{source_text[:24000]}"

    if not reference_images or not attach_images:
        return text_content

    content = [{"type": "text", "text": text_content}]
    for item in reference_images:
        content.append({"type": "text", "text": f"参考图片：{item['label']}（{item['name']}）"})
        content.append({"type": "image_url", "image_url": {"url": item["data_url"]}})
    return content


def _supports_image_payload(base_url: str, model: str) -> bool:
    text = f"{base_url} {model}".lower()
    if "deepseek" in text:
        return False
    return True


def _model_error_message(resp) -> str:
    detail = ""
    try:
        body = resp.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif isinstance(error, str):
            detail = error
        if not detail and isinstance(body, dict):
            detail = str(body.get("message") or body.get("detail") or "")
    except Exception:
        detail = str(getattr(resp, "text", "") or "")
    detail = _normalize_text(detail)[:240]
    return f"剧本模型服务错误({resp.status_code})：{detail}" if detail else f"剧本模型服务错误({resp.status_code})"


def _service_error_message(resp, label: str) -> str:
    detail = ""
    try:
        body = resp.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif isinstance(error, str):
            detail = error
        if not detail and isinstance(body, dict):
            detail = str(body.get("message") or body.get("detail") or "")
    except Exception:
        detail = str(getattr(resp, "text", "") or "")
    detail = _normalize_text(detail)[:240]
    return f"{label}服务错误({resp.status_code})：{detail}" if detail else f"{label}服务错误({resp.status_code})"


def _post_storyboard_payload(base_url: str, api_key: str, payload: dict):
    try:
        return requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_MANGA_TIMEOUT", 180)), 30),
        )
    except Exception as exc:
        raise MangaScriptError(f"剧本模型请求失败：{exc}", 502)


def _normalize_ai_image_size(value: str) -> str:
    text = str(value or "16:9").strip().lower()
    if text in AI_IMAGE_SIZE_OPTIONS or re.fullmatch(r"\d{2,5}x\d{2,5}", text):
        return text
    return "16:9"


def _normalize_ai_image_resolution(value: str) -> str:
    text = str(value or "1k").strip().lower()
    return text if text in AI_IMAGE_RESOLUTION_OPTIONS else "1k"


def _normalize_seedream_size(value: str) -> str:
    text = str(value or "2k").strip().lower()
    if text in {"2k", "3k", "4k"}:
        return text
    if re.fullmatch(r"\d{2,5}x\d{2,5}", text):
        return text
    return "2k"


def _build_ai_image_prompt(mode: str, prompt: str) -> str:
    text = _normalize_text(prompt)
    if str(mode or "").strip().lower() != "reverse_shot":
        if not text:
            raise MangaScriptError("请输入生图提示词")
        return text[:6000]
    if not text:
        raise MangaScriptError("请在描述框中用 @对象 描述正面镜头站位")
    return f"{get_ai_image_reverse_prompt()}\n\n用户站位描述：\n{text[:3000]}"


def _post_ai_image_payload(base_url: str, api_key: str, payload: dict):
    try:
        return requests.post(
            f"{base_url}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_IMAGE_SUBMIT_TIMEOUT", 60)), 20),
        )
    except Exception as exc:
        raise MangaScriptError(f"生图任务提交失败：{exc}", 502)


def _get_ai_image_task(base_url: str, api_key: str, task_id: str):
    try:
        return requests.get(
            f"{base_url}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=max(int(getattr(settings, "AI_IMAGE_QUERY_TIMEOUT", 30)), 10),
        )
    except Exception as exc:
        raise MangaScriptError(f"生图任务查询失败：{exc}", 502)


def _extract_ai_image_task_id(body: dict) -> str:
    data = body.get("data") if isinstance(body, dict) else None
    if isinstance(data, list) and data:
        return str((data[0] or {}).get("task_id") or "").strip()
    if isinstance(data, dict):
        return str(data.get("task_id") or data.get("id") or "").strip()
    return ""


def _extract_generation_image_urls(body: dict) -> list[str]:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return []
    urls = []
    for item in data:
        if not isinstance(item, dict):
            continue
        value = item.get("url") or item.get("image_url")
        if isinstance(value, list):
            urls.extend(str(url).strip() for url in value if str(url or "").strip())
        elif value:
            urls.append(str(value).strip())
        b64_json = str(item.get("b64_json") or "").strip()
        if b64_json:
            urls.append(f"data:image/png;base64,{b64_json}")
    return urls


def _is_seedream_runtime(runtime: dict) -> bool:
    text = f"{runtime.get('provider')} {runtime.get('base_url')} {runtime.get('model')}".lower()
    return "seedream" in text or "doubao" in text or "volces" in text or "volcengine" in text or "ark.cn" in text


def _extract_ai_image_urls(task_data: dict) -> list[str]:
    images = (((task_data or {}).get("result") or {}).get("images") or [])
    urls = []
    for item in images:
        value = (item or {}).get("url")
        if isinstance(value, list):
            urls.extend(str(url).strip() for url in value if str(url or "").strip())
        elif value:
            urls.append(str(value).strip())
    return urls


def submit_ai_image_generation(
    *,
    mode: str = "text",
    prompt: str = "",
    model: str = "",
    size: str = "16:9",
    resolution: str = "1k",
    reference_images: list[dict] | None = None,
) -> dict:
    runtime = get_ai_image_config(model)
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "gpt-image-2").strip() or "gpt-image-2"
    if not api_key or not base_url or not model:
        raise MangaScriptError("生图模型配置不完整，请先在后台模型设置中补全 API 地址、API Key 和模型名称", 500)

    mode_key = str(mode or "text").strip().lower()
    images = reference_images or []
    if len(images) > MAX_AI_IMAGE_REFERENCES:
        raise MangaScriptError("参考图最多支持 16 张")
    if mode_key == "reverse_shot":
        scene_fields = {item.get("field") for item in images}
        object_count = sum(1 for item in images if item.get("field") == "object_images")
        if not {"front_scene_image", "reverse_scene_image"}.issubset(scene_fields):
            raise MangaScriptError("反打画面需要上传场景正面参考图和场景反打参考图")
        if object_count <= 0:
            raise MangaScriptError("请至少上传 1 张角色或物品参考图")

    prompt_text = _build_ai_image_prompt(mode_key, prompt)
    if _is_seedream_runtime(runtime):
        payload = {
            "model": model,
            "prompt": prompt_text,
            "sequential_image_generation": "disabled",
            "response_format": "url",
            "size": _normalize_seedream_size(resolution),
            "stream": False,
            "watermark": True,
        }
        if images:
            image_urls = [item["data_url"] for item in images]
            payload["image"] = image_urls if len(image_urls) > 1 else image_urls[0]
    else:
        payload = {
            "model": model,
            "prompt": prompt_text,
            "n": 1,
            "size": _normalize_ai_image_size(size),
            "resolution": _normalize_ai_image_resolution(resolution),
        }
        if images:
            payload["image_urls"] = [item["data_url"] for item in images]

    resp = _post_ai_image_payload(base_url, api_key, payload)
    if resp.status_code >= 400:
        raise MangaScriptError(_service_error_message(resp, "生图模型"), 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"生图模型返回非 JSON：{exc}", 502)

    task_id = _extract_ai_image_task_id(body)
    image_urls = _extract_generation_image_urls(body)
    if image_urls:
        return {
            "task_id": task_id,
            "status": "completed",
            "images": image_urls,
            "model": model,
            "size": payload["size"],
            "resolution": _normalize_ai_image_resolution(resolution),
            "mode": mode_key,
            "reference_images": [
                {"field": item["field"], "label": item["label"], "name": item["name"]}
                for item in images
            ],
        }
    if not task_id:
        raise MangaScriptError("生图模型未返回任务ID", 502)
    return {
        "task_id": task_id,
        "status": "submitted",
        "model": model,
        "size": payload["size"],
        "resolution": payload["resolution"],
        "mode": mode_key,
        "reference_images": [
            {"field": item["field"], "label": item["label"], "name": item["name"]}
            for item in images
        ],
    }


def get_ai_image_task_result(task_id: str) -> dict:
    task_id = str(task_id or "").strip()
    if not task_id:
        raise MangaScriptError("缺少任务ID")
    runtime = get_ai_image_config()
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    if not api_key or not base_url:
        raise MangaScriptError("生图模型配置不完整，请先在后台模型设置中补全", 500)

    resp = _get_ai_image_task(base_url, api_key, task_id)
    if resp.status_code >= 400:
        raise MangaScriptError(_service_error_message(resp, "生图任务"), 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"生图任务返回非 JSON：{exc}", 502)

    data = body.get("data") if isinstance(body, dict) else {}
    data = data if isinstance(data, dict) else {}
    error = data.get("error") if isinstance(data.get("error"), dict) else {}
    return {
        "task_id": data.get("id") or task_id,
        "status": data.get("status") or "",
        "progress": data.get("progress") or 0,
        "created": data.get("created"),
        "completed": data.get("completed"),
        "actual_time": data.get("actual_time"),
        "cost": data.get("cost"),
        "images": _extract_ai_image_urls(data),
        "expires_at": (((data.get("result") or {}).get("images") or [{}])[0] or {}).get("expires_at"),
        "error": error.get("message") or data.get("message") or "",
    }


def generate_manga_storyboard(
    source_text: str,
    model_preset: str = "assistant",
    style: str = "3d",
    reference_images: list[dict] | None = None,
    position_description: str = "",
) -> dict:
    requested_model_preset = str(model_preset or "assistant").strip().lower() or "assistant"
    use_vision_model = bool(reference_images)
    runtime = get_manga_vision_llm_config() if use_vision_model else get_runtime_llm_config(model_preset)
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    if not api_key or not base_url or not model:
        if use_vision_model:
            raise MangaScriptError("图文识别模型配置不完整，请先在后台模型设置中补全 API 地址、API Key 和模型名称", 500)
        raise MangaScriptError("剧本模型配置不完整，请先在后台模型设置中补全", 500)

    style_key = normalize_manga_style(style)
    style_label = STYLE_LABELS[style_key]
    system_prompt = (
        f"{get_manga_storyboard_prompt()}\n\n"
        f"当前风格：{style_label}\n"
        f"当前风格提示词：{get_manga_style_prompt(style_key)}\n\n"
        "如果用户上传了人物站位图，必须优先参考图片中的人物位置、空间关系、"
        "前后朝向和镜头轴线，保证人物站位连续一致。\n"
        "硬性要求：输出必须是可解析 JSON；每个 groups[*].shots 的 duration_seconds 累计不得超过 15 秒。"
    )
    image_payload_enabled = bool(reference_images) and _supports_image_payload(base_url, model)
    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": _build_manga_user_content(
                    source_text,
                    style_label,
                    reference_images,
                    position_description,
                    attach_images=image_payload_enabled,
                ),
            },
        ],
    }
    resp = _post_storyboard_payload(base_url, api_key, payload)
    if resp.status_code >= 400 and image_payload_enabled:
        payload["messages"][1]["content"] = _build_manga_user_content(
            source_text,
            style_label,
            reference_images,
            position_description,
            attach_images=False,
        )
        resp = _post_storyboard_payload(base_url, api_key, payload)
    if resp.status_code >= 400:
        raise MangaScriptError(_model_error_message(resp), 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"剧本模型返回非 JSON：{exc}", 502)

    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise MangaScriptError("剧本模型未返回有效内容", 502)
    usage_cost = _calculate_token_usage_cost(body.get("usage") or {}, model)
    groups = _normalize_ai_prompt_groups(content)
    if not groups:
        raise MangaScriptError("剧本模型未返回可用提示词", 502)
    return {
        "storyboard": _render_prompt_groups(groups),
        "groups": groups,
        "sections": _flatten_groups(groups),
        "source_text": source_text,
        "model": model,
        "base_url": base_url,
        "model_preset": "vision" if use_vision_model else requested_model_preset,
        "requested_model_preset": requested_model_preset,
        "usage_cost": usage_cost,
        "style": style_key,
        "style_label": style_label,
        "reference_images": [
            {"field": item["field"], "label": item["label"], "name": item["name"]}
            for item in (reference_images or [])
        ],
        "position_description": position_description,
    }
