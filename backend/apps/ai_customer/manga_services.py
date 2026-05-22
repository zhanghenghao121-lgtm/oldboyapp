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
    "scene_front_image": "场景正面图",
    "scene_back_image": "场景反面图",
    "character_position_image": "人物站位图",
}


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


def prepare_storyboard_references(image_files: dict, raw_scene_context: str = "", position_description: str = "") -> dict:
    references = []
    scenes = []
    try:
        scene_context = json.loads(raw_scene_context or "[]")
    except Exception:
        scene_context = []

    if isinstance(scene_context, list):
        for idx, item in enumerate(scene_context, start=1):
            if not isinstance(item, dict):
                continue
            name = _normalize_text(item.get("name", ""))[:80] or f"场景{idx}"
            front_field = str(item.get("front_field") or "")
            back_field = str(item.get("back_field") or "")
            scene = {"name": name, "images": []}
            for field_name, direction in [(front_field, "正面"), (back_field, "反面")]:
                if not field_name:
                    continue
                image = _prepare_uploaded_image(image_files, field_name, f"场景《{name}》{direction}图")
                if image:
                    image["scene_name"] = name
                    image["direction"] = direction
                    image["label"] = f"场景《{name}》{direction}图"
                    references.append(image)
                    scene["images"].append({"direction": direction, "field": field_name, "name": image["name"]})
            scenes.append(scene)

    character_image = _prepare_uploaded_image(image_files, "character_position_image", "人物站位图")
    if character_image:
        character_image["label"] = "人物站位图"
        references.append(character_image)

    return {
        "images": references,
        "scenes": scenes,
        "position_description": _normalize_text(position_description)[:2000],
    }


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
        prompt = _clean_prompt_line(shot.get("prompt") or shot.get("text") or shot.get("content") or "")
        if not prompt or not STORYBOARD_MEANINGFUL_PATTERN.search(prompt):
            continue
        duration = _coerce_duration_seconds(
            shot.get("duration_seconds") or shot.get("duration") or shot.get("seconds")
        )
        if current and current_seconds + duration > MAX_GROUP_SECONDS:
            _append_group(groups, current)
            current = []
            current_seconds = 0.0
        current.append({"prompt": prompt, "duration_seconds": duration})
        current_seconds += duration
    _append_group(groups, current)
    return groups


def _normalize_ai_prompt_groups(content: str) -> list[dict]:
    data = _extract_json_object(content)
    flattened = []

    if isinstance(data.get("groups"), list):
        for group in data.get("groups") or []:
            if not isinstance(group, dict):
                continue
            shots = group.get("shots") or group.get("items") or group.get("sections") or []
            if isinstance(shots, list):
                flattened.extend(item for item in shots if isinstance(item, dict))

    if not flattened:
        sections = data.get("sections") or data.get("shots") or data.get("prompts") or []
        if isinstance(sections, list):
            flattened.extend(item for item in sections if isinstance(item, dict))

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


def _extract_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else {}
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


def _post_chat_completion(runtime: dict, messages: list[dict], temperature: float = 0.4) -> dict:
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise MangaScriptError("剧本模型配置不完整，请先在后台模型设置中补全", 500)

    payload = {
        "model": model,
        "stream": False,
        "temperature": temperature,
        "messages": messages,
    }
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_MANGA_TIMEOUT", 180)), 30),
        )
    except Exception as exc:
        raise MangaScriptError(f"剧本模型请求失败：{exc}", 502)
    if resp.status_code >= 400:
        raise MangaScriptError(f"剧本模型服务错误({resp.status_code})", 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"剧本模型返回非 JSON：{exc}", 502)

    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise MangaScriptError("剧本模型未返回有效内容", 502)
    return {
        "content": content,
        "usage_cost": _calculate_token_usage_cost(body.get("usage") or {}, model),
    }


def _normalize_scene_names(content: str) -> list[dict]:
    data = _extract_json_object(content)
    raw_scenes = data.get("scenes") if isinstance(data, dict) else []
    names = []
    if isinstance(raw_scenes, list):
        for item in raw_scenes:
            if isinstance(item, dict):
                name = item.get("name") or item.get("scene") or item.get("title")
            else:
                name = item
            normalized = _normalize_text(name)[:80]
            if normalized and normalized not in names:
                names.append(normalized)

    if not names:
        pattern = re.compile(r"(?:场景|地点|内景|外景|INT\.?|EXT\.?)\s*[:：]?\s*([^\n，。；;]{2,30})", re.IGNORECASE)
        for match in pattern.findall(content):
            normalized = _normalize_text(match)[:80]
            if normalized and normalized not in names:
                names.append(normalized)

    return [{"id": idx, "name": name} for idx, name in enumerate(names[:30], start=1)]


