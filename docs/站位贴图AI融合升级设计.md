# 站位贴图 AI 融合升级设计

## 1. 背景与目标

本文档用于交给 Codex 实施站位贴图功能升级，参考 `d:\document\md文档\自然融合-new.md`，并结合当前项目已有实现进行落地设计。

当前项目已有能力：

- 前端入口：`frontend/src/components/StickerComposer.vue`
- 后端服务：`backend/apps/ai_customer/cutout_services.py`
- 资产模型：`PositionStickerAsset`
- 历史合成模型：`PositionStickerComposition`
- 生图服务封装：`submit_ai_image_generation`
- remove.bg 配置：`remove_bg_api_key`
- 豆包 Seedream 配置：`doubao-seedream-5-0-260128`

本次升级目标：

1. 取消“免费快速抠图”功能。
2. 用户上传人物形象图后，先调用 `doubao-seedream-5-0-260128` 自动生成：
   - 人物正面全身图，背景空白；
   - 人物背面全身图，背景空白。
3. 再分别调用 remove.bg，把正面全身图和背面全身图处理成透明 PNG 素材。
4. 资产库展示正面/背面透明素材，用户可选择其一放入站位画布。
5. 原“自然融合”升级为“AI 融合”，调用 Seedream 根据：
   - 原始场景图；
   - 站位贴图参考图；
   - 人物透明素材；
   - 图层位置数据；
   生成最终人物融入场景的画面。
6. 后续代码改动完成验证后，默认提交并推送到 `main`，触发当前仓库自动部署。

## 2. 产品流程

新版用户流程：

```text
上传场景图
  ↓
上传人物形象图
  ↓
Seedream 生成正面全身白/空背景图
  ↓
remove.bg 生成正面透明 PNG
  ↓
Seedream 生成背面全身白/空背景图
  ↓
remove.bg 生成背面透明 PNG
  ↓
资产库展示正面/背面人物素材
  ↓
用户选择素材添加到画布
  ↓
拖动、缩放、旋转、调整层级
  ↓
生成站位贴图参考图
  ↓
调用 Seedream AI 融合
  ↓
保存最终图到 COS，并记录历史
```

## 3. 范围定义

### 3.1 必须实现

- 移除前端“免费快速抠图”选项。
- 后端停用 `fast` 模式，不再调用 OpenCV 白底抠图。
- 新增人物素材生成流程：
  - 上传原始人物图；
  - Seedream 生成正面全身图；
  - remove.bg 处理正面透明图；
  - Seedream 生成背面全身图；
  - remove.bg 处理背面透明图；
  - 保存所有中间图和最终透明图到 COS。
- 资产库支持正面/背面素材展示和添加。
- 图层 JSON 保存素材朝向、来源资产、原始图、生成图等信息。
- 合成流程新增“站位参考图”概念。
- “AI 融合”必须调用 Seedream，不再依赖本地 Pillow 阴影、色温、边缘柔化作为最终融合方案。
- 错误信息必须落库并返回给前端。
- API Key 不得下发到浏览器，不得打印完整明文。

### 3.2 暂不实现

- 不做 3D 姿态编辑。
- 不做视频生成。
- 不做多帧连续性。
- 不做积分扣费，保留扩展点即可。
- 不重建全新 composer app，优先复用 `ai_customer` 现有结构。

## 4. 数据模型改造

### 4.1 PositionStickerAsset 扩展

当前模型只有一个透明素材。新版需要一个人物资产包含正面和背面两套素材。

建议扩展字段：

