import io
import os
import time
import uuid
from datetime import datetime

import requests
from django.conf import settings
from PIL import Image
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.ai_image_services import AIImageError, get_ai_image_task_result, submit_ai_image_generation
from apps.ai_customer.models import PositionStickerAsset, PositionStickerComposition
from apps.ai_customer.runtime_config import get_remove_bg_api_key
from apps.ai_customer.storyboard_services import StoryboardError, _persist_storyboard_png, _reference_image_data_url
from apps.storage.models import UploadedFileRecord

STICKER_NATURAL_BLEND_MODEL = "doubao-seedream-5-0-260128"
STICKER_NATURAL_BLEND_PROMPT = """请在不改变画面构图的前提下，对这张站位合成图进行自然融合处理。

必须严格遵守：
1. 保持所有人物的身份、五官、发型、服装、配饰、姿势、站位、大小和数量不变。
2. 保持背景场景结构、家具、门窗、墙体、地面、道具、透视关系不变。
3. 不增加人物，不删除人物，不改变人物动作，不重绘人物面部和服装细节。
4. 只优化人物和场景之间的融合感。
5. 为人物脚底添加符合地面的自然接触阴影，让脚底真实落地。
6. 统一人物与背景的光照方向、明暗关系、色温、边缘过渡、清晰度和颗粒质感。
7. 明显减少人物边缘白边和贴纸感，让人物自然融入底层场景。
8. 输出真实自然、高清干净的最终剧照图，不要出现文字、水印、UI 或额外边框。"""


class CutoutError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _opencv():
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise CutoutError("服务器未安装抠图处理依赖，请联系管理员", 500) from exc
    return cv2, np


def _decode_image(raw: bytes):
    cv2, np = _opencv()
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise CutoutError("无法读取图片文件，请上传 JPG、PNG 或 WebP 图片")
    height, width = image.shape[:2]
    if width < 2 or height < 2:
        raise CutoutError("图片尺寸无效")
    return image, width, height


def _fast_white_background_cutout(raw: bytes) -> tuple[bytes, int, int]:
    cv2, np = _opencv()
    image, width, height = _decode_image(raw)
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

    rgb = image[:, :, :3].astype(np.int16)
    minimum = rgb.min(axis=2)
    maximum = rgb.max(axis=2)
    chroma = maximum - minimum

    # Pure white pixels disappear; the short transition reduces white halos on clear edges.
    white_strength = np.clip((minimum - 220) / 30.0, 0.0, 1.0)
    neutral_strength = np.clip((28 - chroma) / 18.0, 0.0, 1.0)
    removed = white_strength * neutral_strength
    generated_alpha = np.rint(255 * (1.0 - removed)).astype(np.uint8)
    image[:, :, 3] = np.minimum(image[:, :, 3], generated_alpha)

    success, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
    if not success:
        raise CutoutError("生成透明 PNG 失败", 500)
    return encoded.tobytes(), width, height


def _remove_bg_cutout(raw: bytes, filename: str, content_type: str) -> tuple[bytes, int, int]:
    api_key = get_remove_bg_api_key()
    if not api_key:
        raise CutoutError("管理员尚未配置 remove.bg API Key", 503)
    try:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": api_key},
            files={"image_file": (filename or "character.png", raw, content_type or "image/png")},
            data={"size": "auto", "format": "png"},
            timeout=90,
        )
    except requests.RequestException as exc:
        raise CutoutError("AI 抠图服务连接失败，请稍后重试", 502) from exc

    if response.status_code != 200:
        message = "AI 抠图失败"
        try:
            errors = response.json().get("errors") or []
            if errors:
                message = str(errors[0].get("title") or message)
        except ValueError:
            pass
        raise CutoutError(f"{message}（remove.bg {response.status_code}）", 502)

    png_bytes = response.content
    _, width, height = _decode_image(png_bytes)
    return png_bytes, width, height


