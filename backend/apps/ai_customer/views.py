import json

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.ai_customer.manga_services import (
    MangaScriptError,
    extract_story_source_text,
    generate_manga_storyboard,
    get_ai_image_task_result,
    normalize_manga_style,
    prepare_ai_image_references,
    prepare_reference_images,
    submit_ai_image_generation,
)
from apps.ai_customer.cutout_services import (
    CutoutError,
    cutout_character,
    get_cutout_asset,
    list_sticker_assets,
    remove_sticker_asset,
)
from apps.ai_customer.position_services import (
    generate_reverse_prompt,
    recognize_position_image,
)
from apps.ai_customer.runtime_config import (
    get_ai_image_config,
    get_ai_image_configs,
    get_ai_image_reverse_prompt,
    get_assistant_llm_config,
    get_manga_llm_config,
    get_manga_storyboard_prompt,
    get_manga_style_prompt,
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
def ai_manga_config(request):
    if not _feature_allowed(request):
        return _feature_denied()
    assistant = get_assistant_llm_config()
    manga = get_manga_llm_config()
    return ok(
        {
            "default_model_preset": "assistant",
            "default_style": "3d",
            "storyboard_prompt": get_manga_storyboard_prompt(),
            "style_options": [
                {"id": "3d", "label": "3D风格", "prompt": get_manga_style_prompt("3d")},
                {"id": "real", "label": "真人风格", "prompt": get_manga_style_prompt("real")},
            ],
            "model_options": [
                _serialize_model_option("assistant", "助手模型", assistant),
                _serialize_model_option("manga", "剧本模型", manga),
            ],
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
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ai_image_task(request, task_id):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        return ok(get_ai_image_task_result(task_id))
    except MangaScriptError as exc:
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
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_position_recognize(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        return ok(recognize_position_image(request.FILES))
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_position_reverse_prompt(request):
    if not _feature_allowed(request):
        return _feature_denied()
    try:
        try:
            bindings = json.loads(str(request.data.get("bindings", "[]") or "[]"))
        except Exception:
            bindings = []
        if not isinstance(bindings, list):
            bindings = []
        try:
            recognition = json.loads(str(request.data.get("recognition", "{}") or "{}"))
        except Exception:
            recognition = {}
        if not isinstance(recognition, dict):
            recognition = {}
        result = generate_reverse_prompt(
            str(request.data.get("position_description", "") or ""),
            bindings=bindings,
            recognition=recognition,
        )
        return ok(result)
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_storyboard(request):
    if not _feature_allowed(request):
        return _feature_denied()
    file_obj = request.FILES.get("file")
    text = str(request.data.get("text", "")).strip()
    model_preset = str(request.data.get("model_preset", "assistant")).strip().lower() or "assistant"
    style = normalize_manga_style(request.data.get("style", "3d"))
    if model_preset not in {"assistant", "manga"}:
        return bad("模型选项不支持")
    try:
        source_text = extract_story_source_text(file_obj=file_obj, text=text)
        reference_images = prepare_reference_images(request.FILES)
        position_description = str(request.data.get("position_description", "") or "").strip()[:2000]
        result = generate_manga_storyboard(
            source_text,
            model_preset=model_preset,
            style=style,
            reference_images=reference_images,
            position_description=position_description,
        )
        return ok(result)
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)
