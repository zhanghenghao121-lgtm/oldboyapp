<template>
  <section class="composer-grid">
    <aside class="composer-controls">
      <div class="control-card">
        <h3>1. 上传场景背景</h3>
        <label class="file-drop">
          <input type="file" accept="image/*" @change="handleSceneUpload" />
          <strong>{{ sceneName || '选择一张场景图' }}</strong>
          <span>作为最底层，角色会叠加在该图片上</span>
        </label>
      </div>

      <div class="control-card">
        <h3>2. 上传角色或透明图</h3>
        <el-radio-group v-model="cutoutMode" class="cutout-modes">
          <el-radio-button value="fast">免费快速抠图</el-radio-button>
          <el-radio-button value="ai">AI 精细抠图</el-radio-button>
          <el-radio-button value="transparent">透明图直传</el-radio-button>
        </el-radio-group>
        <p class="hint">{{ cutoutHint }}</p>
        <label class="file-drop compact" :class="{ disabled: !hasScene || cutting }">
          <input type="file" accept="image/*" :disabled="!hasScene || cutting" @change="handleCharacterUpload" />
          <strong>{{ cutting ? uploadBusyText : uploadActionText }}</strong>
          <span>{{ hasScene ? uploadTipText : '请先上传场景图' }}</span>
        </label>
        <el-checkbox v-model="saveToLibrary" class="save-option">处理后保存到资产库</el-checkbox>
      </div>

      <div class="control-card library-card">
        <div class="card-head">
          <h3>3. 资产库</h3>
          <el-button text size="small" :loading="libraryLoading" @click="loadAssetLibrary">刷新</el-button>
        </div>
        <div v-if="libraryLoading && !assetLibrary.length" class="no-layer">正在加载资产...</div>
        <div v-else-if="!assetLibrary.length" class="no-layer">勾选保存后，处理过的透明素材会留在这里。</div>
        <div v-else class="asset-list">
          <div v-for="asset in assetLibrary" :key="asset.id" class="asset-row">
            <img :src="aiImageCutoutAssetUrl(asset.key)" :alt="asset.name" />
            <div class="asset-info">
              <strong>{{ asset.name }}</strong>
              <small>{{ cutoutModeLabel(asset.mode) }}</small>
            </div>
            <el-button text size="small" :loading="addingAssetId === asset.id" :disabled="!hasScene" @click="addAssetToCanvas(asset)">添加</el-button>
            <el-button text size="small" class="remove-asset" @click="deleteAsset(asset)">移除</el-button>
          </div>
        </div>
      </div>

      <div class="control-card layers-card">
        <div class="card-head">
          <h3>4. 图层</h3>
          <span>{{ layers.length }} 个素材</span>
        </div>
        <div v-if="!layers.length" class="no-layer">处理后的透明素材会出现在这里。</div>
        <button
          v-for="layer in layers"
          :key="layer.id"
          type="button"
          class="layer-row"
          :class="{ selected: selectedId === layer.id }"
          @click="selectLayer(layer.id)"
        >
          <span>{{ layer.name }}</span>
          <small>{{ layerModeLabel(layer.mode) }}</small>
        </button>
        <div class="layer-actions">
          <el-button size="small" plain :disabled="!selectedId" @click="moveSelected('down')">下移</el-button>
          <el-button size="small" plain :disabled="!selectedId" @click="moveSelected('up')">上移</el-button>
          <el-button size="small" plain :disabled="!selectedId" @click="removeSelected">删除</el-button>
        </div>
      </div>

      <div class="control-card history-card">
        <div class="card-head">
          <h3>5. 合成方式</h3>
        </div>
        <el-radio-group v-model="blendMode" class="blend-modes">
          <el-radio-button value="normal">普通合成</el-radio-button>
          <el-radio-button value="natural">自然融合</el-radio-button>
        </el-radio-group>
        <p class="hint compact">{{ blendModeHint }}</p>
      </div>

      <div class="control-card history-card">
        <div class="card-head">
          <h3>6. 历史记录</h3>
          <el-button text size="small" :loading="historyLoading" @click="loadCompositionHistory">刷新</el-button>
        </div>
        <div v-if="historyLoading && !compositionHistory.length" class="no-layer">正在加载历史...</div>
        <div v-else-if="!compositionHistory.length" class="no-layer">合成图片后会自动保存可编辑记录。</div>
        <div v-else class="history-list">
          <div v-for="item in compositionHistory" :key="item.id" class="history-row">
            <img :src="historyPreviewUrl(item)" :alt="item.title || item.scene_name || '站位贴图'" />
            <div class="history-info">
              <strong>{{ item.title || item.scene_name || '站位贴图' }}</strong>
              <small>{{ blendModeLabel(item.blend_mode) }} · {{ formatHistoryTime(item.updated_at || item.created_at) }}</small>
            </div>
            <el-button text size="small" :loading="editingHistoryId === item.id" @click="editHistory(item)">编辑</el-button>
            <el-button text size="small" @click="previewHistory(item)">预览</el-button>
            <el-button text size="small" class="remove-asset" :loading="deletingHistoryId === item.id" @click="deleteHistory(item)">删除</el-button>
          </div>
        </div>
      </div>

      <div class="compose-actions">
        <el-button plain @click="resetComposer">清空画布</el-button>
        <el-button class="generate-btn" type="primary" :loading="composing" :disabled="!hasScene || sceneUploading || !layers.length" @click="composeImage">
          开始合成
        </el-button>
      </div>
    </aside>

    <div class="canvas-panel">
      <header class="canvas-head">
        <div>
          <h3>场景画布</h3>
          <p>点击角色后拖动、缩放或旋转；图层列表控制遮挡顺序。</p>
        </div>
        <el-button v-if="compositeUrl" type="primary" plain @click="openComposite">打开合成图</el-button>
      </header>
      <div class="canvas-frame" v-loading="cutting || composing || sceneUploading || !!editingHistoryId">
        <canvas ref="canvasElement"></canvas>
      </div>
      <div v-if="compositeUrl" class="composite-result">
        <span>合成结果已上传</span>
        <a :href="compositeUrl" target="_blank" rel="noopener noreferrer">{{ compositeUrl }}</a>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Canvas, FabricImage } from 'fabric'

