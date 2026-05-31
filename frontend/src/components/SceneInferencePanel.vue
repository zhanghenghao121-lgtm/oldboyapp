<template>
  <section class="scene-inference">
    <aside class="inference-controls">
      <div class="glass-card intro-card">
        <p class="eyebrow">SCENE INFERENCE</p>
        <h3>用正面 + 反打补完整个空间</h3>
        <p>上传同一场景的两张基础图，AI 会推理左侧面、右侧面、俯瞰图，再生成可旋转查看的 2:1 全景图。</p>
      </div>

      <div class="glass-card">
        <div class="card-head">
          <h3>1. 场景输入</h3>
          <span>必须成对上传</span>
        </div>
        <label class="scene-drop" :class="{ filled: inputs.front.url, busy: uploadingType === 'front' }">
          <input type="file" accept="image/*" :disabled="Boolean(uploadingType)" @change="(event) => uploadInputImage(event, 'front')" />
          <img v-if="inputs.front.url" :src="previewUrl(inputs.front.url)" alt="正面图" />
          <strong>{{ uploadingType === 'front' ? '上传中...' : inputs.front.name || '上传正面图' }}</strong>
          <span>front view</span>
        </label>
        <label class="scene-drop" :class="{ filled: inputs.back.url, busy: uploadingType === 'back' }">
          <input type="file" accept="image/*" :disabled="Boolean(uploadingType)" @change="(event) => uploadInputImage(event, 'back')" />
          <img v-if="inputs.back.url" :src="previewUrl(inputs.back.url)" alt="反打图" />
          <strong>{{ uploadingType === 'back' ? '上传中...' : inputs.back.name || '上传反打图' }}</strong>
          <span>reverse view</span>
        </label>
      </div>

      <div class="glass-card">
        <div class="card-head">
          <h3>2. 模型与任务</h3>
          <span>{{ statusText }}</span>
        </div>
        <el-input v-model="projectTitle" maxlength="100" placeholder="项目名称，可选" />
        <el-select v-model="modelKey" placeholder="选择生图模型">
          <el-option v-for="model in imageModels" :key="model.id" :label="model.label" :value="model.id" />
        </el-select>
        <div class="action-stack">
          <el-button class="infer-btn" type="primary" :loading="inferring" :disabled="!canStartInference" @click="startInference">
            开始推理
          </el-button>
          <el-button plain :loading="refreshing" :disabled="!currentProject?.id" @click="refreshProject">刷新任务</el-button>
          <el-button
            class="pano-btn"
            type="success"
            :loading="generatingPanorama"
            :disabled="!canGeneratePanorama"
            @click="startPanorama"
          >
            生成 equirectangular 2:1 全景图
          </el-button>
        </div>
      </div>

      <div class="glass-card history-card">
        <div class="card-head">
          <h3>历史记录</h3>
          <el-button text size="small" :loading="loadingProjects" @click="loadProjects">刷新</el-button>
        </div>
        <div v-if="!projects.length" class="empty-row">暂无场景推理记录。</div>
        <div
          v-for="project in projects"
          :key="project.id"
          class="project-row"
          :class="{ active: currentProject?.id === project.id }"
        >
          <button type="button" class="project-select" @click="selectProject(project)">
            <span>{{ project.title || '场景推理' }}</span>
            <small>{{ projectStatus(project.status) }} · {{ project.model_key }}</small>
          </button>
          <el-button
            text
            type="danger"
            size="small"
            :loading="deletingProjectId === project.id"
            @click.stop="deleteProject(project)"
          >
            删除
          </el-button>
        </div>
      </div>
    </aside>

    <main class="result-board">
      <div class="board-head">
        <div>
          <p class="eyebrow">MULTI VIEW SET</p>
          <h3>五视角场景参考</h3>
        </div>
        <p>左侧面、右侧面、俯瞰图可单独下载；五张图齐全后可继续生成全景图。</p>
      </div>

      <div class="view-grid">
        <article v-for="card in viewCards" :key="card.key" class="view-card" :class="{ generated: card.generated }">
          <div class="view-frame">
            <img v-if="card.url" :src="previewUrl(card.url)" :alt="card.label" />
            <div v-else class="empty-view">
              <span>{{ card.short }}</span>
              <small>{{ card.waiting }}</small>
            </div>
          </div>
          <div class="view-copy">
            <div>
              <strong>{{ card.label }}</strong>
              <small>{{ card.tip }}</small>
            </div>
            <div class="view-actions">
              <el-button v-if="card.url" size="small" plain @click="openImage(card.url)">预览</el-button>
              <el-button v-if="card.downloadable && card.url" size="small" plain @click="downloadImage(card.url, card.filename)">下载</el-button>
            </div>
          </div>
          <div v-if="card.job" class="job-line" :class="card.job.status">
            {{ jobStatus(card.job) }}
          </div>
        </article>
      </div>
    </main>

    <aside class="panorama-panel">
      <div class="pano-head">
        <div>
          <p class="eyebrow">PANORAMA VIEWER</p>
          <h3>2:1 全景旋转查看</h3>
        </div>
        <el-button size="small" plain :loading="capturingPanorama" :disabled="!panoramaUrl" @click="capturePanoramaView">截屏高清修复</el-button>
      </div>
      <div
        ref="panoramaViewerRef"
        class="panorama-viewer"
        :class="{ empty: !panoramaUrl }"
        :style="panoramaStyle"
        @pointerdown="startPanoramaDrag"
        @pointermove="movePanorama"
        @pointerup="stopPanoramaDrag"
        @pointerleave="stopPanoramaDrag"
        @wheel.prevent="zoomPanorama"
      >
        <div v-if="!panoramaUrl" class="pano-empty">
          <strong>等待全景图</strong>
          <span>生成完成后可拖拽旋转、滚轮缩放。</span>
        </div>
        <div v-else class="pano-hud">
          <span>拖拽旋转</span>
          <span>缩放 {{ panoramaZoom }}%</span>
        </div>
      </div>
      <div class="pano-actions">
        <el-button plain :disabled="!panoramaUrl" @click="openImage(panoramaUrl)">预览大图</el-button>
        <el-button type="primary" :disabled="!panoramaUrl" @click="downloadImage(panoramaUrl, 'scene_panorama.png')">下载全景图</el-button>
      </div>
      <div v-if="screenshotJob" class="screenshot-job" :class="screenshotJob.status">
        <span v-if="screenshotRunning">高清修复生成中，可以离开页面，稍后回来刷新后下载。</span>
        <span v-else-if="screenshotJob.status === 'failed'">{{ screenshotJob.error_message || '高清修复失败，请重新截屏。' }}</span>
        <el-button
          v-if="screenshotReady"
          type="success"
          @click="downloadImage(screenshotJob.image_url, 'scene_panorama_view_hd.png')"
        >
          下载高清修复图
        </el-button>
        <el-button v-else-if="screenshotRunning" plain :loading="refreshing" @click="refreshProject">刷新修复结果</el-button>
      </div>
      <div v-if="currentProject?.error_message" class="error-box">{{ currentProject.error_message }}</div>
    </aside>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createSceneInferenceProject,
  deleteSceneInferenceProject,
  enhanceSceneInferenceScreenshot,
  generateSceneInferencePanorama,
  generateSceneInferenceViews,
  getSceneInferenceProject,
  getSceneInferenceProjects,
  refreshSceneInferenceProject,
} from '../api/aiImage'
import { getStoryboardConfig } from '../api/storyboard'
import { storageFileUrl, uploadToCos } from '../api/storage'

