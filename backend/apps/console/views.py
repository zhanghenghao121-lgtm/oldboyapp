from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.console.models import SiteBackground
from apps.console.permissions import IsConsoleAdmin
from apps.console.serializers import (
    BackgroundUpdateSerializer,
    ConsoleLoginSerializer,
    ConsoleUserSerializer,
    ConsoleUserUpdateSerializer,
    SiteBackgroundSerializer,
)

User = get_user_model()


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _ensure_scene_defaults():
    for scene, _ in SiteBackground.SCENE_CHOICES:
        SiteBackground.objects.get_or_create(scene=scene)


@api_view(["GET"])
@permission_classes([AllowAny])
def public_backgrounds(request):
    _ensure_scene_defaults()
    scene_map = {item.scene: item.image_url for item in SiteBackground.objects.all()}
    return ok(scene_map)


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

    login(request, user)
    return ok({"user": {"id": user.id, "username": user.username, "email": user.email}})


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_me(request):
    user = request.user
    return ok({"user": {"id": user.id, "username": user.username, "email": user.email}})


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsConsoleAdmin])
def console_logout(request):
    logout(request)
    return ok()


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_backgrounds(request):
    _ensure_scene_defaults()
    serializer = SiteBackgroundSerializer(SiteBackground.objects.all(), many=True)
    return ok(serializer.data)


@csrf_exempt
@api_view(["PUT"])
@permission_classes([IsConsoleAdmin])
def console_background_update(request, scene):
    if scene not in [item[0] for item in SiteBackground.SCENE_CHOICES]:
        return bad("场景不支持", 404)

    s = BackgroundUpdateSerializer(data=request.data)
    if not s.is_valid():
        return bad("参数错误")

    obj, _ = SiteBackground.objects.get_or_create(scene=scene)
    obj.image_url = s.validated_data["image_url"]
    obj.updated_by = request.user
    obj.save(update_fields=["image_url", "updated_by", "updated_at"])
    return ok(SiteBackgroundSerializer(obj).data)


@api_view(["GET"])
@permission_classes([IsConsoleAdmin])
def console_users(request):
    keyword = request.query_params.get("keyword", "").strip()
    page = max(int(request.query_params.get("page", 1)), 1)
    page_size = min(max(int(request.query_params.get("page_size", 10)), 1), 100)

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

    if user.id == request.user.id and payload.get("is_active") is False:
        return bad("不能停用当前登录管理员")

    for key, value in payload.items():
        setattr(user, key, value)
    user.save(update_fields=list(payload.keys()))
    return ok(ConsoleUserSerializer(user).data)
