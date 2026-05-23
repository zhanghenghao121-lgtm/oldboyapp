from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.console.auth import issue_console_token, resolve_console_user, revoke_console_token
from apps.console.models import SiteConfig
from apps.console.permissions import IsConsoleAdmin
from apps.console.serializers import (
    ConsoleLoginSerializer,
    ConsoleUserUpdateSerializer,
    SiteConfigSerializer,
    SiteConfigUpdateSerializer,
)
from apps.ai_customer.runtime_config import (
    DEFAULT_AI_IMAGE_REVERSE_PROMPT,
    DEFAULT_MANGA_3D_STYLE_PROMPT,
    DEFAULT_MANGA_REAL_STYLE_PROMPT,
    DEFAULT_MANGA_STORYBOARD_PROMPT,
)

User = get_user_model()


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _config_defaults():
    return {
        SiteConfig.KEY_DEFAULT_AVATAR: getattr(settings, "DEFAULT_AVATAR_URL", "/octopus-avatar.svg") or "/octopus-avatar.svg",
        SiteConfig.KEY_AI_ASSISTANT_BASE_URL: getattr(settings, "AI_CS_LLM_BASE_URL", ""),
        SiteConfig.KEY_AI_ASSISTANT_API_KEY: getattr(settings, "AI_CS_LLM_API_KEY", ""),
        SiteConfig.KEY_AI_ASSISTANT_MODEL: getattr(settings, "AI_CS_LLM_MODEL", ""),
        SiteConfig.KEY_AI_MANGA_BASE_URL: getattr(settings, "AI_CS_LLM_BASE_URL", ""),
        SiteConfig.KEY_AI_MANGA_API_KEY: getattr(settings, "AI_CS_LLM_API_KEY", ""),
        SiteConfig.KEY_AI_MANGA_MODEL: getattr(settings, "AI_CS_LLM_MODEL", ""),
        SiteConfig.KEY_AI_MANGA_VISION_BASE_URL: "https://ark.cn-beijing.volces.com/api/v3",
        SiteConfig.KEY_AI_MANGA_VISION_API_KEY: "",
        SiteConfig.KEY_AI_MANGA_VISION_MODEL: "doubao-seed-2-0-mini-260428",
        SiteConfig.KEY_AI_IMAGE_BASE_URL: "https://api.apimart.ai/v1",
        SiteConfig.KEY_AI_IMAGE_API_KEY: "",
        SiteConfig.KEY_AI_IMAGE_MODEL: "gpt-image-2",
        SiteConfig.KEY_AI_IMAGE_REVERSE_PROMPT: DEFAULT_AI_IMAGE_REVERSE_PROMPT,
        SiteConfig.KEY_AI_MANGA_STORYBOARD_PROMPT: DEFAULT_MANGA_STORYBOARD_PROMPT,
        SiteConfig.KEY_AI_MANGA_3D_STYLE_PROMPT: DEFAULT_MANGA_3D_STYLE_PROMPT,
        SiteConfig.KEY_AI_MANGA_REAL_STYLE_PROMPT: DEFAULT_MANGA_REAL_STYLE_PROMPT,
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


def _serialize_console_user(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": user.avatar_url or "",
        "signature": user.signature or "",
        "points": float(user.points or 0),
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login,
        "date_joined": user.date_joined,
    }


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
        rows.append({"key": item.key, "value": item.value, "updated_at": item.updated_at})
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
    q = str(request.query_params.get("q", "") or "").strip()
    queryset = User.objects.all().order_by("-id")
    if q:
        queryset = queryset.filter(Q(username__icontains=q) | Q(email__icontains=q)).order_by("-id")
    users = queryset[:200]
    return ok({"list": [_serialize_console_user(user) for user in users]})


@csrf_exempt
@api_view(["PATCH"])
@permission_classes([IsConsoleAdmin])
def console_user_update(request, user_id):
    target = User.objects.filter(id=user_id).first()
    if not target:
        return bad("用户不存在", 404)

    s = ConsoleUserUpdateSerializer(data=request.data, partial=True)
    if not s.is_valid():
        errors = s.errors
        first_error = next(iter(errors.values()))[0] if errors else "参数错误"
        return bad(first_error)

    payload = s.validated_data
    if not payload:
        return bad("没有可更新字段")

    if "username" in payload:
        username = payload["username"].strip()
        if User.objects.filter(username=username).exclude(id=target.id).exists():
            return bad("用户名已存在")
        target.username = username

    if "email" in payload:
        email = payload["email"].lower().strip()
        if User.objects.filter(email__iexact=email).exclude(id=target.id).exists():
            return bad("邮箱已存在")
        target.email = email

    if "avatar_url" in payload:
        target.avatar_url = payload.get("avatar_url", "").strip()
    if "signature" in payload:
        target.signature = payload.get("signature", "").strip()
    if "points" in payload:
        target.points = payload["points"]
    if "is_active" in payload:
        target.is_active = payload["is_active"]

    target.save()
    return ok({"user": _serialize_console_user(target)})