import {
  aiImageCutoutAssetUrl,
  createAiImageStickerComposition,
  cutoutAiImageCharacter,
  deleteAiImageStickerComposition,
  deleteAiImageCutoutAsset,
  getAiImageCutoutAssets,
  getAiImageStickerCompositions,
} from '../api/aiImage'
import { storageFileUrl, uploadToCos } from '../api/storage'

const canvasElement = ref(null)
const sceneName = ref('')
const sceneKey = ref('')
const sceneUrl = ref('')
const hasScene = ref(false)
const cutoutMode = ref('fast')
const blendMode = ref('natural')
const saveToLibrary = ref(false)
const cutting = ref(false)
const composing = ref(false)
const sceneUploading = ref(false)
const libraryLoading = ref(false)
const historyLoading = ref(false)
const assetLibrary = ref([])
const compositionHistory = ref([])
const addingAssetId = ref('')
const editingHistoryId = ref('')
const deletingHistoryId = ref('')
const layers = ref([])
const selectedId = ref('')
const compositeUrl = ref('')
let editor = null
let layerCounter = 0

const cutoutHint = computed(() => {
  if (cutoutMode.value === 'transparent') return '适合已经带透明通道的 PNG 或 WebP，不调用抠图服务。'
  if (cutoutMode.value === 'ai') return '适合复杂背景，将调用 remove.bg 服务。'
  return '适合纯白或接近白色背景，不消耗 AI 抠图额度。'
})
const uploadActionText = computed(() => (cutoutMode.value === 'transparent' ? '上传透明图片' : '添加角色图片'))
const uploadBusyText = computed(() => (cutoutMode.value === 'transparent' ? '正在上传透明图...' : '正在抠图并上传...'))
const uploadTipText = computed(() => (cutoutMode.value === 'transparent' ? '可直接添加已抠除背景的透明素材' : '可连续添加多个角色'))
const blendModeHint = computed(() =>
  blendMode.value === 'natural'
    ? '添加脚底接触阴影、柔化透明边缘、减少白边，并让人物亮度和色温更接近背景。'
    : '只按当前图层位置、大小、旋转和透明度直接叠加，适合快速站位草稿。'
)

const cutoutModeLabel = (mode) => {
  if (mode === 'transparent') return '透明图直传'
  if (mode === 'ai') return 'AI 精细抠图'
  return '免费快速抠图'
}

const layerModeLabel = (mode) => {
  if (mode === 'transparent') return '透明'
  if (mode === 'ai') return 'AI'
  return '免费'
}

const blendModeLabel = (mode) => (mode === 'natural' ? '自然融合' : '普通合成')

const imageDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.readAsDataURL(file)
  })

const historyPreviewUrl = (item) => storageFileUrl(item.result_key || item.result_url || '')

const formatHistoryTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', { hour12: false })
}

const applyEditableStyle = (image) => {
  image.set({
    cornerColor: '#6ee7ac',
    borderColor: '#6ee7ac',
    transparentCorners: false,
  })
}

const setSceneBackground = async (source, width, height) => {
  const image = await FabricImage.fromURL(source)
  editor.clear()
  editor.setDimensions({ width, height })
  image.set({
    left: 0,
    top: 0,
    scaleX: width / image.width,
    scaleY: height / image.height,
    selectable: false,
    evented: false,
  })
  editor.backgroundImage = image
  editor.backgroundColor = '#0b1213'
  editor.requestRenderAll()
}

const normalizeCanvasDimension = (value, fallback) => {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? Math.round(number) : fallback
}

const captureCanvasSnapshot = () => ({
  scene_name: sceneName.value,
  scene_key: sceneKey.value,
  scene_url: sceneUrl.value,
  blend_mode: blendMode.value,
  canvas_width: normalizeCanvasDimension(editor.width, 760),
  canvas_height: normalizeCanvasDimension(editor.height, 500),
  layers: editor.getObjects().map((object) => ({
    id: object.stickerId,
    name: object.stickerName,
    key: object.stickerKey,
    url: object.stickerUrl,
    mode: object.cutoutMode,
    left: object.left || 0,
    top: object.top || 0,
    scale_x: object.scaleX || 1,
    scale_y: object.scaleY || 1,
    angle: object.angle || 0,
    opacity: object.opacity ?? 1,
    flip_x: !!object.flipX,
    flip_y: !!object.flipY,
  })),
})

const initializeCanvas = () => {
  editor = new Canvas(canvasElement.value, {
    backgroundColor: '#0b1213',
    preserveObjectStacking: true,
    selectionColor: 'rgba(110, 231, 172, 0.12)',
    selectionBorderColor: '#6ee7ac',
  })
  editor.setDimensions({ width: 760, height: 500 })
  editor.on('selection:created', syncSelection)
  editor.on('selection:updated', syncSelection)
  editor.on('selection:cleared', () => {
    selectedId.value = ''
  })
  editor.on('object:modified', () => {
    compositeUrl.value = ''
    refreshLayers()
  })
}

const refreshLayers = () => {
  layers.value = editor
    ? [...editor.getObjects()].reverse().map((object) => ({
        id: object.stickerId,
        name: object.stickerName,
        mode: object.cutoutMode,
      }))
    : []
}

function syncSelection() {
  selectedId.value = editor?.getActiveObject()?.stickerId || ''
}

const findLayer = (id) => editor?.getObjects().find((item) => item.stickerId === id)

const loadAssetLibrary = async () => {
  libraryLoading.value = true
  try {
    const res = await getAiImageCutoutAssets()
    assetLibrary.value = res.data.list || []
  } catch (error) {
    ElMessage.error(String(error || '资产库加载失败'))
  } finally {
    libraryLoading.value = false
  }
}

const handleSceneUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  try {
    const dataUrl = await imageDataUrl(file)
    const image = await FabricImage.fromURL(dataUrl)
    const scale = Math.min(1040 / image.width, 680 / image.height, 1)
    const width = Math.max(Math.round(image.width * scale), 1)
    const height = Math.max(Math.round(image.height * scale), 1)
    image.scale(scale)
    image.set({ left: 0, top: 0, selectable: false, evented: false })
    editor.clear()
    editor.setDimensions({ width, height })
    editor.backgroundImage = image
    editor.requestRenderAll()
    sceneName.value = file.name
    hasScene.value = true
    sceneKey.value = ''
    sceneUrl.value = ''
    selectedId.value = ''
    compositeUrl.value = ''
    refreshLayers()
    sceneUploading.value = true
    try {
      const uploaded = await uploadToCos(file, 'images/sticker-scenes', { timeout: 120000 })
      sceneKey.value = uploaded.data.key
      sceneUrl.value = uploaded.data.url
    } catch (uploadError) {
      ElMessage.error(String(uploadError || '场景图上传失败，请重新上传后再合成'))
    } finally {
      sceneUploading.value = false
    }
  } catch (error) {
    ElMessage.error(String(error || '场景图加载失败'))
    if (!hasScene.value) {
      sceneName.value = ''
      sceneKey.value = ''
      sceneUrl.value = ''
    }
    sceneUploading.value = false
  }
}

const handleCharacterUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  cutting.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('mode', cutoutMode.value)
    formData.append('save_to_library', saveToLibrary.value ? 'true' : 'false')
    const res = await cutoutAiImageCharacter(formData)
    const item = res.data
    await addCharacterLayer(item, file.name.replace(/\.[^.]+$/, ''))
    if (item.library_asset) {
      assetLibrary.value = [item.library_asset, ...assetLibrary.value.filter((asset) => asset.id !== item.library_asset.id)]
    }
    const actionName = cutoutMode.value === 'transparent' ? '透明图上传完成' : '抠图完成'
    ElMessage.success(item.library_asset ? `${actionName}，已加入画布并保存到资产库` : `${actionName}，已加入画布`)
  } catch (error) {
    ElMessage.error(String(error || '素材处理失败'))
  } finally {
    cutting.value = false
  }
}

const addCharacterLayer = async (item, name) => {
  const image = await FabricImage.fromURL(aiImageCutoutAssetUrl(item.key))
  layerCounter += 1
  image.stickerId = `character-${layerCounter}`
  image.stickerName = name || item.name || `角色 ${layerCounter}`
  image.stickerKey = item.key
  image.stickerUrl = item.url || ''
  image.cutoutMode = item.mode
  const targetHeight = Math.min(editor.height * 0.62, image.height)
  image.scaleToHeight(targetHeight)
  image.set({
    left: (editor.width - image.getScaledWidth()) / 2,
    top: Math.max(editor.height - image.getScaledHeight() - 12, 0),
  })
  applyEditableStyle(image)
  editor.add(image)
  editor.setActiveObject(image)
  editor.requestRenderAll()
  selectedId.value = image.stickerId
  compositeUrl.value = ''
  refreshLayers()
}

const addAssetToCanvas = async (asset) => {
  if (!hasScene.value) {
    ElMessage.warning('请先上传场景图')
    return
  }
  addingAssetId.value = asset.id
  try {
    await addCharacterLayer(asset, asset.name)
    ElMessage.success('资产已加入画布')
  } catch (error) {
    ElMessage.error(String(error || '添加资产失败'))
  } finally {
    addingAssetId.value = ''
  }
}

const deleteAsset = async (asset) => {
  try {
    await ElMessageBox.confirm(`确认从资产库移除“${asset.name}”？`, '移除资产', { type: 'warning' })
    await deleteAiImageCutoutAsset(asset.id)
    assetLibrary.value = assetLibrary.value.filter((item) => item.id !== asset.id)
    ElMessage.success('资产已移除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(String(error || '移除资产失败'))
  }
}

const selectLayer = (id) => {
  const object = findLayer(id)
  if (!object) return
  editor.setActiveObject(object)
  editor.requestRenderAll()
  selectedId.value = id
}

const moveSelected = (direction) => {
  const object = findLayer(selectedId.value)
  if (!object) return
  if (direction === 'up') editor.bringObjectForward(object)
  else editor.sendObjectBackwards(object)
  editor.requestRenderAll()
  refreshLayers()
}

const removeSelected = () => {
  const object = findLayer(selectedId.value)
  if (!object) return
  editor.remove(object)
  selectedId.value = ''
  compositeUrl.value = ''
  editor.requestRenderAll()
  refreshLayers()
}

const resetComposer = () => {
  editor.clear()
  editor.backgroundColor = '#0b1213'
  editor.setDimensions({ width: 760, height: 500 })
  editor.requestRenderAll()
  sceneName.value = ''
  sceneKey.value = ''
  sceneUrl.value = ''
  hasScene.value = false
  selectedId.value = ''
  compositeUrl.value = ''
  refreshLayers()
}

const downloadComposite = (blob, filename) => {
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(objectUrl)
}

const imageFromUrl = (source) =>
  new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('图片加载失败'))
    image.src = source
  })

const canvasToPngBlob = (canvas) =>
  new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), 'image/png'))

const clampChannel = (value) => Math.min(255, Math.max(0, Math.round(value)))

const getAverageTone = (imageData, alphaAware = false) => {
  const data = imageData.data
  let r = 0
  let g = 0
  let b = 0
  let count = 0
  const step = Math.max(4, Math.floor(data.length / 24000) * 4)
  for (let i = 0; i < data.length; i += step) {
    const alpha = alphaAware ? data[i + 3] / 255 : 1
    if (alphaAware && alpha < 0.12) continue
    r += data[i] * alpha
    g += data[i + 1] * alpha
    b += data[i + 2] * alpha
    count += alpha
  }
  if (!count) return { r: 128, g: 128, b: 128, luma: 128 }
  const tone = { r: r / count, g: g / count, b: b / count }
  tone.luma = tone.r * 0.2126 + tone.g * 0.7152 + tone.b * 0.0722
  return tone
}

