from django.http import HttpResponse
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.cutout_services import (
    CutoutError,
    create_sticker_composition,
    cutout_character,
    enhance_sticker_composite,
    get_cutout_asset,
    list_sticker_assets,
    list_sticker_compositions,
    remove_sticker_asset,
    remove_sticker_composition,
)
from apps.ai_customer.models import (
    OctopusNote,
    OctopusNoteFolder,
    SceneInferenceProject,
    StoryboardPanel,
    StoryboardProject,
    StorySegment,
)
from apps.ai_customer.octopus_planet_services import (
    OctopusPlanetError,
    common_tags,
    particles,
    publish_detail,
    publish_note,
    search_particles,
)
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
    return bool(user and user.is_authenticated and (user.can_access_storyboard or user.is_staff or user.is_superuser))


def _feature_denied():
    return bad("账号无此功能权限", 403)


def _workbench_allowed(request):
    user = request.user
    return bool(user and user.is_authenticated and (user.can_access_workbench or user.is_staff or user.is_superuser))


def _workbench_denied():
    return bad("账号无此功能权限", 403)


def _clean_name(value, fallback="未命名"):
    text = str(value or "").strip()
    return (text or fallback)[:120]


def _clean_octopus_image_urls(value):
    if not isinstance(value, list):
        return []
    image_urls = []
    for item in value:
        url = str(item or "").strip()
        if url:
            image_urls.append(url[:1000])
        if len(image_urls) >= 10:
            break
    return image_urls


def _serialize_octopus_folder(folder):
    note_count = getattr(folder, "note_count", None)
    if note_count is None:
        note_count = folder.notes.count()
    return {
        "id": folder.id,
        "name": folder.name,
        "cover_url": folder.cover_url,
        "note_count": int(note_count or 0),
        "created_at": folder.created_at,
        "updated_at": folder.updated_at,
    }


