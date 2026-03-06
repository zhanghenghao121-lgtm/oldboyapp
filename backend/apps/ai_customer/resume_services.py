import base64
import json
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from urllib.parse import urlparse

import requests
from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.models import AICustomerSetting
from apps.storage.models import UploadedFileRecord


class ResumeAssistantError(Exception):
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


def _safe_json(resp):
    try:
        return resp.json()
    except ValueError:
        raise ResumeAssistantError("上游服务返回非JSON格式", 502)


def _cos_get_image_bytes(url: str) -> bytes:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise ResumeAssistantError("COS配置不完整", 500)

    parsed = urlparse(url)
    path_key = parsed.path.lstrip("/")
    record = UploadedFileRecord.objects.filter(url__startswith=f"{parsed.scheme}://{parsed.netloc}{parsed.path}").order_by("-id").first()
    key = (record.key if record and record.key else path_key).strip()
    if not key:
        raise ResumeAssistantError("截图地址无效", 400)

    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    try:
        obj = client.get_object(Bucket=settings.COS_BUCKET, Key=key)
    except Exception as exc:
        raise ResumeAssistantError(f"COS读取失败: {exc}", 502)

    body = obj.get("Body")
    if body is None:
        raise ResumeAssistantError("COS返回内容为空", 502)
    try:
        if hasattr(body, "get_raw_stream"):
            content = body.get_raw_stream().read()
        elif hasattr(body, "read"):
            content = body.read()
        else:
            content = b""
    except Exception as exc:
        raise ResumeAssistantError(f"COS读取失败: {exc}", 502)
    if not content:
        raise ResumeAssistantError("截图内容为空", 400)
    return content


def _http_get_image_bytes(url: str) -> bytes:
    if not isinstance(url, str) or not url.strip():
        raise ResumeAssistantError("截图地址无效", 400)
    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        raise ResumeAssistantError("截图地址必须是 http/https", 400)
    try:
        resp = requests.get(clean_url, timeout=max(int(getattr(settings, "AI_RESUME_IMAGE_FETCH_TIMEOUT", 12)), 5))
    except requests.RequestException as exc:
        # Private COS resources may block direct HTTP access; fallback to COS SDK read.
        try:
            content = _cos_get_image_bytes(clean_url)
        except ResumeAssistantError:
            raise ResumeAssistantError(f"截图下载失败: {exc}", 502)
        else:
            if len(content) > 10 * 1024 * 1024:
                raise ResumeAssistantError("单张截图不能超过10MB", 400)
            return content
    if resp.status_code >= 400:
        if resp.status_code in {401, 403, 404}:
            try:
                content = _cos_get_image_bytes(clean_url)
            except ResumeAssistantError:
                raise ResumeAssistantError(f"截图下载失败({resp.status_code})", 502)
            else:
                if len(content) > 10 * 1024 * 1024:
                    raise ResumeAssistantError("单张截图不能超过10MB", 400)
                return content
        raise ResumeAssistantError(f"截图下载失败({resp.status_code})", 502)
    content = resp.content or b""
    if not content:
        raise ResumeAssistantError("截图内容为空", 400)
    if len(content) > 10 * 1024 * 1024:
        raise ResumeAssistantError("单张截图不能超过10MB", 400)
    return content


def _normalize_roi_map(rois):
    roi_map = {}
    if not isinstance(rois, list):
        return roi_map
    for item in rois:
        if not isinstance(item, dict):
            continue
        try:
            image_index = int(item.get("image_index"))
        except (TypeError, ValueError):
            continue
        rects = item.get("rects") or []
        if not isinstance(rects, list) or not rects:
            continue
        rect = rects[0]
        if not isinstance(rect, dict):
            continue
        try:
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            w = float(rect.get("w", 0))
            h = float(rect.get("h", 0))
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        x = max(0.0, min(1.0, x))
        y = max(0.0, min(1.0, y))
        w = max(0.0, min(1.0 - x, w))
        h = max(0.0, min(1.0 - y, h))
        if w <= 0 or h <= 0:
            continue
        roi_map[image_index] = {"x": x, "y": y, "w": w, "h": h}
    return roi_map


