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
from apps.ai_customer.runtime_config import (
    get_ai_image_config,
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
    image_config = get_ai_image_config()
    return ok(
        {
            "default_model": image_config.get("model") or "gpt-image-2",
            "default_size": "16:9",
            "default_resolution": "1k",
            "default_n": 1,
            "reverse_prompt": get_ai_image_reverse_prompt(),
            "model_options": [
                {
                    "id": image_config.get("model") or "gpt-image-2",
                    "label": image_config.get("model") or "GPT-Image-2",
                    "model": image_config.get("model") or "gpt-image-2",
                }
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
    try:
        mode = str(request.data.get("mode", "text") or "text").strip().lower()
        references = prepare_ai_image_references(request.FILES)
        result = submit_ai_image_generation(
            mode=mode,
            prompt=str(request.data.get("prompt", "") or ""),
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
    try:
        return ok(get_ai_image_task_result(task_id))
    except MangaScriptError as exc:
        return bad(str(exc), exc.status)


@csrf_exempt
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ai_manga_storyboard(request):
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