const inputs = reactive({
  front: { url: '', name: '' },
  back: { url: '', name: '' },
})
const projects = ref([])
const currentProject = ref(null)
const imageModels = ref([])
const modelKey = ref('gpt-image-2')
const projectTitle = ref('')
const uploadingType = ref('')
const inferring = ref(false)
const generatingPanorama = ref(false)
const refreshing = ref(false)
const loadingProjects = ref(false)
const deletingProjectId = ref(null)
const panoramaYaw = ref(0)
const panoramaZoom = ref(120)
const panoramaViewerRef = ref(null)
const capturingPanorama = ref(false)
let pollingTimer = null
let dragState = null
let panoramaImage = null

const previewUrl = (url) => storageFileUrl(url)
const panoramaUrl = computed(() => currentProject.value?.panorama_image_url || '')
const running = computed(() => ['inference_running', 'panorama_running'].includes(currentProject.value?.status || ''))
const canStartInference = computed(() => Boolean(inputs.front.url && inputs.back.url && modelKey.value && !uploadingType.value))
const canGeneratePanorama = computed(() => {
  const project = currentProject.value
  return Boolean(project?.id && project.left_image_url && project.right_image_url && project.top_image_url && !generatingPanorama.value)
})
const statusText = computed(() => projectStatus(currentProject.value?.status || 'draft'))
const panoramaStyle = computed(() => {
  if (!panoramaUrl.value) return {}
  return {
    backgroundImage: `url("${previewUrl(panoramaUrl.value)}")`,
    backgroundPosition: `${panoramaYaw.value}px center`,
    backgroundSize: `auto ${panoramaZoom.value}%`,
  }
})

