from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_script_breakdown.models import AiScriptAsset, AiScriptBreakdownProject, AiScriptShotSegment
from apps.ai_script_breakdown.services import (
    ScriptBreakdownError,
    create_project,
    generate_position_image,
    refresh_position_image,
    regenerate_position,
    regenerate_segment,
    run_project,
    serialize_project,
    update_asset,
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


def _project_queryset(request):
    return AiScriptBreakdownProject.objects.filter(user=request.user)


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def script_breakdown_projects(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        if request.method == "GET":
            projects = _project_queryset(request)[:50]
            return ok({"list": [serialize_project(project) for project in projects]})
        project = create_project(request.user, request.data)
        return ok(serialize_project(project, include_detail=True))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def script_breakdown_project_detail(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _project_queryset(request).filter(id=project_id).first()
    if not project:
        return bad("AI拆剧任务不存在", 404)
    if request.method == "DELETE":
        project.delete()
        return ok()
    project = (
        _project_queryset(request)
        .prefetch_related("assets", "scene_blocks__segments__shot_lines")
        .get(id=project.id)
    )
    return ok(serialize_project(project, include_detail=True))


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def script_breakdown_project_run(request, project_id):
    if not _feature_allowed(request):
        return _feature_denied()
    project = _project_queryset(request).filter(id=project_id).first()
    if not project:
        return bad("AI拆剧任务不存在", 404)
    try:
        return ok(run_project(project))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


def _owned_segment(request, segment_id):
    return AiScriptShotSegment.objects.filter(id=segment_id, project__user=request.user).select_related("project", "scene_block").first()


def _owned_asset(request, asset_id):
    return AiScriptAsset.objects.filter(id=asset_id, project__user=request.user).select_related("project").first()


@csrf_exempt
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def script_breakdown_asset_detail(request, asset_id):
    if not _feature_allowed(request):
        return _feature_denied()
    asset = _owned_asset(request, asset_id)
    if not asset:
        return bad("素材不存在", 404)
    if request.method == "DELETE":
        asset.delete()
        return ok()
    try:
        return ok(update_asset(asset, request.data))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def script_breakdown_segment_regenerate(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("小段落不存在", 404)
    try:
        return ok(regenerate_segment(segment))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def script_breakdown_segment_regenerate_position(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("小段落不存在", 404)
    try:
        return ok(regenerate_position(segment, request.data))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def script_breakdown_segment_generate_position(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("小段落不存在", 404)
    try:
        return ok(generate_position_image(segment, request.data))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def script_breakdown_segment_refresh_position(request, segment_id):
    if not _feature_allowed(request):
        return _feature_denied()
    segment = _owned_segment(request, segment_id)
    if not segment:
        return bad("小段落不存在", 404)
    try:
        return ok(refresh_position_image(segment))
    except ScriptBreakdownError as exc:
        return bad(str(exc), exc.status)