const sampleSceneTone = (context, rect) => {
  const x = Math.max(0, Math.floor(rect.left))
  const y = Math.max(0, Math.floor(rect.top))
  const width = Math.max(1, Math.min(context.canvas.width - x, Math.ceil(rect.width)))
  const height = Math.max(1, Math.min(context.canvas.height - y, Math.ceil(rect.height)))
  if (width <= 0 || height <= 0) return { r: 128, g: 128, b: 128, luma: 128 }
  return getAverageTone(context.getImageData(x, y, width, height))
}

const processLayerForNaturalBlend = (sourceImage, sceneTone) => {
  const canvas = document.createElement('canvas')
  canvas.width = sourceImage.naturalWidth || sourceImage.width
  canvas.height = sourceImage.naturalHeight || sourceImage.height
  const context = canvas.getContext('2d')
  context.drawImage(sourceImage, 0, 0, canvas.width, canvas.height)

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const layerTone = getAverageTone(imageData, true)
  const data = imageData.data
  const brightnessShift = (sceneTone.luma - layerTone.luma) * 0.18
  const toneStrength = 0.12
  const ambientStrength = 0.06

  for (let i = 0; i < data.length; i += 4) {
    const alpha = data[i + 3] / 255
    if (alpha <= 0) continue

    if (alpha < 0.98) {
      const safeAlpha = Math.max(alpha, 0.18)
      data[i] = clampChannel((data[i] - 255 * (1 - safeAlpha)) / safeAlpha)
      data[i + 1] = clampChannel((data[i + 1] - 255 * (1 - safeAlpha)) / safeAlpha)
      data[i + 2] = clampChannel((data[i + 2] - 255 * (1 - safeAlpha)) / safeAlpha)
    }

    data[i] = clampChannel(data[i] + (sceneTone.r - layerTone.r) * toneStrength + brightnessShift)
    data[i + 1] = clampChannel(data[i + 1] + (sceneTone.g - layerTone.g) * toneStrength + brightnessShift)
    data[i + 2] = clampChannel(data[i + 2] + (sceneTone.b - layerTone.b) * toneStrength + brightnessShift)

    const gray = data[i] * 0.2126 + data[i + 1] * 0.7152 + data[i + 2] * 0.0722
    data[i] = clampChannel(gray + (data[i] - gray) * 0.96 + sceneTone.r * ambientStrength * alpha)
    data[i + 1] = clampChannel(gray + (data[i + 1] - gray) * 0.96 + sceneTone.g * ambientStrength * alpha)
    data[i + 2] = clampChannel(gray + (data[i + 2] - gray) * 0.96 + sceneTone.b * ambientStrength * alpha)
  }

  context.putImageData(imageData, 0, 0)
  return canvas
}

const softenAlphaEdges = (sourceCanvas, radius = 1.2) => {
  const canvas = document.createElement('canvas')
  canvas.width = sourceCanvas.width
  canvas.height = sourceCanvas.height
  const context = canvas.getContext('2d')
  context.drawImage(sourceCanvas, 0, 0)

  const imageData = context.getImageData(0, 0, canvas.width, canvas.height)
  const maskCanvas = document.createElement('canvas')
  maskCanvas.width = canvas.width
  maskCanvas.height = canvas.height
  const maskContext = maskCanvas.getContext('2d')
  const maskData = maskContext.createImageData(canvas.width, canvas.height)

  for (let i = 0; i < imageData.data.length; i += 4) {
    const alpha = imageData.data[i + 3]
    maskData.data[i] = 255
    maskData.data[i + 1] = 255
    maskData.data[i + 2] = 255
    maskData.data[i + 3] = alpha
  }
  maskContext.putImageData(maskData, 0, 0)

  const blurCanvas = document.createElement('canvas')
  blurCanvas.width = canvas.width
  blurCanvas.height = canvas.height
  const blurContext = blurCanvas.getContext('2d')
  blurContext.filter = `blur(${radius}px)`
  blurContext.drawImage(maskCanvas, 0, 0)
  const blurData = blurContext.getImageData(0, 0, canvas.width, canvas.height)

  for (let i = 0; i < imageData.data.length; i += 4) {
    const originalAlpha = imageData.data[i + 3]
    if (originalAlpha <= 0) continue
    const blurredAlpha = blurData.data[i + 3]
    const softenedAlpha = Math.min(originalAlpha, Math.round(blurredAlpha * 1.08))
    imageData.data[i + 3] = originalAlpha > 248 && softenedAlpha > 236 ? originalAlpha : softenedAlpha
  }

  context.putImageData(imageData, 0, 0)
  return canvas
}

