import requests
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

User = get_user_model()
POINTS_COST_PER_CHAR = Decimal("0.01")

DEFAULT_STORYBOARD_PROMPT = "将输入的剧本生成分镜提示词，模板是分镜号、分镜画面、景别、特效。"
DEFAULT_PARAGRAPH_PROMPT = (
    "将输入的剧本按“**秒～**秒”时间段格式拆分，输出总时长不超过15秒的分镜提示词。"
    "每条包含：时间段、分镜号、分镜画面、景别、特效。"
)


def _get_default_prompt(key: str, fallback: str):
    try:
        from apps.console.models import SiteConfig

        obj = SiteConfig.objects.filter(key=key).first()
        if obj and obj.value.strip():
            return obj.value.strip()
    except Exception:
        pass
    return fallback


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _calc_required_points(script_text: str) -> Decimal:
    return Decimal(len(script_text)) * POINTS_COST_PER_CHAR


def _consume_user_points(user_id: int, required_points: Decimal):
    with transaction.atomic():
        user = User.objects.select_for_update().get(id=user_id)
        balance = Decimal(user.points or 0)
        if balance < required_points:
            return None, f"积分不足（当前 {balance:.2f}，需 {required_points:.2f}）"
        user.points = balance - required_points
        user.save(update_fields=["points"])
        return Decimal(user.points), None


def _refund_user_points(user_id: int, points: Decimal):
    with transaction.atomic():
        user = User.objects.select_for_update().get(id=user_id)
        user.points = Decimal(user.points or 0) + points
        user.save(update_fields=["points"])


def _call_deepseek(system_prompt: str, user_prompt: str):
    api_key = settings.DEEPSEEK_API_KEY.strip()
    if not api_key:
        return None, "DEEPSEEK_API_KEY 未配置"

    base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": settings.DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=90)
    except requests.RequestException:
        return None, "模型服务请求失败，请稍后重试"
    if resp.status_code >= 400:
        return None, f"模型服务错误({resp.status_code})"
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        return None, "模型未返回内容"
    content = (choices[0].get("message") or {}).get("content", "").strip()
    if not content:
        return None, "模型返回为空"
    return content, None


@api_view(["GET"])
@permission_classes([AllowAny])
def ping(request):
    return ok({"module": "script_optimizer", "status": "ready"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def storyboard(request):
    script_text = str(request.data.get("script", "")).strip()
    prompt = str(request.data.get("prompt", "")).strip() or _get_default_prompt(
        "storyboard_default_prompt", DEFAULT_STORYBOARD_PROMPT
    )
    if not script_text:
        return bad("请输入剧本内容")
    if len(script_text) > 10000:
        return bad("剧本最多10000字")
    required_points = _calc_required_points(script_text)
    remaining_points, err = _consume_user_points(request.user.id, required_points)
    if err:
        return bad(err, 402)

    system_prompt = (
        "你是专业分镜导演。输出必须结构化、可直接用于绘图/拍摄。"
        "不要输出无关解释。"
    )
    user_prompt = f"要求：{prompt}\n\n剧本：\n{script_text}"
    content, err = _call_deepseek(system_prompt, user_prompt)
    if err:
        _refund_user_points(request.user.id, required_points)
        return bad(err, 502)
    return ok(
        {
            "result": content,
            "mode": "storyboard",
            "cost_points": float(required_points),
            "remaining_points": float(remaining_points),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def paragraph_storyboard(request):
    script_text = str(request.data.get("script", "")).strip()
    prompt = str(request.data.get("prompt", "")).strip() or _get_default_prompt(
        "paragraph_default_prompt", DEFAULT_PARAGRAPH_PROMPT
    )
    if not script_text:
        return bad("请输入剧本内容")
    if len(script_text) > 10000:
        return bad("剧本最多10000字")
    required_points = _calc_required_points(script_text)
    remaining_points, err = _consume_user_points(request.user.id, required_points)
    if err:
        return bad(err, 402)

    system_prompt = (
        "你是动画分镜导演。把内容压缩为15秒内的段落分镜。"
        "每行必须以“X秒～Y秒”开头，并保持时间连续。"
    )
    user_prompt = f"要求：{prompt}\n\n剧本：\n{script_text}"
    content, err = _call_deepseek(system_prompt, user_prompt)
    if err:
        _refund_user_points(request.user.id, required_points)
        return bad(err, 502)
    return ok(
        {
            "result": content,
            "mode": "paragraph_storyboard",
            "cost_points": float(required_points),
            "remaining_points": float(remaining_points),
        }
    )
