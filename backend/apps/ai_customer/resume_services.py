import base64
import uuid
from datetime import datetime
from decimal import Decimal
from io import BytesIO

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


def _http_get_image_as_base64(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ResumeAssistantError("截图地址无效", 400)
    clean_url = url.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        raise ResumeAssistantError("截图地址必须是 http/https", 400)

    try:
        resp = requests.get(clean_url, timeout=max(int(getattr(settings, "AI_RESUME_IMAGE_FETCH_TIMEOUT", 12)), 5))
    except requests.RequestException as exc:
        raise ResumeAssistantError(f"截图下载失败: {exc}", 502)
    if resp.status_code >= 400:
        raise ResumeAssistantError(f"截图下载失败({resp.status_code})", 502)

    content = resp.content or b""
    if len(content) == 0:
        raise ResumeAssistantError("截图内容为空", 400)
    if len(content) > 10 * 1024 * 1024:
        raise ResumeAssistantError("单张截图不能超过10MB", 400)
    return base64.b64encode(content).decode("ascii")


def extract_job_requirements(image_urls):
    if not isinstance(image_urls, list) or not image_urls:
        raise ResumeAssistantError("请至少上传1张职位要求截图", 400)
    if len(image_urls) > 6:
        raise ResumeAssistantError("职位要求截图最多6张", 400)

    ocr_url = (getattr(settings, "AI_RESUME_OCR_URL", "") or "").strip()
    if not ocr_url:
        raise ResumeAssistantError("OCR服务未配置", 500)

    images_b64 = [_http_get_image_as_base64(url) for url in image_urls]

    payload = {
        "images_base64": images_b64,
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
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list):
        raise ResumeAssistantError("OCR返回结构异常", 502)

    texts = []
    avg_conf_values = []
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
                    if text and (not isinstance(conf, (int, float)) or float(conf) >= 0.35):
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
    if len(ocr_text) < 30:
        raise ResumeAssistantError("OCR识别结果过少，请上传更清晰的职位要求截图", 400)

    avg_conf = sum(avg_conf_values) / len(avg_conf_values) if avg_conf_values else 0.0
    return ocr_text, {"line_count": len(cleaned), "avg_conf": round(avg_conf, 4)}


def generate_resume_text(setting: AICustomerSetting, job_title: str, ocr_text: str) -> str:
    base_url = settings.AI_CS_LLM_BASE_URL.rstrip("/")
    api_key = (settings.AI_CS_LLM_API_KEY or "").strip()
    model = settings.AI_CS_LLM_MODEL
    if not api_key:
        raise ResumeAssistantError("AI模型密钥未配置", 500)

    system_prompt = (
        f"{setting.base_prompt}\n"
        f"语气风格：{setting.tone_style}\n"
        "你现在是简历助手，请基于岗位要求输出可直接写入简历的内容草稿。"
        "不得虚构具体公司/学校/项目，缺失信息必须标注[待填写]。"
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
        f"{ocr_text}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "temperature": 0.4,
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


def render_resume_pdf(job_title: str, resume_text: str, ocr_text: str) -> bytes:
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


def run_resume_assistant(user, setting: AICustomerSetting, job_title: str, image_urls):
    ocr_text, ocr_meta = extract_job_requirements(image_urls)
    resume_text = generate_resume_text(setting, job_title, ocr_text)
    pdf_bytes = render_resume_pdf(job_title, resume_text, ocr_text)
    pdf_url, pdf_key = upload_resume_pdf(user, pdf_bytes)
    return {
        "pdf_url": pdf_url,
        "pdf_key": pdf_key,
        "ocr_text": ocr_text,
        "ocr_meta": ocr_meta,
        "resume_text": resume_text,
    }


def resume_points_cost() -> Decimal:
    return Decimal(str(getattr(settings, "AI_RESUME_ASSISTANT_COST", 10)))
