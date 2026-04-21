<template>
  <div class="boards-shell">
    <header class="boards-topbar">
      <div class="boards-brand">
        <span class="brand-pill">Storyboard Frames</span>
        <div>
          <h2>分镜图生成台</h2>
          <p>左边改分镜词，右边一键出图。每条分镜词对应一张分镜图。</p>
        </div>
      </div>
      <nav class="boards-nav">
        <button class="board-nav-btn" type="button" @click="$router.push('/ai-manga')">AI漫剧创作</button>
        <button class="board-nav-btn" type="button" @click="$router.push('/ai-customer')">AI章鱼助手</button>
      </nav>
    </header>

    <main class="boards-main">
      <section class="boards-hero">
        <div>
          <p class="hero-kicker">SEEDREAM STORY FRAMES</p>
          <h1>把分镜稿直接推进到画面阶段</h1>
          <p class="hero-sub">固定使用 `doubao-seedream-5-0-260128`。你可以先改每段提示词，再单独生成对应分镜图。</p>
        </div>
        <div class="hero-actions">
          <el-button class="ghost-btn" @click="$router.push('/ai-manga')">返回分镜稿</el-button>
          <el-button class="main-btn" type="primary" :disabled="!sections.length" :loading="generatingAll" @click="generateAllImages">
            批量生成全部
          </el-button>
        </div>
      </section>

      <section v-if="sections.length" class="boards-grid">
        <article class="panel-card prompt-panel">
          <div class="panel-head">
            <div>
              <p class="panel-kicker">SHOT PROMPTS</p>
              <h3>分镜提示词</h3>
            </div>
            <span class="count-badge">{{ sections.length }} 段</span>
          </div>

          <div class="prompt-list">
            <div v-for="item in sections" :key="item.id" class="prompt-card" :class="{ active: activeSectionId === item.id }">
              <div class="prompt-card-head">
                <button class="shot-anchor" type="button" @click="activeSectionId = item.id">
                  {{ item.title || `分镜${item.index}` }}
                </button>
                <el-button plain size="small" :loading="item.generating" @click="generateOneImage(item)">
                  {{ item.imageUrl ? '重新生成' : '生成' }}
                </el-button>
              </div>
              <el-input
                v-model="item.prompt"
                type="textarea"
                resize="none"
                :rows="8"
                class="prompt-editor"
                placeholder="可继续微调这一段分镜提示词"
                @focus="activeSectionId = item.id"
              />
            </div>
          </div>
        </article>

        <article class="panel-card image-panel">
          <div class="panel-head">
            <div>
              <p class="panel-kicker">SHOT FRAMES</p>
              <h3>分镜图输出</h3>
            </div>
            <span class="model-chip">{{ imageModelName }}</span>
          </div>

          <div class="image-list">
            <div v-for="item in sections" :key="`image-${item.id}`" class="image-card" :class="{ active: activeSectionId === item.id }">
              <div class="image-card-head">
                <div>
                  <p class="image-title">{{ item.title || `分镜${item.index}` }}</p>
                  <p class="image-sub">{{ item.imageUrl ? '已生成，可继续微调后重出' : '尚未生成' }}</p>
                </div>
                <div class="image-actions">
                  <el-button plain size="small" :loading="item.generating" @click="generateOneImage(item)">
                    {{ item.imageUrl ? '重生成' : '生成图片' }}
                  </el-button>
                  <el-button plain size="small" :disabled="!item.imageUrl" @click="copyPrompt(item.prompt)">复制提示词</el-button>
                </div>
              </div>

              <div v-if="item.imageUrl" class="image-frame">
                <img :src="item.imageUrl" :alt="item.title || `分镜${item.index}`" />
              </div>
              <div v-else class="image-empty">
                <p>这段分镜还没有出图。</p>
                <span>点击右上角“生成图片”，系统会用当前提示词出一张对应的分镜图。</span>
              </div>

              <p v-if="item.error" class="image-error">{{ item.error }}</p>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="empty-wrap">
        <p>还没有可用的分镜稿。</p>
        <el-button class="main-btn" type="primary" @click="$router.push('/ai-manga')">先去生成分镜稿</el-button>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { generateAiMangaStoryboardImage } from '../api/aiManga'
import { getActiveStoryboardPayload, saveAiMangaDraft, setActiveStoryboardPayload } from '../utils/aiMangaDrafts'

const router = useRouter()
const sections = ref([])
const activeSectionId = ref(null)
const generatingAll = ref(false)
const imageModelName = 'doubao-seedream-5-0-260128'
const lastSavedSignature = ref('')

const hydrateSections = (rawSections, rawStoryboard = '') => {
  const normalized = Array.isArray(rawSections) ? rawSections : []
  if (normalized.length) {
    sections.value = normalized.map((item, idx) => ({
      id: item.id || idx + 1,
      index: item.index || idx + 1,
      title: item.title || `分镜${idx + 1}`,
      prompt: item.prompt || '',
      imageUrl: item.imageUrl || '',
      generating: false,
      error: '',
    }))
  } else if (String(rawStoryboard || '').trim()) {
    sections.value = [
      {
        id: 1,
        index: 1,
        title: '分镜1',
        prompt: String(rawStoryboard || '').trim(),
        imageUrl: '',
        generating: false,
        error: '',
      },
    ]
  } else {
    sections.value = []
  }
  activeSectionId.value = sections.value[0]?.id || null
}