def _direct_transparent_upload(raw: bytes) -> tuple[bytes, int, int]:
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:
        raise CutoutError("无法读取图片文件，请上传 JPG、PNG 或 WebP 图片") from exc

    has_alpha = "A" in image.getbands() or "transparency" in image.info
    if not has_alpha:
        raise CutoutError("请上传带透明通道的 PNG 或 WebP 图片")
    image = image.convert("RGBA")
    width, height = image.size
    if width < 2 or height < 2:
        raise CutoutError("图片尺寸无效")
    if image.getchannel("A").getextrema()[0] >= 255:
        raise CutoutError("图片没有透明区域，请上传透明图片或选择抠图模式")

    output = io.BytesIO()
    try:
        image.save(output, format="PNG", compress_level=6)
    except Exception as exc:
        raise CutoutError("透明 PNG 处理失败", 500)
    return output.getvalue(), width, height


def _upload_transparent_png(png_bytes: bytes, user) -> tuple[dict, UploadedFileRecord]:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise CutoutError("COS 配置不完整", 500)

    key = f"images/cutouts/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.png"
    client = CosS3Client(
        CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
    )
    try:
        client.put_object(
            Bucket=settings.COS_BUCKET,
            Body=io.BytesIO(png_bytes),
            Key=key,
            ContentType="image/png",
        )
    except Exception as exc:
        raise CutoutError("透明图片上传失败，请稍后重试", 502) from exc

    base_url = str(settings.COS_BASE_URL or "").rstrip("/")
    url = (
        f"{base_url}/{key}"
        if base_url
        else f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    )
    record = UploadedFileRecord.objects.create(
        user=user,
        key=key,
        url=url,
        content_type="image/png",
        size=len(png_bytes),
    )
    return {"url": url, "key": key, "content_type": "image/png", "size": len(png_bytes)}, record


def _serialize_sticker_asset(asset: PositionStickerAsset) -> dict:
    record = asset.file_record
    return {
        "id": asset.id,
        "name": asset.name,
        "key": record.key,
        "url": record.url,
        "content_type": record.content_type,
        "size": record.size,
        "width": asset.width,
        "height": asset.height,
        "mode": asset.cutout_mode,
        "created_at": asset.created_at,
    }


def list_sticker_assets(user) -> list[dict]:
    assets = PositionStickerAsset.objects.filter(user=user).select_related("file_record")[:100]
    return [_serialize_sticker_asset(asset) for asset in assets]


def _serialize_sticker_composition(composition: PositionStickerComposition) -> dict:
    scene_record = composition.scene_file_record
    result_record = composition.result_file_record
    return {
        "id": composition.id,
        "title": composition.title,
        "scene_name": composition.scene_name,
        "scene_key": scene_record.key,
        "scene_url": scene_record.url,
        "result_key": result_record.key,
        "result_url": result_record.url,
        "blend_mode": composition.blend_mode,
        "canvas_width": composition.canvas_width,
        "canvas_height": composition.canvas_height,
        "layers": composition.layers_json if isinstance(composition.layers_json, list) else [],
        "created_at": composition.created_at,
        "updated_at": composition.updated_at,
    }


def list_sticker_compositions(user) -> list[dict]:
    compositions = PositionStickerComposition.objects.filter(user=user).select_related("scene_file_record", "result_file_record")[:50]
    return [_serialize_sticker_composition(composition) for composition in compositions]


def _owned_upload_record(user, key: str, *, field_name: str) -> UploadedFileRecord:
    normalized_key = str(key or "").strip()
    if not normalized_key:
        raise CutoutError(f"缺少{field_name}")
    record = UploadedFileRecord.objects.filter(user=user, key=normalized_key).first()
    if not record:
        raise CutoutError(f"{field_name}不存在或无权访问", 404)
    return record


def _uploaded_record_by_url(user, url: str) -> UploadedFileRecord | None:
    return UploadedFileRecord.objects.filter(user=user, url=str(url or "").strip()).first()


def _first_completed_ai_image(result: dict) -> str:
    return str((result.get("images") or [""])[0] or "").strip()


