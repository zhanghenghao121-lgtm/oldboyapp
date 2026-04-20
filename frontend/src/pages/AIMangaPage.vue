<template>
  <div class="manga-shell">
    <aside class="manga-sidebar">
      <div class="paper-glow paper-glow-a"></div>
      <div class="paper-glow paper-glow-b"></div>
      <div class="sidebar-head">
        <span class="sidebar-tag">Storyboard Lab</span>
        <h2>AI漫剧</h2>
        <p>把文档与文本压成可直接复制的漫画分镜稿。</p>
      </div>

      <button class="nav-btn" type="button" @click="$router.push('/ai-customer')">AI章鱼助手</button>
      <button class="nav-btn active" type="button" @click="$router.push('/ai-manga')">AI漫剧创作</button>

      <div class="sidebar-panel">
        <p class="panel-title">使用方式</p>
        <ol class="sidebar-steps">
          <li>上传 PDF 或 Word 文档，或直接输入剧情文本。</li>
          <li>右上角选择模型，默认使用助手模型。</li>
          <li>点击“识别剧本”，系统会按分镜提示词自动输出。</li>
        </ol>
      </div>
    </aside>

    <main class="manga-main">
      <div class="manga-hero">
        <div>
          <p class="hero-kicker">NEON PAPER CUT</p>
          <h1>AI漫剧创作台</h1>
          <p class="hero-sub">面向剧本、小说片段、策划案与分集大纲的漫画分镜整理器。</p>
        </div>
      </div>

      <section class="studio-grid">
        <article class="studio-card input-card">
          <div class="card-head">
            <div>
              <p class="card-kicker">SCRIPT SOURCE</p>
              <h3>剧本文本 / 文档输入</h3>
            </div>
            <div class="upload-actions">
              <el-select v-model="selectedModelPreset" class="model-select" placeholder="选择模型">
                <el-option
                  v-for="item in modelOptions"
                  :key="item.id"
                  :label="`${item.label} · ${item.model || '未配置'}`"
                  :value="item.id"
                />
              </el-select>
              <el-button plain class="prompt-btn" @click="promptDialogVisible = true">分镜提示词</el-button>
              <input ref="fileInputRef" type="file" class="file-hidden" accept=".pdf,.doc,.docx" @change="handleFileChange" />
              <el-button class="outline-btn" @click="pickFile">上传文档</el-button>
              <span v-if="selectedFileName" class="file-chip">{{ selectedFileName }}</span>
            </div>
          </div>

          <el-input
            v-model="inputText"
            type="textarea"
            :rows="17"
            resize="none"
            class="story-input"
            placeholder="可以直接粘贴剧情文本、对白、人物小传、分集梗概，也可以只上传文档后识别。"
          />

          <div class="action-row">
            <p class="action-tip">支持 PDF / DOCX。旧版 `.doc` 建议先另存为 `.docx`。</p>
            <el-button class="main-action" type="primary" :loading="generating" @click="submitStoryboard">识别剧本</el-button>
          </div>
        </article>

        <article class="studio-card result-card">
          <div class="card-head">
            <div>
              <p class="card-kicker">OUTPUT BOARD</p>
              <h3>漫画分镜输出</h3>
            </div>
            <div class="result-actions">
              <span class="model-badge">{{ currentModelLabel }}</span>
              <el-button plain :disabled="!storyboardText" @click="copyStoryboard">复制内容</el-button>
            </div>
          </div>

          <div v-if="!storyboardText && !generating" class="result-empty">
            <p>分镜结果会在这里出现。</p>
            <span>系统会自动按后台设定的分镜提示词整理镜头、场景、台词与画面提示词。</span>
          </div>

          <div v-else class="result-panel" v-loading="generating">
            <pre>{{ storyboardText || '正在识别剧本，请稍候...' }}</pre>
          </div>
        </article>
      </section>
    </main>

    <el-dialog v-model="promptDialogVisible" title="系统分镜提示词" width="760px">
      <div class="prompt-dialog-body">
        <pre>{{ storyboardPrompt }}</pre>
      </div>
      <template #footer>
        <el-button @click="copyPrompt">复制提示词</el-button>
        <el-button type="primary" @click="promptDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { getAiMangaConfig, generateAiMangaStoryboard } from '../api/aiManga'

