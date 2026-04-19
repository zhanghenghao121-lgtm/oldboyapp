import io
import json
import zipfile
from xml.etree import ElementTree

import requests
from django.conf import settings

from apps.ai_customer.runtime_config import (
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
        "source_text": source_text,
        "model": model,
        "base_url": base_url,
        "model_preset": str(model_preset or "assistant").strip().lower() or "assistant",
    }
