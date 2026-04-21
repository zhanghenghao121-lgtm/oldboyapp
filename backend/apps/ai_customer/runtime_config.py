from django.conf import settings

from apps.console.models import SiteConfig


DEFAULT_MANGA_STORYBOARD_PROMPT = (
    "你是专业的漫画导演与分镜编剧。"
    "请把用户提供的剧本、小说片段、策划文案或剧情设定，整理成适合 AI 漫剧创作的分镜稿。"
    "输出必须结构化、清晰、可复制，不要解释。"
    "\n输出要求："
    "\n1. 先给出作品标题和整体风格建议。"
    "\n2. 按“第1镜、第2镜...”顺序输出。"
    "\n3. 每个分镜至少包含：场景、景别/镜头、画面内容、人物动作/表情、台词/旁白、画面提示词。"
    "\n4. 画面提示词要适合中文生图模型理解，突出人物、环境、构图、光线与情绪。"
    "\n5. 若原文信息不足，不得胡编关键剧情，可用“[待补充]”标记。"
    "\n6. 保持中文输出，格式整洁，适合直接复制到后续创作流程。"
)

DEFAULT_MANGA_IMAGE_PROMPT = "每段分镜提示词优化为图片描述作为首帧。"


def _read_config_value(key: str, default: str = "") -> str:
    try:
        value = (
            SiteConfig.objects.filter(key=key)
            .values_list("value", flat=True)
            .first()
        )
    except Exception:
        value = None
    text = str(value or "").strip()
    return text or str(default or "").strip()


def get_assistant_llm_config():
    return {
        "base_url": _read_config_value(
            SiteConfig.KEY_AI_ASSISTANT_BASE_URL,
            getattr(settings, "AI_CS_LLM_BASE_URL", ""),
        ),
        "api_key": _read_config_value(
            SiteConfig.KEY_AI_ASSISTANT_API_KEY,
            getattr(settings, "AI_CS_LLM_API_KEY", ""),
        ),
        "model": _read_config_value(
            SiteConfig.KEY_AI_ASSISTANT_MODEL,
            getattr(settings, "AI_CS_LLM_MODEL", ""),
        ),
    }


def get_manga_llm_config():
    assistant = get_assistant_llm_config()
    return {
        "base_url": _read_config_value(SiteConfig.KEY_AI_MANGA_BASE_URL, assistant["base_url"]),
        "api_key": _read_config_value(SiteConfig.KEY_AI_MANGA_API_KEY, assistant["api_key"]),
        "model": _read_config_value(SiteConfig.KEY_AI_MANGA_MODEL, assistant["model"]),
    }


def get_runtime_llm_config(preset: str = "assistant"):
    if str(preset or "").strip().lower() == "manga":
        return get_manga_llm_config()
    return get_assistant_llm_config()


def get_manga_storyboard_prompt():
    return _read_config_value(
        SiteConfig.KEY_AI_MANGA_STORYBOARD_PROMPT,
        DEFAULT_MANGA_STORYBOARD_PROMPT,
    )


def get_manga_image_prompt():
    return _read_config_value(
        SiteConfig.KEY_AI_MANGA_IMAGE_PROMPT,
        DEFAULT_MANGA_IMAGE_PROMPT,
    )
