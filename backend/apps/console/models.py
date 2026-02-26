from django.conf import settings
from django.db import models


class SiteBackground(models.Model):
    SCENE_LOGIN = "login"
    SCENE_HOME = "home"
    SCENE_CHOICES = [
        (SCENE_LOGIN, "登录页"),
        (SCENE_HOME, "首页"),
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
