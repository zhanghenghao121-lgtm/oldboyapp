from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0023_positionstickercomposition"),
    ]

    operations = [
        migrations.AddField(
            model_name="positionstickercomposition",
            name="blend_mode",
            field=models.CharField(
                choices=[("normal", "普通合成"), ("natural", "自然融合")],
                default="normal",
                max_length=16,
            ),
        ),
    ]
