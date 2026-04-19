from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from qcloud_cos import CosConfig, CosS3Client
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.console.auth import issue_console_token, resolve_console_user, revoke_console_token
from apps.console.models import SiteConfig
from apps.console.permissions import IsConsoleAdmin
from apps.console.serializers import (
    ConsoleLoginSerializer,
    SiteConfigSerializer,
    SiteConfigUpdateSerializer,
    ConsoleUserSerializer,
    ConsoleUserUpdateSerializer,
)
from apps.storage.models import UploadedFileRecord

User = get_user_model()


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _safe_int(raw, default, minimum=None, maximum=None):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def _config_defaults():
    return {
        SiteConfig.KEY_DEFAULT_AVATAR: getattr(settings, "DEFAULT_AVATAR_URL", "/octopus-avatar.svg") or "/octopus-avatar.svg",
        SiteConfig.KEY_RECHARGE_WECHAT: "Dsdfcc2000",
        SiteConfig.KEY_RECHARGE_QR_URL: "",
        SiteConfig.KEY_AI_ASSISTANT_BASE_URL: getattr(settings, "AI_CS_LLM_BASE_URL", ""),
        SiteConfig.KEY_AI_ASSISTANT_API_KEY: getattr(settings, "AI_CS_LLM_API_KEY", ""),
        SiteConfig.KEY_AI_ASSISTANT_MODEL: getattr(settings, "AI_CS_LLM_MODEL", ""),
        SiteConfig.KEY_AI_MANGA_BASE_URL: getattr(settings, "AI_CS_LLM_BASE_URL", ""),
        SiteConfig.KEY_AI_MANGA_API_KEY: getattr(settings, "AI_CS_LLM_API_KEY", ""),
        SiteConfig.KEY_AI_MANGA_MODEL: getattr(settings, "AI_CS_LLM_MODEL", ""),
        SiteConfig.KEY_AI_MANGA_STORYBOARD_PROMPT: (
            "你是专业的漫画导演与分镜编剧。请把输入内容整理为适合 AI 漫剧创作的分镜稿，"
            "按“第1镜、第2镜...”输出，每个分镜至少包含：场景、景别/镜头、画面内容、人物动作/表情、台词/旁白、画面提示词。"
        ),
    }


def _ensure_config_defaults():
    defaults = _config_defaults()
    for key, value in defaults.items():
        obj, _ = SiteConfig.objects.get_or_create(key=key, defaults={"value": value})
        if not (obj.value or "").strip():
            obj.value = value
            obj.save(update_fields=["value", "updated_at"])


def _get_admin_user(request):
    user = getattr(request, "console_user", None)
    if user:
        return user
    user, _ = resolve_console_user(request)
    return user


