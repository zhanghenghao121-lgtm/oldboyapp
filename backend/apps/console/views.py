from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.views.decorators.csrf import csrf_exempt
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
)
from apps.ai_customer.runtime_config import (
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
