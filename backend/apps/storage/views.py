import os
import uuid
import re
import io
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from qcloud_cos import CosConfig, CosS3Client
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import UploadSerializer
from .models import UploadedFileRecord

ALLOWED_CONTENT_PREFIXES = ("image/", "video/", "audio/")
ALLOWED_FOLDER_PATTERN = re.compile(r"^[a-zA-Z0-9/_-]{1,100}$")


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _compress_image_bytes(raw: bytes, content_type: str):
    try:
        image = Image.open(io.BytesIO(raw))
    except (UnidentifiedImageError, OSError):
        return raw, content_type, ""

    original_format = (image.format or "").upper()
    if original_format == "GIF":
        return raw, content_type, ""

    max_edge = max(int(getattr(settings, "IMAGE_UPLOAD_MAX_EDGE", 2048)), 256)
    quality = min(max(int(getattr(settings, "IMAGE_UPLOAD_QUALITY", 82)), 50), 95)

    image = image.convert("RGB")
    width, height = image.size
    scale = min(max_edge / max(width, 1), max_edge / max(height, 1), 1)
    target_size = (max(int(width * scale), 1), max(int(height * scale), 1))
    if target_size != image.size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)

    target_format = "WEBP" if original_format in ("PNG", "WEBP", "BMP") else "JPEG"
    out = io.BytesIO()
    save_kwargs = {"optimize": True}
    if target_format in ("WEBP", "JPEG"):
        save_kwargs["quality"] = quality
    image.save(out, format=target_format, **save_kwargs)
    compressed = out.getvalue()

    if len(compressed) >= len(raw):
        return raw, content_type, ""

    if target_format == "WEBP":
        return compressed, "image/webp", ".webp"
    return compressed, "image/jpeg", ".jpg"


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def upload(request):
    s = UploadSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    file_obj = s.validated_data["file"]
    folder = s.validated_data.get("folder", "uploads").strip("/") or "uploads"
    if not ALLOWED_FOLDER_PATTERN.match(folder):
        return bad("目录格式不合法")

    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return bad("文件超过大小限制（最大10MB）", 413)

    content_type = file_obj.content_type or "application/octet-stream"
    if not any(content_type.startswith(prefix) for prefix in ALLOWED_CONTENT_PREFIXES):
        return bad("仅支持图片、视频或音频文件上传", 415)

    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        return bad("COS配置不完整", 500)

    date_path = datetime.now().strftime("%Y/%m/%d")
    ext = os.path.splitext(file_obj.name)[1].lower()
    body = file_obj.file
    final_size = file_obj.size
    final_content_type = content_type
    if content_type.startswith("image/"):
        raw = file_obj.read()
        file_obj.seek(0)
        compressed, final_content_type, new_ext = _compress_image_bytes(raw, content_type)
        body = compressed
        final_size = len(compressed)
        if new_ext:
            ext = new_ext

    key = f"{folder}/{date_path}/{uuid.uuid4().hex}{ext}"

    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Body=body,
        Key=key,
        ContentType=final_content_type,
    )

    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"

    UploadedFileRecord.objects.create(
        user=request.user,
        key=key,
        url=url,
        content_type=final_content_type,
        size=final_size,
    )
    return ok({
        "url": url,
        "key": key,
        "content_type": final_content_type,
        "size": final_size,
    })
