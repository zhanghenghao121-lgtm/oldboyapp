DEFAULT_SCRIPT_LIVE_ACTION_STYLE_PROMPT = (
    "真人写实电影质感，真实人物表演，真实光影，真实场景空间，镜头运动自然，人物表情细腻，"
    "画面高清4K，无字幕，无文字，无水印，适合Seedance 2.0生成视频。"
)

DEFAULT_SCRIPT_ANIME_3D_STYLE_PROMPT = (
    "3D动漫电影质感，角色保持动漫建模风格，场景具有高质量CG渲染效果，光影柔和，动作自然，"
    "表情夸张但符合剧情，画面高清4K，无字幕，无文字，无水印，适合Seedance 2.0生成视频。"
)

DEFAULT_SCRIPT_ASSET_EXTRACT_PROMPT = """你是一名专业影视导演、分镜师、短视频剧情拆解师。请从剧本中提取 AI 拆剧需要的资产信息。

要求：
1. 只能提取剧本中明确出现的场景、角色和关键道具，不要添加剧本中没有的内容。
2. 场景需要补充正面视角和反打视角描述，基于剧情中的人物对峙、移动方向、镜头方向理解。
3. 如果上传素材和剧本文字可能对应，请在 matched_uploaded_asset_name 中标记；无法确定则留空。
4. 输出严格 JSON，不要 markdown 或解释。

输出格式：
{
  "scenes": [{"name": "", "description": "", "front_view_description": "", "reverse_view_description": "", "matched_uploaded_asset_name": ""}],
  "characters": [{"name": "", "description": "", "matched_uploaded_asset_name": ""}],
  "props": [{"name": "", "description": "", "matched_uploaded_asset_name": ""}]
}"""

DEFAULT_SCRIPT_SCENE_SPLIT_PROMPT = """你是一名影视剧本场景统筹。请将完整剧本按照场景拆解为多个大段落。

规则：
1. 只按照场景变化拆解；同一个场景内的连续剧情不要拆开为多个大段落。
2. 不允许增加、减少或改变剧情顺序。
3. 每个大段落必须保留原始剧本文本，列出出场角色和关键道具。
4. 每个大段落必须包含场景正面视角和反打视角描述。
5. 输出严格 JSON，不要 markdown 或解释。

输出格式：
{
  "scene_blocks": [
    {
      "scene_number": "",
      "scene_name": "",
      "location": "",
      "time_of_day": "",
      "scene_description": "",
      "front_view_description": "",
      "reverse_view_description": "",
      "original_text": "",
      "characters": [],
      "props": [],
      "order_index": 1
    }
  ]
}"""

DEFAULT_SCRIPT_SHOT_SEGMENT_PROMPT = """你是一名 Seedance 2.0 短视频分镜导演。请将场景大段落拆解为多个 15 秒以内的小段落分镜提示词。

规则：
1. 必须严格按照原始剧情拆解，不允许增加剧情、删减剧情、改变台词、改变剧情顺序。
2. 每个小段落最多 {{max_segment_seconds}} 秒，通常包含 3 到 6 行分镜。
3. 每个小段落第一行必须是后台风格提示词；copy_text 中不要出现序号、解释或 markdown。
4. 每一行分镜必须使用格式：【景别】【画面描述，包含人物台词】。
5. 景别只能使用：远景、全景、中景、近景、特写、俯视、仰视、过肩镜头、反打镜头、空镜。
6. 如果人物有台词，必须完整保留台词。
7. 如果上下小段落剧情动作连续，将上一小段最后一行作为当前小段落的承接镜头，放在风格提示词之后，并标记 is_continuity_anchor=true。
8. 承接镜头不能改写，必须和上一小段最后一行完全一致。
9. 每个小段落只输出剧情分镜提示词，不要生成站位图、站位图提示词或 position_layout。
10. 输出严格 JSON，不要 markdown 或解释。

输出格式：
{
  "segments": [
    {
      "segment_title": "",
      "estimated_duration": 0,
      "scene_view": "front",
      "continuity_from_previous": false,
      "previous_anchor_line": "",
      "shot_lines": [
        {"shot_size": "", "description": "", "dialogue": "", "line_text": "", "is_continuity_anchor": false}
      ],
      "copy_text": ""
    }
  ]
}"""

DEFAULT_SCRIPT_POSITION_PROMPT = """请生成一张影视开场站位参考图，画面无文字、无字幕、无水印，高清，空间关系清晰。

风格要求：
{{style_prompt}}

场景信息：
{{scene_block}}

当前15秒小段剧情分镜：
{{segment_copy_text}}

用户站位描述：
{{position_description}}

已上传并引用的素材：
{{referenced_assets}}

要求：
1. 保持已上传场景、角色、道具的外观一致。
2. 只表现这一小段开始时的站位关系。
3. 清楚表达角色左右、前后、朝向、距离、道具归属和镜头方向。
4. 不要添加剧本没有出现的新角色或新道具。
5. 这是一张导演用站位参考图，不要出现任何文字标注。"""

DEFAULT_SCRIPT_VALIDATE_PROMPT = """请校验 AI 拆剧结果是否严格符合原始剧本。

校验规则：
1. 是否增加、删减或篡改原剧本剧情和台词。
2. 是否改变人物关系和剧情顺序。
3. 每个小段落 estimated_duration 是否超过 {{max_segment_seconds}} 秒。
4. 每行分镜是否符合格式：【景别】【画面描述，包含人物台词】。
5. 每个小段落 copy_text 第一行是否是后台风格提示词。
6. 如果小段落之间剧情连续，是否正确添加承接镜头。
7. 是否缺少关键角色、关键道具或场景信息。

如果没有问题，输出：
{"valid": true, "errors": [], "fixed_json": null}

如果有问题，请输出：
{"valid": false, "errors": [{"type": "", "message": "", "location": ""}], "fixed_json": {}}

fixed_json 必须在不增加、不减少剧情的前提下修复问题。"""