```python
class PositionStickerAsset(models.Model):
    MODE_SEEDREAM = "seedream"
    MODE_TRANSPARENT = "transparent"

    STATUS_PENDING = "pending"
    STATUS_GENERATING_FRONT = "generating_front"
    STATUS_MATTING_FRONT = "matting_front"
    STATUS_GENERATING_BACK = "generating_back"
    STATUS_MATTING_BACK = "matting_back"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    # existing fields:
    # user, file_record, name, cutout_mode, width, height, created_at

    status = models.CharField(max_length=32, default=STATUS_SUCCESS)
    error_message = models.TextField(blank=True, default="")

    original_file_record = models.ForeignKey(
        "storage.UploadedFileRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    front_fullbody_record = models.ForeignKey(
        "storage.UploadedFileRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    back_fullbody_record = models.ForeignKey(
        "storage.UploadedFileRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    front_transparent_record = models.ForeignKey(
        "storage.UploadedFileRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    back_transparent_record = models.ForeignKey(
        "storage.UploadedFileRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    front_prompt = models.TextField(blank=True, default="")
    back_prompt = models.TextField(blank=True, default="")
```

兼容要求：

- 旧字段 `file_record` 可继续代表默认透明素材，建议指向正面透明素材。
- 旧 `fast` 资产仍可显示历史，但不允许新建。
- 序列化时新增：
  - `status`
  - `error_message`
  - `original_url`
  - `front_fullbody_url`
  - `back_fullbody_url`
  - `front_transparent_url`
  - `back_transparent_url`

### 4.2 PositionStickerComposition 扩展

当前模型可继续使用，建议增加：

```python
placement_reference_file_record = models.ForeignKey(
    "storage.UploadedFileRecord",
    null=True,
    blank=True,
    on_delete=models.SET_NULL,
    related_name="+",
)
ai_fusion_model = models.CharField(max_length=100, blank=True, default="")
ai_fusion_prompt = models.TextField(blank=True, default="")
```

如果希望更干净，也可新增 `PositionStickerFusionJob` 记录每次 AI 融合任务：

```python
class PositionStickerFusionJob(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    composition = models.ForeignKey(PositionStickerComposition, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=32, default=STATUS_PENDING)
    model_key = models.CharField(max_length=100, default="doubao-seedream-5-lite")
    prompt = models.TextField(blank=True, default="")
    input_payload = models.JSONField(default=dict)
    output_payload = models.JSONField(default=dict)
    result_file_record = models.ForeignKey("storage.UploadedFileRecord", null=True, blank=True, on_delete=models.SET_NULL)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

第一版可以同步生成并只扩展 `PositionStickerComposition`，但建议使用 job 模型，方便长任务轮询和失败排查。

## 5. 后端服务设计

### 5.1 停用免费快速抠图

修改 `cutout_character`：

- 不再接受 `fast` 模式。
- `fast` 入参直接返回 400：

```text
免费快速抠图已下线，请上传人物形象图生成正背面透明素材，或上传已有透明 PNG。
```

- 前端不再显示该入口。
- `_fast_white_background_cutout` 可保留以兼容旧代码，但新流程不再调用；也可后续删除 OpenCV 依赖。

### 5.2 人物正背面素材生成

新增服务函数：

```python
def generate_position_sticker_character(file_obj, user, *, save_to_library=True) -> dict:
    """
    上传人物形象图后：
    1. 保存原图；
    2. Seedream 生成正面全身图；
    3. remove.bg 处理正面透明 PNG；
    4. Seedream 生成背面全身图；
    5. remove.bg 处理背面透明 PNG；
    6. 更新 PositionStickerAsset；
    7. 返回资产序列化结果。
    """
```

同步第一版可以直接在 `/ai-image/cutout` 内完成，但需把前端超时调大。更推荐新增异步接口：

```http
POST /api/v1/ai-image/position-assets
GET  /api/v1/ai-image/position-assets
GET  /api/v1/ai-image/position-assets/{id}
```

当前项目已有 Celery worker，推荐使用 Celery 执行 Seedream + remove.bg 长任务。

### 5.3 Seedream 调用

复用 `submit_ai_image_generation`：

```python
result = submit_ai_image_generation(
    prompt=prompt,
    model="doubao-seedream-5-lite",
    size="3:4",
    resolution="2k",
    reference_images=[
        {
            "field": "character_reference",
            "label": "人物形象参考图",
            "name": "人物形象参考图",
            "data_url": _generation_reference_url(original_url, user),
        }
    ],
)
```

注意：

- `doubao-seedream-5-lite` 在 `runtime_config.py` 中会映射到后台配置的 `doubao-seedream-5-0-260128`。
- Seedream 返回远程 URL 时必须立即转存 COS。
- 可复用 `_persist_storyboard_png`，也可以新增更语义化的 `_persist_sticker_png`。

### 5.4 正面全身图提示词

```text
根据上传的人物形象参考图，生成该人物的正面全身角色素材图。

