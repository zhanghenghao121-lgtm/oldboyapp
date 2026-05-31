from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.cutout_services import (
    CutoutError,
    cutout_character,
    get_cutout_asset,
    list_sticker_assets,
    remove_sticker_asset,
)
from apps.ai_customer.models import SceneInferenceProject, StoryboardPanel, StoryboardProject, StorySegment
from apps.ai_customer.runtime_config import (
    get_ai_image_configs,
    get_storyboard_llm_configs,
)
from apps.ai_customer.storyboard_services import (
    StoryboardError,
    analyze_project,
    compose_grid,
    create_project,
    delete_asset,
    generate_panel_images,
    generate_panels_and_images,
    generate_video_prompts,
    regenerate_panel,
    refresh_panel_images,
    save_asset,
    serialize_project,
    serialize_segment,
    update_panel,
)
from apps.ai_customer.scene_inference_services import (
    SceneInferenceError,
    create_scene_inference_project,
    enhance_scene_screenshot,
    generate_scene_inference_views,
    generate_scene_panorama,
    refresh_scene_inference_project,
    serialize_scene_inference_project,
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
                {
                    "id": item["id"],
                    "label": item["label"],
                    "model": item["model"],
                    "supports_reference_images": True,
                    "supports_panorama": True,
                }
                for item in get_ai_image_configs()
            ],
            "style_options": ["电影写实", "3D动漫", "国风水墨", "赛博朋克"],
        }
    )


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


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def storyboard_segment_asset_delete(request, segment_id, asset_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        delete_asset(segment, asset_id)
        return ok()
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
        return ok(
            {
                "panels": generate_panels_and_images(
                    segment,
                    str(request.data.get("model") or ""),
                    request.data.get("panel_count"),
                    request.data.get("supplementary_description"),
                ),
                "panel_count": segment.panel_count,
                "supplementary_description": segment.supplementary_description,
            }
        )
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


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_segment_generate_video_prompts(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("剧情小段不存在", 404)
    try:
        return ok({"panels": generate_video_prompts(segment)})
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


def _owned_panel(request, panel_id):
    return StoryboardPanel.objects.filter(id=panel_id, segment__project__user=request.user).select_related("segment__project").first()


@csrf_exempt
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def storyboard_panel_update(request, panel_id):
    if not _feature_allowed(request):
        return _feature_denied()
    panel = _owned_panel(request, panel_id)
    if not panel:
        return bad("分镜不存在", 404)
    return ok(update_panel(panel, request.data))


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard_panel_regenerate(request, panel_id):
    if not _feature_allowed(request):
        return _feature_denied()
    panel = _owned_panel(request, panel_id)
    if not panel:
        return bad("分镜不存在", 404)
    try:
        return ok(regenerate_panel(panel, request.data))
    except StoryboardError as exc:
        return bad(str(exc), exc.status)


def _owned_scene_inference_project(request, project_id):
    return SceneInferenceProject.objects.filter(id=project_id, user=request.user).prefetch_related("jobs").first()


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def scene_inference_projects(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        if request.method == "GET":
            projects = SceneInferenceProject.objects.filter(user=request.user).prefetch_related("jobs")[:30]
            return ok({"list": [serialize_scene_inference_project(project, include_jobs=False) for project in projects]})
        project = create_scene_inference_project(request.user, request.data)
        return ok(serialize_scene_inference_project(project))
    except SceneInferenceError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scene_inference_project_detail(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    return ok(serialize_scene_inference_project(project))


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scene_inference_generate_views(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    try:
        return ok(generate_scene_inference_views(project, request.data))
    except SceneInferenceError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scene_inference_generate_panorama(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    try:
        return ok(generate_scene_panorama(project, request.data))
    except SceneInferenceError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def scene_inference_refresh(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    return ok(refresh_scene_inference_project(project))


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scene_inference_enhance_screenshot(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    try:
        return ok(enhance_scene_screenshot(project, request.data))
    except SceneInferenceError as exc:
        return bad(str(exc), exc.status)
