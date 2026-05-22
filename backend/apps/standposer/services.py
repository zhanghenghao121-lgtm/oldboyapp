import os
import uuid
from datetime import datetime

from django.conf import settings
from qcloud_cos import CosConfig, CosS3Client


class StandposerUploadError(Exception):
    pass


def _cos_client():
    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    return CosS3Client(config)


def cos_download_url(key: str, fallback_url: str = "") -> str:
    if not key:
        return fallback_url
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        return fallback_url
    try:
        return _cos_client().get_presigned_url(
            Method="GET",
            Bucket=settings.COS_BUCKET,
            Key=key,
            Expired=int(getattr(settings, "STANDPOSER_SIGNED_URL_TTL", 3600)),
        )
    except Exception:
        return fallback_url


def upload_to_cos(file_obj, folder: str, allowed_extensions: set[str], allowed_content_types: set[str] | None = None):
    filename = str(getattr(file_obj, "name", "") or "")
    ext = os.path.splitext(filename)[1].lower()
    content_type = str(getattr(file_obj, "content_type", "") or "application/octet-stream")
    size = int(getattr(file_obj, "size", 0) or 0)

    if ext not in allowed_extensions:
        raise StandposerUploadError("文件类型不支持")
    if allowed_content_types and content_type not in allowed_content_types:
        raise StandposerUploadError("文件类型不支持")
    if size <= 0:
        raise StandposerUploadError("文件不能为空")
    if size > int(getattr(settings, "STANDPOSER_MAX_UPLOAD_SIZE", 80 * 1024 * 1024)):
        raise StandposerUploadError("文件超过大小限制")
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise StandposerUploadError("COS配置不完整")

    date_path = datetime.now().strftime("%Y/%m/%d")
    key = f"{folder.strip('/')}/{date_path}/{uuid.uuid4().hex}{ext}"
    client = _cos_client()
    try:
        client.put_object(Bucket=settings.COS_BUCKET, Body=file_obj.file, Key=key, ContentType=content_type)
    except Exception as exc:
        raise StandposerUploadError(f"上传COS失败：{exc}") from exc

    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    return {"url": url, "key": key, "size": size, "content_type": content_type}