def _resolve_ai_image_ref(result: dict, model: str) -> str:
    image_ref = _first_completed_ai_image(result)
    if image_ref:
        return image_ref

    task_id = str(result.get("task_id") or "").strip()
    if not task_id:
        raise CutoutError("Seedream 融合未返回图片")

    for _ in range(6):
        time.sleep(2)
        try:
            task = get_ai_image_task_result(task_id, model)
        except AIImageError as exc:
            raise CutoutError(f"Seedream 融合任务查询失败：{exc}", exc.status) from exc
        image_ref = _first_completed_ai_image(task)
        if image_ref:
            return image_ref
        status = str(task.get("status") or "").strip().lower()
        if status in {"failed", "failure", "error", "cancelled", "canceled"}:
            raise CutoutError(f"Seedream 融合失败：{task.get('error') or '任务失败'}", 502)

    raise CutoutError("Seedream 融合仍在处理中，请稍后重试", 202)


def _normalize_canvas_size(value, fallback: int) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = fallback
    return min(max(size, 1), 10000)


def _normalize_blend_mode(value) -> str:
    mode = str(value or PositionStickerComposition.BLEND_NORMAL).strip().lower()
    if mode not in {PositionStickerComposition.BLEND_NORMAL, PositionStickerComposition.BLEND_NATURAL}:
        raise CutoutError("合成方式不支持")
    return mode


def _normalize_float(value, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_sticker_layers(layers, user) -> list[dict]:
    if not isinstance(layers, list):
        raise CutoutError("图层数据格式错误")
    normalized = []
    for index, layer in enumerate(layers[:80], start=1):
        if not isinstance(layer, dict):
            continue
        key = str(layer.get("key") or "").strip()
        if not key.startswith("images/cutouts/"):
            raise CutoutError("图层素材格式不支持")
        _owned_upload_record(user, key, field_name="图层素材")
        normalized.append(
            {
                "id": str(layer.get("id") or f"layer-{index}")[:80],
                "name": str(layer.get("name") or f"素材 {index}")[:120],
                "key": key,
                "url": str(layer.get("url") or "")[:1000],
                "mode": str(layer.get("mode") or "fast")[:20],
                "left": _normalize_float(layer.get("left"), 0.0),
                "top": _normalize_float(layer.get("top"), 0.0),
                "scale_x": _normalize_float(layer.get("scale_x"), 1.0),
                "scale_y": _normalize_float(layer.get("scale_y"), 1.0),
                "angle": _normalize_float(layer.get("angle"), 0.0),
                "opacity": _normalize_float(layer.get("opacity"), 1.0),
                "flip_x": bool(layer.get("flip_x")),
                "flip_y": bool(layer.get("flip_y")),
            }
        )
    if not normalized:
        raise CutoutError("请至少保留一个图层后再保存历史")
    return normalized


def create_sticker_composition(user, payload: dict) -> dict:
    scene_record = _owned_upload_record(user, payload.get("scene_key"), field_name="场景图")
    result_record = _owned_upload_record(user, payload.get("result_key"), field_name="合成图")
    layers = _normalize_sticker_layers(payload.get("layers"), user)
    title = str(payload.get("title") or "").strip()[:120]
    composition = PositionStickerComposition.objects.create(
        user=user,
        scene_file_record=scene_record,
        result_file_record=result_record,
        title=title or str(payload.get("scene_name") or "站位贴图")[:120],
        scene_name=str(payload.get("scene_name") or "")[:255],
        blend_mode=_normalize_blend_mode(payload.get("blend_mode")),
        canvas_width=_normalize_canvas_size(payload.get("canvas_width"), 760),
        canvas_height=_normalize_canvas_size(payload.get("canvas_height"), 500),
        layers_json=layers,
    )
    return _serialize_sticker_composition(composition)


def enhance_sticker_composite(user, payload: dict) -> dict:
    source_record = _owned_upload_record(user, payload.get("composite_key") or payload.get("result_key"), field_name="合成草图")
    references = [
        {
            "field": "sticker_composite",
            "label": "当前站位合成草图",
            "name": "当前站位合成草图",
            "data_url": _reference_image_data_url(source_record.key, user),
        }
    ]
    try:
        result = submit_ai_image_generation(
            prompt=STICKER_NATURAL_BLEND_PROMPT,
            model=STICKER_NATURAL_BLEND_MODEL,
            size="16:9",
            resolution="2k",
            reference_images=references,
        )
        image_ref = _resolve_ai_image_ref(result, STICKER_NATURAL_BLEND_MODEL)
        final_url = _persist_storyboard_png(
            image_ref,
            user,
            "sticker_fusions",
            STICKER_NATURAL_BLEND_MODEL,
            allow_remote_fallback=False,
        )
    except AIImageError as exc:
        raise CutoutError(f"Seedream 自然融合失败：{exc}", exc.status) from exc
    except StoryboardError as exc:
        raise CutoutError(str(exc), exc.status) from exc

    final_record = _uploaded_record_by_url(user, final_url)
    if not final_record:
        raise CutoutError("Seedream 融合结果保存失败", 502)
    return {
        "url": final_record.url,
        "key": final_record.key,
        "content_type": final_record.content_type,
        "size": final_record.size,
        "model": STICKER_NATURAL_BLEND_MODEL,
        "prompt": STICKER_NATURAL_BLEND_PROMPT,
        "source_key": source_record.key,
    }


def remove_sticker_composition(composition_id: int, user):
    composition = PositionStickerComposition.objects.filter(id=composition_id, user=user).first()
    if not composition:
        raise CutoutError("历史记录不存在", 404)
    composition.delete()


def remove_sticker_asset(asset_id: int, user):
    asset = PositionStickerAsset.objects.filter(id=asset_id, user=user).first()
    if not asset:
        raise CutoutError("资产不存在", 404)
    asset.delete()


def get_cutout_asset(key: str, user) -> bytes:
    normalized_key = str(key or "").strip()
    record = UploadedFileRecord.objects.filter(
        user=user,
        key=normalized_key,
        content_type="image/png",
    ).first()
    if not record or not normalized_key.startswith("images/cutouts/"):
        raise CutoutError("透明图片不存在", 404)
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise CutoutError("COS 配置不完整", 500)
    client = CosS3Client(
        CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
        )
    )
    try:
        response = client.get_object(Bucket=settings.COS_BUCKET, Key=normalized_key)
        return response["Body"].get_raw_stream().read()
    except Exception as exc:
        raise CutoutError("透明图片读取失败", 502) from exc


