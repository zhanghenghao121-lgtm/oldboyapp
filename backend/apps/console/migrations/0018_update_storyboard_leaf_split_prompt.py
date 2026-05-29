from django.db import migrations


OLD_LEAF_PROMPT_MARKER = "请判断给定剧情段是否适合由一组 6、9 或 12 个连续分镜完整表达"

NEW_LEAF_PROMPT = """你是一名短视频分镜导演。请判断给定剧情段是否适合成为一个总时长约 15 秒的视频片段，并由一组 6、9 或 12 个连续分镜图作为该 15 秒视频的参考图完整表达。

判断标准：
1. 叶子小段必须像一个可生成 15 秒视频的独立剧情画面：有明确的开始状态、核心动作/情绪变化和结束状态。
2. 小段应处于同一或视觉连续的空间内，镜头可以切换景别，但不应包含明显跨地点、跨时间或多轮事件推进。
3. 角色、动作和情绪变化需要能在约 15 秒内被观众理解，并能由 6、9 或 12 张连续分镜图稳定呈现。
4. 如果段落中包含多个 15 秒视频事件、多个情绪转折、多个连续动作高潮，或需要超过 15 秒才能表达清楚，必须继续拆成按顺序衔接的更小段落。
5. 拆分 children 时，每个 child 都应对应一个可单独生成 15 秒视频的剧情片段，而不是按文字长度平均切分。
6. 只能使用原段落已有剧情信息，不补造关键事件、人物关系或结局。

输出严格 JSON：
{
  "can_be_9_grid": true,
  "score": 92,
  "reason": "判断理由",
  "analysis": "适合 15 秒视频表现的核心动作、情绪变化和空间关系",
  "children": [
    {
      "order": 1,
      "title": "15秒视频片段标题",
      "summary": "该 15 秒片段的起承转合概述",
      "original_text": "该 15 秒片段覆盖的原剧情内容",
      "split_reason": "为何这是一个独立 15 秒视频片段"
    }
  ]
}

当 can_be_9_grid 为 true 时，children 必须为空数组。"""


def update_leaf_prompt(apps, schema_editor):
    SiteConfig = apps.get_model("console", "SiteConfig")
    row = SiteConfig.objects.filter(key="storyboard_leaf_split_prompt").first()
    if not row:
        SiteConfig.objects.create(key="storyboard_leaf_split_prompt", value=NEW_LEAF_PROMPT)
        return
    value = str(row.value or "")
    if OLD_LEAF_PROMPT_MARKER in value:
        row.value = NEW_LEAF_PROMPT
        row.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("console", "0017_storyboard_video_prompt"),
    ]

    operations = [
        migrations.RunPython(update_leaf_prompt, migrations.RunPython.noop),
    ]
