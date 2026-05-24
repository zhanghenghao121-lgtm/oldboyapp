import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _error_detail(resp) -> str:
    detail = ""
    try:
        body = resp.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif isinstance(error, str):
            detail = error
        if not detail and isinstance(body, dict):
            detail = str(body.get("message") or body.get("detail") or "")
    except Exception:
        detail = str(getattr(resp, "text", "") or "")
    return " ".join(detail.split())[:240]


def chat_completion(runtime: dict, payload: dict, *, service_name: str = "模型"):
    api_key = str(runtime.get("api_key") or "").strip()
    base_url = str(runtime.get("base_url") or "").strip().rstrip("/")
    if not api_key or not base_url:
        raise LLMClientError(f"{service_name}配置不完整，请先在后台补全 API 地址和 API Key", 500)
    try:
        resp = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_MANGA_TIMEOUT", 180)), 30),
        )
    except Exception as exc:
        logger.exception("%s请求失败", service_name)
        raise LLMClientError(f"{service_name}请求失败，请稍后重试", 502) from exc
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.error("%s返回错误 status=%s detail=%s", service_name, resp.status_code, detail)
        raise LLMClientError(f"{service_name}服务错误({resp.status_code})：{detail}" if detail else f"{service_name}服务错误({resp.status_code})", 502)
    try:
        return resp.json()
    except Exception as exc:
        logger.exception("%s返回非 JSON", service_name)
        raise LLMClientError(f"{service_name}返回格式异常", 502) from exc


def image_generation(base_url: str, api_key: str, payload: dict, *, service_name: str = "生图模型"):
    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/images/generations",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_IMAGE_SUBMIT_TIMEOUT", 60)), 20),
        )
    except Exception as exc:
        logger.exception("%s请求失败", service_name)
        raise LLMClientError(f"{service_name}请求失败，请稍后重试", 502) from exc
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.error("%s返回错误 status=%s detail=%s", service_name, resp.status_code, detail)
        raise LLMClientError(f"{service_name}服务错误({resp.status_code})：{detail}" if detail else f"{service_name}服务错误({resp.status_code})", 502)
    try:
        return resp.json()
    except Exception as exc:
        logger.exception("%s返回非 JSON", service_name)
        raise LLMClientError(f"{service_name}返回格式异常", 502) from exc


def task_status(base_url: str, api_key: str, task_id: str, *, service_name: str = "生图任务"):
    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=max(int(getattr(settings, "AI_IMAGE_QUERY_TIMEOUT", 30)), 10),
        )
    except Exception as exc:
        logger.exception("%s查询失败", service_name)
        raise LLMClientError(f"{service_name}查询失败，请稍后重试", 502) from exc
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.error("%s返回错误 status=%s detail=%s", service_name, resp.status_code, detail)
        raise LLMClientError(f"{service_name}服务错误({resp.status_code})：{detail}" if detail else f"{service_name}服务错误({resp.status_code})", 502)
    try:
        return resp.json()
    except Exception as exc:
        logger.exception("%s返回非 JSON", service_name)
        raise LLMClientError(f"{service_name}返回格式异常", 502) from exc
