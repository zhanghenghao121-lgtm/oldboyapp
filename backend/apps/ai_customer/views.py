import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.ai_image_services import (
    AIImageError,
    get_ai_image_task_result,
    prepare_ai_image_references,
    submit_ai_image_generation,
)
from apps.ai_customer.cutout_services import (
    CutoutError,
    cutout_character,
    get_cutout_asset,
    list_sticker_assets,
    remove_sticker_asset,
)
from apps.ai_customer.models import StoryboardProject, StorySegment
from apps.ai_customer.runtime_config import (
    get_ai_image_configs,
    get_ai_image_reverse_prompt,
    get_storyboard_llm_configs,
)
from apps.ai_customer.storyboard_services import (
    StoryboardError,
    analyze_project,
    compose_grid,
    create_project,
    generate_panel_images,
    generate_panels,
    refresh_panel_images,
    save_asset,
    serialize_project,
    serialize_segment,
)


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _feature_allowed(request):
    user = request.user
    return bool(user and user.is_authenticated and (user.is_whitelisted or user.is_staff or user.is_superuser))


def _feature_denied():
    return bad("当前账号未加入功能白名单，请联系管理员开通", 403)


def _serialize_model_option(option_id: str, label: str, runtime: dict):
    return {
        "id": option_id,
        "label": label,
        "model": str(runtime.get("model") or "").strip(),
        "base_url": str(runtime.get("base_url") or "").strip(),
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def storyboard_config(request):
    if not _feature_allowed(request):
        return _feature_denied()
    return ok(
        {
            "default_analysis_model": "deepseek-v4-pro",
            "default_image_model": "gpt-image-2",
            "analysis_models": [
                _serialize_model_option(item["id"], item["label"], item)
                for item in get_storyboard_llm_configs()
            ],
            "image_models": [
                {"id": item["id"], "label": item["label"], "model": item["model"]}
                for item in get_ai_image_configs()
            ],
            "style_options": ["电影写实", "3D动漫", "国风水墨", "赛博朋克"],
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_image_config(request):
    if not _feature_allowed(request):
        return _feature_denied()
    image_configs = get_ai_image_configs()
    image_config = image_configs[0]
    return ok(
        {
            "default_model": image_config.get("model") or "gpt-image-2",
            "default_size": "16:9",
            "default_resolution": "1k",
            "default_n": 1,
            "reverse_prompt": get_ai_image_reverse_prompt(),
            "model_options": [
                {
                    "id": item.get("id") or item.get("model"),
                    "label": item.get("label") or item.get("model"),
                    "model": item.get("model"),
                    "provider": item.get("provider"),
                }
                for item in image_configs
            ],
            "size_options": [
                "16:9",
                "9:16",
                "1:1",
                "4:3",
                "3:4",
                "3:2",
                "2:3",
                "21:9",
            ],
            "resolution_options": ["1k", "2k", "4k"],
        }
    )


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_image_generate(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        mode = str(request.data.get("mode", "text") or "text").strip().lower()
        try:
            object_names = json.loads(str(request.data.get("object_names", "[]") or "[]"))
        except Exception:
            object_names = []
        if not isinstance(object_names, list):
            object_names = []
        object_names = [str(item or "").strip() for item in object_names]
        references = prepare_ai_image_references(request.FILES, object_names=object_names)
        result = submit_ai_image_generation(
            mode=mode,
            prompt=str(request.data.get("prompt", "") or ""),
            model=str(request.data.get("model", "") or ""),
            size=str(request.data.get("size", "16:9") or "16:9"),
            resolution=str(request.data.get("resolution", "1k") or "1k"),
            reference_images=references,
        )
        return ok(result)
    except AIImageError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_image_task(request, task_id):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        return ok(get_ai_image_task_result(task_id))
    except AIImageError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_image_cutout(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        return ok(
            cutout_character(
                request.FILES.get("file"),
                str(request.data.get("mode", "fast") or "fast"),
                request.user,
                save_to_library=str(request.data.get("save_to_library", "") or "").strip().lower() in {"1", "true", "yes", "on"},
            )
        )
    except CutoutError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_image_cutout_asset(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        content = get_cutout_asset(request.query_params.get("key", ""), request.user)
        return HttpResponse(content, content_type="image/png")
    except CutoutError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_image_cutout_assets(request):
    if not _feature_allowed(request):
        return _feature_denied()
    return ok({"list": list_sticker_assets(request.user)})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def ai_image_cutout_asset_delete(request, asset_id):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        remove_sticker_asset(asset_id, request.user)
        return ok()
    except CutoutError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def storyboard_projects(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        if request.method == "GET":
            projects = StoryboardProject.objects.filter(user=request.user)[:30]
            return ok({"list": [serialize_project(project) for project in projects]})
        project = create_project(request.user, request.data)
        return ok(serialize_project(project))
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_project_analyze(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = StoryboardProject.objects.filter(id=project_id, user=request.user).first()
    if not project:
        return bad("故事板项目不存在", 404)
    try:
        return ok(analyze_project(project))
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def storyboard_project_segments(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = StoryboardProject.objects.filter(id=project_id, user=request.user).first()
    if not project:
        return bad("故事板项目不存在", 404)
    roots = project.segments.filter(parent__isnull=True).prefetch_related("children", "assets", "panels")
    return ok({"project": serialize_project(project), "segments": [serialize_segment(segment) for segment in roots]})


def _owned_segment(request, segment_id):
    return StorySegment.objects.filter(id=segment_id, project__user=request.user).select_related("project").first()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def storyboard_segment_assets_required(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    return ok({"required_assets": segment.required_assets_json, "assets": [asset for asset in serialize_segment(segment, False)["assets"]]})


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_segment_assets(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok(save_asset(segment, request.data))
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_segment_generate_panels(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok({"panels": generate_panels(segment)})
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_segment_generate_images(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok({"panels": generate_panel_images(segment, str(request.data.get("model") or ""))})
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def storyboard_segment_refresh_images(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok({"panels": refresh_panel_images(segment)})
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_segment_compose_grid(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok({"grid_image_url": compose_grid(segment, request.user)})
    except StoryboardError as exc:
        return bad(str(exc), exc.status)