要求：
1. 人物正面朝向镜头，完整全身，从头到脚都要显示。
2. 保持人物五官、发型、发色、服装款式、服装颜色、饰品、体型和气质与参考图一致。
3. 姿势自然站立，双脚可见，身体不要被遮挡。
4. 背景必须为空白纯色背景，干净简单，适合后续 remove.bg 抠图。
5. 只生成一个人物，不要多人，不要文字、水印、边框或 UI。
6. 高清，人物居中，边缘完整，留出少量边距。
```

### 5.5 背面全身图提示词

```text
根据上传的人物形象参考图，生成该人物的背面全身角色素材图。

要求：
1. 人物背对镜头，完整全身，从头到脚都要显示。
2. 保持发型、发色、服装款式、服装颜色、饰品、体型比例和整体气质与参考图一致。
3. 背面服装结构要与正面设定合理一致。
4. 姿势自然站立，双脚可见，身体不要被遮挡。
5. 背景必须为空白纯色背景，干净简单，适合后续 remove.bg 抠图。
6. 只生成一个人物，不要多人，不要文字、水印、边框或 UI。
7. 高清，人物居中，边缘完整，留出少量边距。
```

### 5.6 remove.bg 处理

复用 `_remove_bg_cutout`：

```python
front_png_bytes, front_width, front_height = _remove_bg_cutout(
    front_fullbody_bytes,
    "front-fullbody.png",
    "image/png",
)
```

注意：

- remove.bg 失败要更新资产状态为 `failed`。
- 错误信息直接显示给前端，但不要包含 API Key。
- 透明 PNG 仍保存到 `images/cutouts/...`，以兼容现有 `aiImageCutoutAssetUrl` 和图层校验。

## 6. AI 融合设计

### 6.1 站位参考图

当前前端会先把画布导出为合成图。新版把这个图明确命名为“站位参考图”。

站位参考图作用：

- 告诉 AI 人物位置；
- 告诉 AI 人物大小；
- 告诉 AI 朝向；
- 告诉 AI 遮挡层级；
- 不要求本地图像自然融合。

### 6.2 AI 融合入参

`enhance_sticker_composite` 需要升级为多参考图：

```python
references = [
    {"field": "scene", "label": "原始场景图", "data_url": scene_data_url},
    {"field": "placement_reference", "label": "站位贴图参考图", "data_url": composite_data_url},
    {"field": "character_1", "label": "人物透明素材 1", "data_url": material_data_url},
]
```

`payload` 应包含：

- `scene_key`
- `placement_reference_key` 或 `composite_key`
- `layers`
- `canvas_width`
- `canvas_height`

### 6.3 AI 融合提示词

```text
请根据原始场景图、站位贴图参考图和人物透明素材，生成一张 AI 融合后的最终画面。

