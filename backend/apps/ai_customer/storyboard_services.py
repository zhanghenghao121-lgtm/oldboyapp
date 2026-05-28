import base64
import io
import json
import logging
import re
import uuid
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from PIL import Image, ImageOps
from django.conf import settings
from django.db import transaction
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.llm_clients import LLMClientError, chat_completion
from apps.ai_customer.ai_image_services import (
    AIImageError,
    get_ai_image_task_result,
    submit_ai_image_generation,
)
from apps.ai_customer.models import (
    StoryboardAsset,
    StoryboardPanel,
    StoryboardProject,
    StorySegment,
)
from apps.ai_customer.runtime_config import (
    get_storyboard_asset_prompt,
    get_ai_image_config,
    get_storyboard_leaf_split_prompt,
    get_storyboard_llm_config,
    get_storyboard_panel_prompt,
    get_storyboard_scene_split_prompt,
    get_storyboard_single_panel_prompt,
    get_storyboard_video_prompt,
)
from apps.storage.models import UploadedFileRecord

logger = logging.getLogger(__name__)

MAX_SPLIT_DEPTH = 3
ASSET_TYPE_BY_GROUP = {
    "characters": StoryboardAsset.TYPE_CHARACTER,
    "scenes": StoryboardAsset.TYPE_SCENE,
    "props": StoryboardAsset.TYPE_PROP,
}
ALLOWED_ASSET_TYPES = {*ASSET_TYPE_BY_GROUP.values(), StoryboardAsset.TYPE_POSITION}
ALLOWED_PANEL_COUNTS = {6, 9, 12}


class StoryboardError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _json_content(body: dict, label: str) -> dict:
    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise StoryboardError(f"{label}未返回有效内容", 502)
    content = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.I | re.S)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\}|\[.*\])", content, re.S)
        try:
            data = json.loads(match.group(1)) if match else None
        except Exception:
            data = None
    if not isinstance(data, dict):
        logger.error("%s JSON解析失败 content=%s", label, content[:500])
        raise StoryboardError(f"{label}返回格式异常，请重试", 502)
    return data


def _call_storyboard_json(system_prompt: str, user_content: str, model: str, label: str) -> dict:
    runtime = get_storyboard_llm_config(model)
    service_name = f"{label}（{runtime.get('label') or runtime.get('model') or '未命名模型'} / {runtime.get('model') or '-'}）"
    payload = {
        "model": runtime.get("model"),
        "temperature": 0.25,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    try:
        body = chat_completion(runtime, payload, service_name=service_name)
    except LLMClientError as exc:
        logger.exception("%s调用失败 model=%s", label, runtime.get("model"))
        raise StoryboardError(str(exc), exc.status) from exc
    return _json_content(body, label)


def serialize_asset(asset: StoryboardAsset) -> dict:
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "name": asset.name,
        "description": asset.description,
        "image_url": asset.image_url,
    }


def serialize_panel(panel: StoryboardPanel) -> dict:
    return {
        "id": panel.id,
        "panel_no": panel.panel_no,
        "shot_type": panel.shot_type,
        "camera_angle": panel.camera_angle,
        "camera_movement": panel.camera_movement,
        "screen_description": panel.screen_description,
        "image_prompt": panel.image_prompt,
        "video_prompt": panel.video_prompt,
        "emotion": panel.emotion,
        "characters": panel.characters,
        "props": panel.props,
        "image_url": panel.image_url,
        "generation_task_id": panel.generation_task_id,
    }


def serialize_segment(segment: StorySegment, include_children: bool = True) -> dict:
    data = {
        "id": segment.id,
        "parent_id": segment.parent_id,
        "level": segment.level,
        "order": segment.order_index,
        "title": segment.title,
        "summary": segment.summary,
        "original_text": segment.original_text,
        "scene_name": segment.scene_name,
        "time_of_day": segment.time_of_day,
        "mood": segment.mood,
        "is_leaf": segment.is_leaf,
        "split_reason": segment.split_reason,
        "grid_feasibility_score": segment.grid_feasibility_score,
        "analysis": segment.analysis_json,
        "required_assets": segment.required_assets_json,
        "panel_count": segment.panel_count,
        "supplementary_description": segment.supplementary_description,
        "assets": [serialize_asset(asset) for asset in segment.assets.all()],
        "panels": [serialize_panel(panel) for panel in segment.panels.all()],
        "grid_image_url": segment.grid_image_url,
    }
    if include_children:
        data["children"] = [serialize_segment(child) for child in segment.children.all()]
    return data


