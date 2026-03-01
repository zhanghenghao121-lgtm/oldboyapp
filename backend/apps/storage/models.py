from django.db import models
from django.conf import settings


class UploadedFileRecord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    content_type = models.CharField(max_length=200, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class UploadAuditLog(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_REJECTED = "rejected"
    STATUS_ERROR = "error"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "成功"),
        (STATUS_REJECTED, "拒绝"),
        (STATUS_ERROR, "错误"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    folder = models.CharField(max_length=120, blank=True, default="")
    filename = models.CharField(max_length=300, blank=True, default="")
    content_type = models.CharField(max_length=200, blank=True, default="")
    size = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    message = models.CharField(max_length=300, blank=True, default="")
    ip = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
