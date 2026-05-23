from django.conf import settings

from apps.console.models import SiteConfig


DEFAULT_MANGA_STORYBOARD_PROMPT = (
    "你是专业的剧本镜头提示词解析师。请把用户提供的剧本、小说片段、策划案或剧情设定解析为视频生成提示词。"
    "\n解析规则："
    "\n1. 只基于原文信息整理，不要改写剧情走向，不要补造关键人物关系。"
    "\n2. 每条提示词必须包含景别/镜头、主体动作、场景环境、光线氛围、关键视觉细节。"
    "\n3. 每条提示词给出 duration_seconds，单条建议 3 到 5 秒；每个段落 group 的总时长必须不超过 15 秒。"
    "\n4. 按剧情顺序分组输出，段落内 shot 连续编号。"
    "\n5. 只输出 JSON，不要 markdown，不要解释。JSON 格式："
    '{"groups":[{"title":"段落 1","shots":[{"prompt":"[景别/镜头] ...","duration_seconds":4}]}]}'
)

DEFAULT_MANGA_3D_STYLE_PROMPT = (
    "你是一名专业提示词工程师、分镜导演和3D动漫短剧导演。请根据剧本内容，优化成适合AI视频生成的多组分镜提示词。"
    "\n风格基调：中国3D古风动漫风格，高质感，电影级分镜与运镜，演员级微表情，高级布光，故事节奏舒适，动作连贯，人物站位稳定，镜头不越轴。"
    "\n每组提示词应包含：场景、人物形象参考图、人物初始站位、剧情内容、镜头拆分。"
    "\n镜头描述必须包含人物表情、人物动作、镜头运动、台词/音效。"
    "\n输出规则："
    "\n1. 景别只能使用：全景、中景、近景、特写、过肩镜头、正反打镜头。"
    "\n2. 使用过肩镜头时，必须注明前景是哪位角色的左肩或右肩。"
    "\n3. 使用正反打镜头时，必须注明当前镜头拍摄哪位角色，例如“正打近景，镜头拍顾知夏”或“反打近景，镜头拍小敏”。"
    "\n4. 正反打镜头只适用于两人短对话，不适用于三人及以上多人长对话。"
    "\n5. 人物台词尽量保持完整，不要将一句台词拆成多段。"
    "\n6. 每段画面都要描述清楚人物在画面左侧、右侧、前景、后景或中央的位置。"
    "\n7. 所有分镜之间人物站位必须连续一致，不要越轴。"
    "\n8. 动作要连贯自然，镜头切换要符合电影逻辑。"
    "\n9. 如果剧情中包含重要道具、法术、表情变化、眼神变化，必须加入特写或近景强化。"
    "\n10. 当出现三人或三人以上的长对话时，必须切分为多个景别：先用全景或中景交代人物站位，再根据说话角色切换近景、过肩镜头或反应特写，避免整段都使用单一中景。"
    "\n11. 多人长对话中，不使用正反打镜头；应使用全景、中景、近景、特写、过肩镜头来组织空间关系。"
    "\n12. 不要输出解释，只输出分镜结果。"
)
DEFAULT_MANGA_REAL_STYLE_PROMPT = (
    "真人影视质感，真实摄影机语言，自然光影和真实表演，场景细节可信，避免动漫化和卡通化。"
)

DEFAULT_AI_IMAGE_REVERSE_PROMPT = (
    "根据参考图生成同一场景的反打镜头画面。"
    "\n参考图1：场景的正面镜头背景。"
    "\n参考图2：同一场景的反打镜头背景。"
    "\n参考图3：正面镜头下的人物完整站位图。"
    "\n\n请以参考图2作为新的背景和摄像机角度，推理参考图3中所有人物在真实三维空间中的位置，并在反打镜头中重新摆放人物。"
    "\n\n重要要求："
    "\n1. 不是镜像翻转参考图3，而是保持人物在场景中的真实空间位置不变，仅切换到反方向摄像机视角。"
    "\n2. 人物之间的前后距离、左右空间关系、遮挡关系要根据反打镜头重新计算。"
    "\n3. 正面镜头中靠近镜头的人物，在反打镜头中应变为远离镜头；正面镜头中远离镜头的人物，在反打镜头中应更靠近镜头。"
    "\n4. 正面镜头中位于场景左侧/右侧的人物，要按照场景真实坐标转换到反打视角，不要简单复制画面左右。"
    "\n5. 所有人物的身份、服装、发型、体型、表情和动作保持一致。"
    "\n6. 背景必须使用参考图2的反打镜头背景，不能使用参考图1的正面背景。"
    "\n7. 保持同一场景、同一时间、同一光线、同一风格、同一镜头高度。"
    "\n8. 不要新增人物，不要减少人物，不要改变人物站位逻辑，不要改变场景布局。"
    "\n9. 画面构图自然，符合影视反打镜头逻辑，不要越轴。"
    "\n\n输出：一张反打镜头下的人物站位画面。"
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


def get_manga_vision_llm_config():
    return {
        "base_url": _read_config_value(
            SiteConfig.KEY_AI_MANGA_VISION_BASE_URL,
            "https://ark.cn-beijing.volces.com/api/v3",
        ),
        "api_key": _read_config_value(SiteConfig.KEY_AI_MANGA_VISION_API_KEY, ""),
        "model": _read_config_value(
            SiteConfig.KEY_AI_MANGA_VISION_MODEL,
            "doubao-seed-2-0-mini-260428",
        ),
    }


def get_ai_image_config():
    return {
        "base_url": _read_config_value(
            SiteConfig.KEY_AI_IMAGE_BASE_URL,
            "https://api.apimart.ai/v1",
        ),
        "api_key": _read_config_value(SiteConfig.KEY_AI_IMAGE_API_KEY, ""),
        "model": _read_config_value(SiteConfig.KEY_AI_IMAGE_MODEL, "gpt-image-2"),
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


def get_ai_image_reverse_prompt():
    return _read_config_value(
        SiteConfig.KEY_AI_IMAGE_REVERSE_PROMPT,
        DEFAULT_AI_IMAGE_REVERSE_PROMPT,
    )


def get_manga_style_prompt(style: str = "3d"):
    normalized = str(style or "").strip().lower()
    if normalized in {"real", "live", "真人", "realistic"}:
        return _read_config_value(
            SiteConfig.KEY_AI_MANGA_REAL_STYLE_PROMPT,
            DEFAULT_MANGA_REAL_STYLE_PROMPT,
        )
    return _read_config_value(
        SiteConfig.KEY_AI_MANGA_3D_STYLE_PROMPT,
        DEFAULT_MANGA_3D_STYLE_PROMPT,
    )