核心要求：
1. 以原始场景图作为最终背景基础，保持场景结构、空间布局、家具、门窗、墙体、地面、主要物体不变。
2. 以站位贴图参考图作为人物位置参考，严格保持每个人物的位置、大小、朝向、旋转关系和遮挡层级。
3. 以人物透明素材作为人物形象参考，保持人物身份、五官、发型、服装、体型、饰品和整体气质一致。
4. 不要增加人物，不要删除人物，不要改变人物数量。
5. 不要交换人物身份，不要移动人物站位，不要改变正面/背面朝向。
6. 让人物自然融入场景，而不是贴图效果。
7. 根据场景光源方向，为人物添加合理的光照、明暗关系、脚底接触阴影和环境反射。
8. 统一人物与背景的色温、对比度、清晰度、景深、颗粒和边缘过渡。
9. 输出高清干净的最终剧照，不要文字、水印、边框或 UI。
```

多人物追加：

```text
画面中共有 {count} 个人物。必须保持数量为 {count}，不要多生成、不要漏生成。每个人物位置以站位贴图参考图为准，不要交换人物位置。
```

## 7. API 调整

### 7.1 上传人物形象并生成素材

推荐新增：

```http
POST /api/v1/ai-image/position-assets
```

请求：

```text
multipart/form-data
file: image
name: string optional
save_to_library: true
```

同步返回：

```json
{
  "id": 1,
  "status": "pending",
  "name": "角色",
  "original_url": "https://...",
  "front_transparent_url": "",
  "back_transparent_url": "",
  "error_message": ""
}
```

查询：

```http
GET /api/v1/ai-image/position-assets/{id}
```

成功返回：

```json
{
  "id": 1,
  "status": "success",
  "front_transparent": {
    "key": "images/cutouts/...",
    "url": "https://...",
    "width": 768,
    "height": 1536
  },
  "back_transparent": {
    "key": "images/cutouts/...",
    "url": "https://...",
    "width": 768,
    "height": 1536
  }
}
```

兼容方案：

- 也可暂时复用 `POST /api/v1/ai-image/cutout`。
- 当前 `mode=ai` 改为新版“生成正背面人物素材”。
- `mode=transparent` 保留，供用户上传已有透明图。
- `mode=fast` 禁用。

### 7.2 AI 融合接口

当前接口：

```http
POST /api/v1/ai-image/sticker-compositions/enhance
```

建议继续复用，但语义改为 AI 融合。请求增加：

```json
{
  "scene_key": "images/composites/original-scene.png",
  "placement_reference_key": "images/composites/placement.png",
  "layers": [
    {
      "id": "character-1",
      "name": "角色",
      "key": "images/cutouts/front.png",
      "orientation": "front",
      "left": 100,
      "top": 200,
      "scale_x": 0.5,
      "scale_y": 0.5,
      "angle": 0,
      "z_index": 1
    }
  ]
}
```

返回：

```json
{
  "url": "https://...",
  "key": "images/sticker_fusions/...",
  "model": "doubao-seedream-5-0-260128",
  "prompt": "..."
}
```

## 8. 前端改造

### 8.1 上传人物模块

从：

```text
免费快速抠图 / AI 精细抠图 / 透明图直传
```

改为：

```text
生成人物素材 / 透明图直传
```

推荐文案：

- 生成人物素材：上传人物形象图，自动生成正面/背面透明全身素材。
- 透明图直传：上传已带透明通道的 PNG 或 WebP。

### 8.2 资产库展示

每个人物资产展示：

```text
角色名
状态：生成中 / 成功 / 失败
[正面素材] 添加
[背面素材] 添加
```

生成中状态需要展示阶段：

- 正在生成正面全身图
- 正在处理正面透明素材
- 正在生成背面全身图
- 正在处理背面透明素材

### 8.3 图层数据

新增字段：

```json
{
  "id": "character-1",
  "type": "character",
  "asset_id": 12,
  "name": "角色",
  "orientation": "front",
  "key": "images/cutouts/...",
  "url": "https://...",
  "mode": "seedream",
  "left": 100,
  "top": 200,
  "scale_x": 0.5,
  "scale_y": 0.5,
  "angle": 0,
  "opacity": 1,
  "flip_x": false,
  "flip_y": false,
  "z_index": 1
}
```

### 8.4 合成方式

从：

```text
普通合成 / 自然融合
```

改为：

```text
站位参考图 / AI 融合
```

第一版可以保留一个主按钮：

```text
AI 融合生成
```

按钮逻辑：

1. 前端导出当前画布为站位参考图。
2. 上传站位参考图到 COS。
3. 调用 AI 融合接口。
4. 保存最终图和历史记录。

## 9. 兼容与迁移

- 旧 `fast` 资产继续可用于历史编辑，但前端显示为“旧版快速抠图”。
- 新建不再允许 `fast`。
- 旧 `natural` 历史继续显示为“旧版自然融合”。
- 新 AI 融合结果仍保存到 `PositionStickerComposition`，历史记录可继续复用。
- 新增字段必须允许空值，避免旧数据迁移失败。

## 10. 验收标准

### 10.1 人物素材生成

- 上传普通人物图后，后台创建资产记录。
- 自动生成正面全身图。
- 自动生成背面全身图。
- 正面和背面都成功通过 remove.bg 生成透明 PNG。
- COS 中能访问所有图片。
- 前端资产库能显示正面/背面素材。
- 正面/背面素材都能添加到画布。

### 10.2 站位编辑

- 支持拖动、缩放、旋转、删除。
- 支持图层上移/下移。
- 图层 JSON 正确保存 `asset_id`、`orientation`、`key`、位置和缩放信息。
- 历史记录可恢复编辑。

### 10.3 AI 融合

- 点击 AI 融合后，前端先上传站位参考图。
- 后端使用原始场景图、站位参考图、人物透明素材调用 Seedream。
- 最终图保存到 COS。
- 最终图人物位置基本遵守站位参考图。
- 人物自然融入场景，有合理光影和脚底接触阴影。
- 失败时前端显示具体错误，后端记录错误。

### 10.4 安全

- 浏览器接口不返回 API Key。
- 日志不打印完整 API Key。
- remove.bg 和 Seedream Key 均只在后端读取。

## 11. 推荐实现顺序

1. 后端模型迁移：扩展 `PositionStickerAsset`，可选新增 `PositionStickerFusionJob`。
2. 后端停用 `fast`，保留 `transparent`。
3. 后端实现 Seedream 正面/背面生成服务。
4. 后端实现 remove.bg 串联透明化。
5. 后端实现资产状态查询接口。
6. 前端上传人物图后轮询资产生成状态。
7. 前端资产库支持正面/背面添加到画布。
8. 前端图层 JSON 加入 `asset_id` 和 `orientation`。
9. 后端升级 `enhance_sticker_composite` 为 AI 融合多参考图。
10. 前端将“自然融合”改为“AI 融合生成”。
11. 增加测试。
12. 提交并推送 `main`，确认 GitHub Actions 部署成功。

## 12. 测试建议

后端测试：

```text
1. fast 模式返回已下线错误。
2. transparent 模式仍可上传透明 PNG。
3. Seedream 人物素材生成成功时，正面/背面记录完整。
4. remove.bg 失败时资产状态为 failed。
5. AI 融合接口会传入场景图、站位参考图和人物透明素材。
6. 旧历史记录序列化不报错。
```

前端测试：

```text
1. 上传人物图后显示生成进度。
2. 正面素材可添加到画布。
3. 背面素材可添加到画布。
4. 图层操作正常。
5. AI 融合生成时按钮 loading 和错误提示正常。
6. 历史记录可打开最终图并恢复图层。
```

生产验证：

```text
1. backend 容器可访问 ark.cn-beijing.volces.com。
2. remove.bg API Key 有效且额度正常。
3. COS CORS 允许前端读取图片并导出 canvas。
4. GitHub Actions 自动部署成功。
5. /api/v1/healthz 返回 ok。
```

## 13. Codex 执行约定

给 Codex 实施时，请按以下约定执行：

```text
请基于 docs/站位贴图AI融合升级设计.md 实施站位贴图升级。

要求：
1. 优先复用现有 ai_customer 模块，不要新建无必要的大模块。
2. 取消免费快速抠图入口和新建能力。
3. 上传人物形象图后，使用 doubao-seedream-5-0-260128 生成正面/背面全身空背景图。
4. 使用 remove.bg 将正面/背面全身图转为透明 PNG。
5. 自然融合升级为 AI 融合，必须把原始场景图、站位参考图、人物透明素材都作为参考图传给 Seedream。
6. API Key 只允许后端读取，不能下发到前端。
7. 保持旧历史记录尽量可读可编辑。
8. 增加必要测试并运行。
9. 完成后提交并推送代码到 main，等待自动部署完成并回传结果。
```