def _crop_image_by_roi(image_bytes: bytes, roi: dict) -> bytes:
    if not roi:
        return image_bytes
    try:
        from PIL import Image
    except Exception:
        return image_bytes
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        left = int(width * roi["x"])
        top = int(height * roi["y"])
        right = int(width * (roi["x"] + roi["w"]))
        bottom = int(height * (roi["y"] + roi["h"]))
        left = max(0, min(left, width - 1))
        top = max(0, min(top, height - 1))
        right = max(left + 1, min(right, width))
        bottom = max(top + 1, min(bottom, height))
        cropped = img.crop((left, top, right, bottom))
        out = BytesIO()
        fmt = (img.format or "PNG").upper()
        if fmt not in {"PNG", "JPEG", "JPG", "WEBP"}:
            fmt = "PNG"
        cropped.save(out, format="JPEG" if fmt == "JPG" else fmt)
        return out.getvalue()
    except Exception:
        return image_bytes


def _extract_by_json_base64(ocr_url: str, images_bytes):
    payload = {
        "images_base64": [base64.b64encode(raw).decode("ascii") for raw in images_bytes],
        "lang": "ch",
        "det": True,
        "rec": True,
    }
    try:
        resp = requests.post(
            ocr_url,
            json=payload,
            timeout=max(int(getattr(settings, "AI_RESUME_OCR_TIMEOUT", 45)), 10),
        )
    except requests.RequestException as exc:
        raise ResumeAssistantError(f"OCR服务请求失败: {exc}", 502)
    if resp.status_code >= 400:
        raise ResumeAssistantError(f"OCR服务错误({resp.status_code})", 502)
    data = _safe_json(resp)
    if not isinstance(data, (dict, list)):
        raise ResumeAssistantError("OCR返回结构异常", 502)
    return _normalize_ocr_results(data)


def _normalize_conf(value):
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _collect_ocr_lines(node, out, depth=0):
    if depth > 8:
        return
    if isinstance(node, dict):
        text_value = None
        for key in ("rec_text", "text", "word", "words", "content", "label"):
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                text_value = value.strip()
                break
        if text_value:
            conf = None
            for key in ("score", "conf", "confidence", "prob"):
                conf = _normalize_conf(node.get(key))
                if conf is not None:
                    break
            out.append({"text": text_value, "conf": conf if conf is not None else 1.0})

        for key, value in node.items():
            if key in {"text", "rec_text", "word", "words", "content", "label", "score", "conf", "confidence", "prob"}:
                continue
            _collect_ocr_lines(value, out, depth + 1)
        return

    if isinstance(node, list):
        for item in node:
            _collect_ocr_lines(item, out, depth + 1)
        return

    if isinstance(node, str):
        row = node.strip()
        if row:
            out.append({"text": row, "conf": 1.0})


def _normalize_ocr_results(payload):
    # Expected format: {"results":[{"lines":[...], "avg_conf": ...}, ...]}
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        normalized = []
        for image_result in payload.get("results") or []:
            if isinstance(image_result, dict):
                lines = image_result.get("lines")
                if isinstance(lines, list):
                    normalized.append({"lines": lines, "avg_conf": image_result.get("avg_conf", 0.0)})
                    continue
                extracted = []
                _collect_ocr_lines(image_result, extracted)
                normalized.append({"lines": extracted, "avg_conf": image_result.get("avg_conf", 0.0)})
            else:
                extracted = []
                _collect_ocr_lines(image_result, extracted)
                normalized.append({"lines": extracted, "avg_conf": 0.0})
        if normalized:
            return normalized

    # Fallback: extract from any JSON structure.
    extracted = []
    _collect_ocr_lines(payload, extracted)
    if not extracted:
        raise ResumeAssistantError("OCR返回结构异常", 502)
    return [{"lines": extracted, "avg_conf": 0.0}]


