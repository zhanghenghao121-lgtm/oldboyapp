from django.db import migrations, models


def seed_doubao_image_defaults(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    defaults = {
        "ai_image_doubao_base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "ai_image_doubao_api_key": "",
        "ai_image_doubao_model": "doubao-seedream-5-0-260128",
    }
    for key, value in defaults.items():
        SiteConfig.objects.get_or_create(key=key, defaults={"value": value})


class Migration(migrations.Migration):

    dependencies = [
        ("console", "0012_update_ai_image_reverse_prompt"),
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
                    ("ai_manga_vision_base_url", "图文模型API地址"),
                    ("ai_manga_vision_api_key", "图文模型API Key"),
                    ("ai_manga_vision_model", "图文模型名称"),
                    ("ai_image_base_url", "生图模型API地址"),
                    ("ai_image_api_key", "生图模型API Key"),
                    ("ai_image_model", "生图模型名称"),
                    ("ai_image_doubao_base_url", "豆包生图API地址"),
                    ("ai_image_doubao_api_key", "豆包生图API Key"),
                    ("ai_image_doubao_model", "豆包生图模型名称"),
                    ("ai_image_reverse_prompt", "反打画面提示词"),
                    ("ai_manga_storyboard_prompt", "AI剧本解析规则"),
                    ("ai_manga_3d_style_prompt", "3D风格提示词"),
                    ("ai_manga_real_style_prompt", "真人风格提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_doubao_image_defaults, migrations.RunPython.noop),
    ]
