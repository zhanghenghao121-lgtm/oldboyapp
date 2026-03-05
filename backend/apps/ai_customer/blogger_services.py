import base64
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from qcloud_cos import CosConfig, CosS3Client

from apps.ai_customer.models import AiBloggerAsset, AiBloggerPost, AiBloggerVideoTask, AiHotItem
from apps.storage.models import UploadedFileRecord


class BloggerError(Exception):
    def __init__(self, message: str, status: int = 500):
        super().__init__(message)
        self.status = status


def _json_or_raise(resp):
    try:
        return resp.json()
    except ValueError:
        raise BloggerError("上游服务返回非JSON格式", 502)


def _llm_complete(system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
    base_url = settings.AI_CS_LLM_BASE_URL.rstrip("/")
    api_key = (settings.AI_CS_LLM_API_KEY or "").strip()
    model = settings.AI_CS_LLM_MODEL
    if not api_key:
        raise BloggerError("AI模型密钥未配置", 500)

    payload = {
        "model": model,
        "stream": False,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    resp = requests.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=max(int(getattr(settings, "AI_BLOGGER_LLM_TIMEOUT", 90)), 20),
    )
    if resp.status_code >= 400:
        raise BloggerError(f"文案模型调用失败({resp.status_code})", 502)
    body = _json_or_raise(resp)
    text = ""
    if isinstance(body, dict):
        choices = body.get("choices") or []
        if choices and isinstance(choices[0], dict):
            text = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise BloggerError("文案模型未返回有效内容", 502)
    return text


def gen_title(hot_word: str, style_prompt: str = "") -> str:
    system_prompt = "你是资深短视频标题策划，请输出一个吸睛标题。只输出标题，不要解释。"
    user_prompt = f"热点词：{hot_word}\n风格：{style_prompt or '二次元热血'}\n要求：20字以内，情绪饱满。"
    title = _llm_complete(system_prompt, user_prompt, temperature=0.8)
    return title.splitlines()[0][:60].strip("《》\"' ") or f"{hot_word}爆款解读"


def gen_copy(hot_word: str, title: str, style_prompt: str = "") -> str:
    system_prompt = (
        "你是短视频爆款文案助手，输出3段结构：开场钩子、核心观点、结尾引导。"
        "风格鲜明、可口播。只输出正文。"
    )
    user_prompt = f"热点词：{hot_word}\n标题：{title}\n风格：{style_prompt or '二次元热血'}\n长度：180-260字。"
    return _llm_complete(system_prompt, user_prompt, temperature=0.7)


def _ark_base_url() -> str:
    return (getattr(settings, "ARK_BASE_URL", "") or settings.ARK_IMAGE_BASE_URL).rstrip("/")


def fetch_hotwords(limit: int = 50, force: bool = False) -> Dict[str, Any]:
    ttl = max(int(getattr(settings, "HOTWORDS_CACHE_TTL", 1200)), 60)
    cache_key = f"ai_blogger:hotwords:{int(limit)}"
    if not force:
        cached = cache.get(cache_key)
        if isinstance(cached, list) and cached:
            return {"items": cached[:limit], "cached": True}

    url = (getattr(settings, "AA1_HOT_URL", "") or "").strip()
    fallback_url = (getattr(settings, "AA1_HOT_URL_FALLBACK", "") or "").strip()
    if not url and not fallback_url:
        rows = list(AiHotItem.objects.order_by("position", "-id")[:limit])
        items = [{"word": row.word, "position": row.position, "hot_value": row.hot_value} for row in rows]
        return {"items": items, "cached": False}

    timeout_s = max(int(getattr(settings, "AA1_HOT_TIMEOUT", 12)), 3)
    proxy_url = (getattr(settings, "AA1_HOT_PROXY", "") or "").strip()
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
    candidates = [item for item in [url, fallback_url] if item]

    last_error = ""
    resp = None
    for candidate in candidates:
        try:
            resp = requests.get(candidate, timeout=timeout_s, proxies=proxies)
        except requests.RequestException as exc:
            last_error = str(exc)
            continue
        if resp.status_code >= 400:
            last_error = f"热点接口失败({resp.status_code})"
            resp = None
            continue
        break
    if resp is None:
        raise BloggerError(f"热点接口不可用：{last_error or 'unknown'}", 502)
    body = _json_or_raise(resp)

    payload_list = []
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            payload_list = data.get("word_list") or data.get("list") or []
        elif isinstance(data, list):
            payload_list = data
    elif isinstance(body, list):
        payload_list = body

    items = []
    now = timezone.now()
    for idx, item in enumerate(payload_list, start=1):
        if not isinstance(item, dict):
            continue
        word = str(item.get("word") or item.get("title") or "").strip()
        if not word:
            continue
        position = item.get("position") or item.get("rank") or idx
        hot_value = str(item.get("hot_value") or item.get("hot") or item.get("value") or "").strip()
        items.append({"word": word, "position": int(position), "hot_value": hot_value})
        AiHotItem.objects.update_or_create(
            source="aa1_douyin_hot",
            word=word,
            defaults={
                "position": int(position),
                "hot_value": hot_value[:64],
                "raw_json": item,
                "fetched_at": now,
            },
        )
        if len(items) >= limit:
            break

    cache.set(cache_key, items, ttl)
    return {"items": items, "cached": False}


def _download_bytes(url: str, timeout: int = 20) -> bytes:
    resp = requests.get(url, timeout=timeout)
    if resp.status_code >= 400:
        raise BloggerError(f"资源下载失败({resp.status_code})", 502)
    return resp.content or b""


def _upload_bytes_to_cos(user, key: str, body: bytes, content_type: str):
    if not body:
        raise BloggerError("文件内容为空", 500)
    if not all([settings.COS_SECRET_ID, settings.COS_SECRET_KEY, settings.COS_BUCKET, settings.COS_REGION]):
        raise BloggerError("COS配置不完整", 500)
    config = CosConfig(Region=settings.COS_REGION, SecretId=settings.COS_SECRET_ID, SecretKey=settings.COS_SECRET_KEY)
    client = CosS3Client(config)
    try:
        client.put_object(
            Bucket=settings.COS_BUCKET,
            Body=body,
            Key=key,
            ContentType=content_type,
        )
    except Exception as exc:
        raise BloggerError(f"上传COS失败: {exc}", 502)

    if settings.COS_BASE_URL:
        url = f"{settings.COS_BASE_URL.rstrip('/')}/{key}"
    else:
        url = f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    UploadedFileRecord.objects.create(user=user, key=key, url=url, content_type=content_type, size=len(body))
    return url


def _ratio_hint(ratio: str) -> str:
    if ratio == "16:9":
        return "横版构图，适合视频封面，主体居中"
    return "竖版构图，适合短视频首帧，主体清晰"


def _parse_image_item(item: Dict[str, Any]) -> Dict[str, Any]:
    url = str(item.get("url") or "").strip()
    b64 = str(item.get("b64_json") or "").strip()
    if url:
        return {"kind": "url", "value": url}
    if b64:
        return {"kind": "b64", "value": b64}
    raise BloggerError("生图结果缺少url/b64_json", 502)


def generate_post_images(post: AiBloggerPost) -> List[AiBloggerAsset]:
    api_key = (settings.ARK_API_KEY or "").strip()
    if not api_key:
        raise BloggerError("ARK_API_KEY 未配置", 500)
    model = getattr(settings, "SEEDREAM_MODEL", "doubao-seedream-4-5-251128")
    image_count = max(1, min(int(post.image_count or 1), 3))
    size = getattr(settings, "AI_BLOGGER_IMAGE_SIZE", "2K")
    base_prompt = (
        f"热点：{post.hot_word}\n"
        f"标题：{post.title}\n"
        f"文案核心：{post.copy[:200]}\n"
        f"风格：{post.style_prompt or '二次元霓虹'}\n"
        f"要求：{_ratio_hint(post.ratio)}，高对比，高细节，适合社交媒体封面。"
    )
    assets = []
    for idx in range(image_count):
        payload = {
            "model": model,
            "prompt": f"{base_prompt}\n变体序号：{idx + 1}",
            "size": size,
            "output_format": "png",
            "watermark": False,
        }
        resp = requests.post(
            f"{_ark_base_url()}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_BLOGGER_IMAGE_TIMEOUT", 90)), 20),
        )
        if resp.status_code >= 400:
            raise BloggerError(f"生图失败({resp.status_code})", 502)
        body = _json_or_raise(resp)
        items = body.get("data") if isinstance(body, dict) else None
        if not isinstance(items, list) or not items:
            raise BloggerError("生图返回为空", 502)
        ref = _parse_image_item(items[0] if isinstance(items[0], dict) else {})
        if ref["kind"] == "url":
            img_bytes = _download_bytes(ref["value"], timeout=20)
        else:
            try:
                img_bytes = base64.b64decode(ref["value"])
            except Exception:
                raise BloggerError("生图base64解析失败", 502)
        key = f"ai_blogger/images/{post.id}/{uuid.uuid4().hex}.png"
        url = _upload_bytes_to_cos(post.user, key, img_bytes, "image/png")
        asset = AiBloggerAsset.objects.create(
            post=post,
            type=AiBloggerAsset.TYPE_IMAGE,
            cos_key=key,
            url=url,
            meta_json={"model": model, "size": size},
        )
        assets.append(asset)
    return assets


