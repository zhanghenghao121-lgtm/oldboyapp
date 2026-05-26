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
        <h3>2. 上传角色并抠图</h3>
        <el-radio-group v-model="cutoutMode" class="cutout-modes">
          <el-radio-button value="fast">免费快速抠图</el-radio-button>
          <el-radio-button value="ai">AI 精细抠图</el-radio-button>
        </el-radio-group>
        <p class="hint">{{ cutoutMode === 'fast' ? '适合纯白或接近白色背景，不消耗 AI 抠图额度。' : '适合复杂背景，将调用 remove.bg 服务。' }}</p>
        <label class="file-drop compact" :class="{ disabled: !hasScene || cutting }">
          <input type="file" accept="image/*" :disabled="!hasScene || cutting" @change="handleCharacterUpload" />
          <strong>{{ cutting ? '正在抠图并上传...' : '添加角色图片' }}</strong>
          <span>{{ hasScene ? '可连续添加多个角色' : '请先上传场景图' }}</span>
        </label>
        <el-checkbox v-model="saveToLibrary" class="save-option">抠图后保存到资产库</el-checkbox>
      </div>

      <div class="control-card library-card">
        <div class="card-head">
          <h3>3. 资产库</h3>
          <el-button text size="small" :loading="libraryLoading" @click="loadAssetLibrary">刷新</el-button>
        </div>
        <div v-if="libraryLoading && !assetLibrary.length" class="no-layer">正在加载资产...</div>
        <div v-else-if="!assetLibrary.length" class="no-layer">勾选保存后，抠图角色会留在这里。</div>
        <div v-else class="asset-list">
          <div v-for="asset in assetLibrary" :key="asset.id" class="asset-row">
            <img :src="aiImageCutoutAssetUrl(asset.key)" :alt="asset.name" />
            <div class="asset-info">
              <strong>{{ asset.name }}</strong>
              <small>{{ asset.mode === 'ai' ? 'AI 精细抠图' : '免费快速抠图' }}</small>
            </div>
            <el-button text size="small" :loading="addingAssetId === asset.id" :disabled="!hasScene" @click="addAssetToCanvas(asset)">添加</el-button>
            <el-button text size="small" class="remove-asset" @click="deleteAsset(asset)">移除</el-button>
          </div>
        </div>
      </div>

      <div class="control-card layers-card">
        <div class="card-head">
          <h3>4. 图层</h3>
          <span>{{ layers.length }} 个角色</span>
        </div>
        <div v-if="!layers.length" class="no-layer">抠图后的角色会出现在这里。</div>
        <button
          v-for="layer in layers"
          :key="layer.id"
          type="button"
          class="layer-row"
          :class="{ selected: selectedId === layer.id }"
          @click="selectLayer(layer.id)"
        >
          <span>{{ layer.name }}</span>
          <small>{{ layer.mode === 'ai' ? 'AI' : '免费' }}</small>
        </button>
        <div class="layer-actions">
          <el-button size="small" plain :disabled="!selectedId" @click="moveSelected('down')">下移</el-button>
          <el-button size="small" plain :disabled="!selectedId" @click="moveSelected('up')">上移</el-button>
          <el-button size="small" plain :disabled="!selectedId" @click="removeSelected">删除</el-button>
        </div>
      </div>

      <div class="compose-actions">
        <el-button plain @click="resetComposer">清空画布</el-button>
        <el-button class="generate-btn" type="primary" :loading="composing" :disabled="!hasScene || !layers.length" @click="composeImage">
          合成图片
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
      <div class="canvas-frame" v-loading="cutting || composing">
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
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Canvas, FabricImage } from 'fabric'

import {
  aiImageCutoutAssetUrl,
  cutoutAiImageCharacter,
  deleteAiImageCutoutAsset,
  getAiImageCutoutAssets,
} from '../api/aiManga'
import { uploadToCos } from '../api/storage'

const canvasElement = ref(null)
const sceneName = ref('')
const hasScene = ref(false)
const cutoutMode = ref('fast')
const saveToLibrary = ref(false)
const cutting = ref(false)
const composing = ref(false)
const libraryLoading = ref(false)
const assetLibrary = ref([])
const addingAssetId = ref('')
const layers = ref([])
const selectedId = ref('')
const compositeUrl = ref('')
let editor = null
let layerCounter = 0

const imageDataUrl = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(new Error('读取图片失败'))
    reader.readAsDataURL(file)
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
    editor.clear()
    editor.setDimensions({ width, height })
    image.scale(scale)
    image.set({ left: 0, top: 0, selectable: false, evented: false })
    editor.backgroundImage = image
    editor.requestRenderAll()
    sceneName.value = file.name
    hasScene.value = true
    selectedId.value = ''
    compositeUrl.value = ''
    refreshLayers()
  } catch (error) {
    ElMessage.error(String(error || '场景图加载失败'))
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
    ElMessage.success(item.library_asset ? '抠图完成，已加入画布并保存到资产库' : '抠图完成，已加入画布')
  } catch (error) {
    ElMessage.error(String(error || '角色抠图失败'))
  } finally {
    cutting.value = false
  }
}

const addCharacterLayer = async (item, name) => {
  const image = await FabricImage.fromURL(aiImageCutoutAssetUrl(item.key))
  layerCounter += 1
  image.stickerId = `character-${layerCounter}`
  image.stickerName = name || item.name || `角色 ${layerCounter}`
  image.cutoutMode = item.mode
  const targetHeight = Math.min(editor.height * 0.62, image.height)
  image.scaleToHeight(targetHeight)
  image.set({
    left: (editor.width - image.getScaledWidth()) / 2,
    top: Math.max(editor.height - image.getScaledHeight() - 12, 0),
    cornerColor: '#6ee7ac',
    borderColor: '#6ee7ac',
    transparentCorners: false,
  })
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

const composeImage = async () => {
  if (!editor || !hasScene.value || !layers.value.length) return
  composing.value = true
  try {
    editor.discardActiveObject()
    editor.requestRenderAll()
    const blob = await editor.toBlob({ format: 'png', multiplier: 1 })
    if (!blob) throw new Error('生成合成图失败')
    const filename = `scene-composite-${Date.now()}.png`
    const file = new File([blob], filename, { type: 'image/png' })
    const res = await uploadToCos(file, 'images/composites', { timeout: 120000 })
    compositeUrl.value = res.data.url
    downloadComposite(blob, filename)
    ElMessage.success('合成图片已上传并开始下载')
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

.cutout-modes {
  width: 100%;
}

.hint {
  min-height: 38px;
  margin: 10px 0;
  line-height: 1.5;
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

.asset-row {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px;
  border: 1px solid rgba(145, 184, 169, 0.2);
  border-radius: 8px;
  background: #0b1414;
}

.asset-row img {
  width: 46px;
  height: 46px;
  flex: none;
  object-fit: contain;
  border-radius: 6px;
  background: repeating-conic-gradient(#152020 0 25%, #1d2c2b 0 50%) 50% / 14px 14px;
}

.asset-info {
  min-width: 0;
  flex: 1;
}

.asset-info strong,
.asset-info small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.asset-info small {
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
