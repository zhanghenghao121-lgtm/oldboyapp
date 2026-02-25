import os
import uuid
from datetime import datetime
from qcloud_cos import CosConfig, CosS3Client
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import UploadSerializer
from .models import UploadedFileRecord


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def upload(request):
    s = UploadSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    file_obj = s.validated_data["file"]
    folder = s.validated_data.get("folder", "uploads").strip("/") or "uploads"

    if file_obj.size > settings.MAX_UPLOAD_SIZE:
        return bad("文件超过大小限制", 413)

    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        return bad("COS配置不完整", 500)

    date_path = datetime.now().strftime("%Y/%m/%d")
    ext = os.path.splitext(file_obj.name)[1]
    key = f"{folder}/{date_path}/{uuid.uuid4().hex}{ext}"

    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    client.put_object(
        Bucket=settings.COS_BUCKET,
        Body=file_obj.file,
        Key=key,
        ContentType=file_obj.content_type or "application/octet-stream",
    )

    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"

    UploadedFileRecord.objects.create(
        user=request.user,
        key=key,
        url=url,
        content_type=file_obj.content_type or "application/octet-stream",
        size=file_obj.size,
    )
    return ok({
        "url": url,
        "key": key,
        "content_type": file_obj.content_type or "application/octet-stream",
        "size": file_obj.size,
    })
