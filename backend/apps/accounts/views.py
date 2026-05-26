from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django_redis import get_redis_connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import PointsUsageLog
from .serializers import (
    EmailCodeSerializer,
    RegisterSerializer,
    LoginSerializer,
    ProfileUpdateSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
)
from .utils import valid_com_email, valid_password, gen_numeric_code

User = get_user_model()
DEFAULT_AVATAR = getattr(settings, "DEFAULT_AVATAR_URL", "")


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _user_payload(user):
    feature_allowed = bool(user.is_whitelisted or user.is_staff or user.is_superuser)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": user.avatar_url or DEFAULT_AVATAR,
        "signature": user.signature or "",
        "points": float(user.points or 0),
        "is_whitelisted": bool(user.is_whitelisted),
        "is_staff": bool(user.is_staff),
        "is_superuser": bool(user.is_superuser),
        "feature_allowed": feature_allowed,
    }


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "unknown")


def _cache_get(key):
    return cache.get(key)


def _cache_set(key, value, ttl):
    cache.set(key, value, ttl)


def _cache_delete(key):
    cache.delete(key)


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def email_code(request):
    s = EmailCodeSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")
    email = s.validated_data["email"].lower()
    scene = s.validated_data["scene"]
    username = s.validated_data.get("username", "").strip()

    if not valid_com_email(email):
        return bad("邮箱必须以.com结尾")

    exists = User.objects.filter(email=email).exists()
    if scene == "register" and exists:
        return bad("邮箱已注册")
    if scene == "reset" and not exists:
        return bad("邮箱不存在")
    if scene == "register":
        if not username:
            return bad("注册场景下必须提供用户名")
        if User.objects.filter(username=username).exists():
            return bad("用户名已存在")

    ip = _client_ip(request)
    if _cache_get(f"email_rate:{email}"):
        return bad("发送过于频繁，请60秒后再试", 429)
    if _cache_get(f"ip_rate:{ip}"):
        return bad("请求过于频繁，请稍后重试", 429)

    daily_key = f"email_daily:{timezone.now().strftime('%Y%m%d')}:{email}"
    try:
        r = get_redis_connection("default")
        daily_count = int(r.get(daily_key) or 0)
        if daily_count >= settings.EMAIL_CODE_DAILY_LIMIT:
            return bad("今日发送次数已达上限", 429)
    except Exception:
        daily_count = 0

    code = gen_numeric_code()
    _cache_set(f"email_code:{scene}:{email}", code, 300)
    if scene == "register":
        _cache_set(f"email_bind:register:{email}", username, 300)
    _cache_set(f"email_rate:{email}", "1", 60)
    _cache_set(f"ip_rate:{ip}", "1", 60)

    try:
        r = get_redis_connection("default")
        r.incr(daily_key)
        r.expire(daily_key, 86400)
    except Exception:
        pass

    send_mail(
        subject="OldboyApp 验证码",
        message=f"您的验证码是：{code}，5分钟内有效。",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    return ok()


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    s = RegisterSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")
    username = s.validated_data["username"].strip()
    password = s.validated_data["password"]
    email = s.validated_data["email"].lower()
    email_code = s.validated_data["email_code"].strip()

    if not valid_com_email(email):
        return bad("邮箱必须以.com结尾")
    if not valid_password(password):
        return bad("密码必须至少8位，且包含大小写字母和数字")
    if User.objects.filter(username=username).exists():
        return bad("用户名已存在")
    if User.objects.filter(email=email).exists():
        return bad("邮箱已存在")

    code = _cache_get(f"email_code:register:{email}")
    if not code or str(code).lower() != email_code.lower():
        return bad("邮箱验证码错误或已过期")
    bind_username = _cache_get(f"email_bind:register:{email}")
    if not bind_username or str(bind_username) != username:
        return bad("邮箱验证码与用户名不匹配，请重新获取验证码")

    User.objects.create_user(username=username, email=email, password=password, avatar_url=DEFAULT_AVATAR)
    _cache_delete(f"email_code:register:{email}")
    _cache_delete(f"email_bind:register:{email}")
    return ok()


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    s = LoginSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    account = s.validated_data["username"].strip()
    password = s.validated_data["password"]
    ip = _client_ip(request)
    login_limit_key = f"login_limit:{ip}:{account.lower()}"
    attempts = int(_cache_get(login_limit_key) or 0)
    if attempts >= 8:
        return bad("登录尝试过于频繁，请稍后再试", 429)

    username = account
    if "@" in account:
        bind_user = User.objects.filter(email__iexact=account).only("username").first()
        if bind_user:
            username = bind_user.username

    user = authenticate(request, username=username, password=password)
    if not user:
        _cache_set(login_limit_key, attempts + 1, 300)
        return bad("用户名/邮箱或密码错误", 401)

    _cache_delete(login_limit_key)
    login(request, user)
    return ok({"user": _user_payload(user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return ok({"user": _user_payload(user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def points_logs(request):
    rows = PointsUsageLog.objects.filter(user=request.user).order_by("-id")[:100]
    data = [
        {
            "id": row.id,
            "usage_type": row.usage_type,
            "amount": float(row.amount),
            "balance_after": float(row.balance_after),
            "description": row.description,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return ok({"list": data})


@csrf_exempt
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def profile_update(request):
    if "email" in request.data:
        return bad("用户邮箱不可修改")

    s = ProfileUpdateSerializer(data=request.data, partial=True)
    if not s.is_valid():
        errors = s.errors
        first_error = next(iter(errors.values()))[0] if errors else "参数错误"
        return bad(first_error)

    user = request.user
    payload = s.validated_data
    if not payload:
        return bad("没有可更新字段")

    if "username" in payload:
        username = payload["username"].strip()
        if User.objects.filter(username=username).exclude(id=user.id).exists():
            return bad("用户名已存在")
        user.username = username

    if "avatar_url" in payload:
        user.avatar_url = payload.get("avatar_url", "").strip()
    if "signature" in payload:
        user.signature = payload.get("signature", "").strip()

    user.save()
    return ok({"user": _user_payload(user)})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def logout_view(request):
    logout(request)
    return ok()


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    s = ResetPasswordSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")
    email = s.validated_data["email"].lower()
    email_code = s.validated_data["email_code"].strip()
    new_password = s.validated_data["new_password"]

    if not valid_com_email(email):
        return bad("邮箱必须以.com结尾")
    if not valid_password(new_password):
        return bad("密码必须至少8位，且包含大小写字母和数字")

    code = _cache_get(f"email_code:reset:{email}")
    if not code or str(code).lower() != email_code.lower():
        return bad("邮箱验证码错误或已过期")

    user = User.objects.filter(email=email).first()
    if not user:
        return bad("邮箱不存在")
    user.set_password(new_password)
    user.save(update_fields=["password"])
    _cache_delete(f"email_code:reset:{email}")
    return ok()


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    s = ChangePasswordSerializer(data=request.data)
    if not s.is_valid():
        errors = s.errors
        first_error = next(iter(errors.values()))[0] if errors else "参数错误"
        return bad(first_error)

    user = request.user
    email = (user.email or "").lower().strip()
    if not email:
        return bad("当前账号未绑定邮箱")
    if not valid_com_email(email):
        return bad("邮箱必须以.com结尾")

    email_code = s.validated_data["email_code"].strip()
    new_password = s.validated_data["new_password"]
    confirm_password = s.validated_data["confirm_password"]
    if new_password != confirm_password:
        return bad("两次输入的新密码不一致")
    if not valid_password(new_password):
        return bad("密码必须至少8位，且包含大小写字母和数字")

    code = _cache_get(f"email_code:reset:{email}")
    if not code or str(code).lower() != email_code.lower():
        return bad("邮箱验证码错误或已过期")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    _cache_delete(f"email_code:reset:{email}")
    logout(request)
    return ok()
