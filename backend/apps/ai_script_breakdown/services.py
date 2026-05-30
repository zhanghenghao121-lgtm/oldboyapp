import json
import logging
import re

from django.db import transaction

from apps.ai_customer.llm_clients import LLMClientError, chat_completion
from apps.ai_customer.runtime_config import get_storyboard_llm_config
from apps.console.models import SiteConfig
from apps.ai_script_breakdown.models import (
    AiScriptAsset,
    AiScriptBreakdownProject,
    AiScriptSceneBlock,
    AiScriptShotLine,
    AiScriptShotSegment,
)
from apps.ai_script_breakdown.prompts import (
    DEFAULT_SCRIPT_ANIME_3D_STYLE_PROMPT,
    DEFAULT_SCRIPT_ASSET_EXTRACT_PROMPT,
    DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT,
    DEFAULT_SCRIPT_POSITION_PROMPT,
    DEFAULT_SCRIPT_SCENE_SPLIT_PROMPT,
    DEFAULT_SCRIPT_SHOT_SEGMENT_PROMPT,
    DEFAULT_SCRIPT_VALIDATE_PROMPT,
)

logger = logging.getLogger(__name__)

STYLE_PROMPT_KEY = {
    AiScriptBreakdownProject.STYLE_LIVE_ACTION: "ai_script_live_action_style_prompt",
    AiScriptBreakdownProject.STYLE_ANIME_3D: "ai_script_anime_3d_style_prompt",
}
STYLE_PROMPT_DEFAULT = {
    AiScriptBreakdownProject.STYLE_LIVE_ACTION: DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT,
    AiScriptBreakdownProject.STYLE_ANIME_3D: DEFAULT_SCRIPT_ANIME_3D_STYLE_PROMPT,
}
PROMPT_DEFAULTS = {
    "ai_script_asset_extract_prompt": DEFAULT_SCRIPT_ASSET_EXTRACT_PROMPT,
    "ai_script_scene_split_prompt": DEFAULT_SCRIPT_SCENE_SPLIT_PROMPT,
    "ai_script_shot_segment_prompt": DEFAULT_SCRIPT_SHOT_SEGMENT_PROMPT,
    "ai_script_position_prompt": DEFAULT_SCRIPT_POSITION_PROMPT,
    "ai_script_validate_prompt": DEFAULT_SCRIPT_VALIDATE_PROMPT,
}
ALLOWED_STYLES = {item[0] for item in AiScriptBreakdownProject.STYLE_CHOICES}
ALLOWED_ASSET_TYPES = {item[0] for item in AiScriptAsset.TYPE_CHOICES}
ALLOWED_VIEWS = {item[0] for item in AiScriptShotSegment.VIEW_CHOICES}


class ScriptBreakdownError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _config_value(key: str, default: str = "") -> str:
    try:
        value = SiteConfig.objects.filter(key=key).values_list("value", flat=True).first()
    except Exception:
        value = None
    return str(value or default or "").strip()


def _style_prompt(style: str) -> str:
    style_key = style if style in ALLOWED_STYLES else AiScriptBreakdownProject.STYLE_LIVE_ACTION
    return _config_value(STYLE_PROMPT_KEY[style_key], STYLE_PROMPT_DEFAULT[style_key])


def _prompt(key: str) -> str:
    return _config_value(key, PROMPT_DEFAULTS[key])


def _render_template(template: str, context: dict) -> str:
    text = template
    for key, value in context.items():
        if not isinstance(value, str):
            value = json.dumps(value, ensure_ascii=False, default=str)
        text = text.replace("{{" + key + "}}", value)
    return text


