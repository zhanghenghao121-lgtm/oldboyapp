<template>
  <div class="script-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">AI SCRIPT PROMPT</p>
        <h1>AI剧本创作</h1>
      </div>
      <div class="topbar-actions">
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

        <div class="action-row">
          <el-button plain :disabled="!inputText && !selectedFile" @click="clearInput">清空</el-button>
          <el-button class="primary-action" type="primary" :loading="generating" @click="submitStoryboard">识别剧本</el-button>
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
          <strong>等待识别剧本</strong>
          <span>输出会按段落分组展示，每组总时长不超过 15 秒。</span>
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
const generating = ref(false)
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

const currentModelLabel = computed(() => {
  const matched = modelOptions.value.find((item) => item.id === selectedModelPreset.value)
  return matched?.model ? `${matched.label} · ${matched.model}` : '未选择模型'
})

const currentStyle = computed(() => styleOptions.value.find((item) => item.id === selectedStyle.value) || styleOptions.value[0])
const currentStyleLabel = computed(() => currentStyle.value?.label || '3D风格')
const currentStylePrompt = computed(() => currentStyle.value?.prompt || '')

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

const loadConfig = async () => {
  const res = await getAiMangaConfig()
  storyboardPrompt.value = res.data.storyboard_prompt || ''
  modelOptions.value = res.data.model_options || []
  styleOptions.value = res.data.style_options?.length ? res.data.style_options : styleOptions.value
  selectedModelPreset.value = res.data.default_model_preset || 'assistant'
  selectedStyle.value = res.data.default_style || '3d'
}

const submitStoryboard = async () => {
  if (!inputText.value.trim() && !selectedFile.value) {
    ElMessage.warning('请输入文本或上传文档后再识别剧本')
    return
  }

  const formData = new FormData()
  if (selectedFile.value) formData.append('file', selectedFile.value)
  formData.append('text', inputText.value)
  formData.append('model_preset', selectedModelPreset.value)
  formData.append('style', selectedStyle.value)

  generating.value = true
  try {
    const res = await generateAiMangaStoryboard(formData)
    groups.value = res.data.groups || []
    storyboardText.value = res.data.storyboard || renderGroups(groups.value)
    Object.keys(collapsedGroups).forEach((key) => delete collapsedGroups[key])
    ElMessage.success('剧本识别完成')
  } catch (e) {
    ElMessage.error(String(e || '剧本识别失败'))
  } finally {
    generating.value = false
  }
}

const clearInput = () => {
  inputText.value = ''
  selectedFile.value = null
  selectedFileName.value = ''
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
}
</style>