def serialize_project(project: StoryboardProject, include_segments: bool = False) -> dict:
    data = {
        "id": project.id,
        "title": project.title,
        "original_story": project.original_story,
        "style_preset": project.style_preset,
        "aspect_ratio": project.aspect_ratio,
        "analysis_model": project.analysis_model,
        "image_model": project.image_model,
        "status": project.status,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if include_segments:
        roots = project.segments.filter(parent__isnull=True).prefetch_related("children", "assets", "panels")
        data["segments"] = [serialize_segment(segment) for segment in roots]
    return data


def create_project(user, payload: dict) -> StoryboardProject:
    story = str(payload.get("original_story") or "").strip()
    if len(story) < 20:
        raise StoryboardError("请输入至少 20 个字的完整剧情内容")
    return StoryboardProject.objects.create(
        user=user,
        title=str(payload.get("title") or "未命名故事板").strip()[:255] or "未命名故事板",
        original_story=story,
        style_preset=str(payload.get("style_preset") or "").strip()[:100],
        aspect_ratio=str(payload.get("aspect_ratio") or "16:9").strip()[:20] or "16:9",
        analysis_model=str(payload.get("analysis_model") or "deepseek-v4-pro").strip()[:100],
        image_model=str(payload.get("image_model") or "gpt-image-2").strip()[:100],
    )


def _leaf_assets(segment: StorySegment, model: str) -> dict:
    data = _call_storyboard_json(
        get_storyboard_asset_prompt(),
        f"剧情段标题：{segment.title}\n场景：{segment.scene_name}\n剧情内容：\n{segment.original_text or segment.summary}",
        model,
        "故事板素材提取模型",
    )
    return {
        key: [item for item in (data.get(key) or []) if isinstance(item, dict)]
        for key in ASSET_TYPE_BY_GROUP
    }


def _create_asset_slots(segment: StorySegment, required_assets: dict) -> None:
    for group, asset_type in ASSET_TYPE_BY_GROUP.items():
        for item in required_assets.get(group) or []:
            name = str(item.get("name") or "").strip()[:255]
            if not name:
                continue
            StoryboardAsset.objects.get_or_create(
                project=segment.project,
                segment=segment,
                asset_type=asset_type,
                name=name,
                defaults={"description": str(item.get("description") or "").strip()},
            )


def _split_segment(segment: StorySegment, model: str, depth: int) -> None:
    judgment = _call_storyboard_json(
        get_storyboard_leaf_split_prompt(),
        f"场景：{segment.scene_name}\n段落标题：{segment.title}\n剧情内容：\n{segment.original_text or segment.summary}",
        model,
        "故事板递归拆解模型",
    )
    children = [item for item in (judgment.get("children") or []) if isinstance(item, dict)]
    is_leaf = bool(judgment.get("can_be_9_grid")) or depth >= MAX_SPLIT_DEPTH or not children
    segment.grid_feasibility_score = int(judgment.get("score") or 0)
    segment.analysis_json = judgment
    segment.is_leaf = is_leaf
    if is_leaf:
        segment.required_assets_json = _leaf_assets(segment, model)
    segment.save(update_fields=["grid_feasibility_score", "analysis_json", "is_leaf", "required_assets_json"])
    if is_leaf:
        _create_asset_slots(segment, segment.required_assets_json)
        return
    for index, item in enumerate(children, start=1):
        child = StorySegment.objects.create(
            project=segment.project,
            parent=segment,
            level=segment.level + 1,
            order_index=int(item.get("order") or index),
            title=str(item.get("title") or f"{segment.title}-{index}")[:255],
            summary=str(item.get("summary") or ""),
            original_text=str(item.get("original_text") or item.get("summary") or ""),
            scene_name=segment.scene_name,
            time_of_day=segment.time_of_day,
            mood=segment.mood,
            split_reason=str(item.get("split_reason") or judgment.get("reason") or ""),
        )
        _split_segment(child, model, depth + 1)


@transaction.atomic
def analyze_project(project: StoryboardProject) -> dict:
    project.segments.all().delete()
    result = _call_storyboard_json(
        get_storyboard_scene_split_prompt(),
        f"请拆解以下剧情：\n\n{project.original_story}",
        project.analysis_model,
        "故事板场景拆解模型",
    )
    blocks = [item for item in (result.get("scene_blocks") or []) if isinstance(item, dict)]
    if not blocks:
        raise StoryboardError("模型未返回可用的场景段落，请调整剧情或提示词后重试", 502)
    if str(result.get("project_title") or "").strip() and project.title == "未命名故事板":
        project.title = str(result["project_title"]).strip()[:255]
    for index, item in enumerate(blocks, start=1):
        segment = StorySegment.objects.create(
            project=project,
            level=1,
            order_index=int(item.get("order") or index),
            title=str(item.get("title") or f"场景 {index}")[:255],
            summary=str(item.get("summary") or ""),
            original_text=str(item.get("original_text") or item.get("summary") or ""),
            scene_name=str(item.get("scene_name") or ""),
            time_of_day=str(item.get("time_of_day") or ""),
            mood=str(item.get("mood") or ""),
            split_reason=str(item.get("split_reason") or ""),
        )
        _split_segment(segment, project.analysis_model, 1)
    project.status = StoryboardProject.STATUS_ANALYZED
    project.save(update_fields=["title", "status", "updated_at"])
    return serialize_project(project, include_segments=True)


def save_asset(segment: StorySegment, payload: dict) -> dict:
    if not segment.is_leaf:
        raise StoryboardError("只能为可生成分镜板的剧情小段上传素材")
    asset_type = str(payload.get("asset_type") or "").strip()
    if asset_type not in ALLOWED_ASSET_TYPES:
        raise StoryboardError("素材类型不支持")
    name = str(payload.get("name") or "").strip()[:255]
    image_url = str(payload.get("image_url") or "").strip()
    if not name:
        raise StoryboardError("素材名称不能为空")
    asset, _ = StoryboardAsset.objects.update_or_create(
        segment=segment,
        asset_type=asset_type,
        name=name,
        defaults={
            "project": segment.project,
            "description": str(payload.get("description") or "").strip(),
            "image_url": image_url,
        },
    )
    return serialize_asset(asset)


def delete_asset(segment: StorySegment, asset_id: int) -> None:
    asset = segment.assets.filter(id=asset_id).first()
    if not asset:
        raise StoryboardError("素材不存在", 404)
    asset.delete()


def _panel_count(value, fallback: int = 9) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = fallback
    if count not in ALLOWED_PANEL_COUNTS:
        raise StoryboardError("分镜数量仅支持 6、9 或 12 张")
    return count


@transaction.atomic
def generate_panels(segment: StorySegment, panel_count=None, supplementary_description=None) -> list[dict]:
    if not segment.is_leaf:
        raise StoryboardError("请选择已拆解完成的剧情小段")
    count = _panel_count(panel_count, segment.panel_count)
    description = (
        str(supplementary_description).strip()
        if supplementary_description is not None
        else segment.supplementary_description
    )
    segment.panel_count = count
    segment.supplementary_description = description
    segment.grid_image_url = ""
    segment.save(update_fields=["panel_count", "supplementary_description", "grid_image_url"])
    assets = [serialize_asset(asset) for asset in segment.assets.all()]
    result = _call_storyboard_json(
        get_storyboard_panel_prompt(),
        (
            f"剧情段标题：{segment.title}\n场景：{segment.scene_name}\n情绪：{segment.mood}\n"
            f"项目画面风格：{segment.project.style_preset or '未指定'}\n"
            f"需要生成的分镜数量：{count} 张\n"
            f"剧情内容：\n{segment.original_text or segment.summary}\n\n"
            f"用户补充描述：\n{description or '无'}\n\n"
            f"已上传素材参考：\n{json.dumps(assets, ensure_ascii=False)}"
        ),
        segment.project.analysis_model,
        "分镜板规划模型",
    )
    panels = [item for item in (result.get("panels") or []) if isinstance(item, dict)]
    if len(panels) != count:
        raise StoryboardError(f"模型未返回完整的 {count} 个分镜，请重试或调整提示词", 502)
    segment.panels.all().delete()
    rows = []
    for panel_no, item in enumerate(sorted(panels, key=lambda row: int(row.get("panel_no") or 99)), start=1):
        rows.append(
            StoryboardPanel.objects.create(
                segment=segment,
                panel_no=panel_no,
                shot_type=str(item.get("shot_type") or ""),
                camera_angle=str(item.get("camera_angle") or ""),
                camera_movement=str(item.get("camera_movement") or ""),
                screen_description=str(item.get("screen_description") or ""),
                image_prompt=str(item.get("image_prompt") or ""),
                video_prompt=str(item.get("video_prompt") or ""),
                emotion=str(item.get("emotion") or ""),
                characters=item.get("characters") if isinstance(item.get("characters"), list) else [],
                props=item.get("props") if isinstance(item.get("props"), list) else [],
            )
        )
    return [serialize_panel(row) for row in rows]


def _panel_references(segment: StorySegment, asset_ids: list[int] | None = None) -> list[dict]:
    assets = segment.assets.exclude(image_url="")
    if asset_ids is not None:
        assets = assets.filter(id__in=asset_ids)
    return [
        {
            "field": "storyboard_asset",
            "label": f"{asset.get_asset_type_display()}：{asset.name}",
            "name": asset.name,
            "data_url": _reference_image_data_url(asset.image_url, segment.project.user),
        }
        for asset in assets
    ]


def _stored_image_bytes(image_ref: str, user) -> tuple[bytes, str] | None:
    if not user or not image_ref:
        return None
    record = UploadedFileRecord.objects.filter(user=user, url=image_ref).first()
    if not record:
        record = UploadedFileRecord.objects.filter(user=user, key=image_ref).first()
    if not record:
        return None
    try:
        client = CosS3Client(CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY))
        response = client.get_object(Bucket=settings.COS_BUCKET, Key=record.key)
        return response["Body"].get_raw_stream().read(), record.content_type or "image/png"
    except Exception as exc:
        logger.exception("COS 图片读取失败 key=%s", record.key)
        raise StoryboardError("图片读取失败，请稍后重试", 502) from exc


