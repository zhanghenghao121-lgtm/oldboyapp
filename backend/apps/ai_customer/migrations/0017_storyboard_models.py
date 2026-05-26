import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0016_positionstickerasset"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StoryboardProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("original_story", models.TextField()),
                ("style_preset", models.CharField(blank=True, default="", max_length=100)),
                ("aspect_ratio", models.CharField(blank=True, default="16:9", max_length=20)),
                ("analysis_model", models.CharField(blank=True, default="deepseek-v4-pro", max_length=100)),
                ("image_model", models.CharField(blank=True, default="gpt-image-2", max_length=100)),
                ("status", models.CharField(choices=[("draft", "待拆解"), ("analyzed", "已拆解")], default="draft", max_length=50)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="storyboard_projects", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="StorySegment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("level", models.PositiveIntegerField(default=1)),
                ("order_index", models.PositiveIntegerField(default=0)),
                ("title", models.CharField(max_length=255)),
                ("summary", models.TextField(blank=True, default="")),
                ("original_text", models.TextField(blank=True, default="")),
                ("scene_name", models.CharField(blank=True, default="", max_length=255)),
                ("time_of_day", models.CharField(blank=True, default="", max_length=100)),
                ("mood", models.CharField(blank=True, default="", max_length=255)),
                ("is_leaf", models.BooleanField(default=False)),
                ("split_reason", models.TextField(blank=True, default="")),
                ("grid_feasibility_score", models.IntegerField(default=0)),
                ("analysis_json", models.JSONField(default=dict)),
                ("required_assets_json", models.JSONField(default=dict)),
                ("grid_image_url", models.URLField(blank=True, default="", max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("parent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="ai_customer.storysegment")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="segments", to="ai_customer.storyboardproject")),
            ],
            options={"ordering": ["level", "order_index", "id"]},
        ),
        migrations.CreateModel(
            name="StoryboardPanel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("panel_no", models.PositiveIntegerField()),
                ("shot_type", models.CharField(blank=True, default="", max_length=100)),
                ("camera_angle", models.CharField(blank=True, default="", max_length=100)),
                ("camera_movement", models.CharField(blank=True, default="", max_length=100)),
                ("screen_description", models.TextField(blank=True, default="")),
                ("image_prompt", models.TextField(blank=True, default="")),
                ("video_prompt", models.TextField(blank=True, default="")),
                ("emotion", models.CharField(blank=True, default="", max_length=255)),
                ("characters", models.JSONField(default=list)),
                ("props", models.JSONField(default=list)),
                ("image_url", models.URLField(blank=True, default="", max_length=1000)),
                ("generation_task_id", models.CharField(blank=True, default="", max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("segment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="panels", to="ai_customer.storysegment")),
            ],
            options={"ordering": ["panel_no"]},
        ),
        migrations.CreateModel(
            name="StoryboardAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_type", models.CharField(choices=[("character", "人物"), ("scene", "场景"), ("prop", "道具"), ("style", "风格参考"), ("costume", "服装/妆容")], max_length=50)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("image_url", models.URLField(max_length=1000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assets", to="ai_customer.storyboardproject")),
                ("segment", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assets", to="ai_customer.storysegment")),
            ],
            options={"ordering": ["asset_type", "id"]},
        ),
        migrations.AddConstraint(
            model_name="storyboardpanel",
            constraint=models.UniqueConstraint(fields=("segment", "panel_no"), name="unique_storyboard_panel_no"),
        ),
    ]
