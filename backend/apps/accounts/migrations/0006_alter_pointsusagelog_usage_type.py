from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_pointsusagelog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pointsusagelog",
            name="usage_type",
            field=models.CharField(
                choices=[
                    ("script_storyboard", "剧本分镜消耗"),
                    ("paragraph_storyboard", "段落分镜消耗"),
                    ("resume_assistant", "简历助手消耗"),
                    ("refund", "失败退款"),
                ],
                max_length=32,
            ),
        ),
    ]
