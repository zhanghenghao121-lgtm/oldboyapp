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
    KEY_RECHARGE_WECHAT = "recharge_wechat_id"
    KEY_RECHARGE_QR_URL = "recharge_qr_url"
    KEY_AI_ASSISTANT_BASE_URL = "ai_assistant_base_url"
    KEY_AI_ASSISTANT_API_KEY = "ai_assistant_api_key"
    KEY_AI_ASSISTANT_MODEL = "ai_assistant_model"
    KEY_AI_MANGA_BASE_URL = "ai_manga_base_url"
    KEY_AI_MANGA_API_KEY = "ai_manga_api_key"
    KEY_AI_MANGA_MODEL = "ai_manga_model"
    KEY_AI_MANGA_STORYBOARD_PROMPT = "ai_manga_storyboard_prompt"
    KEY_CHOICES = [
        (KEY_DEFAULT_AVATAR, "默认头像URL"),
        (KEY_RECHARGE_WECHAT, "充值页微信号"),
        (KEY_RECHARGE_QR_URL, "充值页二维码URL"),
        (KEY_AI_ASSISTANT_BASE_URL, "助手模型API地址"),
        (KEY_AI_ASSISTANT_API_KEY, "助手模型API Key"),
        (KEY_AI_ASSISTANT_MODEL, "助手模型名称"),
        (KEY_AI_MANGA_BASE_URL, "漫剧模型API地址"),
        (KEY_AI_MANGA_API_KEY, "漫剧模型API Key"),
        (KEY_AI_MANGA_MODEL, "漫剧模型名称"),
        (KEY_AI_MANGA_STORYBOARD_PROMPT, "AI漫剧分镜提示词"),
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
