from django.db import migrations, models


NEW_DEFAULTS = {
    "storyboard_deepseek_base_url": "",
    "storyboard_deepseek_api_key": "",
    "storyboard_deepseek_model": "deepseek-v4-pro",
    "storyboard_doubao_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "storyboard_doubao_api_key": "",
    "storyboard_doubao_model": "doubao-seed-2-0-pro-260215",
}

OLD_KEYS = [
    "ai_assistant_base_url",
    "ai_assistant_api_key",
    "ai_assistant_model",
    "ai_manga_base_url",
    "ai_manga_api_key",
    "ai_manga_model",
    "ai_manga_vision_base_url",
    "ai_manga_vision_api_key",
    "ai_manga_vision_model",
    "ai_manga_storyboard_prompt",
    "ai_manga_3d_style_prompt",
    "ai_manga_real_style_prompt",
]


def seed_storyboard_config(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    SiteConfig.objects.filter(key__in=OLD_KEYS).delete()
    for key, value in NEW_DEFAULTS.items():
        SiteConfig.objects.get_or_create(key=key, defaults={"value": value})


class Migration(migrations.Migration):
    dependencies = [
        ("console", "0014_add_remove_bg_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="siteconfig",
            name="key",
            field=models.CharField(
                choices=[
                    ("default_avatar_url", "默认头像URL"),
                    ("storyboard_deepseek_base_url", "故事板 DeepSeek API地址"),
                    ("storyboard_deepseek_api_key", "故事板 DeepSeek API Key"),
                    ("storyboard_deepseek_model", "故事板 DeepSeek 模型名称"),
                    ("storyboard_doubao_base_url", "故事板 Doubao API地址"),
                    ("storyboard_doubao_api_key", "故事板 Doubao API Key"),
                    ("storyboard_doubao_model", "故事板 Doubao 模型名称"),
                    ("ai_image_base_url", "生图模型API地址"),
                    ("ai_image_api_key", "生图模型API Key"),
                    ("ai_image_model", "生图模型名称"),
                    ("ai_image_doubao_base_url", "豆包生图API地址"),
                    ("ai_image_doubao_api_key", "豆包生图API Key"),
                    ("ai_image_doubao_model", "豆包生图模型名称"),
                    ("remove_bg_api_key", "remove.bg API Key"),
                    ("ai_image_reverse_prompt", "反打画面提示词"),
                    ("storyboard_scene_split_prompt", "故事板场景拆分提示词"),
                    ("storyboard_leaf_split_prompt", "故事板九宫格判断提示词"),
                    ("storyboard_asset_prompt", "故事板素材提取提示词"),
                    ("storyboard_panel_prompt", "故事板九宫格分镜提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
        migrations.RunPython(seed_storyboard_config, migrations.RunPython.noop),
    ]
