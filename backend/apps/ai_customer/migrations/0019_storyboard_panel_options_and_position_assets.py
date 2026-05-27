from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ai_customer", "0018_storyboard_editable_assets"),
    ]

    operations = [
        migrations.AddField(
            model_name="storysegment",
            name="panel_count",
            field=models.PositiveIntegerField(default=9),
        ),
        migrations.AddField(
            model_name="storysegment",
            name="supplementary_description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="storyboardasset",
            name="asset_type",
            field=models.CharField(
                choices=[
                    ("character", "人物"),
                    ("scene", "场景"),
                    ("prop", "道具"),
                    ("position", "站位参考"),
                ],
                max_length=50,
            ),
        ),
    ]
