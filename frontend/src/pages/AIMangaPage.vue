<template>
  <div class="script-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">AI SCRIPT PROMPT</p>
        <h1>AI剧本创作</h1>
      </div>
      <div class="topbar-actions">
        <div class="cost-card" title="按 deepseek-v4-pro / flash 当前 token 价格折算，1 元 = 1 积分">
          <span>累计花费</span>
          <strong>{{ formatPoints(totalCostPoints) }} 积分</strong>
          <small v-if="lastUsageCost">
            本次 {{ formatPoints(lastUsageCost.total_points) }} · {{ formatTokenCount(lastUsageCost.total_tokens) }} tokens
          </small>
          <small v-else>1 元 = 1 积分</small>
        </div>
        <el-select v-model="selectedModelPreset" class="model-select" placeholder="选择模型">
          <el-option
            v-for="item in modelOptions"
            :key="item.id"
            :label="`${item.label} · ${item.model || '未配置'}`"
            :value="item.id"
          />
        </el-select>
        <el-button plain @click="promptDialogVisible = true">后台提示词</el-button>
        <el-button plain @click="$router.push('/profile')">用户信息</el-button>
      </div>
    </header>

    <main class="workspace">
      <section class="input-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow">SOURCE</p>
            <h2>剧本输入</h2>
          </div>
          <div class="style-switch">
            <button
              v-for="style in styleOptions"
              :key="style.id"
              class="style-btn"
              :class="{ active: selectedStyle === style.id }"
              type="button"
              @click="selectedStyle = style.id"
            >
              {{ style.label }}
            </button>
          </div>
        </div>

        <el-input
          v-model="inputText"
          type="textarea"
          :rows="15"
          resize="none"
          class="story-input"
          placeholder="粘贴剧本文本，或上传 PDF / Word 文档后直接识别。"
        />

        <div class="file-row">
          <input ref="fileInputRef" type="file" class="file-hidden" accept=".pdf,.doc,.docx" @change="handleFileChange" />
          <el-button plain @click="pickFile">上传文档</el-button>
          <span v-if="selectedFileName" class="file-chip">{{ selectedFileName }}</span>
          <span class="file-tip">支持 PDF / DOCX</span>
        </div>

        <div class="reference-panel">
          <div class="reference-head">
            <strong>人物站位</strong>
            <span>可选上传站位图，并描述人物在场景中的位置关系。</span>
          </div>
          <div class="position-layout">
            <label class="reference-uploader position-upload">
              <input type="file" accept="image/*" @change="handleCharacterImageChange" />
              <span>人物站位图</span>
              <strong>{{ characterPositionImage?.name || '选择图片' }}</strong>
              <button v-if="characterPositionImage" type="button" @click.prevent="characterPositionImage = null">移除</button>
            </label>
            <el-input
              v-model="positionDescription"
              type="textarea"
              :rows="4"
              resize="none"
              placeholder="例如：男主站在画面左前方，女主在右后方靠窗，镜头轴线从门口朝室内。"
            />
          </div>
        </div>

        <div class="action-row">
          <el-button plain :disabled="!hasStoryboardInput" @click="clearInput">清空</el-button>
          <el-button class="primary-action" type="primary" :loading="generating" @click="submitStoryboard">生成分镜词</el-button>
          <el-button v-if="generating" type="danger" plain @click="cancelStoryboardGeneration">取消生成</el-button>
        </div>
      </section>

      <section class="output-panel">
        <div class="section-head">
          <div>
            <p class="eyebrow">PROMPTS</p>
            <h2>提示词输出</h2>
          </div>
          <div class="output-actions">
            <span class="meta-chip">{{ currentStyleLabel }}</span>
            <span class="meta-chip">{{ currentModelLabel }}</span>
            <el-button plain :disabled="!groups.length" @click="copyAllPrompts">复制全部</el-button>
          </div>
        </div>

        <div v-if="!groups.length && !generating" class="empty-state">
          <strong>等待生成分镜词</strong>
          <span>输入剧本后可补充人物站位图和描述，最终输出会按段落分组展示。</span>
        </div>

        <div v-else class="group-list" v-loading="generating">
          <article v-for="group in groups" :key="group.id" class="prompt-group">
            <div class="group-head" role="button" tabindex="0" @click="toggleGroup(group.id)" @keydown.enter="toggleGroup(group.id)">
              <span>{{ collapsedGroups[group.id] ? '›' : '⌄' }}</span>
              <strong>段落 {{ group.index }}</strong>
              <span>|</span>
              <span>约 {{ formatDuration(group.duration_seconds) }} 秒</span>
              <el-button class="copy-btn" size="small" plain @click.stop="copyGroup(group)">复制</el-button>
            </div>

            <div v-show="!collapsedGroups[group.id]" class="shot-list">
              <div v-for="shot in group.shots" :key="shot.id" class="shot-card">
                <div class="shot-meta">
                  <span class="shot-index">{{ shot.index }}</span>
                  <span class="duration-pill">{{ formatDuration(shot.duration_seconds) }}s</span>
                </div>
                <p>{{ shot.prompt }}</p>
              </div>
            </div>
          </article>
        </div>
      </section>
    </main>

    <el-dialog v-model="promptDialogVisible" title="后台提示词" width="780px">
      <div class="prompt-dialog">
        <h3>解析规则</h3>
        <pre>{{ storyboardPrompt }}</pre>
        <h3>{{ currentStyleLabel }}提示词</h3>
        <pre>{{ currentStylePrompt }}</pre>
      </div>
      <template #footer>
        <el-button @click="copyPromptConfig">复制当前提示词</el-button>
        <el-button type="primary" @click="promptDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { getAiMangaConfig, generateAiMangaStoryboard } from '../api/aiManga'

