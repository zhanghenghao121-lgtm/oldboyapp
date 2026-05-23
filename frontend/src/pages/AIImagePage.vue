<template>
  <div class="image-shell">
    <aside class="tool-rail">
      <div class="brand-block">
        <p class="eyebrow">AI IMAGE</p>
        <h1>AI生图</h1>
      </div>
      <button class="mode-btn" :class="{ active: mode === 'text' }" type="button" @click="mode = 'text'">
        <strong>文生图</strong>
        <span>输入描述生成画面</span>
      </button>
      <button class="mode-btn" :class="{ active: mode === 'reverse_shot' }" type="button" @click="mode = 'reverse_shot'">
        <strong>生出反打画面</strong>
        <span>@角色/物品推理站位</span>
      </button>
      <el-button plain class="back-btn" @click="$router.push('/ai-manga')">返回剧本创作</el-button>
    </aside>

    <main class="studio">
      <header class="studio-head">
        <div>
          <p class="eyebrow">{{ mode === 'reverse_shot' ? 'REVERSE SHOT' : 'TEXT TO IMAGE' }}</p>
          <h2>{{ mode === 'reverse_shot' ? '反打镜头生成' : 'AI 图像生成' }}</h2>
        </div>
        <div class="preset-row">
          <el-button plain @click="settingsDialogRef?.open()">设置</el-button>
          <el-select v-model="selectedModel" class="model-select" placeholder="选择模型">
            <el-option
              v-for="item in modelOptions"
              :key="item.id"
              :label="`${item.label} · ${item.model}`"
              :value="item.model"
            />
          </el-select>
          <el-select v-if="!isSeedreamSelected" v-model="size" class="small-select">
            <el-option v-for="item in sizeOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-segmented v-model="resolution" :options="resolutionOptions" />
        </div>
      </header>

      <section class="work-grid">
        <div class="control-panel">
          <div class="panel-head">
            <h3>{{ mode === 'reverse_shot' ? '镜头参考' : '画面描述' }}</h3>
            <span>{{ isSeedreamSelected ? 'Doubao 使用 1K / 2K / 4K 档位' : '默认 16:9 · 1k · 1 张' }}</span>
          </div>

          <template v-if="mode === 'reverse_shot'">
            <div class="upload-grid">
              <label v-for="item in reverseUploads" :key="item.field" class="upload-card">
                <input type="file" accept="image/*" @change="(event) => handleReverseImageChange(event, item.field)" />
                <span>{{ item.kicker }}</span>
                <strong>{{ reverseImages[item.field]?.name || item.title }}</strong>
                <button v-if="reverseImages[item.field]" type="button" @click.prevent="reverseImages[item.field] = null">移除</button>
              </label>
            </div>

            <div class="object-panel">
              <div class="object-head">
                <div>
                  <h4>角色 / 物品参考</h4>
                  <span>上传后可点击插入 @对象名</span>
                </div>
                <el-button plain size="small" :disabled="objectRefs.length >= 14" @click="addObjectRef">添加对象</el-button>
              </div>
              <div class="object-list">
                <div v-for="item in objectRefs" :key="item.id" class="object-card">
                  <el-input v-model="item.name" maxlength="20" placeholder="对象名，如 顾知夏 / 木箱" />
                  <label class="object-file">
                    <input type="file" accept="image/*" @change="(event) => handleObjectImageChange(event, item.id)" />
                    <span>{{ item.file?.name || '上传参考图' }}</span>
                  </label>
                  <el-button text :disabled="!item.name.trim()" @click="insertMention(item.name)">插入@</el-button>
                  <button class="remove-object" type="button" @click="removeObjectRef(item.id)">×</button>
                </div>
              </div>
            </div>

            <el-input
              ref="promptInputRef"
              v-model="prompt"
              type="textarea"
              :rows="7"
              resize="none"
              placeholder="用 @对象名 描述它们在参考图1正面镜头中的站位，例如：@顾知夏站在门口左侧，面向@木箱，距离镜头更近；@木箱在桌子右后方，半遮挡。"
            />
          </template>

          <el-input
            v-else
            v-model="prompt"
            type="textarea"
            :rows="12"
            resize="none"
            placeholder="描述你想生成的画面，例如：古风庭院夜景，男女主隔着灯影对望，电影级布光，细节丰富。"
          />

          <div class="action-row">
            <el-button plain :disabled="generating" @click="clearForm">清空</el-button>
            <el-button class="generate-btn" type="primary" :loading="generating" @click="submitImage">开始生成</el-button>
          </div>

          <div v-if="taskId" class="task-card">
            <span>任务 {{ taskStatus || 'submitted' }}</span>
            <strong>{{ progress }}%</strong>
            <small>{{ taskId }}</small>
          </div>
        </div>

        <div class="preview-panel">
          <div v-if="!imageUrls.length" class="empty-preview" v-loading="generating">
            <strong>{{ generating ? '正在生成画面' : '等待一张新画面' }}</strong>
            <span>{{ generating ? '提交后会按 3-5 秒间隔自动查询任务结果。' : '生成完成后图片会显示在这里。' }}</span>
          </div>
          <div v-else class="result-stack">
            <img v-for="url in imageUrls" :key="url" :src="url" alt="AI生成结果" />
            <div class="result-actions">
              <el-button plain @click="downloadImage">下载图片</el-button>
              <el-button type="primary" @click="openImage">打开图片</el-button>
            </div>
          </div>
        </div>
      </section>
    </main>
    <UserSettingsDialog ref="settingsDialogRef" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { generateAiImage, getAiImageConfig, getAiImageTask } from '../api/aiManga'
