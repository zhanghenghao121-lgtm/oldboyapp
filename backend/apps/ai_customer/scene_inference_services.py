from __future__ import annotations

import logging
import re

from django.utils import timezone

from apps.ai_customer.ai_image_services import (
    AIImageError,
    get_ai_image_task_result,
    submit_ai_image_generation,
)
from apps.ai_customer.models import SceneInferenceJob, SceneInferenceProject
from apps.ai_customer.runtime_config import get_ai_image_config
from apps.ai_customer.scene_inference_prompts import (
    DEFAULT_SCENE_INFERENCE_LEFT_PROMPT,
    DEFAULT_SCENE_INFERENCE_PANORAMA_PROMPT,
    DEFAULT_SCENE_INFERENCE_RIGHT_PROMPT,
    DEFAULT_SCENE_INFERENCE_TOP_PROMPT,
)
from apps.ai_customer.storyboard_services import (
    StoryboardError,
    _persist_storyboard_png,
    _reference_image_data_url,
)
from apps.console.models import SiteConfig
from apps.storage.models import UploadedFileRecord

logger = logging.getLogger(__name__)

TERMINAL_SUCCESS = {"completed", "complete", "succeeded", "success", "done"}
TERMINAL_FAILED = {"failed", "failure", "error", "cancelled", "canceled"}
VIEW_JOBS = [
    SceneInferenceJob.TYPE_LEFT,
    SceneInferenceJob.TYPE_RIGHT,
    SceneInferenceJob.TYPE_TOP,
]
JOB_FIELD = {
    SceneInferenceJob.TYPE_LEFT: "left_image_url",
    SceneInferenceJob.TYPE_RIGHT: "right_image_url",
    SceneInferenceJob.TYPE_TOP: "top_image_url",
    SceneInferenceJob.TYPE_PANORAMA: "panorama_image_url",
}
JOB_LABEL = {
    SceneInferenceJob.TYPE_LEFT: "左侧面图",
    SceneInferenceJob.TYPE_RIGHT: "右侧面图",
    SceneInferenceJob.TYPE_TOP: "俯瞰图",
    SceneInferenceJob.TYPE_PANORAMA: "equirectangular 2:1 全景图",
    SceneInferenceJob.TYPE_SCREENSHOT_ENHANCE: "高清修复截屏",
}
PROMPT_KEYS = {
    SceneInferenceJob.TYPE_LEFT: (SiteConfig.KEY_SCENE_INFERENCE_LEFT_PROMPT, DEFAULT_SCENE_INFERENCE_LEFT_PROMPT),
    SceneInferenceJob.TYPE_RIGHT: (SiteConfig.KEY_SCENE_INFERENCE_RIGHT_PROMPT, DEFAULT_SCENE_INFERENCE_RIGHT_PROMPT),
    SceneInferenceJob.TYPE_TOP: (SiteConfig.KEY_SCENE_INFERENCE_TOP_PROMPT, DEFAULT_SCENE_INFERENCE_TOP_PROMPT),
    SceneInferenceJob.TYPE_PANORAMA: (SiteConfig.KEY_SCENE_INFERENCE_PANORAMA_PROMPT, DEFAULT_SCENE_INFERENCE_PANORAMA_PROMPT),
}
SCENE_SCREENSHOT_ENHANCE_PROMPT = (
    "保持原图的场景构图、视角、透视关系、物体位置、色调和画风完全不变，"
    "不新增人物或物体，不改变场景布局，只进行高清修复和细节增强。"
    "提升整体清晰度，增强墙面、地面、家具、门窗、建筑材质的纹理细节，"
    "边缘更加清晰锐利，光影层次更自然，空间感更强，修复模糊和低清区域，"
    "减少噪点和压缩痕迹，画面干净细腻，高清4K画质。"
)


class SceneInferenceError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _clean_text(value, default: str = "") -> str:
    return str(value or default or "").strip()


def _owned_upload(user, image_url: str) -> bool:
    text = _clean_text(image_url)
    if not text:
        return False
    return UploadedFileRecord.objects.filter(user=user, url=text).exists() or UploadedFileRecord.objects.filter(user=user, key=text).exists()


