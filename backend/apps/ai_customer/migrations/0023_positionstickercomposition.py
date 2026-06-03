import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0022_alter_positionstickerasset_cutout_mode"),
        ("storage", "0002_uploadauditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PositionStickerComposition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=120)),
                ("scene_name", models.CharField(blank=True, default="", max_length=255)),
                ("canvas_width", models.PositiveIntegerField(default=760)),
                ("canvas_height", models.PositiveIntegerField(default=500)),
                ("layers_json", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "result_file_record",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="storage.uploadedfilerecord"),
                ),
                (
                    "scene_file_record",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="storage.uploadedfilerecord"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="position_sticker_compositions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-updated_at", "-id"],
            },
        ),
    ]
