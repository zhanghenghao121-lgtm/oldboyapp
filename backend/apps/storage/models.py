from django.db import models
from django.conf import settings


class UploadedFileRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    content_type = models.CharField(max_length=200, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