def _validate_uploaded_image(user, image_url: str, label: str) -> str:
    text = _clean_text(image_url)
    if not text:
        raise SceneInferenceError(f"请上传{label}")
    if not _owned_upload(user, text):
        raise SceneInferenceError(f"{label}不存在或无权访问", 404)
    return text


def _read_prompt(job_type: str) -> str:
    key, default = PROMPT_KEYS[job_type]
    value = SiteConfig.objects.filter(key=key).values_list("value", flat=True).first()
    return _clean_text(value, default)


def _render_template(template: str, context: dict) -> str:
    text = str(template or "")
    for key, value in context.items():
        text = text.replace("{{" + key + "}}", str(value))
        text = text.replace("{" + key + "}", str(value))
    return text.strip()


def _model_label(model_key: str) -> str:
    runtime = get_ai_image_config(model_key)
    return _clean_text(runtime.get("label") or runtime.get("model") or model_key, "未命名模型")


def _prompt_for(project: SceneInferenceProject, job_type: str) -> str:
    output_size = "2:1" if job_type == SceneInferenceJob.TYPE_PANORAMA else "16:9"
    target_view = JOB_LABEL.get(job_type, "目标视角")
    reference_order = (
        "参考图顺序：第 1 张是用户上传的正面图，第 2 张是用户上传的反打图。"
        if job_type != SceneInferenceJob.TYPE_PANORAMA
        else "参考图顺序：第 1 张正面图，第 2 张反打图，第 3 张左侧面图，第 4 张右侧面图，第 5 张俯瞰图。"
    )
    source_lock = (
        "\n\n【同一场景硬性约束】\n"
        f"{reference_order}\n"
        f"目标：只补全这个同一空间的{target_view}，输入图是唯一事实来源。\n"
        "必须保留输入图中的空间类型、室内/室外属性、建筑结构、地面材质、门窗/院墙/屋檐/家具/道具的位置关系和光线方向。\n"
        "如果输入是室外院落，就必须仍然是同一室外院落；如果输入是室内房间，就必须仍然是同一室内房间。\n"
        "严禁生成与输入图无关的新地点、新房间、新院落、新建筑风格或新的主体物件；严禁把室外改成室内，或把室内改成室外。\n"
        "无法从正反打确认的区域只能做最小、低存在感的合理补全，不能凭空重建一个全新场景。\n"
        "最终画面应像真实摄影机在同一个场地换到目标方位拍摄，而不是重新设计的概念图。"
    )
    context = {
        "scene_style": "严格保持正面图与反打图的空间类型、建筑结构、画风、材质、光线、色调和时代背景一致",
        "output_size": output_size,
        "model_name": _model_label(project.model_key),
        "extra_requirements": "画面无人物、无文字、无水印、无 UI，空间关系稳定可信，不得生成与输入图不一致的新场景",
    }
    return f"{_render_template(_read_prompt(job_type), context)}{source_lock}"


def _generation_reference_url(image_url: str, user) -> str:
    text = _clean_text(image_url)
    if text.startswith("data:image/"):
        return text
    return _reference_image_data_url(text, user)


def _references(project: SceneInferenceProject, job_type: str) -> list[dict]:
    items = [
        ("正面图", "front", project.front_image_url),
        ("反打图", "back", project.back_image_url),
    ]
    if job_type == SceneInferenceJob.TYPE_PANORAMA:
        items.extend(
            [
                ("左侧面图", "left", project.left_image_url),
                ("右侧面图", "right", project.right_image_url),
                ("俯瞰图", "top", project.top_image_url),
            ]
        )
    refs = []
    for label, field, url in items:
        if not url:
            continue
        refs.append(
            {
                "field": field,
                "label": label,
                "name": label,
                "data_url": _generation_reference_url(url, project.user),
            }
        )
    return refs


def serialize_job(job: SceneInferenceJob) -> dict:
    return {
        "id": job.id,
        "job_type": job.job_type,
        "label": JOB_LABEL.get(job.job_type, job.job_type),
        "model_key": job.model_key,
        "status": job.status,
        "progress": job.progress,
        "task_id": job.task_id,
        "image_url": job.image_url,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "finished_at": job.finished_at,
    }