import UserSettingsDialog from '../components/UserSettingsDialog.vue'

const mode = ref('text')
const prompt = ref('')
const promptInputRef = ref(null)
const settingsDialogRef = ref(null)
const selectedModel = ref('gpt-image-2')
const size = ref('16:9')
const resolution = ref('1k')
const modelOptions = ref([{ id: 'gpt-image-2', label: 'GPT-Image-2', model: 'gpt-image-2' }])
const sizeOptions = ref(['16:9', '9:16', '1:1', '4:3', '3:4', '3:2', '2:3', '21:9'])
const resolutionOptions = ref(['1k', '2k', '4k'])
const reverseImages = reactive({
  front_scene_image: null,
  reverse_scene_image: null,
})
const objectRefs = ref([{ id: Date.now(), name: '', file: null }])
const generating = ref(false)
const taskId = ref('')
const taskStatus = ref('')
const progress = ref(0)
const imageUrls = ref([])
let pollTimer = null

const reverseUploads = [
  { field: 'front_scene_image', kicker: '参考图 1', title: '场景正面背景' },
  { field: 'reverse_scene_image', kicker: '参考图 2', title: '场景反打背景' },
]

const selectedModelOption = computed(() => modelOptions.value.find((item) => item.model === selectedModel.value) || modelOptions.value[0] || {})
const isSeedreamSelected = computed(() => {
  const text = `${selectedModelOption.value.provider || ''} ${selectedModelOption.value.model || ''} ${selectedModelOption.value.label || ''}`.toLowerCase()
  return text.includes('seedream') || text.includes('doubao') || text.includes('volcengine')
})
const validObjectRefs = computed(() => objectRefs.value.filter((item) => item.name.trim() && item.file))
const hasReverseImages = computed(() => reverseUploads.every((item) => reverseImages[item.field]) && validObjectRefs.value.length > 0)

const stopPolling = () => {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = null
}

const handleReverseImageChange = (event, field) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  reverseImages[field] = file
}

const addObjectRef = () => {
  objectRefs.value.push({ id: Date.now() + Math.random(), name: '', file: null })
}

const removeObjectRef = (id) => {
  objectRefs.value = objectRefs.value.filter((item) => item.id !== id)
  if (!objectRefs.value.length) addObjectRef()
}

const handleObjectImageChange = (event, id) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  const matched = objectRefs.value.find((item) => item.id === id)
  if (matched) matched.file = file
}

const insertMention = (name) => {
  const mention = `@${String(name || '').trim()}`
  if (!mention || mention === '@') return
  const textarea = promptInputRef.value?.textarea
  if (!textarea) {
    prompt.value = `${prompt.value}${prompt.value ? ' ' : ''}${mention}`
    return
  }
  const start = textarea.selectionStart ?? prompt.value.length
  const end = textarea.selectionEnd ?? prompt.value.length
  prompt.value = `${prompt.value.slice(0, start)}${mention}${prompt.value.slice(end)}`
  requestAnimationFrame(() => {
    textarea.focus()
    textarea.setSelectionRange(start + mention.length, start + mention.length)
  })
}

const schedulePoll = () => {
  stopPolling()
  pollTimer = window.setTimeout(pollTask, taskStatus.value === 'submitted' ? 10000 : 4000)
}

