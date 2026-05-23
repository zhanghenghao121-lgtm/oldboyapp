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
    KEY_AI_ASSISTANT_BASE_URL = "ai_assistant_base_url"
    KEY_AI_ASSISTANT_API_KEY = "ai_assistant_api_key"
    KEY_AI_ASSISTANT_MODEL = "ai_assistant_model"
    KEY_AI_MANGA_BASE_URL = "ai_manga_base_url"
    KEY_AI_MANGA_API_KEY = "ai_manga_api_key"
    KEY_AI_MANGA_MODEL = "ai_manga_model"
    KEY_AI_MANGA_VISION_BASE_URL = "ai_manga_vision_base_url"
    KEY_AI_MANGA_VISION_API_KEY = "ai_manga_vision_api_key"
    KEY_AI_MANGA_VISION_MODEL = "ai_manga_vision_model"
    KEY_AI_IMAGE_BASE_URL = "ai_image_base_url"
    KEY_AI_IMAGE_API_KEY = "ai_image_api_key"
    KEY_AI_IMAGE_MODEL = "ai_image_model"
    KEY_AI_IMAGE_DOUBAO_BASE_URL = "ai_image_doubao_base_url"
    KEY_AI_IMAGE_DOUBAO_API_KEY = "ai_image_doubao_api_key"
    KEY_AI_IMAGE_DOUBAO_MODEL = "ai_image_doubao_model"
    KEY_AI_IMAGE_REVERSE_PROMPT = "ai_image_reverse_prompt"
    KEY_AI_MANGA_STORYBOARD_PROMPT = "ai_manga_storyboard_prompt"
    KEY_AI_MANGA_3D_STYLE_PROMPT = "ai_manga_3d_style_prompt"
    KEY_AI_MANGA_REAL_STYLE_PROMPT = "ai_manga_real_style_prompt"
    KEY_CHOICES = [
        (KEY_DEFAULT_AVATAR, "默认头像URL"),
        (KEY_AI_ASSISTANT_BASE_URL, "助手模型API地址"),
        (KEY_AI_ASSISTANT_API_KEY, "助手模型API Key"),
        (KEY_AI_ASSISTANT_MODEL, "助手模型名称"),
        (KEY_AI_MANGA_BASE_URL, "剧本模型API地址"),
        (KEY_AI_MANGA_API_KEY, "剧本模型API Key"),
        (KEY_AI_MANGA_MODEL, "剧本模型名称"),
        (KEY_AI_MANGA_VISION_BASE_URL, "图文模型API地址"),
        (KEY_AI_MANGA_VISION_API_KEY, "图文模型API Key"),
        (KEY_AI_MANGA_VISION_MODEL, "图文模型名称"),
        (KEY_AI_IMAGE_BASE_URL, "生图模型API地址"),
        (KEY_AI_IMAGE_API_KEY, "生图模型API Key"),
        (KEY_AI_IMAGE_MODEL, "生图模型名称"),
        (KEY_AI_IMAGE_DOUBAO_BASE_URL, "豆包生图API地址"),
        (KEY_AI_IMAGE_DOUBAO_API_KEY, "豆包生图API Key"),
        (KEY_AI_IMAGE_DOUBAO_MODEL, "豆包生图模型名称"),
        (KEY_AI_IMAGE_REVERSE_PROMPT, "反打画面提示词"),
        (KEY_AI_MANGA_STORYBOARD_PROMPT, "AI剧本解析规则"),
        (KEY_AI_MANGA_3D_STYLE_PROMPT, "3D风格提示词"),
        (KEY_AI_MANGA_REAL_STYLE_PROMPT, "真人风格提示词"),
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