def serialize_scene_inference_project(project: SceneInferenceProject, include_jobs: bool = True) -> dict:
    data = {
        "id": project.id,
        "title": project.title,
        "model_key": project.model_key,
        "status": project.status,
        "front_image_url": project.front_image_url,
        "back_image_url": project.back_image_url,
        "left_image_url": project.left_image_url,
        "right_image_url": project.right_image_url,
        "top_image_url": project.top_image_url,
        "panorama_image_url": project.panorama_image_url,
        "error_message": project.error_message,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }
    if include_jobs:
        data["jobs"] = [serialize_job(job) for job in project.jobs.all()]
    return data


def create_scene_inference_project(user, payload: dict) -> SceneInferenceProject:
    title = _clean_text(payload.get("title"), "场景推理")
    model_key = _clean_text(payload.get("model_key") or payload.get("model"), "gpt-image-2")
    front_image_url = _validate_uploaded_image(user, payload.get("front_image_url"), "正面图")
    back_image_url = _validate_uploaded_image(user, payload.get("back_image_url"), "反打图")
    return SceneInferenceProject.objects.create(
        user=user,
        title=title[:255],
        model_key=model_key[:100],
        front_image_url=front_image_url,
        back_image_url=back_image_url,
    )


def _image_folder(job_type: str) -> str:
    suffix = re.sub(r"[^a-zA-Z0-9_-]", "", job_type.replace("generate_", "")) or "scene"
    return f"scene_inference_{suffix}"


def _finish_job_with_image(job: SceneInferenceJob, image_ref: str) -> None:
    try:
        image_url = _persist_storyboard_png(image_ref, job.project.user, _image_folder(job.job_type), job.model_key)
    except StoryboardError as exc:
        raise SceneInferenceError(str(exc), exc.status) from exc
    job.image_url = image_url
    job.status = SceneInferenceJob.STATUS_SUCCESS
    job.progress = 100
    job.output_payload = {**(job.output_payload or {}), "image_url": image_url}
    job.finished_at = timezone.now()
    job.error_message = ""
    job.save(update_fields=["image_url", "status", "progress", "output_payload", "finished_at", "error_message", "updated_at"])
    project_field = JOB_FIELD.get(job.job_type)
    if project_field:
        setattr(job.project, project_field, image_url)
        job.project.error_message = ""
        job.project.save(update_fields=[project_field, "error_message", "updated_at"])


def enhance_scene_screenshot(project: SceneInferenceProject, payload: dict) -> dict:
    image_url = _validate_uploaded_image(project.user, payload.get("image_url"), "截屏图")
    model_key = _clean_text(payload.get("model_key") or payload.get("model") or project.model_key, project.model_key)
    references = [
        {
            "field": "panorama_screenshot",
            "label": "当前全景视角截屏",
            "name": "当前全景视角截屏",
            "data_url": _generation_reference_url(image_url, project.user),
        }
    ]
    job = SceneInferenceJob.objects.create(
        project=project,
        job_type=SceneInferenceJob.TYPE_SCREENSHOT_ENHANCE,
        model_key=model_key,
        status=SceneInferenceJob.STATUS_RUNNING,
        progress=5,
        prompt_snapshot=SCENE_SCREENSHOT_ENHANCE_PROMPT,
        input_payload={"image_url": image_url, "size": "16:9", "resolution": "4k"},
    )
    try:
        result = submit_ai_image_generation(
            prompt=SCENE_SCREENSHOT_ENHANCE_PROMPT,
            model=model_key,
            size="16:9",
            resolution="4k",
            reference_images=references,
        )
    except AIImageError as exc:
        job.status = SceneInferenceJob.STATUS_FAILED
        job.error_message = str(exc)
        job.progress = 100
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "progress", "finished_at", "updated_at"])
        raise SceneInferenceError(f"高清修复失败：{exc}", exc.status) from exc
    job.task_id = _clean_text(result.get("task_id"))
    job.output_payload = result
    image_ref = _clean_text((result.get("images") or [""])[0] if isinstance(result.get("images"), list) else "")
    if image_ref:
        _finish_job_with_image(job, image_ref)
    else:
        if not job.task_id:
            job.status = SceneInferenceJob.STATUS_FAILED
            job.error_message = "高清修复未返回任务ID，请重新截屏"
            job.progress = 100
            job.finished_at = timezone.now()
            job.save(update_fields=["status", "error_message", "progress", "finished_at", "updated_at"])
            raise SceneInferenceError(job.error_message, 502)
        job.progress = 15
        job.save(update_fields=["task_id", "output_payload", "progress", "updated_at"])
    return serialize_job(job)


