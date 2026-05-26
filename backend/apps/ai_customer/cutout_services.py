import io
import os
import uuid
from datetime import datetime

import requests
from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.runtime_config import get_remove_bg_api_key
from apps.storage.models import UploadedFileRecord


class CutoutError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _opencv():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise CutoutError("服务器未安装抠图处理依赖，请联系管理员", 500) from exc
    return cv2, np


def _decode_image(raw: bytes):
    cv2, np = _opencv()
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise CutoutError("无法读取图片文件，请上传 JPG、PNG 或 WebP 图片")
    height, width = image.shape[:2]
    if width < 2 or height < 2:
        raise CutoutError("图片尺寸无效")
    return image, width, height


def _fast_white_background_cutout(raw: bytes) -> tuple[bytes, int, int]:
    cv2, np = _opencv()
    image, width, height = _decode_image(raw)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

    rgb = image[:, :, :3].astype(np.int16)
    minimum = rgb.min(axis=2)
    maximum = rgb.max(axis=2)
    chroma = maximum - minimum

    # Pure white pixels disappear; the short transition reduces white halos on clear edges.
    white_strength = np.clip((minimum - 220) / 30.0, 0.0, 1.0)
    neutral_strength = np.clip((28 - chroma) / 18.0, 0.0, 1.0)
    removed = white_strength * neutral_strength
    generated_alpha = np.rint(255 * (1.0 - removed)).astype(np.uint8)
    image[:, :, 3] = np.minimum(image[:, :, 3], generated_alpha)

    success, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not success:
        raise CutoutError("生成透明 PNG 失败", 500)
    return encoded.tobytes(), width, height


def _remove_bg_cutout(raw: bytes, filename: str, content_type: str) -> tuple[bytes, int, int]:
    api_key = get_remove_bg_api_key()
    if not api_key:
        raise CutoutError("管理员尚未配置 remove.bg API Key", 503)
    try:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": api_key},
            files={"image_file": (filename or "character.png", raw, content_type or "image/png")},
            data={"size": "auto", "format": "png"},
            timeout=90,
        )
    except requests.RequestException as exc:
        raise CutoutError("AI 抠图服务连接失败，请稍后重试", 502) from exc

    if response.status_code != 200:
        message = "AI 抠图失败"
        try:
            errors = response.json().get("errors") or []
            if errors:
                message = str(errors[0].get("title") or message)
        except ValueError:
            pass
        raise CutoutError(f"{message}（remove.bg {response.status_code}）", 502)

    png_bytes = response.content
    _, width, height = _decode_image(png_bytes)
    return png_bytes, width, height


def _upload_transparent_png(png_bytes: bytes, user) -> dict:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise CutoutError("COS 配置不完整", 500)

    key = f"images/cutouts/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.png"
    client = CosS3Client(
        CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
    )
    try:
        client.put_object(
            Bucket=settings.COS_BUCKET,
            Body=io.BytesIO(png_bytes),
            Key=key,
            ContentType="image/png",
        )
    except Exception as exc:
        raise CutoutError("透明图片上传失败，请稍后重试", 502) from exc

    base_url = str(settings.COS_BASE_URL or "").rstrip("/")
    url = (
        f"{base_url}/{key}"
        if base_url
        else f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    )
    UploadedFileRecord.objects.create(
        user=user,
        key=key,
        url=url,
        content_type="image/png",
        size=len(png_bytes),
    )
    return {"url": url, "key": key, "content_type": "image/png", "size": len(png_bytes)}


def get_cutout_asset(key: str, user) -> bytes:
    normalized_key = str(key or "").strip()
    record = UploadedFileRecord.objects.filter(
        user=user,
        key=normalized_key,
        content_type="image/png",
    ).first()
    if not record or not normalized_key.startswith("images/cutouts/"):
        raise CutoutError("透明图片不存在", 404)
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise CutoutError("COS 配置不完整", 500)
    client = CosS3Client(
        CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
    )
    try:
        response = client.get_object(Bucket=settings.COS_BUCKET, Key=normalized_key)
        return response["Body"].get_raw_stream().read()
    except Exception as exc:
        raise CutoutError("透明图片读取失败", 502) from exc


def cutout_character(file_obj, mode: str, user) -> dict:
    normalized_mode = str(mode or "fast").strip().lower()
    if normalized_mode not in {"fast", "ai"}:
        raise CutoutError("抠图模式不支持")
    if not file_obj:
        raise CutoutError("请上传角色图片")
    if int(file_obj.size or 0) > settings.MAX_UPLOAD_SIZE:
        raise CutoutError("图片超过大小限制（最大 10MB）", 413)

    filename = os.path.basename(file_obj.name or "character.png")
    content_type = str(file_obj.content_type or "application/octet-stream")
    if not content_type.startswith("image/"):
        raise CutoutError("仅支持图片文件", 415)

    raw = file_obj.read()
    if normalized_mode == "fast":
        png_bytes, width, height = _fast_white_background_cutout(raw)
    else:
        png_bytes, width, height = _remove_bg_cutout(raw, filename, content_type)
    uploaded = _upload_transparent_png(png_bytes, user)
    return {
        **uploaded,
        "width": width,
        "height": height,
        "mode": normalized_mode,
        "filename": filename,
    }