watch(panoramaUrl, () => {
  panoramaImage = null
})

const loadImage = (url) =>
  new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('全景图加载失败，无法截屏'))
    image.src = url
  })

const latestJob = (type) => (currentProject.value?.jobs || []).find((job) => job.job_type === type)
const screenshotJob = computed(() => latestJob('enhance_screenshot'))
const screenshotRunning = computed(() => ['pending', 'running'].includes(screenshotJob.value?.status || ''))
const screenshotReady = computed(() => screenshotJob.value?.status === 'success' && Boolean(screenshotJob.value?.image_url))
const shouldPollProject = computed(() => running.value || screenshotRunning.value)

const viewCards = computed(() => {
  const project = currentProject.value || {}
  return [
    {
      key: 'front',
      label: '正面图',
      short: 'F',
      waiting: '等待上传',
      tip: '用户上传原图',
      url: project.front_image_url || inputs.front.url,
      generated: false,
      downloadable: false,
    },
    {
      key: 'back',
      label: '反打图',
      short: 'R',
      waiting: '等待上传',
      tip: '用户上传原图',
      url: project.back_image_url || inputs.back.url,
      generated: false,
      downloadable: false,
    },
    {
      key: 'left',
      label: '左侧面图',
      short: 'L',
      waiting: 'AI 推理生成',
      tip: '根据正面与反打推理',
      url: project.left_image_url,
      generated: true,
      downloadable: true,
      filename: 'scene_left.png',
      job: latestJob('generate_left'),
    },
    {
      key: 'right',
      label: '右侧面图',
      short: 'R',
      waiting: 'AI 推理生成',
      tip: '根据正面与反打推理',
      url: project.right_image_url,
      generated: true,
      downloadable: true,
      filename: 'scene_right.png',
      job: latestJob('generate_right'),
    },
    {
      key: 'top',
      label: '俯瞰图',
      short: 'T',
      waiting: 'AI 推理生成',
      tip: '鸟瞰空间布局',
      url: project.top_image_url,
      generated: true,
      downloadable: true,
      filename: 'scene_top.png',
      job: latestJob('generate_top'),
    },
  ]
})

const projectStatus = (status) => ({
  draft: '待推理',
  inference_running: '视角推理中',
  inference_done: '视角推理完成',
  panorama_running: '全景生成中',
  panorama_done: '全景完成',
  failed: '失败',
}[status] || '待推理')

const jobStatus = (job) => {
  if (!job) return ''
  const label = { running: '生成中', pending: '等待中', success: '已完成', failed: '生成失败' }[job.status] || job.status
  return job.error_message ? `${label}：${job.error_message}` : label
}