def _resolve_uploaded_file_key(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    record = UploadedFileRecord.objects.filter(url=url).order_by("-id").first()
    if record and record.key:
        return str(record.key).strip()
    parsed = urlparse(url)
    return parsed.path.lstrip("/")


def _build_signed_file_url(raw_url: str) -> str:
    url = str(raw_url or "").strip()
    if not url:
        return ""
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        return url
    key = _resolve_uploaded_file_key(url)
    if not key:
        return url
    try:
        config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
        client = CosS3Client(config)
        signed = client.get_presigned_url(
            Method="GET",
            Bucket=settings.COS_BUCKET,
            Key=key,
            Expired=max(int(getattr(settings, "RECHARGE_QR_SIGN_EXPIRE", 3600)), 300),
        )
        return signed or url
    except Exception:
        return url


@api_view(["GET"])
@permission_classes([AllowAny])
def public_backgrounds(request):
    _ensure_config_defaults()
    configs = {item.key: item.value for item in SiteConfig.objects.all()}
    config_latest = max((item.updated_at for item in SiteConfig.objects.all()), default=None)
    data = {"_version": int(config_latest.timestamp()) if config_latest else 0}
    data["default_avatar"] = (
        configs.get(SiteConfig.KEY_DEFAULT_AVATAR) or _config_defaults()[SiteConfig.KEY_DEFAULT_AVATAR]
    )
    data["recharge_wechat_id"] = configs.get(
        SiteConfig.KEY_RECHARGE_WECHAT, _config_defaults()[SiteConfig.KEY_RECHARGE_WECHAT]
    )
    data["recharge_qr_url"] = _build_signed_file_url(
        configs.get(SiteConfig.KEY_RECHARGE_QR_URL, _config_defaults()[SiteConfig.KEY_RECHARGE_QR_URL])
    )
    res = ok(data)
    res["Cache-Control"] = "no-store"
    return res


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def console_login(request):
    s = ConsoleLoginSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    user = authenticate(
        request,
        username=s.validated_data["username"].strip(),
        password=s.validated_data["password"],
    )
    if not user:
        return bad("用户名或密码错误", 401)
    if not user.is_staff:
        return bad("无后台访问权限", 403)

    token = issue_console_token(user.id)
    return ok({"token": token, "user": {"id": user.id, "username": user.username, "email": user.email}})


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_me(request):
    user = _get_admin_user(request)
    if not user:
        return bad("未登录或无权限", 401)
    return ok({"user": {"id": user.id, "username": user.username, "email": user.email}})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def console_logout(request):
    _, token = resolve_console_user(request)
    revoke_console_token(token)
    return ok()


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_configs(request):
    _ensure_config_defaults()
    rows = []
    for item in SiteConfig.objects.all():
        value = item.value
        if item.key == SiteConfig.KEY_RECHARGE_QR_URL:
            value = _build_signed_file_url(value)
        rows.append({"key": item.key, "value": value, "updated_at": item.updated_at})
    return ok(rows)


@csrf_exempt
@api_view(["PUT"])
@permission_classes([IsConsoleAdmin])
def console_config_update(request, key):
    valid_keys = [item[0] for item in SiteConfig.KEY_CHOICES]
    if key not in valid_keys:
        return bad("配置项不支持", 404)

    s = SiteConfigUpdateSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    admin_user = _get_admin_user(request)
    obj, _ = SiteConfig.objects.get_or_create(key=key, defaults={"value": _config_defaults().get(key, "")})
    obj.value = s.validated_data["value"]
    obj.updated_by = admin_user
    obj.save(update_fields=["value", "updated_by", "updated_at"])
    return ok(SiteConfigSerializer(obj).data)


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_users(request):
    keyword = request.query_params.get("keyword", "").strip()
    page = _safe_int(request.query_params.get("page", 1), 1, minimum=1)
    page_size = _safe_int(request.query_params.get("page_size", 10), 10, minimum=1, maximum=100)

    qs = User.objects.all().order_by("-date_joined")
    if keyword:
        qs = qs.filter(Q(username__icontains=keyword) | Q(email__icontains=keyword))

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)
    data = {
        "list": ConsoleUserSerializer(page_obj.object_list, many=True).data,
        "total": paginator.count,
        "page": page_obj.number,
        "page_size": page_size,
    }
    return ok(data)


@csrf_exempt
@api_view(["PATCH"])
@permission_classes([IsConsoleAdmin])
def console_user_update(request, user_id):
    user = User.objects.filter(id=user_id).first()
    if not user:
        return bad("用户不存在", 404)

    s = ConsoleUserUpdateSerializer(data=request.data, context={"user_id": user.id}, partial=True)
    if not s.is_valid():
        errors = s.errors
        first_error = next(iter(errors.values()))[0] if errors else "参数错误"
        return bad(first_error)

    payload = s.validated_data
    if not payload:
        return bad("没有可更新字段")

    admin_user = _get_admin_user(request)
    if admin_user and user.id == admin_user.id and payload.get("is_active") is False:
        return bad("不能停用当前登录管理员")

    for key, value in payload.items():
        setattr(user, key, value)
    user.save(update_fields=list(payload.keys()))
    return ok(ConsoleUserSerializer(user).data)