def _find_video_url(data: Any) -> str:
    if isinstance(data, str):
        if data.startswith("http") and (".mp4" in data or "video" in data):
            return data
        return ""
    if isinstance(data, list):
        for item in data:
            found = _find_video_url(item)
            if found:
                return found
        return ""
    if not isinstance(data, dict):
        return ""
    for key in ("video_url", "url", "download_url"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith("http") and (".mp4" in value or "video" in value):
            return value
    for key in ("video", "output", "result", "data", "outputs"):
        found = _find_video_url(data.get(key))
        if found:
            return found
    return ""


def create_seedance_task(post: AiBloggerPost, image_url: str, task: AiBloggerVideoTask) -> str:
    api_key = (settings.ARK_API_KEY or "").strip()
    if not api_key:
        raise BloggerError("ARK_API_KEY 未配置", 500)
    model = getattr(settings, "SEEDANCE_MODEL", "doubao-seedance-1-5-pro-251215")
    prompt = (
        f"围绕热点《{post.hot_word}》，以{post.style_prompt or '二次元叙事'}风格生成短视频。"
        f"标题：{post.title}。文案：{post.copy[:360]}。镜头有推进和转场，节奏清晰。"
    )
    payload = {
        "model": model,
        "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ],
        "generate_audio": bool(task.generate_audio),
        "ratio": task.ratio,
        "duration": int(task.duration),
        "watermark": bool(task.watermark),
    }
    resp = requests.post(
        f"{_ark_base_url()}/contents/generations/tasks",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=max(int(getattr(settings, "AI_BLOGGER_VIDEO_CREATE_TIMEOUT", 60)), 15),
    )
    if resp.status_code >= 400:
        raise BloggerError(f"创建视频任务失败({resp.status_code})", 502)
    body = _json_or_raise(resp)
    if not isinstance(body, dict):
        raise BloggerError("视频任务返回结构异常", 502)
    task_id = str(body.get("id") or body.get("task_id") or (body.get("data") or {}).get("id") or "").strip()
    if not task_id:
        raise BloggerError("视频任务ID为空", 502)
    return task_id


def poll_seedance_task(task_id: str) -> Dict[str, Any]:
    api_key = (settings.ARK_API_KEY or "").strip()
    if not api_key:
        raise BloggerError("ARK_API_KEY 未配置", 500)
    resp = requests.get(
        f"{_ark_base_url()}/contents/generations/tasks/{task_id}",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=max(int(getattr(settings, "AI_BLOGGER_VIDEO_QUERY_TIMEOUT", 30)), 10),
    )
    if resp.status_code >= 400:
        raise BloggerError(f"查询视频任务失败({resp.status_code})", 502)
    body = _json_or_raise(resp)
    data = body.get("data") if isinstance(body, dict) else None
    root = data if isinstance(data, dict) else (body if isinstance(body, dict) else {})
    status = str(root.get("status") or root.get("state") or "").strip().lower()
    if not status:
        status = "running"
    video_url = _find_video_url(root)
    return {"status": status, "video_url": video_url, "raw": body}


def process_post_generation(post_id: int):
    post = AiBloggerPost.objects.select_related("user").filter(id=post_id).first()
    if not post:
        return
    if post.status_text == AiBloggerPost.STATUS_SUCCESS:
        return

    post.status_text = AiBloggerPost.STATUS_RUNNING
    post.stage_text = AiBloggerPost.STAGE_TITLE
    post.error_text = ""
    post.save(update_fields=["status_text", "stage_text", "error_text", "updated_at"])

    title = gen_title(post.hot_word, post.style_prompt)
    post.title = title
    post.stage_text = AiBloggerPost.STAGE_COPY
    post.save(update_fields=["title", "stage_text", "updated_at"])

    copy_text = gen_copy(post.hot_word, title, post.style_prompt)
    post.copy = copy_text
    post.stage_text = AiBloggerPost.STAGE_IMAGES
    post.save(update_fields=["copy", "stage_text", "updated_at"])

    assets = generate_post_images(post)
    if assets and not post.selected_cover_key:
        post.selected_cover_key = assets[0].cos_key
    post.status_text = AiBloggerPost.STATUS_SUCCESS
    post.stage_text = AiBloggerPost.STAGE_DONE
    post.error_text = ""
    post.save(update_fields=["selected_cover_key", "status_text", "stage_text", "error_text", "updated_at"])


def process_video_generation(video_task_id: int):
    task = AiBloggerVideoTask.objects.select_related("post", "post__user").filter(id=video_task_id).first()
    if not task:
        return
    if task.status_video == AiBloggerVideoTask.STATUS_SUCCESS:
        return

    task.status_video = AiBloggerVideoTask.STATUS_RUNNING
    task.error_text = ""
    task.save(update_fields=["status_video", "error_text", "updated_at"])

    post = task.post
    cover = None
    if post.selected_cover_key:
        cover = post.assets.filter(type=AiBloggerAsset.TYPE_IMAGE, cos_key=post.selected_cover_key).first()
    if not cover:
        cover = post.assets.filter(type=AiBloggerAsset.TYPE_IMAGE).first()
    if not cover or not cover.url:
        raise BloggerError("缺少封面图片，无法生成视频", 400)

    seedance_task_id = create_seedance_task(post, cover.url, task)
    task.seedance_task_id = seedance_task_id
    task.save(update_fields=["seedance_task_id", "updated_at"])

    max_polls = max(int(getattr(settings, "AI_BLOGGER_VIDEO_MAX_POLLS", 60)), 10)
    interval_s = max(float(getattr(settings, "AI_BLOGGER_VIDEO_POLL_INTERVAL", 3)), 1.0)
    for _ in range(max_polls):
        result = poll_seedance_task(seedance_task_id)
        status = str(result.get("status") or "").lower()
        if status in {"succeeded", "success", "completed", "done"}:
            video_url = str(result.get("video_url") or "").strip()
            if not video_url:
                raise BloggerError("视频任务完成但未返回视频地址", 502)
            video_bytes = _download_bytes(video_url, timeout=40)
            key = f"ai_blogger/videos/{post.id}/{uuid.uuid4().hex}.mp4"
            final_url = _upload_bytes_to_cos(post.user, key, video_bytes, "video/mp4")
            asset = AiBloggerAsset.objects.create(
                post=post,
                type=AiBloggerAsset.TYPE_VIDEO,
                cos_key=key,
                url=final_url,
                meta_json={"seedance_task_id": seedance_task_id, "created_at": datetime.now().isoformat()},
            )
            task.video_asset = asset
            task.status_video = AiBloggerVideoTask.STATUS_SUCCESS
            task.error_text = ""
            task.save(update_fields=["video_asset", "status_video", "error_text", "updated_at"])
            return
        if status in {"failed", "error", "cancelled", "canceled"}:
            raise BloggerError("视频生成失败，请更换文案或封面后重试", 502)
        time.sleep(interval_s)

    raise BloggerError("视频生成超时，请稍后重试", 504)