def _extract_by_sparrow(ocr_url: str, images_bytes):
    results = []
    timeout_s = max(int(getattr(settings, "AI_RESUME_OCR_TIMEOUT", 45)), 10)
    for idx, raw in enumerate(images_bytes):
        files = {"file": (f"image_{idx}.png", raw, "image/png")}
        try:
            resp = requests.post(ocr_url, files=files, timeout=timeout_s)
        except requests.RequestException as exc:
            raise ResumeAssistantError(f"OCR服务请求失败: {exc}", 502)
        if resp.status_code >= 400:
            raise ResumeAssistantError(f"OCR服务错误({resp.status_code})", 502)
        data = _safe_json(resp)

        lines = []
        avg_conf = 0.0
        if isinstance(data, dict):
            if isinstance(data.get("result"), list):
                scores = []
                for item in data.get("result") or []:
                    if isinstance(item, dict):
                        text = str(item.get("rec_text") or item.get("text") or "").strip()
                        score = item.get("score")
                        if text:
                            lines.append({"text": text, "conf": score if isinstance(score, (int, float)) else 1.0})
                            if isinstance(score, (int, float)):
                                scores.append(float(score))
                if scores:
                    avg_conf = sum(scores) / len(scores)
            elif isinstance(data.get("data"), dict) and data["data"].get("text"):
                text = str(data["data"].get("text")).strip()
                if text:
                    for row in text.splitlines():
                        row = row.strip()
                        if row:
                            lines.append({"text": row, "conf": 1.0})
                    avg_conf = 1.0
            elif isinstance(data.get("text"), str):
                text = data.get("text").strip()
                if text:
                    for row in text.splitlines():
                        row = row.strip()
                        if row:
                            lines.append({"text": row, "conf": 1.0})
                    avg_conf = 1.0

        results.append({"lines": lines, "avg_conf": avg_conf})
    return results


def extract_job_requirements(image_urls, rois=None):
    if not isinstance(image_urls, list) or not image_urls:
        raise ResumeAssistantError("请至少上传1张职位要求截图", 400)
    if len(image_urls) > 6:
        raise ResumeAssistantError("职位要求截图最多6张", 400)

    ocr_url = (getattr(settings, "AI_RESUME_OCR_URL", "") or "").strip()
    if not ocr_url:
        raise ResumeAssistantError("OCR服务未配置", 500)

    roi_map = _normalize_roi_map(rois)
    images_bytes = []
    for idx, url in enumerate(image_urls):
        raw = _http_get_image_bytes(url)
        raw = _crop_image_by_roi(raw, roi_map.get(idx))
        images_bytes.append(raw)

    provider = str(getattr(settings, "AI_RESUME_OCR_PROVIDER", "json_base64") or "json_base64").strip().lower()
    if provider == "sparrow":
        results = _extract_by_sparrow(ocr_url, images_bytes)
    else:
        results = _extract_by_json_base64(ocr_url, images_bytes)

    texts = []
    avg_conf_values = []
    conf_threshold = float(getattr(settings, "AI_RESUME_OCR_CONF_MIN", 0.20))
    for image_result in results:
        if not isinstance(image_result, dict):
            continue
        avg_conf = image_result.get("avg_conf")
        if isinstance(avg_conf, (int, float)):
            avg_conf_values.append(float(avg_conf))

        lines = image_result.get("lines") or []
        if isinstance(lines, list):
            for line in lines:
                if isinstance(line, dict):
                    text = str(line.get("text", "")).strip()
                    conf = line.get("conf")
                    if text and (not isinstance(conf, (int, float)) or float(conf) >= conf_threshold):
                        texts.append(text)
                elif isinstance(line, str):
                    line = line.strip()
                    if line:
                        texts.append(line)

    cleaned = []
    seen = set()
    for text in texts:
        row = " ".join(text.split())
        if not row:
            continue
        if row in seen:
            continue
        seen.add(row)
        cleaned.append(row)

    ocr_text = "\n".join(cleaned).strip()
    min_chars = max(int(getattr(settings, "AI_RESUME_OCR_MIN_TEXT_CHARS", 12)), 1)
    min_lines = max(int(getattr(settings, "AI_RESUME_OCR_MIN_LINES", 1)), 1)
    if len(ocr_text) < min_chars or len(cleaned) < min_lines:
        raise ResumeAssistantError("OCR识别结果过少，请上传更清晰的职位要求截图", 400)

    avg_conf = sum(avg_conf_values) / len(avg_conf_values) if avg_conf_values else 0.0
    return ocr_text, {"line_count": len(cleaned), "avg_conf": round(avg_conf, 4)}