def extract_manga_scenes(source_text: str, model_preset: str = "assistant") -> dict:
    runtime = get_runtime_llm_config(model_preset)
    system_prompt = (
        "你是专业剧本场景统筹。请只识别剧本中明确出现的场景名称或地点名称，"
        "合并同义重复场景，不要臆造。输出必须是 JSON，格式："
        '{"scenes":[{"name":"场景名称"}]}'
    )
    completion = _post_chat_completion(
        runtime,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请解析以下剧本中的场景名称：\n{source_text[:24000]}"},
        ],
        temperature=0.2,
    )
    content = completion["content"]
    scenes = _normalize_scene_names(content)
    if not scenes:
        raise MangaScriptError("未识别到明确的场景名称，请补充更完整的剧本内容")
    return {
        "source_text": source_text,
        "scenes": scenes,
        "usage_cost": completion["usage_cost"],
    }


def _build_manga_user_content(
    source_text: str,
    style_label: str,
    reference_images: list[dict] | None = None,
    scene_references: list[dict] | None = None,
    position_description: str = "",
):
    text_content = (
        f"请根据以下内容生成 {style_label} 视频提示词分组。\n"
        "如果原文已经包含分镜结构，请整理为更清晰的提示词组。\n"
        "每条提示词应可直接复制给视频生成模型使用。\n"
    )
    if scene_references:
        text_content += "已识别并补充的场景资料如下：\n"
        for scene in scene_references:
            image_directions = "、".join(item["direction"] for item in scene.get("images") or []) or "未上传参考图"
            text_content += f"- {scene.get('name')}：{image_directions}\n"
    if position_description:
        text_content += f"人物站位描述：{position_description}\n"
    if reference_images:
        labels = "、".join(item["label"] for item in reference_images)
        text_content += (
            f"本次还上传了参考图片：{labels}。\n"
            "请结合图片中的场景结构、前后方向、空间关系、人物站位和镜头轴线来生成分镜提示词；"
            "没有在图片中明确出现的信息不要臆造。\n"
        )
    text_content += f"原始内容如下：\n{source_text[:24000]}"

    if not reference_images:
        return text_content

    content = [{"type": "text", "text": text_content}]
    for item in reference_images:
        content.append({"type": "text", "text": f"参考图片：{item['label']}（{item['name']}）"})
        content.append({"type": "image_url", "image_url": {"url": item["data_url"]}})
    return content


def generate_manga_storyboard(
    source_text: str,
    model_preset: str = "assistant",
    style: str = "3d",
    reference_images: list[dict] | None = None,
    scene_references: list[dict] | None = None,
    position_description: str = "",
) -> dict:
    runtime = get_runtime_llm_config(model_preset)
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise MangaScriptError("剧本模型配置不完整，请先在后台模型设置中补全", 500)

    style_key = normalize_manga_style(style)
    style_label = STYLE_LABELS[style_key]
    system_prompt = (
        f"{get_manga_storyboard_prompt()}\n\n"
        f"当前风格：{style_label}\n"
        f"当前风格提示词：{get_manga_style_prompt(style_key)}\n\n"
        "如果用户上传了场景正面图、场景反面图或人物站位图，必须优先参考图片中的空间结构、人物位置、"
        "前后朝向和镜头轴线，保证人物站位连续一致。\n"
        "硬性要求：输出必须是可解析 JSON；每个 groups[*].shots 的 duration_seconds 累计不得超过 15 秒。"
    )
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
                    scene_references,
                    position_description,
                ),
            },
        ],
    }
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_MANGA_TIMEOUT", 180)), 30),
        )
    except Exception as exc:
        raise MangaScriptError(f"剧本模型请求失败：{exc}", 502)
    if resp.status_code >= 400:
        raise MangaScriptError(f"剧本模型服务错误({resp.status_code})", 502)
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
        "model_preset": str(model_preset or "assistant").strip().lower() or "assistant",
        "usage_cost": usage_cost,
        "style": style_key,
        "style_label": style_label,
        "reference_images": [
            {"field": item["field"], "label": item["label"], "name": item["name"]}
            for item in (reference_images or [])
        ],
        "scene_references": scene_references or [],
        "position_description": position_description,
    }
