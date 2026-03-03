from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True)
    avatar_url = models.URLField(max_length=500, blank=True, default="")
    signature = models.CharField(max_length=120, blank=True, default="")
    points = models.DecimalField(max_digits=12, decimal_places=2, default=50)


class PointsUsageLog(models.Model):
    TYPE_SCRIPT_STORYBOARD = "script_storyboard"
    TYPE_PARAGRAPH_STORYBOARD = "paragraph_storyboard"
    TYPE_RESUME_ASSISTANT = "resume_assistant"
    TYPE_REFUND = "refund"
    TYPE_CHOICES = (
        (TYPE_SCRIPT_STORYBOARD, "剧本分镜消耗"),
        (TYPE_PARAGRAPH_STORYBOARD, "段落分镜消耗"),
        (TYPE_RESUME_ASSISTANT, "简历助手消耗"),
        (TYPE_REFUND, "失败退款"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="points_logs")
    usage_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