const loadConfig = async () => {
  const res = await getStoryboardConfig()
  imageModels.value = res.data.image_models || []
  modelKey.value = res.data.default_image_model || imageModels.value[0]?.id || modelKey.value
}

const loadProjects = async () => {
  loadingProjects.value = true
  try {
    const res = await getSceneInferenceProjects()
    projects.value = res.data.list || []
  } catch (error) {
    ElMessage.error(String(error || '场景推理记录加载失败'))
  } finally {
    loadingProjects.value = false
  }
}

const selectProject = async (project) => {
  if (!project?.id) return
  try {
    const res = await getSceneInferenceProject(project.id)
    currentProject.value = res.data
    inputs.front.url = res.data.front_image_url || ''
    inputs.front.name = '正面图'
    inputs.back.url = res.data.back_image_url || ''
    inputs.back.name = '反打图'
    modelKey.value = res.data.model_key || modelKey.value
    projectTitle.value = res.data.title || ''
    resetPanorama()
    maybePoll()
  } catch (error) {
    ElMessage.error(String(error || '场景推理项目加载失败'))
  }
}

const clearCurrentProject = () => {
  stopPolling()
  currentProject.value = null
  projectTitle.value = ''
  inputs.front.url = ''
  inputs.front.name = ''
  inputs.back.url = ''
  inputs.back.name = ''
  resetPanorama()
}

const deleteProject = async (project) => {
  if (!project?.id || deletingProjectId.value) return
  try {
    await ElMessageBox.confirm(
      `确定删除“${project.title || '场景推理'}”吗？删除后无法恢复。`,
      '删除历史记录',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  deletingProjectId.value = project.id
  try {
    await deleteSceneInferenceProject(project.id)
    projects.value = projects.value.filter((item) => item.id !== project.id)
    if (currentProject.value?.id === project.id) clearCurrentProject()
    ElMessage.success('历史记录已删除')
  } catch (error) {
    ElMessage.error(String(error || '历史记录删除失败'))
  } finally {
    deletingProjectId.value = null
  }
}

const uploadInputImage = async (event, type) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传 jpg、png、webp 等图片文件')
    return
  }
  uploadingType.value = type
  try {
    const uploaded = await uploadToCos(file, 'images/scene-inference/inputs', { timeout: 120000 })
    inputs[type].url = uploaded.data.url
    inputs[type].name = file.name
    currentProject.value = null
    ElMessage.success(uploaded.data.compressed ? '图片已压缩并上传' : '图片已上传')
  } catch (error) {
    ElMessage.error(String(error || '图片上传失败'))
  } finally {
    uploadingType.value = ''
  }
}

const stopPolling = () => {
  if (pollingTimer) window.clearInterval(pollingTimer)
  pollingTimer = null
}

const upsertJob = (job) => {
  if (!job || !currentProject.value) return
  const jobs = currentProject.value.jobs || []
  const index = jobs.findIndex((item) => item.id === job.id)
  if (index >= 0) {
    jobs.splice(index, 1, job)
  } else {
    currentProject.value.jobs = [job, ...jobs]
  }
}

const maybePoll = () => {
  stopPolling()
  if (!currentProject.value?.id || !shouldPollProject.value) return
  pollingTimer = window.setInterval(refreshProject, 4500)
}

const refreshProject = async () => {
  if (!currentProject.value?.id || refreshing.value) return
  refreshing.value = true
  try {
    const res = await refreshSceneInferenceProject(currentProject.value.id)
    currentProject.value = res.data
    if (!shouldPollProject.value) stopPolling()
  } catch (error) {
    stopPolling()
    ElMessage.error(String(error || '任务刷新失败'))
  } finally {
    refreshing.value = false
  }
}

