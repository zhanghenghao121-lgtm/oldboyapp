import base64
import io
import json
import logging
import re
import uuid
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageOps
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
    get_storyboard_leaf_split_prompt,
    get_storyboard_llm_config,
    get_storyboard_panel_prompt,
    get_storyboard_scene_split_prompt,
)
from apps.storage.models import UploadedFileRecord

logger = logging.getLogger(__name__)

MAX_SPLIT_DEPTH = 3
ASSET_TYPE_BY_GROUP = {
    "characters": StoryboardAsset.TYPE_CHARACTER,
    "scenes": StoryboardAsset.TYPE_SCENE,
    "props": StoryboardAsset.TYPE_PROP,
    "costumes": StoryboardAsset.TYPE_COSTUME,
    "style_refs": StoryboardAsset.TYPE_STYLE,
}


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
        body = chat_completion(runtime, payload, service_name=label)
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
        raise StoryboardError("只能为可生成九宫格的剧情小段上传素材")
    asset_type = str(payload.get("asset_type") or "").strip()
    if asset_type not in {item[0] for item in StoryboardAsset.TYPE_CHOICES}:
        raise StoryboardError("素材类型不支持")
    name = str(payload.get("name") or "").strip()[:255]
    image_url = str(payload.get("image_url") or "").strip()
    if not name or not image_url:
        raise StoryboardError("素材名称和图片地址不能为空")
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


@transaction.atomic
def generate_panels(segment: StorySegment) -> list[dict]:
    if not segment.is_leaf:
        raise StoryboardError("请选择已拆解完成的剧情小段")
    assets = [serialize_asset(asset) for asset in segment.assets.all()]
    result = _call_storyboard_json(
        get_storyboard_panel_prompt(),
        (
            f"剧情段标题：{segment.title}\n场景：{segment.scene_name}\n情绪：{segment.mood}\n"
            f"项目画面风格：{segment.project.style_preset or '未指定'}\n"
            f"剧情内容：\n{segment.original_text or segment.summary}\n\n"
            f"已上传素材参考：\n{json.dumps(assets, ensure_ascii=False)}"
        ),
        segment.project.analysis_model,
        "九宫格分镜规划模型",
    )
    panels = [item for item in (result.get("panels") or []) if isinstance(item, dict)]
    if len(panels) != 9:
        raise StoryboardError("模型未返回完整的 9 个分镜，请重试或调整提示词", 502)
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


def generate_panel_images(segment: StorySegment, model: str = "") -> list[dict]:
    panels = list(segment.panels.all())
    if len(panels) != 9:
        raise StoryboardError("请先生成完整九宫格分镜提示词")
    references = [
        {
            "field": "storyboard_asset",
            "label": f"{asset.get_asset_type_display()}：{asset.name}",
            "name": asset.name,
            "data_url": asset.image_url,
        }
        for asset in segment.assets.all()
    ]
    image_model = str(model or segment.project.image_model).strip()
    for panel in panels:
        if panel.image_url or panel.generation_task_id:
            continue
        try:
            result = submit_ai_image_generation(
                mode="text",
                prompt=panel.image_prompt,
                model=image_model,
                size=segment.project.aspect_ratio,
                resolution="1k",
                reference_images=references,
            )
        except AIImageError as exc:
            logger.exception("九宫格生图失败 segment=%s panel=%s", segment.id, panel.panel_no)
            raise StoryboardError(f"第 {panel.panel_no} 格生成失败：{exc}", exc.status) from exc
        panel.generation_task_id = str(result.get("task_id") or "")
        panel.image_url = str((result.get("images") or [""])[0] or "")
        panel.save(update_fields=["generation_task_id", "image_url"])
    return [serialize_panel(panel) for panel in segment.panels.all()]


def refresh_panel_images(segment: StorySegment) -> list[dict]:
    for panel in segment.panels.all():
        if panel.image_url or not panel.generation_task_id:
            continue
        try:
            result = get_ai_image_task_result(panel.generation_task_id)
        except AIImageError as exc:
            logger.exception("九宫格任务查询失败 segment=%s panel=%s", segment.id, panel.panel_no)
            raise StoryboardError(f"第 {panel.panel_no} 格任务查询失败：{exc}", exc.status) from exc
        images = result.get("images") or []
        if images:
            panel.image_url = str(images[0])
            panel.save(update_fields=["image_url"])
        elif str(result.get("status") or "").lower() in {"failed", "error"}:
            raise StoryboardError(f"第 {panel.panel_no} 格生成失败：{result.get('error') or '模型任务失败'}", 502)
    return [serialize_panel(panel) for panel in segment.panels.all()]


def _download_image(url: str) -> Image.Image:
    if url.startswith("data:image/"):
        raw = base64.b64decode(url.split(",", 1)[1])
    else:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            raw = response.content
        except Exception as exc:
            logger.exception("分镜图片下载失败 url=%s", url)
            raise StoryboardError("分镜图片下载失败，请稍后重试", 502) from exc
    try:
        return ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    except Exception as exc:
        raise StoryboardError("分镜图片格式无法合成", 502) from exc


def _upload_grid(image_bytes: bytes, user) -> str:
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise StoryboardError("COS 配置不完整，无法保存九宫格成图", 500)
    key = f"images/storyboards/grids/{datetime.now().strftime('%Y/%m/%d')}/{uuid.uuid4().hex}.jpg"
    client = CosS3Client(CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY))
    try:
        client.put_object(Bucket=settings.COS_BUCKET, Body=image_bytes, Key=key, ContentType="image/jpeg")
    except Exception as exc:
        logger.exception("九宫格上传 COS 失败")
        raise StoryboardError("九宫格图片保存失败，请稍后重试", 502) from exc
    base_url = str(settings.COS_BASE_URL or "").rstrip("/")
    url = f"{base_url}/{key}" if base_url else f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    UploadedFileRecord.objects.create(user=user, key=key, url=url, content_type="image/jpeg", size=len(image_bytes))
    return url


def compose_grid(segment: StorySegment, user) -> str:
    panels = list(segment.panels.all())
    if len(panels) != 9 or any(not panel.image_url for panel in panels):
        raise StoryboardError("九张分镜图全部生成完成后才能合成")
    tile_width, tile_height, footer = 640, 360, 40
    canvas = Image.new("RGB", (tile_width * 3, (tile_height + footer) * 3), "#111111")
    draw = ImageDraw.Draw(canvas)
    for index, panel in enumerate(panels):
        image = ImageOps.fit(_download_image(panel.image_url), (tile_width, tile_height), method=Image.Resampling.LANCZOS)
        x = (index % 3) * tile_width
        y = (index // 3) * (tile_height + footer)
        canvas.paste(image, (x, y))
        draw.rectangle((x, y + tile_height, x + tile_width, y + tile_height + footer), fill="#111111")
        draw.text((x + 16, y + tile_height + 13), f"#{panel.panel_no:02d}", fill="#ffffff")
    output = io.BytesIO()
    canvas.save(output, "JPEG", quality=92, optimize=True)
    url = _upload_grid(output.getvalue(), user)
    segment.grid_image_url = url
    segment.save(update_fields=["grid_image_url"])
    return url