def _serialize_octopus_note(note):
    try:
        planet_publish = note.planet_publish
    except Exception:
        planet_publish = None
    return {
        "id": note.id,
        "folder_id": note.folder_id,
        "title": note.title,
        "cover_url": note.cover_url,
        "image_urls": _clean_octopus_image_urls(note.image_urls),
        "content": note.content,
        "font_family": note.font_family,
        "font_size": note.font_size,
        "text_color": note.text_color,
        "planet_publish": {
            "id": planet_publish.id,
            "tag": planet_publish.tag,
            "is_vector_ready": planet_publish.is_vector_ready,
        } if planet_publish and planet_publish.is_public else None,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _octopus_order(value):
    return "created_at" if value == "created_asc" else "-created_at"


def _serialize_model_option(option_id: str, label: str, runtime: dict):
    return {
        "id": option_id,
        "label": label,
        "model": str(runtime.get("model") or "").strip(),
        "base_url": str(runtime.get("base_url") or "").strip(),
    }


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def octopus_note_folders(request):
    if not _workbench_allowed(request):
        return _workbench_denied()
    if request.method == "GET":
        folders = OctopusNoteFolder.objects.filter(user=request.user).annotate(note_count=Count("notes"))
        query = str(request.query_params.get("q") or "").strip()
        if query:
            folders = folders.filter(name__icontains=query)
        order = _octopus_order(request.query_params.get("order"))
        folders = folders.order_by(order, "id" if order == "created_at" else "-id")
        return ok({"list": [_serialize_octopus_folder(folder) for folder in folders]})
    folder = OctopusNoteFolder.objects.create(user=request.user, name=_clean_name(request.data.get("name"), "新文件夹"))
    return ok(_serialize_octopus_folder(folder))


@csrf_exempt
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def octopus_note_folder_detail(request, folder_id):
    if not _workbench_allowed(request):
        return _workbench_denied()
    folder = OctopusNoteFolder.objects.filter(id=folder_id, user=request.user).first()
    if not folder:
        return bad("文件夹不存在", 404)
    if request.method == "DELETE":
        folder.delete()
        return ok({"deleted": True, "id": folder_id})
    update_fields = []
    if "name" in request.data:
        folder.name = _clean_name(request.data.get("name"), folder.name)
        update_fields.append("name")
    if "cover_url" in request.data:
        folder.cover_url = str(request.data.get("cover_url") or "").strip()[:1000]
        update_fields.append("cover_url")
    if update_fields:
        update_fields.append("updated_at")
        folder.save(update_fields=update_fields)
    return ok(_serialize_octopus_folder(folder))


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def octopus_notes(request, folder_id):
    if not _workbench_allowed(request):
        return _workbench_denied()
    folder = OctopusNoteFolder.objects.filter(id=folder_id, user=request.user).first()
    if not folder:
        return bad("文件夹不存在", 404)
    if request.method == "GET":
        notes = OctopusNote.objects.filter(user=request.user, folder=folder)
        query = str(request.query_params.get("q") or "").strip()
        if query:
            notes = notes.filter(Q(title__icontains=query) | Q(content__icontains=query))
        order = _octopus_order(request.query_params.get("order"))
        notes = notes.order_by(order, "id" if order == "created_at" else "-id")
        return ok({"list": [_serialize_octopus_note(note) for note in notes]})
    note = OctopusNote.objects.create(
        user=request.user,
        folder=folder,
        title=_clean_name(request.data.get("title"), "新记事本"),
    )
    return ok(_serialize_octopus_note(note))


@csrf_exempt
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def octopus_note_detail(request, note_id):
    if not _workbench_allowed(request):
        return _workbench_denied()
    note = OctopusNote.objects.select_related("folder").filter(id=note_id, user=request.user).first()
    if not note:
        return bad("记事本不存在", 404)
    if request.method == "GET":
        return ok(_serialize_octopus_note(note))
    if request.method == "DELETE":
        note.delete()
        return ok({"deleted": True, "id": note_id})
    update_fields = []
    if "title" in request.data:
        note.title = _clean_name(request.data.get("title"), note.title)
        update_fields.append("title")
    if "cover_url" in request.data:
        note.cover_url = str(request.data.get("cover_url") or "").strip()[:1000]
        update_fields.append("cover_url")
    if "image_urls" in request.data:
        note.image_urls = _clean_octopus_image_urls(request.data.get("image_urls"))
        update_fields.append("image_urls")
    if "content" in request.data:
        note.content = str(request.data.get("content") or "")
        update_fields.append("content")
    if "font_family" in request.data:
        note.font_family = str(request.data.get("font_family") or "Plus Jakarta Sans").strip()[:120]
        update_fields.append("font_family")
    if "font_size" in request.data:
        try:
            note.font_size = min(max(int(request.data.get("font_size") or 18), 12), 42)
        except (TypeError, ValueError):
            note.font_size = 18
        update_fields.append("font_size")
    if "text_color" in request.data:
        note.text_color = str(request.data.get("text_color") or "#eaf7ff").strip()[:20]
        update_fields.append("text_color")
    if update_fields:
        update_fields.append("updated_at")
        note.save(update_fields=update_fields)
    return ok(_serialize_octopus_note(note))


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def octopus_planet_publish(request):
    if not _workbench_allowed(request):
        return _workbench_denied()
    try:
        publish = publish_note(request.user, request.data.get("notebook_id"), request.data.get("tag"))
        return ok(
            {
                "publish_id": publish.id,
                "notebook_id": publish.note_id,
                "tag": publish.tag,
                "is_vector_ready": publish.is_vector_ready,
                "message": "已发布到章鱼星球" if publish.is_vector_ready else "已发布，星球同步中",
            }
        )
    except OctopusPlanetError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def octopus_planet_common_tags(request):
    if not _workbench_allowed(request):
        return _workbench_denied()
    return ok({"items": common_tags(request.user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def octopus_planet_particles(request):
    if not _workbench_allowed(request):
        return _workbench_denied()
    scope = "mine" if request.query_params.get("scope") == "mine" else "all"
    return ok({"items": particles(scope, request.user)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def octopus_planet_search(request):
    if not _workbench_allowed(request):
        return _workbench_denied()
    scope = "mine" if request.query_params.get("scope") == "mine" else "all"
    try:
        return ok({"items": search_particles(request.query_params.get("tag"), scope, request.user)})
    except OctopusPlanetError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def octopus_planet_publish_detail(request, publish_id):
    if not _workbench_allowed(request):
        return _workbench_denied()
    try:
        return ok(publish_detail(publish_id, request.user))
    except OctopusPlanetError as exc:
        return bad(str(exc), exc.status)


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
def ai_image_sticker_compositions(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        if request.method == "GET":
            return ok({"list": list_sticker_compositions(request.user)})
        return ok(create_sticker_composition(request.user, request.data))
    except CutoutError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_image_sticker_composition_enhance(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        return ok(enhance_sticker_composite(request.user, request.data))
    except CutoutError as exc:
        return bad(str(exc), exc.status)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def ai_image_sticker_composition_delete(request, composition_id):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        remove_sticker_composition(composition_id, request.user)
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


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def scene_inference_project_detail(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _owned_scene_inference_project(request, project_id)
    if not project:
        return bad("场景推理项目不存在", 404)
    if request.method == "DELETE":
        project.delete()
        return ok({"deleted": True, "id": project_id})
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
