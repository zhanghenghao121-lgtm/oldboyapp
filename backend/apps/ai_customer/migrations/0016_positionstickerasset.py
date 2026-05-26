import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0015_remove_aibloggerasset_post_and_more"),
        ("storage", "0002_uploadauditlog"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PositionStickerAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("cutout_mode", models.CharField(choices=[("fast", "免费快速抠图"), ("ai", "AI 精细抠图")], max_length=12)),
                ("width", models.PositiveIntegerField()),
                ("height", models.PositiveIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("file_record", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="position_sticker_asset", to="storage.uploadedfilerecord")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="position_sticker_assets", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
