from django.conf import settings
from django.db import models


class CharacterAsset(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="standposer_characters")
    name = models.CharField(max_length=80)
    model_url = models.URLField(max_length=800)
    cos_key = models.CharField(max_length=500, blank=True, default="")
    file_size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=120, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class StandScene(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="standposer_scenes")
    name = models.CharField(max_length=120, blank=True, default="未命名站位")
    scene_data = models.JSONField(default=dict, blank=True)
    thumbnail_url = models.URLField(max_length=800, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name or f"StandScene {self.pk}"


class SceneShot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="standposer_shots")
    scene = models.ForeignKey(StandScene, on_delete=models.SET_NULL, related_name="shots", null=True, blank=True)
    image_url = models.URLField(max_length=800)
    cos_key = models.CharField(max_length=500, blank=True, default="")
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)
    camera_state = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class GenerationTask(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "等待中"),
        (STATUS_RUNNING, "生成中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="standposer_generation_tasks")
    character = models.ForeignKey(CharacterAsset, on_delete=models.CASCADE, related_name="generation_tasks")
    celery_task_id = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    input_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