const fileInputRef = ref(null)
const selectedFile = ref(null)
const selectedFileName = ref('')
const inputText = ref('')
const characterPositionImage = ref(null)
const positionDescription = ref('')
const generating = ref(false)
const storyboardController = ref(null)
const storyboardCanceled = ref(false)
const groups = ref([])
const storyboardText = ref('')
const promptDialogVisible = ref(false)
const storyboardPrompt = ref('')
const selectedModelPreset = ref('assistant')
const selectedStyle = ref('3d')
const modelOptions = ref([])
const styleOptions = ref([
  { id: '3d', label: '3D风格', prompt: '' },
  { id: 'real', label: '真人风格', prompt: '' },
])
const collapsedGroups = reactive({})
const maxReferenceImageSize = 10 * 1024 * 1024
const targetReferenceImageSize = Math.floor(maxReferenceImageSize * 0.95)
const costStorageKey = 'ai_manga_total_cost_points'
const totalCostPoints = ref(Number(localStorage.getItem(costStorageKey) || 0) || 0)
const lastUsageCost = ref(null)

const hasScriptSource = computed(() => Boolean(inputText.value.trim() || selectedFile.value))
const hasStoryboardInput = computed(() => Boolean(hasScriptSource.value || characterPositionImage.value || positionDescription.value.trim()))

const currentModelLabel = computed(() => {
  const matched = modelOptions.value.find((item) => item.id === selectedModelPreset.value)
  return matched?.model ? `${matched.label} · ${matched.model}` : '未选择模型'
})

const currentStyle = computed(() => styleOptions.value.find((item) => item.id === selectedStyle.value) || styleOptions.value[0])
const currentStyleLabel = computed(() => currentStyle.value?.label || '3D风格')
const currentStylePrompt = computed(() => currentStyle.value?.prompt || '')

const formatPoints = (value) => {
  const numberValue = Number(value || 0)
  if (!Number.isFinite(numberValue) || numberValue <= 0) return '0.0000'
  return numberValue < 0.0001 ? numberValue.toFixed(6) : numberValue.toFixed(4)
}

const formatTokenCount = (value) => Number(value || 0).toLocaleString('zh-CN')