const router = useRouter()
const fileInputRef = ref(null)
const selectedFile = ref(null)
const selectedFileName = ref('')
const inputText = ref('')
const generating = ref(false)
const storyboardText = ref('')
const promptDialogVisible = ref(false)
const storyboardPrompt = ref('')
const selectedModelPreset = ref('assistant')
const modelOptions = ref([])

const currentModelLabel = computed(() => {
  const matched = modelOptions.value.find((item) => item.id === selectedModelPreset.value)
  return matched?.model ? `${matched.label} · ${matched.model}` : '未选择模型'
})

const pickFile = () => {
  if (fileInputRef.value) fileInputRef.value.click()
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
  selectedModelPreset.value = res.data.default_model_preset || 'assistant'
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

  generating.value = true
  try {
    const res = await generateAiMangaStoryboard(formData)
    storyboardText.value = res.data.storyboard || ''
    ElMessage.success('剧本识别完成，可直接复制分镜结果')
  } catch (e) {
    ElMessage.error(String(e || '剧本识别失败'))
  } finally {
    generating.value = false
  }
}

const copyText = async (text, successText) => {
  try {
    await navigator.clipboard.writeText(String(text || ''))
    ElMessage.success(successText)
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const copyStoryboard = () => copyText(storyboardText.value, '分镜结果已复制')
const copyPrompt = () => copyText(storyboardPrompt.value, '提示词已复制')

onMounted(async () => {
  try {
    await loadConfig()
  } catch (e) {
    ElMessage.error(String(e || '获取漫剧配置失败'))
    router.push('/ai-customer')
  }
})
</script>

<style scoped>
.manga-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 280px 1fr;
  background:
    radial-gradient(900px 420px at 18% -4%, rgba(255, 166, 64, 0.14), transparent 65%),
    radial-gradient(780px 380px at 100% 0%, rgba(65, 208, 255, 0.12), transparent 62%),
    linear-gradient(135deg, #120f18, #1d1623 48%, #0f1117);
  color: #f7f2ea;
}
.manga-sidebar {
  position: relative;
  overflow: hidden;
  padding: 24px 18px;
  border-right: 1px solid rgba(255, 209, 153, 0.18);
  background:
    linear-gradient(180deg, rgba(34, 24, 30, 0.96), rgba(18, 16, 24, 0.98)),
    repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.02) 0,
      rgba(255, 255, 255, 0.02) 1px,
      transparent 1px,
      transparent 12px
    );
}
.paper-glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(30px);
  pointer-events: none;
}
.paper-glow-a {
  width: 180px;
  height: 180px;
  background: rgba(255, 152, 51, 0.2);
  top: -60px;
  left: -30px;
}
.paper-glow-b {
  width: 160px;
  height: 160px;
  background: rgba(68, 209, 255, 0.15);
  bottom: -40px;
  right: -30px;
}
.sidebar-head {
  position: relative;
  z-index: 1;
}
.sidebar-tag {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: #ffddaf;
  border: 1px solid rgba(255, 190, 112, 0.28);
  background: rgba(255, 164, 67, 0.08);
}
.sidebar-head h2 {
  margin: 16px 0 6px;
  font-size: 34px;
  line-height: 1;
  font-family: Georgia, 'Times New Roman', serif;
}
.sidebar-head p {
  margin: 0 0 20px;
  color: #cebfae;
  line-height: 1.6;
}
.nav-btn {
  width: 100%;
  margin-bottom: 10px;
  border-radius: 14px;
  border: 1px solid rgba(255, 212, 154, 0.15);
  background: rgba(255, 255, 255, 0.03);
  color: #f2e8dc;
  text-align: left;
  padding: 12px 14px;
}
.nav-btn.active {
  background: linear-gradient(135deg, rgba(255, 162, 72, 0.88), rgba(255, 118, 64, 0.92));
  color: #25120d;
  border-color: transparent;
  box-shadow: 0 14px 32px rgba(255, 120, 50, 0.16);
}
.sidebar-panel {
  margin-top: 22px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(255, 218, 176, 0.14);
  background: rgba(255, 250, 243, 0.04);
}
.panel-title {
  margin: 0 0 10px;
  color: #ffd59a;
  letter-spacing: 0.1em;
  font-size: 12px;
}
.sidebar-steps {
  margin: 0;
  padding-left: 18px;
  color: #d8cab7;
  line-height: 1.75;
}
.manga-main {
  padding: 28px;
}
.manga-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 26px;
  border-radius: 26px;
  border: 1px solid rgba(255, 223, 192, 0.12);
  background:
    linear-gradient(140deg, rgba(255, 248, 238, 0.06), rgba(255, 255, 255, 0.02)),
    radial-gradient(circle at top right, rgba(255, 177, 90, 0.12), transparent 28%);
  box-shadow: 0 16px 40px rgba(5, 6, 12, 0.28);
}
.hero-kicker {
  margin: 0 0 8px;
  color: #ffcb87;
  letter-spacing: 0.18em;
  font-size: 11px;
}
.manga-hero h1 {
  margin: 0;
  font-size: clamp(34px, 4vw, 52px);
  line-height: 1.04;
  font-family: Georgia, 'Times New Roman', serif;
}
.hero-sub {
  margin: 10px 0 0;
  color: #d2c6ba;
}
.hero-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}
.model-select {
  width: 260px;
}
.prompt-btn {
  border-color: rgba(255, 205, 138, 0.24);
  color: #ffe2b7;
  background: rgba(255, 191, 102, 0.08);
}
.studio-grid {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 18px;
}
.studio-card {
  min-height: 560px;
  border-radius: 24px;
  border: 1px solid rgba(255, 223, 192, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 247, 238, 0.05), rgba(255, 255, 255, 0.02)),
    radial-gradient(circle at top right, rgba(61, 211, 255, 0.06), transparent 26%);
  box-shadow: 0 18px 42px rgba(5, 6, 12, 0.24);
  padding: 22px;
}
.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.card-kicker {
  margin: 0 0 6px;
  color: #ffcb87;
  letter-spacing: 0.16em;
  font-size: 11px;
}
.card-head h3 {
  margin: 0;
  font-size: 24px;
  font-family: Georgia, 'Times New Roman', serif;
}
.upload-actions,
.result-actions,
.action-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.file-hidden {
  display: none;
}
.outline-btn {
  border-color: rgba(255, 212, 154, 0.2);
  color: #f7e0be;
  background: rgba(255, 255, 255, 0.04);
}
.file-chip,
.model-badge {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #1c130d;
  background: linear-gradient(135deg, #ffd6a6, #ffb97c);
}
.story-input :deep(.el-textarea__inner) {
  min-height: 410px !important;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(24, 23, 30, 0.96), rgba(18, 18, 24, 0.98)),
    repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.02) 0,
      rgba(255, 255, 255, 0.02) 1px,
      transparent 1px,
      transparent 28px
    );
  border: 1px solid rgba(255, 220, 184, 0.12);
  color: #f7f2ea;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
}
.action-row {
  justify-content: space-between;
  margin-top: 14px;
}
.action-tip {
  margin: 0;
  color: #d0c1af;
  font-size: 12px;
}
.main-action {
  min-width: 148px;
  border: 0;
  background: linear-gradient(135deg, #ff9f4c, #ff6d45);
  box-shadow: 0 14px 28px rgba(255, 121, 68, 0.22);
}
.result-empty {
  min-height: 430px;
  border-radius: 20px;
  border: 1px dashed rgba(255, 218, 176, 0.16);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #d4c7b7;
  padding: 24px;
}
.result-empty p {
  margin: 0 0 10px;
  font-size: 20px;
  font-family: Georgia, 'Times New Roman', serif;
}
.result-panel {
  min-height: 430px;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 250, 244, 0.06), rgba(255, 255, 255, 0.03)),
    linear-gradient(90deg, rgba(255, 177, 90, 0.03), transparent);
  border: 1px solid rgba(255, 220, 184, 0.12);
  padding: 18px;
}
.result-panel pre,
.prompt-dialog-body pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.72;
  color: #f7f2ea;
  font-family: 'SFMono-Regular', Consolas, monospace;
}
.prompt-dialog-body {
  max-height: 62vh;
  overflow: auto;
  padding: 18px;
  border-radius: 18px;
  background: rgba(20, 18, 26, 0.96);
}

@media (max-width: 1080px) {
  .manga-shell {
    grid-template-columns: 1fr;
  }
  .studio-grid {
    grid-template-columns: 1fr;
  }
  .hero-tools,
  .manga-hero,
  .card-head {
    flex-direction: column;
    align-items: stretch;
  }
  .model-select {
    width: 100%;
  }
}
</style>