const pollTask = async () => {
  if (!taskId.value) return
  try {
    const res = await getAiImageTask(taskId.value)
    const data = res.data || {}
    taskStatus.value = data.status || taskStatus.value
    progress.value = Number(data.progress || progress.value || 0)
    if (data.images?.length) imageUrls.value = data.images
    if (data.status === 'completed') {
      generating.value = false
      progress.value = 100
      stopPolling()
      ElMessage.success('图片生成完成')
      return
    }
    if (data.status === 'failed') {
      generating.value = false
      stopPolling()
      ElMessage.error(data.error || '图片生成失败')
      return
    }
    schedulePoll()
  } catch (e) {
    generating.value = false
    stopPolling()
    ElMessage.error(String(e || '查询任务失败'))
  }
}

const submitImage = async () => {
  if (generating.value) return
  if (mode.value === 'text' && !prompt.value.trim()) {
    ElMessage.warning('请输入生图提示词')
    return
  }
  if (mode.value === 'reverse_shot' && !hasReverseImages.value) {
    ElMessage.warning('请上传 2 张场景图和至少 1 张角色/物品参考图')
    return
  }
  if (mode.value === 'reverse_shot' && !prompt.value.trim()) {
    ElMessage.warning('请用 @对象名 描述正面镜头站位')
    return
  }

  const formData = new FormData()
  formData.append('mode', mode.value)
  formData.append('prompt', prompt.value)
  formData.append('model', selectedModel.value)
  formData.append('size', size.value)
  formData.append('resolution', resolution.value)
  reverseUploads.forEach((item) => {
    if (reverseImages[item.field]) formData.append(item.field, reverseImages[item.field])
  })
  formData.append('object_names', JSON.stringify(validObjectRefs.value.map((item) => item.name.trim())))
  validObjectRefs.value.forEach((item) => {
    formData.append('object_images', item.file)
  })

  generating.value = true
  taskId.value = ''
  taskStatus.value = 'submitted'
  progress.value = 0
  imageUrls.value = []
  try {
    const res = await generateAiImage(formData)
    if (res.data.images?.length) {
      imageUrls.value = res.data.images
      taskId.value = res.data.task_id || ''
      taskStatus.value = res.data.status || 'completed'
      progress.value = 100
      generating.value = false
      ElMessage.success('图片生成完成')
      return
    }
    taskId.value = res.data.task_id
    taskStatus.value = res.data.status || 'submitted'
    ElMessage.success('生图任务已提交')
    schedulePoll()
  } catch (e) {
    generating.value = false
    ElMessage.error(String(e || '生图任务提交失败'))
  }
}

const clearForm = () => {
  prompt.value = ''
  reverseUploads.forEach((item) => {
    reverseImages[item.field] = null
  })
  objectRefs.value = [{ id: Date.now(), name: '', file: null }]
  taskId.value = ''
  taskStatus.value = ''
  progress.value = 0
  imageUrls.value = []
  generating.value = false
  stopPolling()
}

const downloadImage = async () => {
  const url = imageUrls.value[0]
  if (!url) return
  try {
    const response = await fetch(url)
    const blob = await response.blob()
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = `ai-image-${taskId.value || Date.now()}.png`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
    ElMessage.success('图片已开始下载')
  } catch {
    window.open(url, '_blank', 'noopener,noreferrer')
    ElMessage.warning('浏览器拦截了直接下载，已为你打开图片')
  }
}

const openImage = () => {
  if (imageUrls.value[0]) window.open(imageUrls.value[0], '_blank', 'noopener,noreferrer')
}

onMounted(async () => {
  try {
    const res = await getAiImageConfig()
    modelOptions.value = res.data.model_options?.length ? res.data.model_options : modelOptions.value
    selectedModel.value = res.data.default_model || modelOptions.value[0].model
    size.value = res.data.default_size || '16:9'
    resolution.value = res.data.default_resolution || '1k'
    sizeOptions.value = res.data.size_options?.length ? res.data.size_options : sizeOptions.value
    resolutionOptions.value = res.data.resolution_options?.length ? res.data.resolution_options : resolutionOptions.value
  } catch (e) {
    ElMessage.error(String(e || '获取生图配置失败'))
  }
})

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.image-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px 1fr;
  background: #0a0f14;
  color: #eef4f0;
}

.tool-rail {
  padding: 24px 16px;
  border-right: 1px solid rgba(145, 184, 169, 0.28);
  background: #0d1717;
}

.brand-block h1,
.studio-head h2,
.panel-head h3 {
  margin: 0;
}

