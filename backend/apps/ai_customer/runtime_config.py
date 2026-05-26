from django.conf import settings

from apps.console.models import SiteConfig
from apps.ai_customer.storyboard_prompts import (
    DEFAULT_STORYBOARD_ASSET_PROMPT,
    DEFAULT_STORYBOARD_LEAF_SPLIT_PROMPT,
    DEFAULT_STORYBOARD_PANEL_PROMPT,
    DEFAULT_STORYBOARD_SCENE_SPLIT_PROMPT,
)

DEFAULT_AI_IMAGE_REVERSE_PROMPT = (
    "你是一名专门为“场景反打镜头站位生成”服务的提示词生成助手。"
    "\n你的任务是：根据用户上传的场景参考图、角色/物品参考图，以及用户通过 @对象 描述的正面镜头站位信息，"
    "自动生成一段高质量、可直接用于图像生成模型的最终提示词，用于生成“同一场景在反打镜头下的人物/物品完整站位图”。"
    "\n\n输入内容定义：参考图1表示场景正面镜头背景；参考图2表示同一场景的反打镜头背景；"
    "角色/物品参考图用于明确每个 @对象 的外观身份。用户文字描述会说明各个 @对象 在参考图1中的位置、朝向、远近、遮挡和相互关系。"
    "\n\n核心任务：识别所有被 @ 提及的角色和物品，理解它们在参考图1正面镜头中的真实三维空间站位，"
    "在不改变人物/物品真实空间位置的前提下，将摄像机切换到参考图2的反打机位，推理并输出反打镜头中的左右位置、前后层次、远近关系、朝向关系和遮挡关系。"
    "\n\n必须遵守：不要镜像翻转；优先依据门、桌子、椅子、窗户、墙面、走廊、沙发、楼梯、前景/中景/远景等场景锚点推理；"
    "正面镜头中靠近镜头的对象在反打镜头中通常更远，正面镜头中远离镜头的对象在反打镜头中通常更近；遮挡关系必须重新计算；不要越轴。"
    "\n\n@对象规则：@角色名 必须严格参考对应图片的性别特征、发型、发色、服装、体型、年龄感和身份辨识特征；"
    "@物品名 必须严格参考对应图片的造型、材质、颜色、比例、类型和识别特征。"
    "\n\n最终提示词必须明确：参考图2是最终画面的背景和机位依据，参考图1只用于理解正面镜头下的站位逻辑和空间关系；"
    "所有 @角色 和 @物品 都必须正确出现；保持同一场景、同一时间、同一光线、同一整体风格；"
    "不新增、不减少、不替换人物或关键物品；不改变场景主体结构；最终画面必须是反打镜头下的完整站位图。"
    "\n\n输出要求：直接输出一段可交给图像生成模型使用的完整中文提示词，不要解释，不要分析过程，不要步骤标题，不要复述系统规则。"
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


def get_ai_image_reverse_prompt():
    return _read_config_value(
        SiteConfig.KEY_AI_IMAGE_REVERSE_PROMPT,
        DEFAULT_AI_IMAGE_REVERSE_PROMPT,
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