def _reference_image_data_url(image_ref: str, user) -> str:
    stored = _stored_image_bytes(image_ref, user)
    if not stored:
        return image_ref
    raw, content_type = stored
    return f"data:{content_type};base64,{base64.b64encode(raw).decode('ascii')}"


def _upload_storyboard_png(image_bytes: bytes, user, folder: str) -> str:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise StoryboardError("COS 配置不完整，无法保存分镜图片", 500)
    safe_folder = re.sub(r"[^a-zA-Z0-9_-]", "", str(folder or "images")) or "images"
    key = f"images/storyboards/{safe_folder}/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.png"
    client = CosS3Client(CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY))
    try:
        client.put_object(Bucket=settings.COS_BUCKET, Body=image_bytes, Key=key, ContentType="image/png")
    except Exception as exc:
        logger.exception("分镜图片上传 COS 失败")
        raise StoryboardError("分镜图片保存失败，请稍后重试", 502) from exc
    base_url = str(settings.COS_BASE_URL or "").rstrip("/")
    url = f"{base_url}/{key}" if base_url else f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    UploadedFileRecord.objects.create(user=user, key=key, url=url, content_type="image/png", size=len(image_bytes))
    return url


def _generated_image_candidates(image_ref: str, image_model: str = "") -> list[str]:
    text = str(image_ref or "").strip()
    if not text or text.startswith("data:image/"):
        return [text] if text else []
    candidates = [text]
    parsed = urlparse(text)
    if not parsed.scheme:
        runtime = get_ai_image_config(image_model)
        base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
        if base_url:
            candidates.insert(0, urljoin(f"{base_url}/", text.lstrip("/")))
    return list(dict.fromkeys(candidates))