const loadStoryboardPayload = () => {
  const payload = getActiveStoryboardPayload()
  if (!payload) {
    ElMessage.warning('请先在 AI漫剧创作页生成分镜稿')
    router.replace('/ai-manga')
    return
  }
  try {
    hydrateSections(payload.sections, payload.storyboard)
    lastSavedSignature.value = currentDraftSignature.value
  } catch {
    ElMessage.error('分镜稿缓存已损坏，请重新生成')
    router.replace('/ai-manga')
  }
}

const persistPayload = () => {
  setActiveStoryboardPayload({
      storyboard: sections.value.map((item) => item.prompt).join('\n\n'),
      sections: sections.value,
      updatedAt: Date.now(),
    })
}

const currentDraftPayload = computed(() => ({
  storyboard: sections.value.map((item) => String(item.prompt || '').trim()).filter(Boolean).join('\n\n'),
  sections: sections.value.map((item) => ({
    id: item.id,
    index: item.index,
    title: item.title,
    prompt: item.prompt,
    imageUrl: item.imageUrl || '',
  })),
  updatedAt: Date.now(),
}))

const currentDraftSignature = computed(() =>
  JSON.stringify(
    currentDraftPayload.value.sections.map((item) => ({
      id: item.id,
      title: item.title,
      prompt: String(item.prompt || '').trim(),
      imageUrl: item.imageUrl || '',
    }))
  )
)