const startInference = async () => {
  if (!canStartInference.value) {
    ElMessage.warning('请先上传正面图和反打图，并选择生图模型')
    return
  }
  stopPolling()
  inferring.value = true
  try {
    const created = await createSceneInferenceProject({
      title: projectTitle.value || '场景推理',
      model_key: modelKey.value,
      front_image_url: inputs.front.url,
      back_image_url: inputs.back.url,
    })
    currentProject.value = created.data
    const res = await generateSceneInferenceViews(created.data.id, { model_key: modelKey.value })
    currentProject.value = res.data
    await loadProjects()
    maybePoll()
    ElMessage.success(running.value ? '视角推理任务已提交' : '视角推理完成')
  } catch (error) {
    ElMessage.error(String(error || '场景推理失败'))
  } finally {
    inferring.value = false
  }
}

const startPanorama = async () => {
  if (!canGeneratePanorama.value) {
    ElMessage.warning('请先生成左侧面、右侧面和俯瞰图')
    return
  }
  stopPolling()
  generatingPanorama.value = true
  try {
    const res = await generateSceneInferencePanorama(currentProject.value.id, { model_key: modelKey.value })
    currentProject.value = res.data
    await loadProjects()
    maybePoll()
    ElMessage.success(running.value ? '全景图任务已提交' : '全景图已生成')
  } catch (error) {
    ElMessage.error(String(error || '全景图生成失败'))
  } finally {
    generatingPanorama.value = false
  }
}

const openImage = (url) => {
  if (url) window.open(previewUrl(url), '_blank', 'noopener,noreferrer')
}

const downloadImage = (url, filename) => {
  if (!url) return
  const link = document.createElement('a')
  link.href = storageFileUrl(url, { download: true })
  link.download = filename || 'scene-image.png'
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  link.click()
}

const resetPanorama = () => {
  panoramaYaw.value = 0
  panoramaZoom.value = 120
}

const canvasBlob = (canvas) =>
  new Promise((resolve) => canvas.toBlob(resolve, 'image/png'))

const drawRepeatedPanorama = (context, image, width, height, renderedWidth, renderedHeight, offsetX, offsetY) => {
  let x = offsetX % renderedWidth
  if (x > 0) x -= renderedWidth
  while (x < width) {
    context.drawImage(image, x, offsetY, renderedWidth, renderedHeight)
    x += renderedWidth
  }
}

const capturePanoramaView = async () => {
  if (!panoramaUrl.value || capturingPanorama.value) return
  if (!currentProject.value?.id) {
    ElMessage.warning('请先选择一个场景推理项目')
    return
  }
  const viewer = panoramaViewerRef.value
  if (!viewer) return
  capturingPanorama.value = true
  try {
    if (!panoramaImage) panoramaImage = await loadImage(previewUrl(panoramaUrl.value))
    const rect = viewer.getBoundingClientRect()
    const viewportScale = Math.max(Math.round(rect.width * (window.devicePixelRatio || 1)), 1920) / Math.max(rect.width, 1)
    const width = Math.max(Math.round(rect.width * viewportScale), 1)
    const height = Math.max(Math.round(rect.height * viewportScale), 1)
    const imageWidth = panoramaImage.naturalWidth || panoramaImage.width
    const imageHeight = panoramaImage.naturalHeight || panoramaImage.height
    const renderedHeight = height * (panoramaZoom.value / 100)
    const renderedWidth = imageWidth * (renderedHeight / imageHeight)
    const offsetY = (height - renderedHeight) / 2
    const offsetX = panoramaYaw.value * viewportScale
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    context.imageSmoothingEnabled = true
    context.imageSmoothingQuality = 'high'
    context.fillStyle = '#05090d'
    context.fillRect(0, 0, width, height)
    context.save()
    context.beginPath()
    context.rect(0, 0, width, height)
    context.clip()
    drawRepeatedPanorama(context, panoramaImage, width, height, renderedWidth, renderedHeight, offsetX, offsetY)
    context.restore()
    const blob = await canvasBlob(canvas)
    if (!blob) throw new Error('截屏生成失败')
    const file = new File([blob], `scene_panorama_view_${Date.now()}.png`, { type: 'image/png' })
    ElMessage.info('当前视角已截屏，正在提交高清修复任务...')
    const uploaded = await uploadToCos(file, 'images/scene-inference/screenshots', { timeout: 120000 })
    const enhanced = await enhanceSceneInferenceScreenshot(currentProject.value.id, {
      image_url: uploaded.data.url,
      model_key: modelKey.value,
    })
    upsertJob(enhanced.data)
    maybePoll()
    ElMessage.success(screenshotReady.value ? '高清修复完成，请点击下载' : '高清修复任务已提交，可离开页面，完成后回来下载')
  } catch (error) {
    ElMessage.error(String(error || '全景截屏失败'))
  } finally {
    capturingPanorama.value = false
  }
}

