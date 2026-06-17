import logging
from urllib.parse import urlparse

import requests
from django.conf import settings
from requests import ConnectionError, Timeout
from requests.exceptions import InvalidSchema, MissingSchema, SSLError


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


def _request_failure_detail(exc: Exception) -> str:
    if isinstance(exc, MissingSchema):
        return "API 地址缺少 http:// 或 https://"
    if isinstance(exc, InvalidSchema):
        return "API 地址格式不正确"
    if isinstance(exc, SSLError):
        return "SSL 证书校验失败，请检查服务器证书链或网络代理"
    if isinstance(exc, ConnectionError):
        return "无法连接到模型服务，请检查服务器网络、DNS、防火墙或代理配置"
    return "请检查 API 地址、服务器网络和模型服务状态"


def _safe_host(base_url: str) -> str:
    parsed = urlparse(str(base_url or "").strip())
    return parsed.netloc or parsed.path.split("/")[0]


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
        raise LLMClientError(f"{service_name}请求失败：{_request_failure_detail(exc)}", 502) from exc
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.error("%s返回错误 status=%s detail=%s", service_name, resp.status_code, detail)
        if resp.status_code in {401, 403}:
            raise LLMClientError(
                f"{service_name}认证失败，请在后台“AI模型配置”检查该模型的 API 地址和 API Key",
                502,
            )
        raise LLMClientError(f"{service_name}服务错误({resp.status_code})：{detail}" if detail else f"{service_name}服务错误({resp.status_code})", 502)
    try:
        return resp.json()
    except Exception as exc:
        logger.exception("%s返回非 JSON", service_name)
        raise LLMClientError(f"{service_name}返回格式异常", 502) from exc


def image_generation(base_url: str, api_key: str, payload: dict, *, service_name: str = "生图模型"):
    endpoint = f"{base_url.rstrip('/')}/images/generations"
    try:
        resp = requests.post(
            endpoint,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=max(int(getattr(settings, "AI_IMAGE_SUBMIT_TIMEOUT", 180)), 60),
        )
    except Timeout as exc:
        logger.exception("%s提交超时", service_name)
        raise LLMClientError(f"{service_name}提交超时，请稍后刷新任务或降低参考图尺寸后重试", 504) from exc
    except Exception as exc:
        logger.exception("%s请求失败 host=%s", service_name, _safe_host(base_url))
        raise LLMClientError(f"{service_name}请求失败：{_request_failure_detail(exc)}", 502) from exc
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
        raise LLMClientError(f"{service_name}查询失败：{_request_failure_detail(exc)}", 502) from exc
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        logger.error("%s返回错误 status=%s detail=%s", service_name, resp.status_code, detail)
        raise LLMClientError(f"{service_name}服务错误({resp.status_code})：{detail}" if detail else f"{service_name}服务错误({resp.status_code})", 502)
    try:
        return resp.json()
    except Exception as exc:
        logger.exception("%s返回非 JSON", service_name)
        raise LLMClientError(f"{service_name}返回格式异常", 502) from exc
