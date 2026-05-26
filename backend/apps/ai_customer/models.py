from django.conf import settings
from django.db import models


class PositionStickerAsset(models.Model):
    MODE_FAST = "fast"
    MODE_AI = "ai"
    MODE_CHOICES = [
        (MODE_FAST, "免费快速抠图"),
        (MODE_AI, "AI 精细抠图"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="position_sticker_assets")
    file_record = models.OneToOneField("storage.UploadedFileRecord", on_delete=models.CASCADE, related_name="position_sticker_asset")
    name = models.CharField(max_length=100)
    cutout_mode = models.CharField(max_length=12, choices=MODE_CHOICES)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
