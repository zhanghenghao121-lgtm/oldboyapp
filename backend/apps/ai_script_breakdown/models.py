from django.conf import settings
from django.db import models


class AiScriptBreakdownProject(models.Model):
    STYLE_LIVE_ACTION = "live_action"
    STYLE_ANIME_3D = "anime_3d"
    STYLE_CHOICES = [
        (STYLE_LIVE_ACTION, "真人写实"),
        (STYLE_ANIME_3D, "3D动漫"),
    ]
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "待拆解"),
        (STATUS_PROCESSING, "拆解中"),
        (STATUS_COMPLETED, "已完成"),
        (STATUS_FAILED, "失败"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="script_breakdown_projects")
    title = models.CharField(max_length=255)
    script_text = models.TextField()
    selected_style = models.CharField(max_length=32, choices=STYLE_CHOICES, default=STYLE_LIVE_ACTION)
    max_segment_seconds = models.PositiveIntegerField(default=15)
    analysis_model = models.CharField(max_length=100, blank=True, default="deepseek-v4-pro")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True, default="")
    extracted_assets_json = models.JSONField(default=dict)
    validation_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]


class AiScriptAsset(models.Model):
    TYPE_SCENE = "scene"
    TYPE_CHARACTER = "character"
    TYPE_PROP = "prop"
    TYPE_CHOICES = [
        (TYPE_SCENE, "场景"),
        (TYPE_CHARACTER, "角色"),
        (TYPE_PROP, "道具"),
    ]

    project = models.ForeignKey(AiScriptBreakdownProject, on_delete=models.CASCADE, related_name="assets")
    asset_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    alias = models.CharField(max_length=255, blank=True, default="")
    file_url = models.URLField(max_length=1000, blank=True, default="")
    ai_description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asset_type", "id"]


class AiScriptSceneBlock(models.Model):
    project = models.ForeignKey(AiScriptBreakdownProject, on_delete=models.CASCADE, related_name="scene_blocks")
    scene_number = models.CharField(max_length=100, blank=True, default="")
    scene_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, default="")
    time_of_day = models.CharField(max_length=100, blank=True, default="")
    scene_description = models.TextField(blank=True, default="")
    front_view_description = models.TextField(blank=True, default="")
    reverse_view_description = models.TextField(blank=True, default="")
    original_text = models.TextField(blank=True, default="")
    characters = models.JSONField(default=list)
    props = models.JSONField(default=list)
    order_index = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_index", "id"]


class AiScriptShotSegment(models.Model):
    VIEW_FRONT = "front"
    VIEW_REVERSE = "reverse"
    VIEW_SIDE = "side"
    VIEW_CLOSEUP = "closeup"
    VIEW_MIXED = "mixed"
    VIEW_CHOICES = [
        (VIEW_FRONT, "正面"),
        (VIEW_REVERSE, "反打"),
        (VIEW_SIDE, "侧面"),
        (VIEW_CLOSEUP, "近景"),
        (VIEW_MIXED, "混合"),
    ]

    project = models.ForeignKey(AiScriptBreakdownProject, on_delete=models.CASCADE, related_name="shot_segments")
    scene_block = models.ForeignKey(AiScriptSceneBlock, on_delete=models.CASCADE, related_name="segments")
    segment_title = models.CharField(max_length=255)
    estimated_duration = models.PositiveIntegerField(default=0)
    style_prompt = models.TextField(blank=True, default="")
    copy_text = models.TextField(blank=True, default="")
    continuity_from_previous = models.BooleanField(default=False)
    previous_anchor_line = models.TextField(blank=True, default="")
    scene_view = models.CharField(max_length=32, choices=VIEW_CHOICES, default=VIEW_FRONT)
    characters = models.JSONField(default=list)
    props = models.JSONField(default=list)
    position_image_prompt = models.TextField(blank=True, default="")
    position_layout_json = models.JSONField(default=dict)
    position_image_url = models.URLField(max_length=1000, blank=True, default="")
    order_index = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scene_block__order_index", "order_index", "id"]


class AiScriptShotLine(models.Model):
    segment = models.ForeignKey(AiScriptShotSegment, on_delete=models.CASCADE, related_name="shot_lines")
    shot_size = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    dialogue = models.TextField(blank=True, default="")
    line_text = models.TextField(blank=True, default="")
    is_continuity_anchor = models.BooleanField(default=False)
    order_index = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order_index", "id"]
