import uuid
import io
import base64
import random
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
from PIL import Image, ImageDraw, ImageFilter
from .serializers import (
    EmailCodeSerializer,
    RegisterSerializer,
    LoginSerializer,
    EnergySliderVerifySerializer,
    ProfileUpdateSerializer,
    ResetPasswordSerializer,
)
from .utils import valid_com_email, valid_password, gen_numeric_code, gen_captcha_text, captcha_base64

User = get_user_model()
ENERGY_SLIDER_TTL = 120
ENERGY_SLIDER_PIECE = 44
ENERGY_SLIDER_W = 320
ENERGY_SLIDER_H = 160
DEFAULT_AVATAR = getattr(settings, "DEFAULT_AVATAR_URL", "")


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "unknown")


def _cache_get(key):
    return cache.get(key)


def _cache_set(key, value, ttl):
    cache.set(key, value, ttl)


def _cache_delete(key):
    cache.delete(key)


def _encode_png(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _build_energy_slider_image():
    bg = Image.new("RGB", (ENERGY_SLIDER_W, ENERGY_SLIDER_H), "#0f1832")
    draw = ImageDraw.Draw(bg)

    # Background gradients and anime-like energy particles
    for i in range(ENERGY_SLIDER_H):
        t = i / max(ENERGY_SLIDER_H - 1, 1)
        r = int(26 + 16 * t)
        g = int(37 + 36 * t)
        b = int(78 + 72 * t)
        draw.line([(0, i), (ENERGY_SLIDER_W, i)], fill=(r, g, b))
    for _ in range(22):
        px = random.randint(0, ENERGY_SLIDER_W - 1)
        py = random.randint(0, ENERGY_SLIDER_H - 1)
        radius = random.randint(1, 3)
        glow = random.choice([(84, 205, 255), (182, 110, 255), (255, 184, 99)])
        draw.ellipse([px - radius, py - radius, px + radius, py + radius], fill=glow)
    for _ in range(3):
        x1 = random.randint(0, ENERGY_SLIDER_W // 2)
        x2 = random.randint(ENERGY_SLIDER_W // 2, ENERGY_SLIDER_W)
        y1 = random.randint(0, ENERGY_SLIDER_H)
        y2 = random.randint(0, ENERGY_SLIDER_H)
        draw.line([(x1, y1), (x2, y2)], fill=(132, 215, 255), width=1)

    x = random.randint(86, 240)
    y = random.randint(34, 92)
    size = ENERGY_SLIDER_PIECE

    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([0, 0, size - 1, size - 1], radius=10, fill=255)

    # Piece and hole
    piece = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    piece.paste(bg.crop((x, y, x + size, y + size)), (0, 0), mask)
    piece = piece.filter(ImageFilter.SHARPEN)

    hole = Image.new("RGBA", (size, size), (98, 160, 255, 165))
    bg_hole = bg.convert("RGBA")
    bg_hole.paste(hole, (x, y), mask)
    hd = ImageDraw.Draw(bg_hole)
    hd.rounded_rectangle([x, y, x + size - 1, y + size - 1], radius=10, outline=(225, 247, 255, 220), width=2)

    return {
        "x": x,
        "y": y,
        "bg": _encode_png(bg_hole),
        "piece": _encode_png(piece),
        "width": ENERGY_SLIDER_W,
        "height": ENERGY_SLIDER_H,
        "piece_size": size,
    }


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


@api_view(["GET"])
@permission_classes([AllowAny])
def captcha(request):
    captcha_id = uuid.uuid4().hex
    code = gen_captcha_text(4)
    image = captcha_base64(code)
    _cache_set(f"captcha:{captcha_id}", code.lower(), 120)
    return ok({"captcha_id": captcha_id, "image_base64": image})


@api_view(["GET"])
@permission_classes([AllowAny])
def energy_slider(request):
    token = uuid.uuid4().hex
    payload = _build_energy_slider_image()
    _cache_set(
        f"energy_slider:{token}",
        {"x": payload["x"], "created_ts": timezone.now().timestamp(), "fail_count": 0},
        ENERGY_SLIDER_TTL,
    )
    return ok(
        {
            "token": token,
            "bg": payload["bg"],
            "piece": payload["piece"],
            "y": payload["y"],
            "width": payload["width"],
            "height": payload["height"],
            "piece_size": payload["piece_size"],
            "expires_in": ENERGY_SLIDER_TTL,
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def energy_slider_verify(request):
    s = EnergySliderVerifySerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    token = s.validated_data["token"]
    offset_x = s.validated_data["offset_x"]
    track = s.validated_data.get("track") or []
    slider_data = _cache_get(f"energy_slider:{token}")
    if not slider_data:
        return bad("验证码已过期，请刷新", 400)

    target_x = int(slider_data.get("x", -1))
    created_ts = float(slider_data.get("created_ts", 0))
    fail_count = int(slider_data.get("fail_count", 0))

    if abs(offset_x - target_x) > 6:
        fail_count += 1
        slider_data["fail_count"] = fail_count
        _cache_set(f"energy_slider:{token}", slider_data, ENERGY_SLIDER_TTL)
        if fail_count >= 5:
            _cache_delete(f"energy_slider:{token}")
            return bad("尝试次数过多，请刷新验证码", 429)
        return bad("能量偏移，结界未闭合", 400)

    # Simple anti-bot checks based on interaction duration/track points.
    elapsed_ms = max(int((timezone.now().timestamp() - created_ts) * 1000), 0)
    if elapsed_ms < 350:
        return bad("验证过快，请重试", 400)
    if track and len(track) < 6:
        return bad("轨迹异常，请重试", 400)

    ticket = uuid.uuid4().hex
    _cache_set(f"energy_ticket:{ticket}", "1", ENERGY_SLIDER_TTL)
    _cache_delete(f"energy_slider:{token}")
    return ok({"captcha_ticket": ticket, "expires_in": ENERGY_SLIDER_TTL})


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    s = LoginSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    account = s.validated_data["username"].strip()
    password = s.validated_data["password"]
    username = account
    if "@" in account:
        u = User.objects.filter(email=account.lower()).only("username").first()
        if u:
            username = u.username

    user = authenticate(request, username=username, password=password)
    if not user:
        return bad("用户名/邮箱或密码错误", 401)

    login(request, user)
    return ok(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url or DEFAULT_AVATAR,
                "signature": user.signature or "",
            }
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user
    return ok(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url or DEFAULT_AVATAR,
                "signature": user.signature or "",
            }
        }
    )


@csrf_exempt
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def profile_update(request):
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

    if "email" in payload:
        email = payload["email"].strip().lower()
        if not valid_com_email(email):
            return bad("邮箱必须以.com结尾")
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            return bad("邮箱已存在")
        user.email = email

    if "avatar_url" in payload:
        user.avatar_url = payload.get("avatar_url", "").strip()
    if "signature" in payload:
        user.signature = payload.get("signature", "").strip()

    user.save()
    return ok(
        {
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url or DEFAULT_AVATAR,
                "signature": user.signature or "",
            }
        }
    )


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