def _call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.4):
    base_url = settings.AI_CS_LLM_BASE_URL.rstrip("/")
    api_key = (settings.AI_CS_LLM_API_KEY or "").strip()
    model = settings.AI_CS_LLM_MODEL
    if not api_key:
        raise ResumeAssistantError("AI模型密钥未配置", 500)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": temperature,
    }

    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_RESUME_LLM_TIMEOUT", 120)), 30),
        )
    except requests.RequestException as exc:
        raise ResumeAssistantError(f"LLM请求失败: {exc}", 502)

    if resp.status_code >= 400:
        raise ResumeAssistantError(f"LLM服务错误({resp.status_code})", 502)

    data = _safe_json(resp)
    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices:
        raise ResumeAssistantError("LLM未返回内容", 502)
    content = ((choices[0] or {}).get("message") or {}).get("content", "")
    content = str(content or "").strip()
    if not content:
        raise ResumeAssistantError("LLM返回为空", 502)
    return content


def _extract_json_block(text: str):
    content = str(text or "").strip()
    if not content:
        return None
    if content.startswith("```"):
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start:end + 1]
    try:
        return json.loads(content)
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(content[start:end + 1])
            except Exception:
                return None
        return None


def extract_skill_points(setting: AICustomerSetting, job_title: str, ocr_text: str):
    system_prompt = (
        "你是技术岗位分析助手。请根据岗位要求提炼技能点，不要编造。"
        "输出必须是JSON对象，格式："
        "{\"skills\":[{\"name\":\"\",\"intro\":\"\",\"usage\":\"\",\"tools\":[\"\",\"\"]}]}"
    )
    user_prompt = (
        f"职位名称：{job_title}\n"
        "请从以下岗位要求中提炼技能点，每个技能点必须包含：\n"
        "1) 简约介绍 intro\n2) 如何使用 usage\n3) 相关工具 tools(数组)\n"
        f"岗位要求文本：\n{ocr_text[:4000]}"
    )
    content = _call_llm(system_prompt, user_prompt, temperature=0.2)
    data = _extract_json_block(content) or {}
    raw = data.get("skills") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    output = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        intro = str(item.get("intro", "")).strip()
        usage = str(item.get("usage", "")).strip()
        tools = item.get("tools") if isinstance(item.get("tools"), list) else []
        tools = [str(t).strip() for t in tools if str(t).strip()][:8]
        if not name:
            continue
        output.append(
            {
                "name": name[:64],
                "intro": intro[:300],
                "usage": usage[:300],
                "tools": tools,
            }
        )
    return output


def generate_resume_text(setting: AICustomerSetting, job_title: str, ocr_text: str, skill_points=None) -> str:
    skill_points = skill_points or []
    skills_text = "无"
    if skill_points:
        rows = []
        for item in skill_points:
            rows.append(
                f"- {item.get('name','')}: 简介={item.get('intro','')}; 使用={item.get('usage','')}; 工具={','.join(item.get('tools') or [])}"
            )
        skills_text = "\n".join(rows)

    system_prompt = (
        f"{setting.resume_system_prompt}\n"
        f"语气风格：{setting.tone_style}\n"
        "输出格式：\n"
        "1. 求职目标\n"
        "2. 职业摘要（3-5条）\n"
        "3. 核心技能（硬技能/工具/软技能）\n"
        "4. 项目经历模板（2段，含要点）\n"
        "5. 工作经历模板（2段，含要点）\n"
        "6. 教育背景模板\n"
        "7. 关键词清单（ATS）\n"
        "要求简洁，使用中文。"
    )
    user_prompt = (
        f"职位名称：{job_title}\n"
        "以下是OCR识别到的职位要求文本，请分析并生成对应简历草稿：\n"
        f"{ocr_text[:5000]}\n\n"
        "以下是提炼出的技能点，请结合使用：\n"
        f"{skills_text}"
    )

    return _call_llm(system_prompt, user_prompt, temperature=0.4)