def _download_generated_image(image_ref: str, image_model: str = "") -> bytes:
    runtime = get_ai_image_config(image_model)
    api_key = str(runtime.get("api_key") or "").strip()
    base_host = urlparse(str(runtime.get("base_url") or "")).netloc
    last_exc = None
    for url in _generated_image_candidates(image_ref, image_model):
        parsed = urlparse(url)
        header_options = [
            {"Accept": "image/*", "User-Agent": "oldboyai-storyboard/1.0"},
        ]
        if api_key and (not parsed.netloc or parsed.netloc == base_host):
            header_options.insert(0, {**header_options[0], "Authorization": f"Bearer {api_key}"})
        for headers in header_options:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.content
            except Exception as exc:
                last_exc = exc
    raise StoryboardError("生成图下载失败，请稍后重试", 502) from last_exc


def _remote_image_fallback(image_ref: str, image_model: str = "") -> str:
    for candidate in _generated_image_candidates(image_ref, image_model):
        if urlparse(candidate).scheme in {"http", "https"}:
            return candidate
    return ""


def _persist_storyboard_png(image_ref: str, user, folder: str, image_model: str = "", allow_remote_fallback: bool = True) -> str:
    if not image_ref:
        return ""
    stored = _stored_image_bytes(image_ref, user)
    if stored:
        raw = stored[0]
    elif image_ref.startswith("data:image/"):
        raw = base64.b64decode(image_ref.split(",", 1)[1])
    else:
        try:
            raw = _download_generated_image(image_ref, image_model)
        except StoryboardError as exc:
            fallback = _remote_image_fallback(image_ref, image_model) if allow_remote_fallback else ""
            if fallback:
                logger.warning("生成图转存下载失败，保留原始地址 url=%s", image_ref)
                return fallback
            logger.exception("生成图下载失败 url=%s", image_ref)
            raise exc
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        image.load()
    except Exception as exc:
        fallback = _remote_image_fallback(image_ref, image_model) if allow_remote_fallback else ""
        if fallback:
            logger.warning("生成图转存校验失败，保留原始地址 url=%s", image_ref)
            return fallback
        raise StoryboardError("生成图不是有效图片，请检查生图服务返回内容", 502) from exc
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return _upload_storyboard_png(output.getvalue(), user, folder)