.eyebrow {
  margin: 0 0 7px;
  color: #9dd6bd;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.mode-btn {
  width: 100%;
  min-height: 76px;
  margin-top: 12px;
  padding: 14px;
  border: 1px solid rgba(145, 184, 169, 0.28);
  border-radius: 8px;
  background: #111f1f;
  color: #dfeee8;
  text-align: left;
}

.mode-btn strong,
.mode-btn span {
  display: block;
}

.mode-btn span {
  margin-top: 6px;
  color: #8ba69d;
  font-size: 13px;
}

.mode-btn.active {
  border-color: #6ee7ac;
  background: #16342b;
}

.back-btn {
  width: 100%;
  margin-top: 18px;
}

.studio {
  padding: 24px;
}

.studio-head,
.preset-row,
.panel-head,
.action-row,
.result-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.preset-row {
  justify-content: flex-end;
  flex-wrap: wrap;
}

.model-select {
  width: 190px;
}

.small-select {
  width: 104px;
}

.work-grid {
  margin-top: 22px;
  display: grid;
  grid-template-columns: minmax(360px, 0.88fr) minmax(420px, 1.12fr);
  gap: 18px;
}

.control-panel,
.preview-panel {
  border: 1px solid rgba(145, 184, 169, 0.26);
  border-radius: 8px;
  background: #101a1b;
  padding: 18px;
}

.panel-head {
  margin-bottom: 14px;
}

.panel-head span,
.empty-preview span,
.task-card small {
  color: #91a8a0;
}

.upload-grid {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
}

.upload-card {
  position: relative;
  min-height: 96px;
  padding: 14px;
  border: 1px dashed rgba(157, 214, 189, 0.44);
  border-radius: 8px;
  background: #0c1516;
  cursor: pointer;
}

.upload-card input {
  display: none;
}

.upload-card span,
.upload-card strong {
  display: block;
}

.upload-card span {
  color: #9dd6bd;
  font-size: 12px;
}

.upload-card strong {
  margin-top: 8px;
}

.upload-card button {
  position: absolute;
  right: 12px;
  bottom: 12px;
  border: 0;
  color: #ffe1df;
  background: transparent;
}

.object-panel {
  margin-bottom: 14px;
  padding: 14px;
  border: 1px solid rgba(145, 184, 169, 0.22);
  border-radius: 8px;
  background: #0b1414;
}

.object-head,
.object-card {
  display: flex;
  align-items: center;
  gap: 10px;
}

.object-head {
  justify-content: space-between;
  margin-bottom: 12px;
}

.object-head h4 {
  margin: 0;
}

.object-head span {
  display: block;
  margin-top: 4px;
  color: #91a8a0;
  font-size: 12px;
}

.object-list {
  display: grid;
  gap: 10px;
}

.object-card {
  position: relative;
  padding: 10px;
  border: 1px solid rgba(145, 184, 169, 0.2);
  border-radius: 8px;
  background: #101a1b;
}

.object-card .el-input {
  width: 160px;
}

.object-file {
  min-width: 0;
  flex: 1;
  height: 32px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border: 1px dashed rgba(157, 214, 189, 0.42);
  border-radius: 8px;
  color: #cfe3dc;
  cursor: pointer;
}

.object-file input {
  display: none;
}

.object-file span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.remove-object {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 8px;
  color: #ffe1df;
  background: rgba(255, 111, 103, 0.12);
}

.action-row {
  justify-content: flex-end;
  margin-top: 14px;
}

.generate-btn {
  border: 0;
  background: #1c9d70;
}

.task-card {
  margin-top: 14px;
  padding: 12px;
  border-radius: 8px;
  background: #0b1414;
}

.task-card span,
.task-card strong,
.task-card small {
  display: block;
}

.task-card strong {
  margin: 4px 0;
  font-size: 24px;
}

.preview-panel {
  min-height: 520px;
}

.empty-preview {
  min-height: 482px;
  display: grid;
  place-content: center;
  gap: 8px;
  text-align: center;
}

.empty-preview strong {
  font-size: 24px;
}

.result-stack img {
  width: 100%;
  max-height: 68vh;
  object-fit: contain;
  border-radius: 8px;
  background: #050909;
}

.result-actions {
  justify-content: flex-end;
  margin-top: 14px;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: #0a0f14;
  box-shadow: inset 0 0 0 1px rgba(145, 184, 169, 0.36) !important;
  color: #eef4f0;
}

@media (max-width: 960px) {
  .image-shell,
  .work-grid {
    grid-template-columns: 1fr;
  }

  .studio-head {
    align-items: stretch;
    flex-direction: column;
  }

  .preset-row {
    justify-content: flex-start;
  }
}
</style>
