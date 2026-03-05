from django.core.cache import cache
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.blogger_services import BloggerError, fetch_hotwords
from apps.ai_customer.blogger_tasks import dispatch_post_generation, dispatch_video_generation
from apps.ai_customer.models import AiBloggerAsset, AiBloggerPost, AiBloggerVideoTask


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _to_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _serialize_asset(asset: AiBloggerAsset):
    return {
        "id": asset.id,
        "type": asset.type,
        "cos_key": asset.cos_key,
        "url": asset.url,
        "meta": asset.meta_json or {},
        "created_at": asset.created_at,
    }


def _serialize_post(post: AiBloggerPost):
    images = post.assets.filter(type=AiBloggerAsset.TYPE_IMAGE).order_by("id")
    return {
        "post_id": post.id,
        "status_text": post.status_text,
        "stage_text": post.stage_text,
        "input_mode": post.input_mode,
        "hot_word": post.hot_word,
        "style_prompt": post.style_prompt,
        "ratio": post.ratio,
        "image_count": post.image_count,
        "title": post.title,
        "copy": post.copy,
        "images": [_serialize_asset(item) for item in images],
        "selected_cover_key": post.selected_cover_key,
        "error_text": post.error_text,
        "created_at": post.created_at,
        "updated_at": post.updated_at,
    }


def _serialize_video_task(task: AiBloggerVideoTask):
    video = _serialize_asset(task.video_asset) if task.video_asset_id else None
    return {
        "video_task_id": task.id,
        "status_video": task.status_video,
        "seedance_task_id": task.seedance_task_id,
        "duration": task.duration,
        "ratio": task.ratio,
        "generate_audio": task.generate_audio,
        "watermark": task.watermark,
        "video": video,
        "error_text": task.error_text,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_blogger_hotwords(request):
    throttle_seconds = max(int(getattr(settings, "AI_BLOGGER_HOTWORDS_MIN_INTERVAL", 10)), 1)
    throttle_key = f"ai_blogger:hotwords:throttle:{request.user.id}"
    if cache.get(throttle_key):
        return bad(f"请求过于频繁，请{throttle_seconds}秒后再试", 429)
    cache.set(throttle_key, 1, throttle_seconds)
    limit = request.query_params.get("limit", 50)
    try:
        limit = max(1, min(int(limit), 100))
    except (TypeError, ValueError):
        limit = 50
    try:
        data = fetch_hotwords(limit=limit, force=False)
        return ok(data)
    except BloggerError as exc:
        return bad(str(exc), exc.status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def ai_blogger_hotwords_refresh(request):
    try:
        data = fetch_hotwords(limit=50, force=True)
        return ok(data)
    except BloggerError as exc:
        return bad(str(exc), exc.status)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def ai_blogger_post_create(request):
    payload = request.data or {}
    input_mode = str(payload.get("input_mode") or "manual").strip().lower()
    hot_word = str(payload.get("hot_word") or "").strip()
    style_prompt = str(payload.get("style_prompt") or "").strip()
    ratio = str(payload.get("ratio") or "9:16").strip()
    image_count = payload.get("image_count", 1)
    try:
        image_count = int(image_count)
    except (TypeError, ValueError):
        image_count = 1
    image_count = max(1, min(image_count, 3))

    if input_mode not in {AiBloggerPost.INPUT_MANUAL, AiBloggerPost.INPUT_AUTO}:
        return bad("input_mode 无效")
    if not hot_word:
        return bad("热点词不能为空")
    if len(hot_word) > 50:
        return bad("热点词不能超过50字")
    if ratio not in {"9:16", "16:9"}:
        ratio = "9:16"

    post = AiBloggerPost.objects.create(
        user=request.user,
        input_mode=input_mode,
        hot_word=hot_word,
        style_prompt=style_prompt[:400],
        ratio=ratio,
        image_count=image_count,
        status_text=AiBloggerPost.STATUS_QUEUED,
        stage_text=AiBloggerPost.STAGE_TITLE,
    )
    dispatch_post_generation(post.id)
    return ok({"post_id": post.id})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_blogger_post_detail(request, post_id: int):
    post = AiBloggerPost.objects.filter(id=post_id, user=request.user).first()
    if not post:
        return bad("任务不存在", 404)
    return ok(_serialize_post(post))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def ai_blogger_select_cover(request, post_id: int):
    post = AiBloggerPost.objects.filter(id=post_id, user=request.user).first()
    if not post:
        return bad("任务不存在", 404)
    cos_key = str((request.data or {}).get("cos_key") or "").strip()
    if not cos_key:
        return bad("cos_key 不能为空")
    asset = post.assets.filter(type=AiBloggerAsset.TYPE_IMAGE, cos_key=cos_key).first()
    if not asset:
        return bad("封面图片不存在", 404)
    post.selected_cover_key = cos_key
    post.save(update_fields=["selected_cover_key", "updated_at"])
    return ok({"post_id": post.id, "selected_cover_key": post.selected_cover_key})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@csrf_exempt
def ai_blogger_video_create(request, post_id: int):
    post = AiBloggerPost.objects.filter(id=post_id, user=request.user).first()
    if not post:
        return bad("任务不存在", 404)
    if post.status_text != AiBloggerPost.STATUS_SUCCESS:
        return bad("图文任务尚未完成，暂不能生成视频")

    payload = request.data or {}
    duration = payload.get("duration", getattr(settings, "DEFAULT_VIDEO_DURATION", 5))
    ratio = str(payload.get("ratio") or getattr(settings, "DEFAULT_VIDEO_RATIO", "adaptive")).strip()
    generate_audio = _to_bool(payload.get("generate_audio"), getattr(settings, "DEFAULT_VIDEO_GENERATE_AUDIO", True))
    watermark = _to_bool(payload.get("watermark"), getattr(settings, "DEFAULT_VIDEO_WATERMARK", False))
    try:
        duration = int(duration)
    except (TypeError, ValueError):
        duration = 5
    duration = max(3, min(duration, 12))
    if ratio not in {"adaptive", "9:16", "16:9", "1:1"}:
        ratio = "adaptive"

    active = post.video_tasks.filter(status_video__in=[AiBloggerVideoTask.STATUS_QUEUED, AiBloggerVideoTask.STATUS_RUNNING]).first()
    if active:
        return ok({"video_task_id": active.id})

    task = AiBloggerVideoTask.objects.create(
        post=post,
        status_video=AiBloggerVideoTask.STATUS_QUEUED,
        duration=duration,
        ratio=ratio,
        generate_audio=generate_audio,
        watermark=watermark,
    )
    dispatch_video_generation(task.id)
    return ok({"video_task_id": task.id})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_blogger_video_detail(request, post_id: int):
    post = AiBloggerPost.objects.filter(id=post_id, user=request.user).first()
    if not post:
        return bad("任务不存在", 404)
    task = post.video_tasks.order_by("-id").first()
    if not task:
        return ok(
            {
                "status_video": "idle",
                "seedance_task_id": "",
                "video": None,
                "error_text": "",
            }
        )
    return ok(_serialize_video_task(task))