const recordUsageCost = (usageCost) => {
  if (!usageCost) return
  lastUsageCost.value = usageCost
  const cost = Number(usageCost.total_points || 0)
  if (!Number.isFinite(cost) || cost <= 0) return
  totalCostPoints.value = Number((totalCostPoints.value + cost).toFixed(6))
  localStorage.setItem(costStorageKey, String(totalCostPoints.value))
}

const pickFile = () => {
  fileInputRef.value?.click()
}

const handleFileChange = (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  selectedFile.value = file
  selectedFileName.value = file.name
}

const validateReferenceImage = (file) => {
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return false
  }
  return true
}

const loadImageFile = (file) =>
  new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const image = new Image()
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片读取失败'))
    }
    image.src = url
  })

const canvasToBlob = (canvas, quality) =>
  new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob)
        else reject(new Error('图片压缩失败'))
      },
      'image/jpeg',
      quality
    )
  })

const renderImageToCanvas = (image, scale = 1) => {
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(image.width * scale))
  canvas.height = Math.max(1, Math.round(image.height * scale))
  const context = canvas.getContext('2d')
  context.fillStyle = '#ffffff'
  context.fillRect(0, 0, canvas.width, canvas.height)
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  return canvas
}

const compressReferenceImage = async (file) => {
  if (file.size <= maxReferenceImageSize) return file

  ElMessage.info('图片超过 10MB，正在自动压缩')
  const image = await loadImageFile(file)
  const maxSide = 4096
  let scale = Math.min(1, maxSide / Math.max(image.width, image.height))
  let canvas = renderImageToCanvas(image, scale)
  let quality = 0.88
  let blob = await canvasToBlob(canvas, quality)

  while (blob.size > targetReferenceImageSize && quality > 0.46) {
    quality -= 0.08
    blob = await canvasToBlob(canvas, quality)
  }

  while (blob.size > targetReferenceImageSize && Math.max(canvas.width, canvas.height) > 1200) {
    scale *= 0.85
    canvas = renderImageToCanvas(image, scale)
    quality = 0.82
    blob = await canvasToBlob(canvas, quality)
    while (blob.size > targetReferenceImageSize && quality > 0.46) {
      quality -= 0.08
      blob = await canvasToBlob(canvas, quality)
    }
  }

  if (blob.size > maxReferenceImageSize) {
    throw new Error('图片压缩后仍超过 10MB，请换一张更小的图片')
  }

  const compressedName = file.name.replace(/\.[^.]+$/, '') || 'image'
  ElMessage.success('图片已自动压缩到 10MB 以下')
  return new File([blob], `${compressedName}.jpg`, { type: 'image/jpeg' })
}

const prepareReferenceImage = async (file) => {
  if (!validateReferenceImage(file)) return null
  return compressReferenceImage(file)
}

const handleCharacterImageChange = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  try {
    const preparedFile = await prepareReferenceImage(file)
    if (preparedFile) characterPositionImage.value = preparedFile
  } catch (e) {
    ElMessage.error(String(e || '图片压缩失败'))
  }
}

const loadConfig = async () => {
  const res = await getAiMangaConfig()
  storyboardPrompt.value = res.data.storyboard_prompt || ''
  modelOptions.value = res.data.model_options || []
  styleOptions.value = res.data.style_options?.length ? res.data.style_options : styleOptions.value
  selectedModelPreset.value = res.data.default_model_preset || 'assistant'
  selectedStyle.value = res.data.default_style || '3d'
}

const submitStoryboard = async () => {
  if (generating.value) return
  if (!inputText.value.trim() && !selectedFile.value) {
    ElMessage.warning('请输入文本或上传文档后再生成分镜词')
    return
  }

  const formData = new FormData()
  if (selectedFile.value) formData.append('file', selectedFile.value)
  formData.append('text', inputText.value)
  formData.append('model_preset', selectedModelPreset.value)
  formData.append('style', selectedStyle.value)
  if (characterPositionImage.value) formData.append('character_position_image', characterPositionImage.value)
  formData.append('position_description', positionDescription.value)

  storyboardController.value = new AbortController()
  storyboardCanceled.value = false
  generating.value = true
  try {
    const res = await generateAiMangaStoryboard(formData, { signal: storyboardController.value.signal })
    if (storyboardCanceled.value) return
    groups.value = res.data.groups || []
    storyboardText.value = res.data.storyboard || renderGroups(groups.value)
    recordUsageCost(res.data.usage_cost)
    Object.keys(collapsedGroups).forEach((key) => delete collapsedGroups[key])
    ElMessage.success('分镜词生成完成')
  } catch (e) {
    if (storyboardCanceled.value || String(e).toLowerCase() === 'canceled') {
      ElMessage.info('已取消生成分镜词')
      return
    }
    ElMessage.error(String(e || '分镜词生成失败'))
  } finally {
    generating.value = false
    storyboardController.value = null
  }
}

