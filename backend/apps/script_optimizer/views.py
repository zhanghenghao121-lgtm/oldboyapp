import requests
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

DEFAULT_STORYBOARD_PROMPT = "将输入的剧本生成分镜提示词，模板是分镜号、分镜画面、景别、特效。"
DEFAULT_PARAGRAPH_PROMPT = (
    "将输入的剧本按“**秒～**秒”时间段格式拆分，输出总时长不超过15秒的分镜提示词。"
    "每条包含：时间段、分镜号、分镜画面、景别、特效。"
)


def ok(data=None):
    return Response({"ok": True, **({"data": data} if data is not None else {})})


def bad(message, status=400):
    return Response({"ok": False, "message": message}, status=status)


def _call_deepseek(system_prompt: str, user_prompt: str):
    api_key = settings.DEEPSEEK_API_KEY.strip()
    if not api_key:
        return None, "DEEPSEEK_API_KEY 未配置"

    base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": "deepseek-reasoner",
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
    prompt = str(request.data.get("prompt", "")).strip() or DEFAULT_STORYBOARD_PROMPT
    if not script_text:
        return bad("请输入剧本内容")
    if len(script_text) > 10000:
        return bad("剧本最多10000字")

    system_prompt = (
        "你是专业分镜导演。输出必须结构化、可直接用于绘图/拍摄。"
        "不要输出无关解释。"
    )
    user_prompt = f"要求：{prompt}\n\n剧本：\n{script_text}"
    content, err = _call_deepseek(system_prompt, user_prompt)
    if err:
        return bad(err, 502)
    return ok({"result": content, "mode": "storyboard"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def paragraph_storyboard(request):
    script_text = str(request.data.get("script", "")).strip()
    prompt = str(request.data.get("prompt", "")).strip() or DEFAULT_PARAGRAPH_PROMPT
    if not script_text:
        return bad("请输入剧本内容")
    if len(script_text) > 10000:
        return bad("剧本最多10000字")

    system_prompt = (
        "你是动画分镜导演。把内容压缩为15秒内的段落分镜。"
        "每行必须以“X秒～Y秒”开头，并保持时间连续。"
    )
    user_prompt = f"要求：{prompt}\n\n剧本：\n{script_text}"
    content, err = _call_deepseek(system_prompt, user_prompt)
    if err:
        return bad(err, 502)
    return ok({"result": content, "mode": "paragraph_storyboard"})
