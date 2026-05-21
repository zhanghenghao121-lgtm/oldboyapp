import io
import json
import re
import zipfile
from xml.etree import ElementTree

import requests
from django.conf import settings

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
STYLE_LABELS = {
    "3d": "3D风格",
    "real": "真人风格",
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


def generate_manga_storyboard(source_text: str, model_preset: str = "assistant", style: str = "3d") -> dict:
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
                "content": (
                    f"请根据以下内容生成 {style_label} 视频提示词分组。\n"
                    "如果原文已经包含分镜结构，请整理为更清晰的提示词组。\n"
                    "每条提示词应可直接复制给视频生成模型使用。\n"
                    "原始内容如下：\n"
                    f"{source_text[:24000]}"
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
        "style": style_key,
        "style_label": style_label,
    }
