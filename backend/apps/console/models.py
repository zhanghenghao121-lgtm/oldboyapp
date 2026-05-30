from django.conf import settings
from django.db import models


class SiteBackground(models.Model):
    SCENE_LOGIN = "login"
    SCENE_HOME = "home"
    SCENE_PROFILE = "profile"
    SCENE_CHOICES = [
        (SCENE_LOGIN, "登录页"),
        (SCENE_HOME, "首页"),
        (SCENE_PROFILE, "用户信息页"),
    ]

    scene = models.CharField(max_length=32, choices=SCENE_CHOICES, unique=True)
    image_url = models.URLField(max_length=500, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_backgrounds",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scene"]

    def __str__(self):
        return f"{self.scene}: {self.image_url}"


class SiteConfig(models.Model):
    KEY_DEFAULT_AVATAR = "default_avatar_url"
    KEY_STORYBOARD_DEEPSEEK_BASE_URL = "storyboard_deepseek_base_url"
    KEY_STORYBOARD_DEEPSEEK_API_KEY = "storyboard_deepseek_api_key"
    KEY_STORYBOARD_DEEPSEEK_MODEL = "storyboard_deepseek_model"
    KEY_STORYBOARD_DOUBAO_BASE_URL = "storyboard_doubao_base_url"
    KEY_STORYBOARD_DOUBAO_API_KEY = "storyboard_doubao_api_key"
    KEY_STORYBOARD_DOUBAO_MODEL = "storyboard_doubao_model"
    KEY_AI_IMAGE_BASE_URL = "ai_image_base_url"
    KEY_AI_IMAGE_API_KEY = "ai_image_api_key"
    KEY_AI_IMAGE_MODEL = "ai_image_model"
    KEY_AI_IMAGE_DOUBAO_BASE_URL = "ai_image_doubao_base_url"
    KEY_AI_IMAGE_DOUBAO_API_KEY = "ai_image_doubao_api_key"
    KEY_AI_IMAGE_DOUBAO_MODEL = "ai_image_doubao_model"
    KEY_REMOVE_BG_API_KEY = "remove_bg_api_key"
    KEY_STORYBOARD_SCENE_SPLIT_PROMPT = "storyboard_scene_split_prompt"
    KEY_STORYBOARD_LEAF_SPLIT_PROMPT = "storyboard_leaf_split_prompt"
    KEY_STORYBOARD_ASSET_PROMPT = "storyboard_asset_prompt"
    KEY_STORYBOARD_PANEL_PROMPT = "storyboard_panel_prompt"
    KEY_STORYBOARD_SINGLE_PANEL_PROMPT = "storyboard_single_panel_prompt"
    KEY_STORYBOARD_VIDEO_PROMPT = "storyboard_video_prompt"
    KEY_AI_SCRIPT_LIVE_ACTION_STYLE_PROMPT = "ai_script_live_action_style_prompt"
    KEY_AI_SCRIPT_ANIME_3D_STYLE_PROMPT = "ai_script_anime_3d_style_prompt"
    KEY_AI_SCRIPT_ASSET_EXTRACT_PROMPT = "ai_script_asset_extract_prompt"
    KEY_AI_SCRIPT_SCENE_SPLIT_PROMPT = "ai_script_scene_split_prompt"
    KEY_AI_SCRIPT_SHOT_SEGMENT_PROMPT = "ai_script_shot_segment_prompt"
    KEY_AI_SCRIPT_POSITION_PROMPT = "ai_script_position_prompt"
    KEY_AI_SCRIPT_VALIDATE_PROMPT = "ai_script_validate_prompt"
    KEY_SCENE_INFERENCE_LEFT_PROMPT = "scene_inference_left_prompt"
    KEY_SCENE_INFERENCE_RIGHT_PROMPT = "scene_inference_right_prompt"
    KEY_SCENE_INFERENCE_TOP_PROMPT = "scene_inference_top_prompt"
    KEY_SCENE_INFERENCE_PANORAMA_PROMPT = "scene_inference_panorama_prompt"
    KEY_CHOICES = [
        (KEY_DEFAULT_AVATAR, "默认头像URL"),
        (KEY_STORYBOARD_DEEPSEEK_BASE_URL, "故事板 DeepSeek API地址"),
        (KEY_STORYBOARD_DEEPSEEK_API_KEY, "故事板 DeepSeek API Key"),
        (KEY_STORYBOARD_DEEPSEEK_MODEL, "故事板 DeepSeek 模型名称"),
        (KEY_STORYBOARD_DOUBAO_BASE_URL, "故事板 Doubao API地址"),
        (KEY_STORYBOARD_DOUBAO_API_KEY, "故事板 Doubao API Key"),
        (KEY_STORYBOARD_DOUBAO_MODEL, "故事板 Doubao 模型名称"),
        (KEY_AI_IMAGE_BASE_URL, "生图模型API地址"),
        (KEY_AI_IMAGE_API_KEY, "生图模型API Key"),
        (KEY_AI_IMAGE_MODEL, "生图模型名称"),
        (KEY_AI_IMAGE_DOUBAO_BASE_URL, "豆包生图API地址"),
        (KEY_AI_IMAGE_DOUBAO_API_KEY, "豆包生图API Key"),
        (KEY_AI_IMAGE_DOUBAO_MODEL, "豆包生图模型名称"),
        (KEY_REMOVE_BG_API_KEY, "remove.bg API Key"),
        (KEY_STORYBOARD_SCENE_SPLIT_PROMPT, "故事板场景拆分提示词"),
        (KEY_STORYBOARD_LEAF_SPLIT_PROMPT, "故事板分镜适配提示词"),
        (KEY_STORYBOARD_ASSET_PROMPT, "故事板素材提取提示词"),
        (KEY_STORYBOARD_PANEL_PROMPT, "故事板分镜生成提示词"),
        (KEY_STORYBOARD_SINGLE_PANEL_PROMPT, "故事板单格重生成提示词"),
        (KEY_STORYBOARD_VIDEO_PROMPT, "故事板视频分镜提示词"),
        (KEY_AI_SCRIPT_LIVE_ACTION_STYLE_PROMPT, "AI拆剧真人写实风格提示词"),
        (KEY_AI_SCRIPT_ANIME_3D_STYLE_PROMPT, "AI拆剧3D动漫风格提示词"),
        (KEY_AI_SCRIPT_ASSET_EXTRACT_PROMPT, "AI拆剧资产提取提示词"),
        (KEY_AI_SCRIPT_SCENE_SPLIT_PROMPT, "AI拆剧场景拆解提示词"),
        (KEY_AI_SCRIPT_SHOT_SEGMENT_PROMPT, "AI拆剧小段落分镜提示词"),
        (KEY_AI_SCRIPT_POSITION_PROMPT, "AI拆剧站位图提示词"),
        (KEY_AI_SCRIPT_VALIDATE_PROMPT, "AI拆剧校验提示词"),
        (KEY_SCENE_INFERENCE_LEFT_PROMPT, "场景推理左侧面提示词"),
        (KEY_SCENE_INFERENCE_RIGHT_PROMPT, "场景推理右侧面提示词"),
        (KEY_SCENE_INFERENCE_TOP_PROMPT, "场景推理俯瞰图提示词"),
        (KEY_SCENE_INFERENCE_PANORAMA_PROMPT, "场景推理全景图提示词"),
    ]

    key = models.CharField(max_length=64, choices=KEY_CHOICES, unique=True)
    value = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_site_configs",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return f"{self.key}"