def _json_content(body: dict, label: str) -> dict:
    content = str((((body.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()
    if not content:
        raise ScriptBreakdownError(f"{label}未返回有效内容", 502)
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
        logger.error("%s JSON解析失败 content=%s", label, content[:700])
        raise ScriptBreakdownError(f"{label}返回格式异常，请重试", 502)
    return data


def _call_script_json(system_prompt: str, user_content: str, model: str, label: str) -> dict:
    runtime = get_storyboard_llm_config(model)
    service_name = f"{label}（{runtime.get('label') or runtime.get('model') or '未命名模型'} / {runtime.get('model') or '-'}）"
    payload = {
        "model": runtime.get("model"),
        "temperature": 0.2,
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
        raise ScriptBreakdownError(str(exc), exc.status) from exc
    return _json_content(body, label)


def serialize_asset(asset: AiScriptAsset) -> dict:
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "name": asset.name,
        "alias": asset.alias,
        "file_url": asset.file_url,
        "ai_description": asset.ai_description,
    }


def serialize_line(line: AiScriptShotLine) -> dict:
    return {
        "id": line.id,
        "shot_size": line.shot_size,
        "description": line.description,
        "dialogue": line.dialogue,
        "line_text": line.line_text,
        "is_continuity_anchor": line.is_continuity_anchor,
        "order": line.order_index,
    }


def serialize_segment(segment: AiScriptShotSegment) -> dict:
    return {
        "id": segment.id,
        "scene_block_id": segment.scene_block_id,
        "segment_title": segment.segment_title,
        "estimated_duration": segment.estimated_duration,
        "style_prompt": segment.style_prompt,
        "copy_text": segment.copy_text,
        "continuity_from_previous": segment.continuity_from_previous,
        "previous_anchor_line": segment.previous_anchor_line,
        "scene_view": segment.scene_view,
        "characters": segment.characters,
        "props": segment.props,
        "position_image_prompt": segment.position_image_prompt,
        "position_layout": segment.position_layout_json,
        "position_image_url": segment.position_image_url,
        "order": segment.order_index,
        "shot_lines": [serialize_line(line) for line in segment.shot_lines.all()],
    }


def serialize_scene(scene: AiScriptSceneBlock) -> dict:
    return {
        "id": scene.id,
        "scene_number": scene.scene_number,
        "scene_name": scene.scene_name,
        "location": scene.location,
        "time_of_day": scene.time_of_day,
        "scene_description": scene.scene_description,
        "front_view_description": scene.front_view_description,
        "reverse_view_description": scene.reverse_view_description,
        "original_text": scene.original_text,
        "characters": scene.characters,
        "props": scene.props,
        "order": scene.order_index,
        "segments": [serialize_segment(segment) for segment in scene.segments.all()],
    }


def serialize_project(project: AiScriptBreakdownProject, include_detail: bool = False) -> dict:
    data = {
        "id": project.id,
        "title": project.title,
        "script_text": project.script_text,
        "selected_style": project.selected_style,
        "max_segment_seconds": project.max_segment_seconds,
        "analysis_model": project.analysis_model,
        "status": project.status,
        "error_message": project.error_message,
        "extracted_assets": project.extracted_assets_json,
        "validation": project.validation_json,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if include_detail:
        data["assets"] = [serialize_asset(asset) for asset in project.assets.all()]
        data["scene_blocks"] = [serialize_scene(scene) for scene in project.scene_blocks.all()]
    return data


def create_project(user, payload: dict) -> AiScriptBreakdownProject:
    script_text = str(payload.get("script_text") or "").strip()
    if len(script_text) < 20:
        raise ScriptBreakdownError("请输入至少 20 个字的剧本内容")
    selected_style = str(payload.get("selected_style") or AiScriptBreakdownProject.STYLE_LIVE_ACTION).strip()
    if selected_style not in ALLOWED_STYLES:
        raise ScriptBreakdownError("拆剧风格不支持")
    try:
        max_seconds = int(payload.get("max_segment_seconds") or 15)
    except (TypeError, ValueError):
        max_seconds = 15
    max_seconds = min(max(max_seconds, 5), 15)
    project = AiScriptBreakdownProject.objects.create(
        user=user,
        title=str(payload.get("title") or "未命名拆剧任务").strip()[:255] or "未命名拆剧任务",
        script_text=script_text,
        selected_style=selected_style,
        max_segment_seconds=max_seconds,
        analysis_model=str(payload.get("analysis_model") or "deepseek-v4-pro").strip()[:100],
    )
    for item in payload.get("assets") or []:
        if not isinstance(item, dict):
            continue
        asset_type = str(item.get("asset_type") or "").strip()
        name = str(item.get("name") or "").strip()
        if asset_type not in ALLOWED_ASSET_TYPES or not name:
            continue
        AiScriptAsset.objects.create(
            project=project,
            asset_type=asset_type,
            name=name[:255],
            alias=str(item.get("alias") or "").strip()[:255],
            file_url=str(item.get("file_url") or "").strip(),
        )
    return project


def _uploaded_assets(project: AiScriptBreakdownProject) -> list[dict]:
    return [serialize_asset(asset) for asset in project.assets.all()]


def _upsert_extracted_assets(project: AiScriptBreakdownProject, extracted: dict) -> None:
    group_to_type = {"scenes": AiScriptAsset.TYPE_SCENE, "characters": AiScriptAsset.TYPE_CHARACTER, "props": AiScriptAsset.TYPE_PROP}
    for group, asset_type in group_to_type.items():
        for item in extracted.get(group) or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()[:255]
            if not name:
                continue
            asset, _ = AiScriptAsset.objects.get_or_create(
                project=project,
                asset_type=asset_type,
                name=name,
                defaults={"alias": str(item.get("matched_uploaded_asset_name") or "").strip()[:255]},
            )
            asset.ai_description = str(item.get("description") or "").strip()
            if item.get("matched_uploaded_asset_name") and not asset.alias:
                asset.alias = str(item["matched_uploaded_asset_name"]).strip()[:255]
            asset.save(update_fields=["ai_description", "alias"])


def _lines_from_copy_text(copy_text: str) -> list[str]:
    return [line.strip() for line in str(copy_text or "").splitlines() if line.strip()]


def _normalize_copy_text(style_prompt: str, shot_lines: list[dict], copy_text: str, previous_anchor: str = "") -> str:
    lines = _lines_from_copy_text(copy_text)
    if not lines or lines[0] != style_prompt:
        lines = [style_prompt] + [line for line in lines if line != style_prompt]
    if previous_anchor and previous_anchor not in lines[1:2]:
        lines.insert(1, previous_anchor)
    has_body_line = any(line not in {style_prompt, previous_anchor} for line in lines)
    if not has_body_line:
        lines.extend(str(item.get("line_text") or "").strip() for item in shot_lines if str(item.get("line_text") or "").strip())
    return "\n".join(lines)


def _last_non_anchor_line(segment: AiScriptShotSegment) -> str:
    line = segment.shot_lines.filter(is_continuity_anchor=False).order_by("-order_index", "-id").first()
    return line.line_text if line else ""


def _save_segment(scene: AiScriptSceneBlock, item: dict, index: int, style_prompt: str, previous_last_line: str) -> AiScriptShotSegment:
    scene_view = str(item.get("scene_view") or AiScriptShotSegment.VIEW_FRONT).strip()
    if scene_view not in ALLOWED_VIEWS:
        scene_view = AiScriptShotSegment.VIEW_MIXED
    try:
        duration = int(item.get("estimated_duration") or 0)
    except (TypeError, ValueError):
        duration = 0
    duration = min(max(duration, 0), scene.project.max_segment_seconds)
    continuity = bool(item.get("continuity_from_previous"))
    previous_anchor = str(item.get("previous_anchor_line") or "").strip()
    if continuity and previous_last_line and not previous_anchor:
        previous_anchor = previous_last_line
    shot_lines = [line for line in (item.get("shot_lines") or []) if isinstance(line, dict)]
    copy_text = _normalize_copy_text(style_prompt, shot_lines, str(item.get("copy_text") or ""), previous_anchor if continuity else "")
    segment = AiScriptShotSegment.objects.create(
        project=scene.project,
        scene_block=scene,
        segment_title=str(item.get("segment_title") or f"{scene.scene_name}-{index}")[:255],
        estimated_duration=duration,
        style_prompt=style_prompt,
        copy_text=copy_text,
        continuity_from_previous=continuity,
        previous_anchor_line=previous_anchor,
        scene_view=scene_view,
        characters=item.get("characters") if isinstance(item.get("characters"), list) else scene.characters,
        props=item.get("props") if isinstance(item.get("props"), list) else scene.props,
        position_image_prompt=str(item.get("position_image_prompt") or ""),
        position_layout_json=item.get("position_layout") if isinstance(item.get("position_layout"), dict) else {},
        order_index=index,
    )
    if continuity and previous_anchor:
        AiScriptShotLine.objects.create(
            segment=segment,
            shot_size="",
            description=previous_anchor,
            line_text=previous_anchor,
            is_continuity_anchor=True,
            order_index=1,
        )
    start_index = 2 if continuity and previous_anchor else 1
    for line_index, line in enumerate(shot_lines, start=start_index):
        line_text = str(line.get("line_text") or "").strip()
        if not line_text:
            shot_size = str(line.get("shot_size") or "中景").strip("【】")
            description = str(line.get("description") or "").strip()
            line_text = f"【{shot_size}】【{description}】" if description else ""
        if not line_text:
            continue
        AiScriptShotLine.objects.create(
            segment=segment,
            shot_size=str(line.get("shot_size") or "").strip("【】"),
            description=str(line.get("description") or ""),
            dialogue=str(line.get("dialogue") or ""),
            line_text=line_text,
            is_continuity_anchor=bool(line.get("is_continuity_anchor")),
            order_index=line_index,
        )
    return segment


def _save_scene_segments(scene: AiScriptSceneBlock, data: dict, style_prompt: str) -> None:
    previous_last_line = ""
    for index, item in enumerate([row for row in (data.get("segments") or []) if isinstance(row, dict)], start=1):
        segment = _save_segment(scene, item, index, style_prompt, previous_last_line)
        previous_last_line = _last_non_anchor_line(segment)


def _scene_payload(scene: AiScriptSceneBlock) -> dict:
    return {
        "scene_number": scene.scene_number,
        "scene_name": scene.scene_name,
        "location": scene.location,
        "time_of_day": scene.time_of_day,
        "scene_description": scene.scene_description,
        "front_view_description": scene.front_view_description,
        "reverse_view_description": scene.reverse_view_description,
        "original_text": scene.original_text,
        "characters": scene.characters,
        "props": scene.props,
    }


def run_project(project: AiScriptBreakdownProject) -> dict:
    project.status = AiScriptBreakdownProject.STATUS_PROCESSING
    project.error_message = ""
    project.save(update_fields=["status", "error_message", "updated_at"])
    project.scene_blocks.all().delete()
    try:
        uploaded_assets = _uploaded_assets(project)
        style_prompt = _style_prompt(project.selected_style)
        extracted = _call_script_json(
            _prompt("ai_script_asset_extract_prompt"),
            (
                f"剧本如下：\n{project.script_text}\n\n"
                f"上传素材如下：\n{json.dumps(uploaded_assets, ensure_ascii=False)}"
            ),
            project.analysis_model,
            "AI拆剧资产提取模型",
        )
        project.extracted_assets_json = extracted
        _upsert_extracted_assets(project, extracted)
        scene_result = _call_script_json(
            _prompt("ai_script_scene_split_prompt"),
            (
                f"剧本如下：\n{project.script_text}\n\n"
                f"已提取资产如下：\n{json.dumps(extracted, ensure_ascii=False)}"
            ),
            project.analysis_model,
            "AI拆剧场景拆解模型",
        )
        scene_items = [item for item in (scene_result.get("scene_blocks") or []) if isinstance(item, dict)]
        if not scene_items:
            raise ScriptBreakdownError("模型未返回可用的场景大段落", 502)
        segment_prompt = _render_template(
            _prompt("ai_script_shot_segment_prompt"),
            {"max_segment_seconds": str(project.max_segment_seconds)},
        )
        for scene_index, item in enumerate(scene_items, start=1):
            scene = AiScriptSceneBlock.objects.create(
                project=project,
                scene_number=str(item.get("scene_number") or "")[:100],
                scene_name=str(item.get("scene_name") or f"场景 {scene_index}")[:255],
                location=str(item.get("location") or "")[:255],
                time_of_day=str(item.get("time_of_day") or "")[:100],
                scene_description=str(item.get("scene_description") or ""),
                front_view_description=str(item.get("front_view_description") or ""),
                reverse_view_description=str(item.get("reverse_view_description") or ""),
                original_text=str(item.get("original_text") or ""),
                characters=item.get("characters") if isinstance(item.get("characters"), list) else [],
                props=item.get("props") if isinstance(item.get("props"), list) else [],
                order_index=int(item.get("order_index") or scene_index),
            )
            segment_result = _call_script_json(
                segment_prompt,
                _render_template(
                    "后台风格提示词：\n{{style_prompt}}\n\n当前场景大段落如下：\n{{scene_block}}\n\n"
                    "上一小段最后一行分镜如下，如果没有则为空：\n{{previous_segment_last_line}}\n\n"
                    "每个小段落剧情时长最多 {{max_segment_seconds}} 秒。",
                    {
                        "style_prompt": style_prompt,
                        "scene_block": _scene_payload(scene),
                        "previous_segment_last_line": "",
                        "max_segment_seconds": str(project.max_segment_seconds),
                    },
                ),
                project.analysis_model,
                "AI拆剧小段落分镜模型",
            )
            _save_scene_segments(scene, segment_result, style_prompt)
        validation = _call_script_json(
            _render_template(
                _prompt("ai_script_validate_prompt"),
                {"max_segment_seconds": str(project.max_segment_seconds)},
            ),
            (
                f"原始剧本：\n{project.script_text}\n\n"
                f"拆剧结果：\n{json.dumps(serialize_project(project, include_detail=True), ensure_ascii=False, default=str)}\n\n"
                f"每段最大秒数：{project.max_segment_seconds}"
            ),
            project.analysis_model,
            "AI拆剧校验模型",
        )
        project.validation_json = validation
        project.status = AiScriptBreakdownProject.STATUS_COMPLETED
        project.save(update_fields=["extracted_assets_json", "validation_json", "status", "updated_at"])
    except ScriptBreakdownError as exc:
        project.status = AiScriptBreakdownProject.STATUS_FAILED
        project.error_message = str(exc)
        project.save(update_fields=["status", "error_message", "updated_at"])
        raise
    return serialize_project(project, include_detail=True)


@transaction.atomic
def regenerate_segment(segment: AiScriptShotSegment) -> dict:
    scene = segment.scene_block
    style_prompt = _style_prompt(segment.project.selected_style)
    previous_segment = (
        AiScriptShotSegment.objects.filter(scene_block=scene, order_index__lt=segment.order_index)
        .order_by("-order_index", "-id")
        .first()
    )
    previous_last_line = _last_non_anchor_line(previous_segment) if previous_segment else ""
    result = _call_script_json(
        _render_template(
            _prompt("ai_script_shot_segment_prompt"),
            {"max_segment_seconds": str(segment.project.max_segment_seconds)},
        ),
        _render_template(
            "后台风格提示词：\n{{style_prompt}}\n\n当前场景大段落如下：\n{{scene_block}}\n\n"
            "上一小段最后一行分镜如下，如果没有则为空：\n{{previous_segment_last_line}}\n\n"
            "只重新生成当前小段落附近的分镜，输出 segments 数组且只包含 1 个小段落。",
            {
                "style_prompt": style_prompt,
                "scene_block": _scene_payload(scene),
                "previous_segment_last_line": previous_last_line,
            },
        ),
        segment.project.analysis_model,
        "AI拆剧小段落重生成模型",
    )
    item = next((row for row in (result.get("segments") or []) if isinstance(row, dict)), None)
    if not item:
        raise ScriptBreakdownError("模型未返回可用的小段落", 502)
    order_index = segment.order_index
    segment.delete()
    updated = _save_segment(scene, item, order_index, style_prompt, previous_last_line)
    return serialize_segment(updated)


@transaction.atomic
def regenerate_position(segment: AiScriptShotSegment) -> dict:
    style_prompt = _style_prompt(segment.project.selected_style)
    result = _call_script_json(
        _prompt("ai_script_position_prompt"),
        (
            f"后台风格提示词：\n{style_prompt}\n\n"
            f"当前小段落：\n{json.dumps(serialize_segment(segment), ensure_ascii=False)}\n\n"
            f"上传素材：\n{json.dumps(_uploaded_assets(segment.project), ensure_ascii=False)}\n\n"
            f"场景正面描述：\n{segment.scene_block.front_view_description}\n\n"
            f"场景反打描述：\n{segment.scene_block.reverse_view_description}"
        ),
        segment.project.analysis_model,
        "AI拆剧站位图模型",
    )
    segment.position_layout_json = result.get("position_layout") if isinstance(result.get("position_layout"), dict) else {}
    segment.position_image_prompt = str(result.get("position_image_prompt") or "")
    segment.save(update_fields=["position_layout_json", "position_image_prompt"])
    return serialize_segment(segment)