def _submit_panel_image(panel: StoryboardPanel, model: str, references: list[dict]) -> None:
    try:
        result = submit_ai_image_generation(
            mode="text",
            prompt=panel.image_prompt,
            model=model,
            size=panel.segment.project.aspect_ratio,
            resolution="1k",
            reference_images=references,
        )
    except AIImageError as exc:
        logger.exception("分镜板生图失败 segment=%s panel=%s", panel.segment_id, panel.panel_no)
        raise StoryboardError(f"第 {panel.panel_no} 格生成失败：{exc}", exc.status) from exc
    panel.generation_task_id = str(result.get("task_id") or "")
    image_ref = str((result.get("images") or [""])[0] or "")
    panel.image_url = _persist_storyboard_png(image_ref, panel.segment.project.user, "panels", model) if image_ref else ""
    panel.save(update_fields=["generation_task_id", "image_url"])


def generate_panel_images(segment: StorySegment, model: str = "", asset_ids: list[int] | None = None) -> list[dict]:
    panels = list(segment.panels.select_related("segment__project__user").all())
    if len(panels) != segment.panel_count:
        raise StoryboardError("请先生成完整分镜板提示词")
    references = _panel_references(segment, asset_ids)
    image_model = str(model or segment.project.image_model).strip()
    if image_model and segment.project.image_model != image_model:
        segment.project.image_model = image_model
        segment.project.save(update_fields=["image_model", "updated_at"])
    for panel in panels:
        if panel.image_url or panel.generation_task_id:
            continue
        _submit_panel_image(panel, image_model, references)
    return [serialize_panel(panel) for panel in segment.panels.all()]


def generate_panels_and_images(segment: StorySegment, model: str = "", panel_count=None, supplementary_description=None) -> list[dict]:
    generate_panels(segment, panel_count, supplementary_description)
    return generate_panel_images(segment, model)