const drawContactShadow = (context, object) => {
  const bounds = object.getBoundingRect()
  const width = Math.max(22, Math.min(bounds.width * 0.62, context.canvas.width * 0.34))
  const height = Math.max(7, Math.min(bounds.height * 0.085, 40))
  const centerX = bounds.left + bounds.width / 2
  const centerY = bounds.top + bounds.height - height * 0.04

  context.save()
  context.globalAlpha = Math.min(0.38, Math.max(0.18, Number(object.opacity ?? 1) * 0.34))
  context.filter = `blur(${Math.max(6, Math.min(20, height * 1.2))}px)`
  context.fillStyle = '#050505'
  context.beginPath()
  context.ellipse(centerX, centerY, width / 2, height / 2, 0, 0, Math.PI * 2)
  context.fill()
  context.restore()
}

const drawNaturalLayer = async (context, object) => {
  if (!object?.stickerKey) return
  const source = aiImageCutoutAssetUrl(object.stickerKey)
  const image = await imageFromUrl(source)
  const bounds = object.getBoundingRect()
  const sceneTone = sampleSceneTone(context, bounds)
  const processed = softenAlphaEdges(processLayerForNaturalBlend(image, sceneTone))
  const center = object.getCenterPoint()
  const angle = ((Number(object.angle) || 0) * Math.PI) / 180
  const scaleX = (Number(object.scaleX) || 1) * (object.flipX ? -1 : 1)
  const scaleY = (Number(object.scaleY) || 1) * (object.flipY ? -1 : 1)

  drawContactShadow(context, object)

  context.save()
  context.globalAlpha = Number(object.opacity ?? 1)
  context.translate(center.x, center.y)
  context.rotate(angle)
  context.scale(scaleX, scaleY)
  context.drawImage(processed, -processed.width / 2, -processed.height / 2)
  context.restore()
}

const addSubtleGrain = (context) => {
  const imageData = context.getImageData(0, 0, context.canvas.width, context.canvas.height)
  const data = imageData.data
  for (let i = 0; i < data.length; i += 4) {
    const noise = Math.round((Math.random() - 0.5) * 3)
    data[i] = clampChannel(data[i] + noise)
    data[i + 1] = clampChannel(data[i + 1] + noise)
    data[i + 2] = clampChannel(data[i + 2] + noise)
  }
  context.putImageData(imageData, 0, 0)
}

const createNaturalCompositeBlob = async () => {
  const width = normalizeCanvasDimension(editor.width, 760)
  const height = normalizeCanvasDimension(editor.height, 500)
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  const sceneSource = storageFileUrl(sceneKey.value || sceneUrl.value)
  if (!sceneSource) throw new Error('缺少场景图')

  const background = await imageFromUrl(sceneSource)
  context.fillStyle = '#0b1213'
  context.fillRect(0, 0, width, height)
  context.drawImage(background, 0, 0, width, height)

  for (const object of editor.getObjects()) {
    await drawNaturalLayer(context, object)
  }

  addSubtleGrain(context)
  return canvasToPngBlob(canvas)
}

const loadCompositionHistory = async () => {
  historyLoading.value = true
  try {
    const res = await getAiImageStickerCompositions()
    compositionHistory.value = res.data.list || []
  } catch (error) {
    ElMessage.error(String(error || '历史记录加载失败'))
  } finally {
    historyLoading.value = false
  }
}

const updateLayerCounterFromHistory = (historyLayers) => {
  const maxId = historyLayers.reduce((max, layer) => {
    const match = String(layer.id || '').match(/(\d+)$/)
    return match ? Math.max(max, Number(match[1])) : max
  }, 0)
  layerCounter = Math.max(layerCounter, maxId)
}

