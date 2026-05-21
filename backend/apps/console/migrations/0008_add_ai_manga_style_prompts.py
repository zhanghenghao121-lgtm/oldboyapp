from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0007_add_ai_manga_image_prompt"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteconfig",
            name="key",
            field=models.CharField(
                choices=[
                    ("default_avatar_url", "默认头像URL"),
                    ("ai_assistant_base_url", "助手模型API地址"),
                    ("ai_assistant_api_key", "助手模型API Key"),
                    ("ai_assistant_model", "助手模型名称"),
                    ("ai_manga_base_url", "剧本模型API地址"),
                    ("ai_manga_api_key", "剧本模型API Key"),
                    ("ai_manga_model", "剧本模型名称"),
                    ("ai_manga_storyboard_prompt", "AI剧本解析规则"),
                    ("ai_manga_3d_style_prompt", "3D风格提示词"),
                    ("ai_manga_real_style_prompt", "真人风格提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
