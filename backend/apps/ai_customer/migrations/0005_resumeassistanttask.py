from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0004_humanreplyclearstate"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ResumeAssistantTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_id", models.CharField(max_length=64, unique=True)),
                ("job_title", models.CharField(max_length=120)),
                ("image_urls", models.JSONField(blank=True, default=list)),
                ("rois", models.JSONField(blank=True, default=list)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("created", "已创建"),
                            ("running", "处理中"),
                            ("succeeded", "成功"),
                            ("failed", "失败"),
                        ],
                        default="created",
                        max_length=16,
                    ),
                ),
                ("progress", models.PositiveSmallIntegerField(default=0)),
                ("cost_points", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("refunded", models.BooleanField(default=False)),
                ("ocr_text", models.TextField(blank=True, default="")),
                ("resume_text", models.TextField(blank=True, default="")),
                ("pdf_url", models.URLField(blank=True, default="", max_length=1000)),
                ("error_message", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resume_tasks", to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={"ordering": ["-id"]},
        ),
    ]