def cutout_character(file_obj, mode: str, user, *, save_to_library: bool = False) -> dict:
    normalized_mode = str(mode or "fast").strip().lower()
    if normalized_mode not in {"fast", "ai", "transparent"}:
        raise CutoutError("抠图模式不支持")
    if not file_obj:
        raise CutoutError("请上传角色图片")
    if int(file_obj.size or 0) > settings.MAX_UPLOAD_SIZE:
        raise CutoutError("图片超过大小限制（最大 10MB）", 413)

    filename = os.path.basename(file_obj.name or "character.png")
    content_type = str(file_obj.content_type or "application/octet-stream")
    if not content_type.startswith("image/"):
        raise CutoutError("仅支持图片文件", 415)

    raw = file_obj.read()
    if normalized_mode == "transparent":
        png_bytes, width, height = _direct_transparent_upload(raw)
    elif normalized_mode == "fast":
        png_bytes, width, height = _fast_white_background_cutout(raw)
    else:
        png_bytes, width, height = _remove_bg_cutout(raw, filename, content_type)
    uploaded, record = _upload_transparent_png(png_bytes, user)
    result = {
        **uploaded,
        "width": width,
        "height": height,
        "mode": normalized_mode,
        "filename": filename,
    }
    if save_to_library:
        name = os.path.splitext(filename)[0].strip()[:100] or "透明角色"
        asset = PositionStickerAsset.objects.create(
            user=user,
            file_record=record,
            name=name,
            cutout_mode=normalized_mode,
            width=width,
            height=height,
        )
        result["library_asset"] = _serialize_sticker_asset(asset)
    return result