const startPanoramaDrag = (event) => {
  if (!panoramaUrl.value) return
  dragState = { x: event.clientX, yaw: panoramaYaw.value }
  event.currentTarget?.setPointerCapture?.(event.pointerId)
}

const movePanorama = (event) => {
  if (!dragState) return
  panoramaYaw.value = dragState.yaw + event.clientX - dragState.x
}

const stopPanoramaDrag = () => {
  dragState = null
}

const zoomPanorama = (event) => {
  if (!panoramaUrl.value) return
  const next = panoramaZoom.value + (event.deltaY > 0 ? -8 : 8)
  panoramaZoom.value = Math.min(Math.max(next, 80), 240)
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadProjects()])
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<style scoped>
.scene-inference {
  display: grid;
  grid-template-columns: 320px minmax(420px, 1fr) 360px;
  gap: 18px;
  align-items: start;
}

.inference-controls,
.panorama-panel,
.result-board {
  min-width: 0;
}

.glass-card,
.result-board,
.panorama-panel {
  border: 1px solid rgba(157, 214, 189, .22);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(17, 31, 32, .92), rgba(10, 17, 22, .95));
  box-shadow: 0 20px 60px rgba(0, 0, 0, .28);
}

.glass-card {
  padding: 16px;
  margin-bottom: 14px;
}

.intro-card {
  background:
    radial-gradient(circle at 20% 0%, rgba(110, 231, 172, .22), transparent 38%),
    linear-gradient(155deg, rgba(22, 52, 43, .96), rgba(10, 17, 22, .95));
}

.eyebrow {
  margin: 0 0 7px;
  color: #9dd6bd;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: .1em;
}

h3,
p {
  margin: 0;
}

.intro-card h3,
.board-head h3,
.pano-head h3 {
  font-size: 22px;
}

.intro-card p,
.board-head p,
.card-head span,
.view-copy small,
.project-row small {
  color: #8ba69d;
  line-height: 1.55;
}

.card-head,
.board-head,
.pano-head,
.view-copy {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.card-head {
  margin-bottom: 12px;
}

.scene-drop {
  position: relative;
  min-height: 124px;
  margin-top: 10px;
  padding: 14px;
  display: grid;
  place-content: center;
  gap: 5px;
  border: 1px dashed rgba(157, 214, 189, .45);
  border-radius: 14px;
  overflow: hidden;
  background: rgba(255, 255, 255, .035);
  color: #eaf5f0;
  text-align: center;
  cursor: pointer;
}

.scene-drop input {
  display: none;
}

.scene-drop img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: .5;
}

.scene-drop strong,
.scene-drop span {
  position: relative;
  z-index: 1;
}

.scene-drop span {
  color: #9dd6bd;
  font-size: 12px;
}

.scene-drop.filled {
  border-style: solid;
}

.scene-drop.busy {
  opacity: .7;
  cursor: wait;
}

.glass-card :deep(.el-input),
.glass-card :deep(.el-select) {
  width: 100%;
  margin-bottom: 10px;
}

.action-stack {
  display: grid;
  gap: 9px;
}

.infer-btn,
.pano-btn {
  width: 100%;
}

.history-card {
  max-height: 340px;
  overflow: auto;
}

.empty-row {
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, .05);
  color: #8ba69d;
}

.project-row {
  width: 100%;
  margin-top: 8px;
  padding: 11px;
  border: 1px solid rgba(157, 214, 189, .18);
  border-radius: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px;
  align-items: center;
  background: rgba(255, 255, 255, .04);
  color: #eaf5f0;
}

