from django.db import migrations, models


def normalize_storyboard_asset_prompt(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    row = SiteConfig.objects.filter(key="storyboard_asset_prompt").first()
    if row and ("costumes" in row.value or "style_refs" in row.value):
        row.value = (
            "你是一名故事板美术统筹。请从可用于一张九宫格分镜图的剧情段落中，只提取生成画面需要参考图的"
            "人物、场景和关键道具，不输出服装或风格分类，不新增原剧情没有的重要资产。"
            "输出严格 JSON，格式为："
            '{"characters":[{"name":"人物名","description":"外观/身份/本段作用"}],'
            '"scenes":[{"name":"场景名","description":"空间和光线特征"}],'
            '"props":[{"name":"道具名","description":"形态和用途"}]}'
        )
        row.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("console", "0015_storyboard_config"),
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
                    ("storyboard_single_panel_prompt", "故事板单格重生成提示词"),
                ],
                max_length=64,
                unique=True,
            ),
        ),
        migrations.RunPython(normalize_storyboard_asset_prompt, migrations.RunPython.noop),
    ]
