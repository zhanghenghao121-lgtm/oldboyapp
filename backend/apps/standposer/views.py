import json

from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import CharacterAsset, GenerationTask, SceneShot, StandScene
from .serializers import (
    CharacterAssetSerializer,
    CharacterCreateSerializer,
    GenerationTaskSerializer,
    SceneShotCreateSerializer,
    SceneShotSerializer,
    StandSceneSerializer,
)
from .services import StandposerUploadError, upload_to_cos
from .tasks import run_test_model_generation


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


@csrf_exempt
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def characters(request):
    if request.method == "GET":
        rows = CharacterAsset.objects.filter(user=request.user)
        return ok({"list": CharacterAssetSerializer(rows, many=True).data})

    serializer = CharacterCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return bad("参数错误")
    try:
        uploaded = upload_to_cos(
            serializer.validated_data["file"],
            "standposer/characters",
            allowed_extensions={".glb"},
            allowed_content_types={"model/gltf-binary", "application/octet-stream"},
        )
    except StandposerUploadError as exc:
        return bad(str(exc), 400 if "COS" not in str(exc) else 500)

    character = CharacterAsset.objects.create(
        user=request.user,
        name=serializer.validated_data["name"].strip(),
        model_url=uploaded["url"],
        cos_key=uploaded["key"],
        file_size=uploaded["size"],
        content_type=uploaded["content_type"],
    )
    return ok(CharacterAssetSerializer(character).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def character_detail(request, character_id):
    character = CharacterAsset.objects.filter(id=character_id, user=request.user).first()
    if not character:
        return bad("角色不存在", 404)
    return ok(CharacterAssetSerializer(character).data)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def character_generate_model(request, character_id):
    character = CharacterAsset.objects.filter(id=character_id, user=request.user).first()
    if not character:
        return bad("角色不存在", 404)
    task = GenerationTask.objects.create(
        user=request.user,
        character=character,
        input_payload={"mode": "test_glb_passthrough"},
    )
    try:
        async_result = run_test_model_generation.delay(task.id)
        task.celery_task_id = async_result.id
        task.save(update_fields=["celery_task_id", "updated_at"])
    except Exception as exc:
        task.status = GenerationTask.STATUS_FAILED
        task.error_message = f"Celery任务提交失败：{exc}"[:500]
        task.save(update_fields=["status", "error_message", "updated_at"])
    return ok(GenerationTaskSerializer(task).data)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def scenes(request):
    serializer = StandSceneSerializer(data=request.data)
    if not serializer.is_valid():
        return bad("参数错误")
    scene = serializer.save(user=request.user)
    return ok(StandSceneSerializer(scene).data)


@csrf_exempt
@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def scene_detail(request, scene_id):
    scene = StandScene.objects.filter(id=scene_id, user=request.user).first()
    if not scene:
        return bad("场景不存在", 404)
    if request.method == "GET":
        return ok(StandSceneSerializer(scene).data)

    serializer = StandSceneSerializer(scene, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad("参数错误")
    serializer.save()
    return ok(serializer.data)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shots(request):
    serializer = SceneShotCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return bad("参数错误")
    scene = None
    scene_id = serializer.validated_data.get("scene_id")
    if scene_id:
        scene = StandScene.objects.filter(id=scene_id, user=request.user).first()
        if not scene:
            return bad("场景不存在", 404)
    try:
        camera_state = json.loads(serializer.validated_data.get("camera_state") or "{}")
    except Exception:
        camera_state = {}
    try:
        uploaded = upload_to_cos(
            serializer.validated_data["image"],
            "standposer/shots",
            allowed_extensions={".png"},
            allowed_content_types={"image/png"},
        )
    except StandposerUploadError as exc:
        return bad(str(exc), 400 if "COS" not in str(exc) else 500)

    shot = SceneShot.objects.create(
        user=request.user,
        scene=scene,
        image_url=uploaded["url"],
        cos_key=uploaded["key"],
        width=serializer.validated_data.get("width") or 0,
        height=serializer.validated_data.get("height") or 0,
        camera_state=camera_state if isinstance(camera_state, dict) else {},
    )
    if scene and not scene.thumbnail_url:
        scene.thumbnail_url = shot.image_url
        scene.save(update_fields=["thumbnail_url", "updated_at"])
    return ok(SceneShotSerializer(shot).data)
