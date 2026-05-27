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


class StoryboardProject(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_ANALYZED = "analyzed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "待拆解"),
        (STATUS_ANALYZED, "已拆解"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="storyboard_projects")
    title = models.CharField(max_length=255)
    original_story = models.TextField()
    style_preset = models.CharField(max_length=100, blank=True, default="")
    aspect_ratio = models.CharField(max_length=20, blank=True, default="16:9")
    analysis_model = models.CharField(max_length=100, blank=True, default="deepseek-v4-pro")
    image_model = models.CharField(max_length=100, blank=True, default="gpt-image-2")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class StorySegment(models.Model):
    project = models.ForeignKey(StoryboardProject, on_delete=models.CASCADE, related_name="segments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    level = models.PositiveIntegerField(default=1)
    order_index = models.PositiveIntegerField(default=0)
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, default="")
    original_text = models.TextField(blank=True, default="")
    scene_name = models.CharField(max_length=255, blank=True, default="")
    time_of_day = models.CharField(max_length=100, blank=True, default="")
    mood = models.CharField(max_length=255, blank=True, default="")
    is_leaf = models.BooleanField(default=False)
    split_reason = models.TextField(blank=True, default="")
    grid_feasibility_score = models.IntegerField(default=0)
    analysis_json = models.JSONField(default=dict)
    required_assets_json = models.JSONField(default=dict)
    panel_count = models.PositiveIntegerField(default=9)
    supplementary_description = models.TextField(blank=True, default="")
    grid_image_url = models.URLField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level", "order_index", "id"]


class StoryboardPanel(models.Model):
    segment = models.ForeignKey(StorySegment, on_delete=models.CASCADE, related_name="panels")
    panel_no = models.PositiveIntegerField()
    shot_type = models.CharField(max_length=100, blank=True, default="")
    camera_angle = models.CharField(max_length=100, blank=True, default="")
    camera_movement = models.CharField(max_length=100, blank=True, default="")
    screen_description = models.TextField(blank=True, default="")
    image_prompt = models.TextField(blank=True, default="")
    video_prompt = models.TextField(blank=True, default="")
    emotion = models.CharField(max_length=255, blank=True, default="")
    characters = models.JSONField(default=list)
    props = models.JSONField(default=list)
    image_url = models.URLField(max_length=1000, blank=True, default="")
    generation_task_id = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["panel_no"]
        constraints = [
            models.UniqueConstraint(fields=["segment", "panel_no"], name="unique_storyboard_panel_no"),
        ]


class StoryboardAsset(models.Model):
    TYPE_CHARACTER = "character"
    TYPE_SCENE = "scene"
    TYPE_PROP = "prop"
    TYPE_POSITION = "position"
    TYPE_CHOICES = [
        (TYPE_CHARACTER, "人物"),
        (TYPE_SCENE, "场景"),
        (TYPE_PROP, "道具"),
        (TYPE_POSITION, "站位参考"),
    ]

    project = models.ForeignKey(StoryboardProject, on_delete=models.CASCADE, related_name="assets")
    segment = models.ForeignKey(StorySegment, null=True, blank=True, on_delete=models.CASCADE, related_name="assets")
    asset_type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    image_url = models.URLField(max_length=1000, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["asset_type", "id"]
