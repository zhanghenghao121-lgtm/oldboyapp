from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ai_customer", "0021_alter_sceneinferencejob_job_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="positionstickerasset",
            name="cutout_mode",
            field=models.CharField(
                choices=[
                    ("fast", "免费快速抠图"),
                    ("ai", "AI 精细抠图"),
                    ("transparent", "透明图直传"),
                ],
                max_length=12,
            ),
        ),
    ]
