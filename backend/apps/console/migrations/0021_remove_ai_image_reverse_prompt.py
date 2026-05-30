from django.db import migrations, models


def remove_reverse_prompt_config(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    SiteConfig.objects.filter(key="ai_image_reverse_prompt").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("console", "0020_update_storyboard_force_15s_prompt"),
    ]

    operations = [
        migrations.RunPython(remove_reverse_prompt_config, migrations.RunPython.noop),
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
                    ("storyboard_scene_split_prompt", "故事板场景拆分提示词"),
                    ("storyboard_leaf_split_prompt", "故事板分镜适配提示词"),
                    ("storyboard_asset_prompt", "故事板素材提取提示词"),
                    ("storyboard_panel_prompt", "故事板分镜生成提示词"),
                    ("storyboard_single_panel_prompt", "故事板单格重生成提示词"),
                    ("storyboard_video_prompt", "故事板视频分镜提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
    ]
