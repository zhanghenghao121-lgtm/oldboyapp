DEFAULT_STORYBOARD_SCENE_SPLIT_PROMPT = """你是一名影视导演和故事板规划师。
请将用户输入的剧情先按场景变化拆分为若干大段内容。场景变化包括地点、时间、连续动作空间或核心冲突发生明显变化。

要求：
1. 只依据原始剧情，不补造关键事件、人物关系或结局。
2. 每个大段保留足够原文信息，便于继续拆为九宫格画面的最小剧情段。
3. 输出严格 JSON，不要 markdown 和解释。

输出格式：
{
  "project_title": "故事标题",
  "scene_blocks": [
    {
      "order": 1,
      "title": "段落标题",
      "scene_name": "场景名称",
      "time_of_day": "时间",
      "mood": "情绪氛围",
      "summary": "本段内容概述",
      "original_text": "覆盖的剧情内容",
      "split_reason": "为何在此处分段"
    }
  ]
}"""

DEFAULT_STORYBOARD_LEAF_SPLIT_PROMPT = """你是一名分镜导演。请判断给定剧情段是否适合由一张包含 9 个连续分镜的故事板图完整表达。

判断标准：
1. 段落应处于同一或视觉连续的场景内。
2. 角色、动作和情绪变化能由 9 个镜头连续呈现，不应包含过多时间跳跃或新场景。
3. 如果信息量过大，必须继续拆成按顺序衔接的更小段落。
4. 只能使用原段落已有剧情信息。

输出严格 JSON：
{
  "can_be_9_grid": true,
  "score": 92,
  "reason": "判断理由",
  "analysis": "适合九宫格表现的核心动作和空间关系",
  "children": [
    {
      "order": 1,
      "title": "子段标题",
      "summary": "子段概述",
      "original_text": "子段剧情内容",
      "split_reason": "拆解原因"
    }
  ]
}

当 can_be_9_grid 为 true 时，children 必须为空数组。"""

DEFAULT_STORYBOARD_ASSET_PROMPT = """你是一名故事板美术统筹。请从可用于一张九宫格分镜图的剧情段落中，提取生成画面需要由用户上传参考图的素材。

要求：
1. 提取人物、场景、关键道具、服装和可选风格参考。
2. 不添加原剧情没有的重要资产。
3. description 要便于用户确认应上传哪一张参考图。
4. 输出严格 JSON。

输出格式：
{
  "characters": [{"name": "人物名", "description": "外观/身份/本段作用"}],
  "scenes": [{"name": "场景名", "description": "空间和光线特征"}],
  "props": [{"name": "道具名", "description": "形态和用途"}],
  "costumes": [{"name": "服装名", "description": "服装参考要求"}],
  "style_refs": [{"name": "风格参考", "description": "需要保持的视觉风格"}]
}"""

DEFAULT_STORYBOARD_PANEL_PROMPT = """你是一名导演和分镜提示词工程师。请根据剧情叶子段以及用户已经上传的素材参考，设计一张 3x3 九宫格故事板所需要的 9 个连续镜头。

要求：
1. 必须输出且只输出 9 个分镜，panel_no 从 1 到 9。
2. 9 个镜头共同完整表达本段剧情，镜头连续、空间关系稳定、人物不越轴。
3. screen_description 是用户可读的分镜画面说明。
4. image_prompt 是可直接交给图像生成模型生成单张分镜图的中文提示词，明确人物、动作、机位、景别、场景、光线、构图和素材一致性。
5. video_prompt 为后续图生视频保留动作和镜头运动线索。
6. 素材参考中出现的人物、场景或道具，需在相应分镜提示词中明确保持参考图一致。
7. 不要求生图模型在画面内绘制任何文字或分镜号，编号由系统排版。
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
      "video_prompt": "图生视频提示词",
      "emotion": "情绪",
      "characters": ["人物名"],
      "props": ["道具名"]
    }
  ]
}"""