def update_panel(panel: StoryboardPanel, payload: dict) -> dict:
    update_fields = []
    for field in ["screen_description", "image_prompt"]:
        if field in payload:
            setattr(panel, field, str(payload.get(field) or "").strip())
            update_fields.append(field)
    if "image_url" in payload:
        panel.image_url = str(payload.get("image_url") or "").strip()
        panel.generation_task_id = ""
        update_fields.extend(["image_url", "generation_task_id"])
    if update_fields:
        panel.save(update_fields=update_fields)
        panel.segment.grid_image_url = ""
        panel.segment.save(update_fields=["grid_image_url"])
    return serialize_panel(panel)


def regenerate_panel(panel: StoryboardPanel, payload: dict) -> dict:
    segment = panel.segment
    raw_ids = payload.get("asset_ids") or []
    if not isinstance(raw_ids, list):
        raise StoryboardError("参考素材参数格式错误")
    asset_ids = []
    for value in raw_ids:
        try:
            asset_ids.append(int(value))
        except (TypeError, ValueError):
            continue
    chosen_assets = [serialize_asset(asset) for asset in segment.assets.filter(id__in=asset_ids)]
    data = _call_storyboard_json(
        get_storyboard_single_panel_prompt(),
        (
            f"剧情段：{segment.original_text or segment.summary}\n"
            f"当前格编号：{panel.panel_no}\n当前画面描述：{panel.screen_description}\n"
            f"当前生图提示词：{panel.image_prompt}\n"
            f"本次选用参考素材：{json.dumps(chosen_assets, ensure_ascii=False)}"
        ),
        segment.project.analysis_model,
        "单格分镜重生成模型",
    )
    for field in [
        "shot_type",
        "camera_angle",
        "camera_movement",
        "screen_description",
        "image_prompt",
        "video_prompt",
        "emotion",
    ]:
        setattr(panel, field, str(data.get(field) or getattr(panel, field)))
    panel.characters = data.get("characters") if isinstance(data.get("characters"), list) else panel.characters
    panel.props = data.get("props") if isinstance(data.get("props"), list) else panel.props
    panel.image_url = ""
    panel.generation_task_id = ""
    panel.save()
    segment.grid_image_url = ""
    segment.save(update_fields=["grid_image_url"])
    image_model = str(payload.get("model") or segment.project.image_model).strip()
    if image_model and segment.project.image_model != image_model:
        segment.project.image_model = image_model
        segment.project.save(update_fields=["image_model", "updated_at"])
    _submit_panel_image(panel, image_model, _panel_references(segment, asset_ids))
    return serialize_panel(panel)


def refresh_panel_images(segment: StorySegment) -> list[dict]:
    for panel in segment.panels.all():
        if panel.image_url or not panel.generation_task_id:
            continue
        try:
            result = get_ai_image_task_result(panel.generation_task_id, segment.project.image_model)
        except AIImageError as exc:
            logger.exception("分镜图任务查询失败 segment=%s panel=%s", segment.id, panel.panel_no)
            raise StoryboardError(f"第 {panel.panel_no} 格任务查询失败：{exc}", exc.status) from exc
        images = result.get("images") or []
        if images:
            panel.image_url = _persist_storyboard_png(str(images[0]), segment.project.user, "panels", segment.project.image_model)
            panel.save(update_fields=["image_url"])
        elif str(result.get("status") or "").lower() in {"completed", "complete", "succeeded", "success", "done"}:
            raise StoryboardError(f"第 {panel.panel_no} 格生成完成但未返回图片地址，请重新生成", 502)
        elif str(result.get("status") or "").lower() in {"failed", "error"}:
            raise StoryboardError(f"第 {panel.panel_no} 格生成失败：{result.get('error') or '模型任务失败'}", 502)
    return [serialize_panel(panel) for panel in segment.panels.all()]


def _download_image(url: str, user=None) -> Image.Image:
    stored = _stored_image_bytes(url, user)
    if stored:
        raw = stored[0]
    elif url.startswith("data:image/"):
        raw = base64.b64decode(url.split(",", 1)[1])
    else:
        try:
            response = requests.get(url, headers={"Accept": "image/*"}, timeout=30)
            response.raise_for_status()
            raw = response.content
        except Exception as exc:
            logger.exception("分镜图片下载失败 url=%s", url)
            raise StoryboardError("分镜图片下载失败，请稍后重试", 502) from exc
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
        image.load()
        return image.convert("RGB")
    except Exception as exc:
        raise StoryboardError("分镜图片格式无法合成", 502) from exc