const editHistory = async (item) => {
  editingHistoryId.value = item.id
  try {
    const width = normalizeCanvasDimension(item.canvas_width, 760)
    const height = normalizeCanvasDimension(item.canvas_height, 500)
    const sceneSource = storageFileUrl(item.scene_key || item.scene_url || '')
    if (!sceneSource) throw new Error('历史记录缺少场景图')
    await setSceneBackground(sceneSource, width, height)
    const historyLayers = Array.isArray(item.layers) ? item.layers : []
    for (const layer of historyLayers) {
      if (!layer.key) continue
      const image = await FabricImage.fromURL(aiImageCutoutAssetUrl(layer.key))
      image.stickerId = layer.id || `character-${layerCounter + 1}`
      image.stickerName = layer.name || '素材'
      image.stickerKey = layer.key
      image.stickerUrl = layer.url || ''
      image.cutoutMode = layer.mode || 'fast'
      image.set({
        left: Number(layer.left || 0),
        top: Number(layer.top || 0),
        scaleX: Number(layer.scale_x || 1),
        scaleY: Number(layer.scale_y || 1),
        angle: Number(layer.angle || 0),
        opacity: Number(layer.opacity ?? 1),
        flipX: !!layer.flip_x,
        flipY: !!layer.flip_y,
      })
      applyEditableStyle(image)
      editor.add(image)
    }
    updateLayerCounterFromHistory(historyLayers)
    sceneName.value = item.scene_name || item.title || '历史场景'
    sceneKey.value = item.scene_key || ''
    sceneUrl.value = item.scene_url || ''
    blendMode.value = item.blend_mode === 'natural' ? 'natural' : 'normal'
    compositeUrl.value = item.result_url || ''
    hasScene.value = true
    selectedId.value = ''
    editor.discardActiveObject()
    editor.requestRenderAll()
    refreshLayers()
    ElMessage.success('历史记录已载入，可继续编辑')
  } catch (error) {
    ElMessage.error(String(error || '历史记录载入失败'))
  } finally {
    editingHistoryId.value = ''
  }
}

const previewHistory = (item) => {
  const url = storageFileUrl(item.result_key || item.result_url || '')
  if (url) window.open(url, '_blank', 'noopener,noreferrer')
}