def _set_project_status(project: SceneInferenceProject) -> None:
    latest = {}
    for job in SceneInferenceJob.objects.filter(project=project).order_by("-created_at", "-id"):
        latest.setdefault(job.job_type, job)
    jobs = [latest[job_type] for job_type in VIEW_JOBS if job_type in latest]
    panorama_job = latest.get(SceneInferenceJob.TYPE_PANORAMA)
    if panorama_job and (
        project.status in {
            SceneInferenceProject.STATUS_PANORAMA_RUNNING,
            SceneInferenceProject.STATUS_PANORAMA_DONE,
            SceneInferenceProject.STATUS_FAILED,
        }
        or project.panorama_image_url
    ):
        jobs.append(panorama_job)
    if any(job.status == SceneInferenceJob.STATUS_FAILED for job in jobs):
        project.status = SceneInferenceProject.STATUS_FAILED
        failed = next((job for job in jobs if job.status == SceneInferenceJob.STATUS_FAILED), None)
        project.error_message = failed.error_message if failed else project.error_message
    elif any(job.status in {SceneInferenceJob.STATUS_PENDING, SceneInferenceJob.STATUS_RUNNING} for job in jobs):
        project.status = (
            SceneInferenceProject.STATUS_PANORAMA_RUNNING
            if any(job.job_type == SceneInferenceJob.TYPE_PANORAMA and job.status in {SceneInferenceJob.STATUS_PENDING, SceneInferenceJob.STATUS_RUNNING} for job in jobs)
            else SceneInferenceProject.STATUS_INFERENCE_RUNNING
        )
    elif project.panorama_image_url:
        project.status = SceneInferenceProject.STATUS_PANORAMA_DONE
        project.error_message = ""
    elif project.left_image_url and project.right_image_url and project.top_image_url:
        project.status = SceneInferenceProject.STATUS_INFERENCE_DONE
        project.error_message = ""
    else:
        project.status = SceneInferenceProject.STATUS_DRAFT
    project.save(update_fields=["status", "error_message", "updated_at"])


def _submit_job(project: SceneInferenceProject, job_type: str) -> SceneInferenceJob:
    prompt = _prompt_for(project, job_type)
    references = _references(project, job_type)
    job = SceneInferenceJob.objects.create(
        project=project,
        job_type=job_type,
        model_key=project.model_key,
        status=SceneInferenceJob.STATUS_RUNNING,
        progress=5,
        prompt_snapshot=prompt,
        input_payload={
            "reference_count": len(references),
            "reference_labels": [item["label"] for item in references],
            "size": "2:1" if job_type == SceneInferenceJob.TYPE_PANORAMA else "16:9",
        },
    )
    try:
        result = submit_ai_image_generation(
            prompt=prompt,
            model=project.model_key,
            size="2:1" if job_type == SceneInferenceJob.TYPE_PANORAMA else "16:9",
            resolution="2k" if job_type == SceneInferenceJob.TYPE_PANORAMA else "1k",
            reference_images=references,
        )
    except AIImageError as exc:
        job.status = SceneInferenceJob.STATUS_FAILED
        job.error_message = str(exc)
        job.progress = 100
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "progress", "finished_at", "updated_at"])
        raise SceneInferenceError(f"{JOB_LABEL.get(job_type, '场景图')}生成失败：{exc}", exc.status) from exc

    job.task_id = _clean_text(result.get("task_id"))
    job.output_payload = result
    image_ref = _clean_text((result.get("images") or [""])[0] if isinstance(result.get("images"), list) else "")
    if image_ref:
        _finish_job_with_image(job, image_ref)
    else:
        job.progress = 15
        job.save(update_fields=["task_id", "output_payload", "progress", "updated_at"])
    return job