def _upload_grid(image_bytes: bytes, user) -> str:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise StoryboardError("COS 配置不完整，无法保存分镜板成图", 500)
    key = f"images/storyboards/grids/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.png"
    client = CosS3Client(CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY))
    try:
        client.put_object(Bucket=settings.COS_BUCKET, Body=image_bytes, Key=key, ContentType="image/png")
    except Exception as exc:
        logger.exception("分镜板上传 COS 失败")
        raise StoryboardError("分镜板图片保存失败，请稍后重试", 502) from exc
    base_url = str(settings.COS_BASE_URL or "").rstrip("/")
    url = f"{base_url}/{key}" if base_url else f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    UploadedFileRecord.objects.create(user=user, key=key, url=url, content_type="image/png", size=len(image_bytes))
    return url


def compose_grid(segment: StorySegment, user) -> str:
    panels = list(segment.panels.all())
    if len(panels) != segment.panel_count or any(not panel.image_url for panel in panels):
        raise StoryboardError(f"{segment.panel_count} 张分镜图全部生成完成后才能合成")
    columns = 4 if segment.panel_count == 12 else 3
    rows = (segment.panel_count + columns - 1) // columns
    tile_width, tile_height = 640, 360
    canvas = Image.new("RGB", (tile_width * columns, tile_height * rows), "#111111")
    for index, panel in enumerate(panels):
        image = ImageOps.fit(_download_image(panel.image_url, user), (tile_width, tile_height), method=Image.Resampling.LANCZOS)
        x = (index % columns) * tile_width
        y = (index // columns) * tile_height
        canvas.paste(image, (x, y))
    output = io.BytesIO()
    canvas.save(output, "PNG", optimize=True)
    url = _upload_grid(output.getvalue(), user)
    segment.grid_image_url = url
    segment.save(update_fields=["grid_image_url"])
    return url


def generate_video_prompts(segment: StorySegment) -> list[dict]:
    panels = list(segment.panels.all())
    if len(panels) != segment.panel_count:
        raise StoryboardError("请先生成完整分镜板")
    storyboard = [
        {
            "panel_no": panel.panel_no,
            "shot_type": panel.shot_type,
            "screen_description": panel.screen_description,
            "image_url": panel.image_url,
        }
        for panel in panels
    ]
    result = _call_storyboard_json(
        get_storyboard_video_prompt(),
        (
            f"故事剧情：\n{segment.original_text or segment.summary}\n\n"
            f"用户补充描述：\n{segment.supplementary_description or '无'}\n\n"
            f"分镜板图片：{segment.grid_image_url or '尚未合成，请依据逐格图片和描述'}\n"
            f"分镜逐格信息：\n{json.dumps(storyboard, ensure_ascii=False)}"
        ),
        segment.project.analysis_model,
        "视频分镜提示词模型",
    )
    prompts = [item for item in (result.get("panels") or []) if isinstance(item, dict)]
    prompt_by_no = {}
    for item in prompts:
        try:
            panel_no = int(item.get("panel_no"))
        except (TypeError, ValueError):
            continue
        text = str(item.get("video_prompt") or "").strip()
        if text:
            prompt_by_no[panel_no] = text
    if len(prompt_by_no) != segment.panel_count:
        raise StoryboardError(f"模型未返回完整的 {segment.panel_count} 条视频分镜提示词，请重试", 502)
    durations = []
    for text in prompt_by_no.values():
        match = re.search(r"[（(]\s*(\d+(?:\.\d+)?)\s*秒\s*[）)]", text)
        if not match or not text.startswith("【") or "】【" not in text:
            raise StoryboardError("视频分镜提示词格式不正确，请重试", 502)
        durations.append(float(match.group(1)))
    if abs(sum(durations) - 15) > 0.01:
        raise StoryboardError("视频分镜总时长必须为 15 秒，请重试", 502)
    for panel in panels:
        panel.video_prompt = prompt_by_no[panel.panel_no]
        panel.save(update_fields=["video_prompt"])
    return [serialize_panel(panel) for panel in segment.panels.all()]
