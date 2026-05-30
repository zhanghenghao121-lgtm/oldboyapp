from django.conf import settings

from apps.console.models import SiteConfig
from apps.ai_customer.storyboard_prompts import (
    DEFAULT_STORYBOARD_ASSET_PROMPT,
    DEFAULT_STORYBOARD_LEAF_SPLIT_PROMPT,
    DEFAULT_STORYBOARD_PANEL_PROMPT,
    DEFAULT_STORYBOARD_SCENE_SPLIT_PROMPT,
    DEFAULT_STORYBOARD_SINGLE_PANEL_PROMPT,
    DEFAULT_STORYBOARD_VIDEO_PROMPT,
)

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


def get_ai_image_configs():
    gpt_image = {
        "id": "gpt-image-2",
        "label": "GPT-Image-2",
        "provider": "apimart",
        "base_url": _read_config_value(
            SiteConfig.KEY_AI_IMAGE_BASE_URL,
            "https://api.apimart.ai/v1",
        ),
        "api_key": _read_config_value(SiteConfig.KEY_AI_IMAGE_API_KEY, ""),
        "model": _read_config_value(SiteConfig.KEY_AI_IMAGE_MODEL, "gpt-image-2"),
    }
    doubao = {
        "id": "doubao-seedream-5-lite",
        "label": "Doubao-Seedream-5.0-lite",
        "provider": "volcengine",
        "base_url": _read_config_value(
            SiteConfig.KEY_AI_IMAGE_DOUBAO_BASE_URL,
            "https://ark.cn-beijing.volces.com/api/v3",
        ),
        "api_key": _read_config_value(SiteConfig.KEY_AI_IMAGE_DOUBAO_API_KEY, ""),
        "model": _read_config_value(
            SiteConfig.KEY_AI_IMAGE_DOUBAO_MODEL,
            "doubao-seedream-5-0-260128",
        ),
    }
    return [gpt_image, doubao]


def get_storyboard_llm_configs():
    return [
        {
            "id": "deepseek-v4-pro",
            "label": "DeepSeek V4 Pro",
            "base_url": _read_config_value(
                SiteConfig.KEY_STORYBOARD_DEEPSEEK_BASE_URL,
                getattr(settings, "AI_CS_LLM_BASE_URL", ""),
            ),
            "api_key": _read_config_value(
                SiteConfig.KEY_STORYBOARD_DEEPSEEK_API_KEY,
                getattr(settings, "AI_CS_LLM_API_KEY", ""),
            ),
            "model": _read_config_value(
                SiteConfig.KEY_STORYBOARD_DEEPSEEK_MODEL,
                "deepseek-v4-pro",
            ),
        },
        {
            "id": "doubao-seed-2-0-pro-260215",
            "label": "Doubao-Seed-2.0-Pro",
            "base_url": _read_config_value(
                SiteConfig.KEY_STORYBOARD_DOUBAO_BASE_URL,
                "https://ark.cn-beijing.volces.com/api/v3",
            ),
            "api_key": _read_config_value(SiteConfig.KEY_STORYBOARD_DOUBAO_API_KEY, ""),
            "model": _read_config_value(
                SiteConfig.KEY_STORYBOARD_DOUBAO_MODEL,
                "doubao-seed-2-0-pro-260215",
            ),
        },
    ]


def get_storyboard_llm_config(model: str = ""):
    requested = str(model or "").strip()
    options = get_storyboard_llm_configs()
    for item in options:
        if requested and requested in {item["id"], item["model"]}:
            return item
    return options[0]


def get_ai_image_config(model: str = ""):
    requested = str(model or "").strip()
    options = get_ai_image_configs()
    for item in options:
        if requested and requested in {item["id"], item["model"]}:
            return item
    return options[0]


def get_remove_bg_api_key():
    return _read_config_value(
        SiteConfig.KEY_REMOVE_BG_API_KEY,
        getattr(settings, "REMOVE_BG_API_KEY", ""),
    )


def get_storyboard_scene_split_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_SCENE_SPLIT_PROMPT,
        DEFAULT_STORYBOARD_SCENE_SPLIT_PROMPT,
    )


def get_storyboard_leaf_split_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_LEAF_SPLIT_PROMPT,
        DEFAULT_STORYBOARD_LEAF_SPLIT_PROMPT,
    )


def get_storyboard_asset_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_ASSET_PROMPT,
        DEFAULT_STORYBOARD_ASSET_PROMPT,
    )


def get_storyboard_panel_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_PANEL_PROMPT,
        DEFAULT_STORYBOARD_PANEL_PROMPT,
    )


def get_storyboard_single_panel_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_SINGLE_PANEL_PROMPT,
        DEFAULT_STORYBOARD_SINGLE_PANEL_PROMPT,
    )


def get_storyboard_video_prompt():
    return _read_config_value(
        SiteConfig.KEY_STORYBOARD_VIDEO_PROMPT,
        DEFAULT_STORYBOARD_VIDEO_PROMPT,
    )