def generate_scene_inference_views(project: SceneInferenceProject, payload: dict | None = None) -> dict:
    payload = payload or {}
    _validate_uploaded_image(project.user, project.front_image_url, "正面图")
    _validate_uploaded_image(project.user, project.back_image_url, "反打图")
    model_key = _clean_text(payload.get("model_key") or payload.get("model") or project.model_key, project.model_key)
    project.model_key = model_key[:100]
    project.status = SceneInferenceProject.STATUS_INFERENCE_RUNNING
    project.left_image_url = ""
    project.right_image_url = ""
    project.top_image_url = ""
    project.panorama_image_url = ""
    project.error_message = ""
    project.save(
        update_fields=[
            "model_key",
            "status",
            "left_image_url",
            "right_image_url",
            "top_image_url",
            "panorama_image_url",
            "error_message",
            "updated_at",
        ]
    )
    for job_type in VIEW_JOBS:
        try:
            _submit_job(project, job_type)
        except SceneInferenceError as exc:
            project.status = SceneInferenceProject.STATUS_FAILED
            project.error_message = str(exc)
            project.save(update_fields=["status", "error_message", "updated_at"])
            raise
    project.refresh_from_db()
    _set_project_status(project)
    return serialize_scene_inference_project(project)


def _refresh_job(job: SceneInferenceJob) -> None:
    if job.status not in {SceneInferenceJob.STATUS_PENDING, SceneInferenceJob.STATUS_RUNNING}:
        return
    if not job.task_id:
        return
    try:
        result = get_ai_image_task_result(job.task_id, job.model_key)
    except AIImageError as exc:
        logger.exception("场景推理任务查询失败 job=%s", job.id)
        job.status = SceneInferenceJob.STATUS_FAILED
        job.error_message = str(exc)
        job.progress = 100
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error_message", "progress", "finished_at", "updated_at"])
        return
    job.output_payload = result
    job.progress = int(result.get("progress") or job.progress or 0)
    images = result.get("images") or []
    if images:
        _finish_job_with_image(job, str(images[0]))
        return
    status = _clean_text(result.get("status")).lower()
    if status in TERMINAL_SUCCESS:
        job.status = SceneInferenceJob.STATUS_FAILED
        job.error_message = "生成完成但未返回图片地址，请重新生成"
        job.progress = 100
        job.finished_at = timezone.now()
    elif status in TERMINAL_FAILED:
        job.status = SceneInferenceJob.STATUS_FAILED
        job.error_message = _clean_text(result.get("error"), "模型任务失败")
        job.progress = 100
        job.finished_at = timezone.now()
    else:
        job.status = SceneInferenceJob.STATUS_RUNNING
    job.save(update_fields=["output_payload", "progress", "status", "error_message", "finished_at", "updated_at"])


def refresh_scene_inference_project(project: SceneInferenceProject) -> dict:
    for job in project.jobs.filter(status__in=[SceneInferenceJob.STATUS_PENDING, SceneInferenceJob.STATUS_RUNNING]).select_related("project__user"):
        _refresh_job(job)
    project.refresh_from_db()
    _set_project_status(project)
    return serialize_scene_inference_project(project)


def generate_scene_panorama(project: SceneInferenceProject, payload: dict | None = None) -> dict:
    payload = payload or {}
    refresh_scene_inference_project(project)
    project.refresh_from_db()
    missing = [
        label
        for label, url in [
            ("正面图", project.front_image_url),
            ("反打图", project.back_image_url),
            ("左侧面图", project.left_image_url),
            ("右侧面图", project.right_image_url),
            ("俯瞰图", project.top_image_url),
        ]
        if not url
    ]
    if missing:
        raise SceneInferenceError(f"请先生成完整视角图：缺少{'、'.join(missing)}")
    model_key = _clean_text(payload.get("model_key") or payload.get("model") or project.model_key, project.model_key)
    project.model_key = model_key[:100]
    project.status = SceneInferenceProject.STATUS_PANORAMA_RUNNING
    project.panorama_image_url = ""
    project.error_message = ""
    project.save(update_fields=["model_key", "status", "panorama_image_url", "error_message", "updated_at"])
    try:
        _submit_job(project, SceneInferenceJob.TYPE_PANORAMA)
    except SceneInferenceError as exc:
        project.status = SceneInferenceProject.STATUS_FAILED
        project.error_message = str(exc)
        project.save(update_fields=["status", "error_message", "updated_at"])
        raise
    project.refresh_from_db()
    _set_project_status(project)
    return serialize_scene_inference_project(project)
