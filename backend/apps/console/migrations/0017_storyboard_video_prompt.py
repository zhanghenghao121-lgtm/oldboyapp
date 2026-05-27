from django.db import migrations, models


DEFAULT_VIDEO_PROMPT = """根据这张分镜板和故事剧情，生成分镜板中每张分镜图用于制作总时长为 15 秒视频的分镜提示词。

要求：
1. 必须为输入中的每一格输出一条 video_prompt，panel_no 必须与分镜图一致。
2. 所有镜头时长相加必须等于 15 秒；镜头动作与运镜应连续并符合原剧情。
3. video_prompt 严格使用格式：【景别】【画面描述】（*秒）。
4. 输出严格 JSON，不要 markdown 或额外解释。

输出格式：
{
  "panels": [
    {"panel_no": 1, "video_prompt": "【全景】【雨夜站台，列车缓缓入站，镜头向前推进】（2秒）"}
  ]
}"""

DEFAULT_PANEL_PROMPT = """你是一名导演和分镜图设计师。请根据剧情段、用户上传的场景图、角色图、道具图、站位参考图以及补充描述，设计连续分镜板。

要求：
1. 用户内容会指定需要生成 6、9 或 12 个分镜；必须严格输出指定数量，panel_no 从 1 顺序编号。
2. 多个镜头共同完整表达本段剧情，镜头连续、空间关系稳定、人物不越轴。
3. screen_description 是用户可读的分镜画面说明。
4. image_prompt 是可直接交给图像生成模型生成单张分镜图的中文提示词，明确人物、动作、机位、景别、场景、光线、构图、站位和素材一致性；保持场景和人物画风与参考图片一致，并要求高清 4K 画质。
5. 素材参考中出现的人物、场景、道具或站位，需在相应分镜提示词中明确遵循参考图。
6. 所有生成图片无文字、无分镜号、无水印。
7. video_prompt 可留空，视频生成提示词将在完整分镜板形成后单独生成。
8. 输出严格 JSON，不要 markdown。

输出格式：
{
  "panels": [
    {
      "panel_no": 1,
      "shot_type": "全景",
      "camera_angle": "平视",
      "camera_movement": "固定",
      "screen_description": "画面描述",
      "image_prompt": "单帧图片提示词",
      "video_prompt": "",
      "emotion": "情绪",
      "characters": ["人物名"],
      "props": ["道具名"]
    }
  ]
}"""

DEFAULT_SINGLE_PANEL_PROMPT = """你是一名分镜导演。请重新设计用户指定的一格分镜画面，同时保持它在原分镜板剧情顺序中的作用。

要求：
1. 只输出这一格分镜的 JSON 对象，不改变它的 panel_no。
2. 结合用户选择的参考素材，重新输出清晰的画面描述和可直接生图的提示词。
3. 镜头必须与该段剧情和相邻镜头逻辑连续，空间关系稳定、人物不越轴。
4. 保持参考图的场景和人物画风一致，高清 4K 画质，不绘制文字、分镜号或水印。
5. 输出严格 JSON，不要 markdown。

输出格式：
{
  "panel_no": 1,
  "shot_type": "中景",
  "camera_angle": "平视",
  "camera_movement": "固定",
  "screen_description": "新的画面描述",
  "image_prompt": "新的单帧图片提示词",
  "video_prompt": "图生视频提示词",
  "emotion": "情绪",
  "characters": ["人物名"],
  "props": ["道具名"]
}"""


def seed_video_prompt(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    SiteConfig.objects.get_or_create(
        key="storyboard_video_prompt",
        defaults={"value": DEFAULT_VIDEO_PROMPT},
    )
    panel = SiteConfig.objects.filter(key="storyboard_panel_prompt").first()
    if panel and "必须输出且只输出 9 个分镜" in panel.value:
        panel.value = DEFAULT_PANEL_PROMPT
        panel.save(update_fields=["value"])
    single = SiteConfig.objects.filter(key="storyboard_single_panel_prompt").first()
    if single and "原九宫格剧情顺序" in single.value:
        single.value = DEFAULT_SINGLE_PANEL_PROMPT
        single.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("console", "0016_storyboard_single_panel_prompt"),
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
        migrations.RunPython(seed_video_prompt, migrations.RunPython.noop),
    ]