const cancelStoryboardGeneration = () => {
  if (!storyboardController.value) return
  storyboardCanceled.value = true
  storyboardController.value.abort()
}

const clearInput = () => {
  inputText.value = ''
  selectedFile.value = null
  selectedFileName.value = ''
  characterPositionImage.value = null
  positionDescription.value = ''
  groups.value = []
  storyboardText.value = ''
}

const formatDuration = (value) => Number(value || 0).toFixed(Number(value || 0) % 1 === 0 ? 0 : 1)

const renderGroups = (items) =>
  (items || [])
    .map((group) => {
      const lines = [`段落 ${group.index} | 约 ${formatDuration(group.duration_seconds)} 秒`]
      ;(group.shots || []).forEach((shot) => {
        lines.push(`${shot.index}.（${formatDuration(shot.duration_seconds)}s）${shot.prompt}`)
      })
      return lines.join('\n')
    })
    .join('\n\n')

const copyText = async (text, successText) => {
  try {
    await navigator.clipboard.writeText(String(text || ''))
    ElMessage.success(successText)
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const copyAllPrompts = () => copyText(storyboardText.value || renderGroups(groups.value), '全部提示词已复制')
const copyGroup = (group) => copyText(renderGroups([group]), `段落 ${group.index} 已复制`)
const copyPromptConfig = () => copyText(`${storyboardPrompt.value}\n\n${currentStylePrompt.value}`.trim(), '当前提示词已复制')

const toggleGroup = (groupId) => {
  collapsedGroups[groupId] = !collapsedGroups[groupId]
}

onMounted(async () => {
  try {
    await loadConfig()
  } catch (e) {
    ElMessage.error(String(e || '获取剧本创作配置失败'))
  }
})
</script>

<style scoped>
.script-shell {
  min-height: 100vh;
  background: #070b16;
  color: #e8eefc;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 28px;
  border-bottom: 1px solid rgba(71, 138, 196, 0.28);
  background: #0a1020;
}

.eyebrow {
  margin: 0 0 6px;
  color: #7fb8ff;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.topbar h1,
.section-head h2 {
  margin: 0;
}

.topbar-actions,
.output-actions,
.file-row,
.action-row,
.style-switch {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.model-select {
  width: 280px;
}

.cost-card {
  position: relative;
  min-width: 168px;
  min-height: 62px;
  display: grid;
  align-content: center;
  gap: 2px;
  padding: 9px 12px;
  border: 1px solid rgba(245, 200, 75, 0.38);
  border-radius: 8px;
  background: #101827;
  color: #cfe0f5;
}

.cost-card span,
.cost-card small {
  font-size: 12px;
  color: #8ea2bd;
  line-height: 1.25;
}

.cost-card strong {
  color: #f5c84b;
  font-size: 17px;
  line-height: 1.25;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(360px, 0.9fr) minmax(480px, 1.1fr);
  gap: 18px;
  padding: 22px;
}

.input-panel,
.output-panel {
  min-height: calc(100vh - 112px);
  border: 1px solid rgba(57, 125, 184, 0.36);
  border-radius: 8px;
  background: #0c1324;
  padding: 18px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 16px;
}

.style-switch {
  padding: 4px;
  border: 1px solid rgba(89, 151, 204, 0.38);
  border-radius: 8px;
  background: #070c18;
}

.style-btn {
  min-width: 94px;
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #9db2cc;
}

.style-btn.active {
  color: #05101d;
  background: #f5c84b;
  font-weight: 700;
}

.story-input :deep(.el-textarea__inner) {
  min-height: 420px !important;
  border-radius: 8px;
  background: #080d19;
  border-color: rgba(83, 145, 198, 0.44);
  color: #edf4ff;
  line-height: 1.7;
}

.file-row {
  margin-top: 14px;
}

.file-hidden {
  display: none;
}

.file-chip,
.meta-chip,
.duration-pill {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 6px;
  background: #1b2a40;
  color: #cfe0f5;
  font-size: 12px;
}

.file-tip {
  color: #8ea2bd;
  font-size: 13px;
}

.reference-panel {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid rgba(83, 145, 198, 0.34);
  border-radius: 8px;
  background: #08101f;
}

.reference-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.reference-head strong {
  color: #e8eefc;
}

.reference-head span {
  color: #8ea2bd;
  font-size: 12px;
}

.reference-uploader {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  border: 1px dashed rgba(127, 184, 255, 0.46);
  border-radius: 8px;
  background: #0a1426;
  padding: 12px;
  color: #a9bdd6;
  cursor: pointer;
}

.position-layout {
  display: grid;
  grid-template-columns: minmax(160px, 0.38fr) minmax(0, 1fr);
  gap: 12px;
}

.position-upload {
  min-height: 116px;
}

.position-layout :deep(.el-textarea__inner) {
  min-height: 116px !important;
  border-radius: 8px;
  background: #080d19;
  border-color: rgba(83, 145, 198, 0.44);
  color: #edf4ff;
  line-height: 1.7;
}

.reference-uploader input {
  display: none;
}

.reference-uploader strong {
  color: #f5c84b;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reference-uploader button {
  align-self: flex-start;
  border: 0;
  border-radius: 5px;
  background: #24344c;
  color: #dbe8f8;
  padding: 4px 8px;
  cursor: pointer;
}

.action-row {
  justify-content: flex-end;
  margin-top: 18px;
}

.primary-action {
  min-width: 132px;
  border: 0;
  background: #1f8fff;
}

.empty-state {
  min-height: 420px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  border: 1px dashed rgba(82, 143, 194, 0.42);
  border-radius: 8px;
  color: #9fb2cb;
}

.empty-state strong {
  color: #e8eefc;
  font-size: 18px;
}

.group-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.prompt-group {
  border-left: 5px solid #0e6ba8;
  padding-left: 14px;
}

.group-head {
  width: 100%;
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 12px;
  border: 1px solid rgba(54, 124, 184, 0.56);
  border-radius: 8px;
  color: #dfe9f8;
  background: #0f182b;
  padding: 0 12px;
  text-align: left;
  cursor: pointer;
}

.copy-btn {
  margin-left: auto;
}

.shot-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px 12px 4px;
}

.shot-card {
  min-height: 104px;
  border: 1px solid rgba(48, 113, 171, 0.5);
  border-radius: 8px;
  background: #0a1120;
  padding: 16px 18px;
}

.shot-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.shot-index {
  min-width: 32px;
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: #24344c;
  color: #dbe8f8;
  font-weight: 700;
}

.duration-pill {
  background: #101d2f;
}

.shot-card p {
  margin: 0;
  color: #edf4ff;
  line-height: 1.85;
  font-weight: 700;
}

.prompt-dialog {
  max-height: 64vh;
  overflow: auto;
}

.prompt-dialog h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.prompt-dialog pre {
  margin: 0 0 18px;
  padding: 14px;
  border-radius: 8px;
  background: #0a1120;
  color: #e8eefc;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

@media (max-width: 1080px) {
  .topbar,
  .section-head {
    flex-direction: column;
    align-items: stretch;
  }

  .workspace {
    grid-template-columns: 1fr;
  }

  .input-panel,
  .output-panel {
    min-height: auto;
  }

  .model-select {
    width: 100%;
  }

  .cost-card {
    width: 100%;
  }

  .position-layout {
    grid-template-columns: 1fr;
  }
}
</style>