def _wrap_text(text: str, width: int = 36):
    rows = []
    for paragraph in str(text or "").splitlines():
        line = paragraph.rstrip()
        if not line:
            rows.append("")
            continue
        while len(line) > width:
            rows.append(line[:width])
            line = line[width:]
        rows.append(line)
    return rows


def render_resume_pdf(job_title: str, resume_text: str, ocr_text: str, skill_points=None) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise ResumeAssistantError(f"PDF生成依赖缺失: {exc}", 500)

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)

    font_name = "STSong-Light"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))
    except Exception:
        font_name = "Helvetica"

    _, height = A4
    left = 40
    top = height - 48
    y = top

    def draw_line(line: str, size: int = 11, gap: int = 18):
        nonlocal y
        if y < 56:
            c.showPage()
            try:
                if font_name == "STSong-Light":
                    pdfmetrics.registerFont(UnicodeCIDFont(font_name))
            except Exception:
                pass
            y = top
        c.setFont(font_name, size)
        c.drawString(left, y, line)
        y -= gap

    draw_line(f"简历助手生成草稿 - {job_title}", size=16, gap=24)
    draw_line(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=10, gap=18)
    draw_line("", size=11, gap=12)
    draw_line("【简历内容建议】", size=12, gap=20)
    for line in _wrap_text(resume_text, width=35):
        draw_line(line or " ", size=11, gap=17)

    skill_points = skill_points or []
    if skill_points:
        draw_line("", size=11, gap=12)
        draw_line("【岗位技能点分析】", size=12, gap=20)
        for idx, skill in enumerate(skill_points, start=1):
            draw_line(f"{idx}. {skill.get('name','')}", size=11, gap=17)
            draw_line(f"   简介：{skill.get('intro','')}", size=10, gap=16)
            draw_line(f"   使用：{skill.get('usage','')}", size=10, gap=16)
            draw_line(f"   工具：{', '.join(skill.get('tools') or [])}", size=10, gap=16)

    draw_line("", size=11, gap=12)
    draw_line("【岗位要求OCR摘要（截断）】", size=12, gap=20)
    excerpt = ocr_text[:1200]
    for line in _wrap_text(excerpt, width=35):
        draw_line(line or " ", size=10, gap=16)

    c.save()
    return buf.getvalue()


def upload_resume_pdf(user, pdf_bytes: bytes):
    if not pdf_bytes:
        raise ResumeAssistantError("PDF内容为空", 500)
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise ResumeAssistantError("COS配置不完整", 500)

    key = f"ai-customer/resume/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.pdf"
    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)

    try:
        client.put_object(
            Bucket=settings.COS_BUCKET,
            Body=pdf_bytes,
            Key=key,
            ContentType="application/pdf",
        )
    except Exception as exc:
        raise ResumeAssistantError(f"PDF上传失败: {exc}", 502)

    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"

    UploadedFileRecord.objects.create(
        user=user,
        key=key,
        url=url,
        content_type="application/pdf",
        size=len(pdf_bytes),
    )
    return url, key


def run_resume_assistant(user, setting: AICustomerSetting, job_title: str, image_urls, rois=None):
    ocr_text, ocr_meta = extract_job_requirements(image_urls, rois=rois)
    skill_points = extract_skill_points(setting, job_title, ocr_text)
    resume_text = generate_resume_text(setting, job_title, ocr_text, skill_points=skill_points)
    pdf_bytes = render_resume_pdf(job_title, resume_text, ocr_text, skill_points=skill_points)
    pdf_url, pdf_key = upload_resume_pdf(user, pdf_bytes)
    return {
        "pdf_url": pdf_url,
        "pdf_key": pdf_key,
        "ocr_text": ocr_text,
        "ocr_meta": ocr_meta,
        "skill_points": skill_points,
        "resume_text": resume_text,
    }


def resume_points_cost() -> Decimal:
    return Decimal(str(getattr(settings, "AI_RESUME_ASSISTANT_COST", 10)))