.project-select {
  min-width: 0;
  border: 0;
  padding: 0;
  display: grid;
  gap: 4px;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.project-row.active,
.project-row:hover {
  border-color: #6ee7ac;
  background: rgba(110, 231, 172, .12);
}

.result-board,
.panorama-panel {
  padding: 18px;
}

.board-head {
  margin-bottom: 15px;
}

.board-head p {
  max-width: 360px;
  font-size: 13px;
  text-align: right;
}

.view-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.view-card {
  border: 1px solid rgba(157, 214, 189, .17);
  border-radius: 16px;
  overflow: hidden;
  background: rgba(255, 255, 255, .035);
}

.view-card.generated {
  background: rgba(110, 231, 172, .045);
}

.view-frame {
  aspect-ratio: 16 / 9;
  display: grid;
  place-items: center;
  overflow: hidden;
  background: #05090d;
}

.view-frame img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}

.empty-view {
  display: grid;
  place-items: center;
  gap: 8px;
  color: #53645f;
}

.empty-view span {
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(157, 214, 189, .22);
  border-radius: 50%;
  color: #9dd6bd;
  font-weight: 900;
}

.empty-view small {
  color: #74877f;
}

.view-copy {
  padding: 12px;
}

.view-copy strong {
  display: block;
}

.view-actions {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.job-line {
  padding: 8px 12px;
  border-top: 1px solid rgba(157, 214, 189, .14);
  color: #9dd6bd;
  font-size: 12px;
}

.job-line.failed {
  color: #ff9d8f;
}

.job-line.success {
  color: #6ee7ac;
}

.panorama-panel {
  position: sticky;
  top: 18px;
}

.pano-head {
  margin-bottom: 14px;
}

.panorama-viewer {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 1px solid rgba(157, 214, 189, .22);
  border-radius: 18px;
  overflow: hidden;
  background-color: #05090d;
  background-repeat: repeat-x;
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.panorama-viewer:active {
  cursor: grabbing;
}

.panorama-viewer.empty {
  cursor: default;
}

.pano-empty {
  height: 100%;
  display: grid;
  place-content: center;
  gap: 8px;
  text-align: center;
  color: #9dd6bd;
}

.pano-empty span {
  color: #8ba69d;
  font-size: 13px;
}

.pano-hud {
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 12px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.pano-hud span {
  padding: 6px 9px;
  border: 1px solid rgba(157, 214, 189, .24);
  border-radius: 999px;
  background: rgba(5, 9, 13, .72);
  color: #dff5ec;
  font-size: 12px;
}

.pano-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
  margin-top: 12px;
}

.screenshot-job {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(157, 214, 189, .22);
  border-radius: 12px;
  display: grid;
  gap: 8px;
  background: rgba(255, 255, 255, .04);
  color: #dff5ec;
  font-size: 13px;
  line-height: 1.55;
}

.screenshot-job.running {
  border-color: rgba(82, 166, 255, .35);
}

.screenshot-job.failed {
  border-color: rgba(255, 157, 143, .35);
  background: rgba(255, 157, 143, .08);
  color: #ffb5aa;
}

.screenshot-job.success {
  border-color: rgba(110, 231, 172, .35);
  background: rgba(110, 231, 172, .08);
}

.screenshot-job :deep(.el-button) {
  width: 100%;
}

.error-box {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 157, 143, .35);
  border-radius: 12px;
  background: rgba(255, 157, 143, .08);
  color: #ffb5aa;
  font-size: 13px;
  line-height: 1.55;
}

@media (max-width: 1320px) {
  .scene-inference {
    grid-template-columns: 300px 1fr;
  }

  .panorama-panel {
    position: static;
    grid-column: 1 / -1;
  }
}

@media (max-width: 920px) {
  .scene-inference,
  .view-grid {
    grid-template-columns: 1fr;
  }

  .board-head {
    flex-direction: column;
  }

  .board-head p {
    text-align: left;
  }
}
</style>