const deleteHistory = async (item) => {
  try {
    await ElMessageBox.confirm(`确认删除历史记录“${item.title || item.scene_name || '站位贴图'}”？`, '删除历史记录', { type: 'warning' })
    deletingHistoryId.value = item.id
    await deleteAiImageStickerComposition(item.id)
    compositionHistory.value = compositionHistory.value.filter((history) => history.id !== item.id)
    ElMessage.success('历史记录已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(String(error || '删除历史记录失败'))
  } finally {
    deletingHistoryId.value = ''
  }
}

const composeImage = async () => {
  if (!editor || !hasScene.value || !layers.value.length) return
  if (sceneUploading.value) {
    ElMessage.warning('场景图还在上传，请稍后再合成')
    return
  }
  if (!sceneKey.value) {
    ElMessage.warning('场景图上传未完成，请重新上传场景图后再合成')
    return
  }
  composing.value = true
  try {
    editor.discardActiveObject()
    editor.requestRenderAll()
    const snapshot = captureCanvasSnapshot()
    let blob = null
    if (blendMode.value === 'natural') {
      try {
        blob = await createNaturalCompositeBlob()
      } catch (blendError) {
        console.warn('Natural blend failed, falling back to canvas export.', blendError)
        blob = await editor.toBlob({ format: 'png', multiplier: 1 })
        ElMessage.warning('自然融合处理失败，已使用普通合成导出')
      }
    } else {
      blob = await editor.toBlob({ format: 'png', multiplier: 1 })
    }
    if (!blob) throw new Error('生成合成图失败')
    const filename = `scene-composite-${Date.now()}.png`
    const file = new File([blob], filename, { type: 'image/png' })
    const res = await uploadToCos(file, 'images/composites', { timeout: 120000 })
    compositeUrl.value = res.data.url
    const saved = await createAiImageStickerComposition({
      title: sceneName.value ? `${sceneName.value} 合成` : '站位贴图',
      scene_name: snapshot.scene_name,
      scene_key: snapshot.scene_key,
      scene_url: snapshot.scene_url,
      blend_mode: snapshot.blend_mode,
      result_key: res.data.key,
      result_url: res.data.url,
      canvas_width: snapshot.canvas_width,
      canvas_height: snapshot.canvas_height,
      layers: snapshot.layers,
    })
    compositionHistory.value = [saved.data, ...compositionHistory.value.filter((item) => item.id !== saved.data.id)]
    downloadComposite(blob, filename)
    ElMessage.success(`${blendModeLabel(blendMode.value)}图片已上传，历史记录已保存`)
  } catch (error) {
    ElMessage.error(String(error || '合成失败'))
  } finally {
    composing.value = false
  }
}

const openComposite = () => {
  if (compositeUrl.value) window.open(compositeUrl.value, '_blank', 'noopener,noreferrer')
}

onMounted(() => {
  initializeCanvas()
  loadAssetLibrary()
  loadCompositionHistory()
})
onBeforeUnmount(() => editor?.dispose())
</script>

<style scoped>
.composer-grid {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 340px minmax(460px, 1fr);
  gap: 18px;
}

.composer-controls,
.canvas-panel {
  border: 1px solid rgba(145, 184, 169, 0.26);
  border-radius: 8px;
  background: #101a1b;
  padding: 18px;
}

.control-card + .control-card {
  margin-top: 16px;
}

.control-card h3,
.canvas-head h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.file-drop {
  min-height: 82px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  padding: 12px;
  border: 1px dashed rgba(157, 214, 189, 0.46);
  border-radius: 8px;
  background: #0b1414;
  cursor: pointer;
}

.file-drop.compact {
  min-height: 66px;
}

.file-drop.disabled {
  opacity: 0.52;
  cursor: not-allowed;
}

.file-drop input {
  display: none;
}

.file-drop span,
.hint,
.no-layer,
.canvas-head p,
.composite-result span {
  color: #91a8a0;
  font-size: 13px;
}

.cutout-modes,
.blend-modes {
  width: 100%;
  display: grid;
}

.cutout-modes {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.blend-modes {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.cutout-modes :deep(.el-radio-button),
.blend-modes :deep(.el-radio-button) {
  min-width: 0;
}

.cutout-modes :deep(.el-radio-button__inner),
.blend-modes :deep(.el-radio-button__inner) {
  width: 100%;
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 7px 5px;
  white-space: normal;
  line-height: 1.2;
  font-size: 12px;
}

.hint {
  min-height: 38px;
  margin: 10px 0;
  line-height: 1.5;
}

.hint.compact {
  min-height: 0;
  margin-bottom: 0;
}

.save-option {
  margin-top: 10px;
  color: #dfeee8;
}

.card-head,
.layer-row,
.layer-actions,
.compose-actions,
.canvas-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-head span {
  color: #9dd6bd;
  font-size: 13px;
}

.no-layer {
  padding: 12px 0;
}

.asset-list {
  display: grid;
  gap: 8px;
  max-height: 290px;
  overflow-y: auto;
}

.history-list {
  display: grid;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.asset-row,
.history-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px;
  border: 1px solid rgba(145, 184, 169, 0.2);
  border-radius: 8px;
  background: #0b1414;
}

.asset-row img,
.history-row img {
  width: 46px;
  height: 46px;
  flex: none;
  object-fit: contain;
  border-radius: 6px;
  background: repeating-conic-gradient(#152020 0 25%, #1d2c2b 0 50%) 50% / 14px 14px;
}

.history-row img {
  object-fit: cover;
}

.asset-info,
.history-info {
  min-width: 0;
  flex: 1;
}

.asset-info strong,
.asset-info small,
.history-info strong,
.history-info small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-info small,
.history-info small {
  margin-top: 3px;
  color: #91a8a0;
}

.remove-asset {
  color: #f89a92;
}

.layer-row {
  width: 100%;
  margin-bottom: 7px;
  padding: 10px 11px;
  border: 1px solid rgba(145, 184, 169, 0.2);
  border-radius: 8px;
  background: #0b1414;
  color: #e2efe9;
}

.layer-row.selected {
  border-color: #6ee7ac;
  background: #16342b;
}

.layer-row span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.layer-row small {
  color: #9dd6bd;
}

.layer-actions {
  justify-content: flex-end;
  margin-top: 10px;
}

.compose-actions {
  margin-top: 18px;
}

.generate-btn {
  border: 0;
  background: #1c9d70;
}

.canvas-head {
  margin-bottom: 15px;
}

.canvas-head h3 {
  margin-bottom: 6px;
}

.canvas-head p {
  margin: 0;
}

.canvas-frame {
  min-height: 520px;
  max-height: calc(100vh - 210px);
  display: grid;
  place-items: center;
  overflow: auto;
  padding: 14px;
  border-radius: 8px;
  background: #080e0f;
}

.canvas-frame :deep(.canvas-container) {
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.32);
}

.composite-result {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-top: 14px;
  padding: 10px;
  border-radius: 8px;
  background: #0b1414;
}

.composite-result a {
  min-width: 0;
  overflow: hidden;
  color: #6ee7ac;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1050px) {
  .composer-grid {
    grid-template-columns: 1fr;
  }
}
</style>
