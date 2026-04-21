import io
import json
import re
import zipfile
from xml.etree import ElementTree

import requests
from django.conf import settings

from apps.ai_customer.runtime_config import (
    get_assistant_llm_config,
    get_manga_image_prompt,
    get_manga_storyboard_prompt,
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
    for node in root.findall(".//w:t", namespace):
        if node.text:
            texts.append(node.text)
    return _normalize_text("".join(texts))


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


def _unique_entity_list(values) -> list[str]:
    seen = set()
    items = []
    for value in values or []:
        text = _normalize_text(value)
        if not text or not STORYBOARD_MEANINGFUL_PATTERN.search(text):
            continue
        if text in seen:
            continue
        seen.add(text)
        items.append(text[:40])
    return items[:8]


def _call_llm_json(runtime: dict, *, system_prompt: str, user_prompt: str) -> dict:
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise MangaScriptError("用于优化分镜图提示词的模型配置不完整，请先在后台补全", 500)

    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
        raise MangaScriptError(f"分镜图提示词优化请求失败：{exc}", 502)
    if resp.status_code >= 400:
        raise MangaScriptError(f"分镜图提示词优化服务错误({resp.status_code})", 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"分镜图提示词优化返回非 JSON：{exc}", 502)
    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise MangaScriptError("分镜图提示词优化未返回有效内容", 502)
    return _extract_json_object(content)


def prepare_storyboard_image_sections(sections: list[dict]) -> list[dict]:
    runtime = get_assistant_llm_config()
    system_prompt = (
        "你是漫画分镜首帧图片提示词优化助手。"
        f"请严格按照以下系统要求优化每段分镜提示词：{get_manga_image_prompt()}\n"
        "你必须输出 JSON，不要输出 markdown，不要解释。"
        "JSON 结构必须是："
        '{"optimized_prompt":"", "characters":[""], "scenes":[""], "items":[""]}'
        "其中：characters 提取人物，scenes 提取场景，items 提取关键物品。"
    )

    prepared = []
    for idx, section in enumerate(sections or [], start=1):
        raw_prompt = _normalize_text((section or {}).get("prompt") or "")
        if not raw_prompt or not STORYBOARD_MEANINGFUL_PATTERN.search(raw_prompt):
            continue
        title = str((section or {}).get("title") or f"分镜{idx}").strip() or f"分镜{idx}"
        try:
            data = _call_llm_json(
                runtime,
                system_prompt=system_prompt,
                user_prompt=f"请处理以下分镜内容，并返回指定 JSON。\n分镜标题：{title}\n分镜内容：\n{raw_prompt[:5000]}",
            )
        except MangaScriptError:
            data = {}

        optimized_prompt = _normalize_text(data.get("optimized_prompt") or raw_prompt)
        prepared.append(
            {
                "id": (section or {}).get("id") or len(prepared) + 1,
                "index": (section or {}).get("index") or len(prepared) + 1,
                "title": title,
                "raw_prompt": raw_prompt,
                "prompt": optimized_prompt,
                "characters": _unique_entity_list(data.get("characters") or []),
                "scenes": _unique_entity_list(data.get("scenes") or []),
                "items": _unique_entity_list(data.get("items") or []),
            }
        )
    return prepared


def generate_manga_storyboard(source_text: str, model_preset: str = "assistant") -> dict:
    runtime = get_runtime_llm_config(model_preset)
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    model = str(runtime.get("model") or "").strip()
    if not api_key or not base_url or not model:
        raise MangaScriptError("漫剧模型配置不完整，请先在后台模型设置中补全", 500)

    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": get_manga_storyboard_prompt()},
            {
                "role": "user",
                "content": (
                    "请根据以下内容生成 AI 漫剧分镜稿。\n"
                    "如果原文已经包含分镜结构，请整理得更清晰。\n"
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
        raise MangaScriptError(f"漫剧模型请求失败：{exc}", 502)
    if resp.status_code >= 400:
        raise MangaScriptError(f"漫剧模型服务错误({resp.status_code})", 502)
    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"漫剧模型返回非 JSON：{exc}", 502)

    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise MangaScriptError("漫剧模型未返回有效内容", 502)
    return {
        "storyboard": content,
        "sections": split_storyboard_sections(content),
        "source_text": source_text,
        "model": model,
        "base_url": base_url,
        "model_preset": str(model_preset or "assistant").strip().lower() or "assistant",
    }


def _build_reference_asset_note(reference_assets) -> str:
    if not isinstance(reference_assets, list):
        return ""
    lines = []
    for item in reference_assets:
        if not isinstance(item, dict):
            continue
        category = _normalize_text(item.get("category") or "")
        label = _normalize_text(item.get("label") or "")
        url = _normalize_text(item.get("url") or "")
        if not category or not label:
            continue
        line = f"{category}:{label}"
        if url:
            line += f"（参考图：{url}）"
        lines.append(line)
    if not lines:
        return ""
    return "参考素材：\n" + "\n".join(f"- {line}" for line in lines)


def optimize_storyboard_image_prompt(prompt: str, reference_assets=None) -> str:
    runtime = get_assistant_llm_config()
    system_prompt = (
        "你是漫画分镜首帧图片提示词优化助手。"
        f"请严格按照以下系统要求优化提示词：{get_manga_image_prompt()}\n"
        "请只输出最终可直接用于图片生成的中文提示词，不要解释，不要 markdown。"
    )
    reference_note = _build_reference_asset_note(reference_assets)
    data = _call_llm_json(
        runtime,
        system_prompt=system_prompt + '若无法输出 JSON，请至少把 optimized_prompt 字段补全。',
        user_prompt=(
            "请把下面这段分镜提示词优化为更适合首帧图片生成的描述，并返回 JSON。\n"
            '{"optimized_prompt":"", "characters":[""], "scenes":[""], "items":[""]}\n'
            f"分镜提示词：\n{_normalize_text(prompt)[:5000]}\n"
            f"{reference_note}\n"
        ).strip(),
    )
    optimized_prompt = _normalize_text(data.get("optimized_prompt") or prompt)
    if reference_note:
        optimized_prompt = f"{optimized_prompt}\n{reference_note}"
    return optimized_prompt


def generate_manga_storyboard_image(prompt: str, reference_assets=None) -> dict:
    api_key = str(getattr(settings, "ARK_API_KEY", "") or "").strip()
    base_url = str(getattr(settings, "ARK_IMAGE_BASE_URL", "") or "").strip().rstrip("/")
    if not api_key:
        raise MangaScriptError("ARK_API_KEY 未配置，暂时无法生成分镜图", 500)
    if not base_url:
        raise MangaScriptError("ARK_IMAGE_BASE_URL 未配置，暂时无法生成分镜图", 500)

    text = _normalize_text(prompt)
    if not text:
        raise MangaScriptError("分镜提示词不能为空")
    try:
        optimized_prompt = optimize_storyboard_image_prompt(text, reference_assets=reference_assets)
    except MangaScriptError:
        optimized_prompt = text

    payload = {
        "model": "doubao-seedream-5-0-260128",
        "prompt": optimized_prompt[:4000],
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": "2K",
        "stream": False,
        "watermark": True,
    }
    try:
        resp = requests.post(
            f"{base_url}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "ARK_IMAGE_TIMEOUT", 90)), 30),
        )
    except Exception as exc:
        raise MangaScriptError(f"分镜图请求失败：{exc}", 502)

    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = {"message": (resp.text or "").strip()[:300]}
        message = ""
        if isinstance(body, dict):
            if isinstance(body.get("error"), dict):
                message = str(body["error"].get("message") or body["error"].get("type") or "")
            if not message:
                message = str(body.get("message") or body.get("detail") or body.get("msg") or "")
        raise MangaScriptError(message or f"分镜图服务错误({resp.status_code})", 502)

    try:
        body = resp.json()
    except Exception as exc:
        raise MangaScriptError(f"分镜图返回非 JSON：{exc}", 502)
    items = body.get("data") or []
    first = items[0] if isinstance(items, list) and items else {}
    image_url = str((first or {}).get("url") or "").strip()
    if not image_url:
        raise MangaScriptError("分镜图结果缺少图片地址", 502)
    return {
        "image_url": image_url,
        "model": "doubao-seedream-5-0-260128",
        "prompt": optimized_prompt,
    }