const copyPrompt = async (text) => {
  try {
    await navigator.clipboard.writeText(String(text || ''))
    ElMessage.success('提示词已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const generateOneImage = async (item) => {
  if (!item || item.generating) return
  const prompt = String(item.prompt || '').trim()
  if (!prompt) {
    ElMessage.warning('请先填写这一段分镜提示词')
    return
  }
  item.generating = true
  item.error = ''
  activeSectionId.value = item.id
  try {
    const res = await generateAiMangaStoryboardImage({
      section_id: item.id,
      prompt,
    })
    item.imageUrl = res.data.image_url || ''
    persistPayload()
    ElMessage.success(`${item.title || '分镜'} 图片生成完成`)
  } catch (e) {
    item.error = String(e || '生成失败')
    ElMessage.error(item.error)
  } finally {
    item.generating = false
  }
}

const generateAllImages = async () => {
  if (!sections.value.length || generatingAll.value) return
  generatingAll.value = true
  try {
    for (const item of sections.value) {
      await generateOneImage(item)
    }
  } finally {
    generatingAll.value = false
  }
}

const defaultDraftName = () => {
  const head = sections.value.find((item) => String(item.prompt || '').trim())?.title || '分镜图草稿'
  const now = new Date()
  const stamp = `${now.getMonth() + 1}/${now.getDate()} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
  return `${head} ${stamp}`
}

const saveDraftFlow = async () => {
  const { value } = await ElMessageBox.prompt('请输入草稿名称，保存后可从 AI漫剧 的“草稿记录”再次打开。', '保存草稿', {
    confirmButtonText: '保存',
    cancelButtonText: '取消',
    inputValue: defaultDraftName(),
    inputPlaceholder: '例如：第1话 分镜图草稿',
  })
  const draft = saveAiMangaDraft({
    name: value,
    payload: currentDraftPayload.value,
  })
  lastSavedSignature.value = currentDraftSignature.value
  persistPayload()
  ElMessage.success(`草稿已保存：${draft.name}`)
}

const maybeSaveDraftBeforeLeave = async () => {
  if (!sections.value.length || currentDraftSignature.value === lastSavedSignature.value) return true
  try {
    await ElMessageBox.confirm('返回分镜稿前，是否保存当前分镜图草稿？', '保存草稿', {
      confirmButtonText: '保存并返回',
      cancelButtonText: '直接返回',
      distinguishCancelAndClose: true,
      type: 'warning',
    })
    await saveDraftFlow()
    return true
  } catch (e) {
    if (e === 'cancel') return true
    return false
  }
}

onMounted(loadStoryboardPayload)

onBeforeRouteLeave(async (to) => {
  if (to.path !== '/ai-manga') return true
  return await maybeSaveDraftBeforeLeave()
})
</script>

<style scoped>
.boards-shell {
  min-height: 100vh;
  background:
    radial-gradient(900px 400px at 0% -10%, rgba(255, 120, 74, 0.12), transparent 56%),
    radial-gradient(740px 360px at 100% 0%, rgba(83, 198, 255, 0.11), transparent 58%),
    linear-gradient(135deg, #110f18, #181420 45%, #0e1017);
  color: #f8f1e8;
}
.boards-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 28px;
  border-bottom: 1px solid rgba(255, 211, 163, 0.16);
  background:
    linear-gradient(180deg, rgba(32, 20, 26, 0.96), rgba(17, 16, 24, 0.98)),
    repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.02) 0, rgba(255, 255, 255, 0.02) 1px, transparent 1px, transparent 12px);
}
.boards-brand {
  display: flex;
  align-items: center;
  gap: 16px;
}
.brand-pill {
  display: inline-flex;
  padding: 6px 11px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.14em;
  color: #ffd7a5;
  background: rgba(255, 160, 72, 0.08);
  border: 1px solid rgba(255, 185, 114, 0.24);
}
.boards-brand h2 {
  margin: 0 0 6px;
  font-size: 30px;
  font-family: Georgia, 'Times New Roman', serif;
}
.boards-brand p {
  margin: 0;
  color: #cbbcad;
}
.boards-nav {
  display: inline-flex;
  gap: 10px;
  flex-wrap: wrap;
}
.board-nav-btn {
  min-width: 148px;
  padding: 12px 18px;
  border-radius: 14px;
  border: 1px solid rgba(255, 212, 154, 0.16);
  color: #f3e7d8;
  background: rgba(255, 255, 255, 0.03);
}
.boards-main {
  padding: 28px;
}
.boards-hero {
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
.boards-hero h1 {
  margin: 0;
  font-size: clamp(30px, 4vw, 48px);
  line-height: 1.04;
  font-family: Georgia, 'Times New Roman', serif;
}
.hero-sub {
  margin: 10px 0 0;
  color: #d2c6ba;
}
.hero-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ghost-btn {
  border-color: rgba(255, 205, 138, 0.24);
  color: #ffe2b7;
  background: rgba(255, 191, 102, 0.08);
}
.boards-grid {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 0.96fr 1.04fr;
  gap: 18px;
}
.panel-card {
  min-height: 680px;
  border-radius: 24px;
  border: 1px solid rgba(255, 223, 192, 0.12);
  background:
    linear-gradient(180deg, rgba(255, 247, 238, 0.05), rgba(255, 255, 255, 0.02)),
    radial-gradient(circle at top right, rgba(61, 211, 255, 0.06), transparent 26%);
  box-shadow: 0 18px 42px rgba(5, 6, 12, 0.24);
  padding: 22px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.panel-kicker {
  margin: 0 0 6px;
  color: #ffcb87;
  letter-spacing: 0.16em;
  font-size: 11px;
}
.panel-head h3 {
  margin: 0;
  font-size: 24px;
  font-family: Georgia, 'Times New Roman', serif;
}
.count-badge,
.model-chip {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  font-size: 12px;
  color: #1c130d;
  background: linear-gradient(135deg, #ffd6a6, #ffb97c);
}
.prompt-list,
.image-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: calc(100vh - 260px);
  overflow: auto;
  padding-right: 4px;
}
.prompt-card,
.image-card {
  border-radius: 18px;
  border: 1px solid rgba(255, 218, 176, 0.12);
  background: rgba(18, 17, 24, 0.68);
  padding: 16px;
}
.prompt-card.active,
.image-card.active {
  border-color: rgba(255, 182, 104, 0.42);
  box-shadow: 0 0 0 1px rgba(255, 178, 102, 0.14);
}
.prompt-card-head,
.image-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.shot-anchor {
  border: 0;
  padding: 0;
  background: transparent;
  color: #fff1dc;
  font-size: 18px;
  font-family: Georgia, 'Times New Roman', serif;
  cursor: pointer;
}
.prompt-editor :deep(.el-textarea__inner) {
  border-radius: 18px;
  min-height: 180px !important;
  background:
    linear-gradient(180deg, rgba(24, 23, 30, 0.96), rgba(18, 18, 24, 0.98)),
    repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.02) 0, rgba(255, 255, 255, 0.02) 1px, transparent 1px, transparent 26px);
  border: 1px solid rgba(255, 220, 184, 0.12);
  color: #f7f2ea;
}
.image-title {
  margin: 0 0 6px;
  color: #fff1dc;
  font-size: 18px;
  font-family: Georgia, 'Times New Roman', serif;
}
.image-sub {
  margin: 0;
  color: #cdbba8;
  font-size: 12px;
}
.image-actions {
  display: inline-flex;
  gap: 10px;
  flex-wrap: wrap;
}
.image-frame {
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(255, 220, 184, 0.12);
  background: rgba(10, 11, 18, 0.72);
}
.image-frame img {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  object-fit: cover;
}
.image-empty {
  min-height: 260px;
  border-radius: 18px;
  border: 1px dashed rgba(255, 218, 176, 0.16);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #d4c7b7;
  padding: 24px;
}
.image-empty p {
  margin: 0 0 10px;
  font-size: 20px;
  font-family: Georgia, 'Times New Roman', serif;
}
.image-error {
  margin: 12px 0 0;
  color: #ff958d;
  white-space: pre-wrap;
}
.empty-wrap {
  margin-top: 24px;
  min-height: 48vh;
  border-radius: 24px;
  border: 1px dashed rgba(255, 220, 184, 0.16);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #d4c7b7;
}

@media (max-width: 1080px) {
  .boards-topbar,
  .boards-hero {
    flex-direction: column;
    align-items: stretch;
  }
  .boards-grid {
    grid-template-columns: 1fr;
  }
}
</style>
