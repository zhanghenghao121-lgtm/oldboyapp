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
          <div class="style-picker">
            <span class="style-label">画面风格</span>
            <div class="style-options">
              <button
                v-for="option in styleOptions"
                :key="option"
                type="button"
                class="style-option"
                :class="{ active: selectedStyle === option }"
                @click="selectStyle(option)"
              >
                {{ option }}
              </button>
            </div>
            <p class="style-tip">生成与复制时会自动拼接：{{ selectedStyle }} + 分镜提示词 + {{ selectedStyle }}</p>
          </div>
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
                <div class="prompt-card-actions">
                  <el-button plain size="small" :loading="item.preparing" @click="prepareOneSection(item)">重新优化</el-button>
                  <el-button plain size="small" :loading="item.generating" @click="generateOneImage(item)">
                    {{ item.imageUrl ? '重新生成' : '生成' }}
                  </el-button>
                </div>
              </div>
              <p v-if="item.preparing" class="prep-tip">正在用 DeepSeek 优化这段分镜提示词并提取人物/场景/物品...</p>
              <el-input
                v-model="item.prompt"
                type="textarea"
                resize="none"
                :rows="8"
                class="prompt-editor"
                placeholder="这里显示优化后的首帧图片提示词，也可以继续手动微调。"
                @focus="activeSectionId = item.id"
              />
              <div class="entity-groups">
                <div class="entity-group">
                  <p class="entity-title">人物</p>
                  <div v-if="item.characters.length" class="entity-list">
                    <div v-for="entity in item.characters" :key="`character-${item.id}-${entity.name}`" class="entity-chip">
                      <div class="entity-meta">
                        <span>{{ entity.name }}</span>
                        <img v-if="entity.url" :src="entity.url" :alt="entity.name" class="entity-thumb" />
                      </div>
                      <input
                        :id="referenceInputId(item.id, 'characters', entity.name)"
                        type="file"
                        accept="image/*"
                        class="file-hidden"
                        @change="handleReferenceUpload($event, item, 'characters', entity)"
                      />
                      <el-button plain size="small" :loading="entity.uploading" @click="pickReferenceFile(item.id, 'characters', entity.name)">
                        {{ entity.url ? '重传参考图' : '上传参考图' }}
                      </el-button>
                    </div>
                  </div>
                  <p v-else class="entity-empty">未提取到明确人物</p>
                </div>

                <div class="entity-group">
                  <p class="entity-title">场景</p>
                  <div v-if="item.scenes.length" class="entity-list">
                    <div v-for="entity in item.scenes" :key="`scene-${item.id}-${entity.name}`" class="entity-chip">
                      <div class="entity-meta">
                        <span>{{ entity.name }}</span>
                        <img v-if="entity.url" :src="entity.url" :alt="entity.name" class="entity-thumb" />
                      </div>
                      <input
                        :id="referenceInputId(item.id, 'scenes', entity.name)"
                        type="file"
                        accept="image/*"
                        class="file-hidden"
                        @change="handleReferenceUpload($event, item, 'scenes', entity)"
                      />
                      <el-button plain size="small" :loading="entity.uploading" @click="pickReferenceFile(item.id, 'scenes', entity.name)">
                        {{ entity.url ? '重传参考图' : '上传参考图' }}
                      </el-button>
                    </div>
                  </div>
                  <p v-else class="entity-empty">未提取到明确场景</p>
                </div>

                <div class="entity-group">
                  <p class="entity-title">物品</p>
                  <div v-if="item.items.length" class="entity-list">
                    <div v-for="entity in item.items" :key="`item-${item.id}-${entity.name}`" class="entity-chip">
                      <div class="entity-meta">
                        <span>{{ entity.name }}</span>
                        <img v-if="entity.url" :src="entity.url" :alt="entity.name" class="entity-thumb" />
                      </div>
                      <input
                        :id="referenceInputId(item.id, 'items', entity.name)"
                        type="file"
                        accept="image/*"
                        class="file-hidden"
                        @change="handleReferenceUpload($event, item, 'items', entity)"
                      />
                      <el-button plain size="small" :loading="entity.uploading" @click="pickReferenceFile(item.id, 'items', entity.name)">
                        {{ entity.url ? '重传参考图' : '上传参考图' }}
                      </el-button>
                    </div>
                  </div>
                  <p v-else class="entity-empty">未提取到关键物品</p>
                </div>
              </div>
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
                  <el-button plain size="small" :disabled="!item.imageUrl" @click="copyStyledPrompt(item)">复制提示词</el-button>
                </div>
              </div>

              <p class="styled-prompt-preview">生图风格词：{{ selectedStyle }} / 实际生图提示词将自动拼接该风格。</p>

              <div v-if="item.imageUrl" class="image-frame">
                <img :src="item.imageUrl" :alt="item.title || `分镜${item.index}`" />
              </div>
              <div v-else class="image-empty">
                <p>这段分镜还没有出图。</p>
                <span>点击右上角“生成图片”，系统会用当前提示词出一张对应的分镜图。</span>
              </div>

              <div v-if="referenceGallery(item).length" class="reference-gallery">
                <div class="reference-gallery-head">
                  <span>参考图缩略图库</span>
                  <small>已关联 {{ referenceGallery(item).length }} 张参考图</small>
                </div>
                <div class="reference-gallery-list">
                  <div v-for="asset in referenceGallery(item)" :key="`${item.id}-${asset.category}-${asset.name}`" class="reference-card">
                    <img :src="asset.url" :alt="asset.name" class="reference-card-image" />
                    <div class="reference-card-meta">
                      <span class="reference-card-tag">{{ asset.category }}</span>
                      <strong>{{ asset.name }}</strong>
                    </div>
                  </div>
                </div>
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

import { prepareAiMangaStoryboardSections, generateAiMangaStoryboardImage } from '../api/aiManga'
import { uploadToCos } from '../api/storage'
import { getActiveStoryboardPayload, saveAiMangaDraft, setActiveStoryboardPayload } from '../utils/aiMangaDrafts'

const router = useRouter()
const sections = ref([])
const activeSectionId = ref(null)
const generatingAll = ref(false)
const imageModelName = 'doubao-seedream-5-0-260128'
const lastSavedSignature = ref('')
const styleOptions = ['二维动漫', '3D动漫', '写实真人']
const selectedStyle = ref(styleOptions[0])

const normalizeEntityGroup = (values) => {
  return (Array.isArray(values) ? values : [])
    .map((item) => {
      if (typeof item === 'string') return { name: item, url: '', fileName: '', uploading: false }
      return {
        name: String(item?.name || '').trim(),
        url: String(item?.url || '').trim(),
        fileName: String(item?.fileName || '').trim(),
        uploading: false,
      }
    })
    .filter((item) => item.name)
}

const hydrateSections = (rawSections, rawStoryboard = '') => {
  const normalized = Array.isArray(rawSections) ? rawSections : []
  if (normalized.length) {
    sections.value = normalized.map((item, idx) => ({
      id: item.id || idx + 1,
      index: item.index || idx + 1,
      title: item.title || `分镜${idx + 1}`,
      rawPrompt: item.rawPrompt || item.prompt || '',
      prompt: item.prompt || '',
      characters: normalizeEntityGroup(item.characters),
      scenes: normalizeEntityGroup(item.scenes),
      items: normalizeEntityGroup(item.items),
      imageUrl: item.imageUrl || '',
      preparing: false,
      preparedAt: item.preparedAt || 0,
      generating: false,
      error: '',
    }))
  } else if (String(rawStoryboard || '').trim()) {
    sections.value = [
      {
        id: 1,
        index: 1,
        title: '分镜1',
        rawPrompt: String(rawStoryboard || '').trim(),
        prompt: String(rawStoryboard || '').trim(),
        characters: [],
        scenes: [],
        items: [],
        imageUrl: '',
        preparing: false,
        preparedAt: 0,
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
    selectedStyle.value = styleOptions.includes(payload.style) ? payload.style : styleOptions[0]
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
    style: selectedStyle.value,
    updatedAt: Date.now(),
  })
}

const currentDraftPayload = computed(() => ({
  storyboard: sections.value.map((item) => String(item.prompt || '').trim()).filter(Boolean).join('\n\n'),
  sections: sections.value.map((item) => ({
    id: item.id,
    index: item.index,
    title: item.title,
    rawPrompt: item.rawPrompt,
    prompt: item.prompt,
    characters: item.characters,
    scenes: item.scenes,
    items: item.items,
    imageUrl: item.imageUrl || '',
    preparedAt: item.preparedAt || 0,
  })),
  style: selectedStyle.value,
  updatedAt: Date.now(),
}))

const currentDraftSignature = computed(() =>
  JSON.stringify(
    {
      style: selectedStyle.value,
      sections: currentDraftPayload.value.sections.map((item) => ({
        id: item.id,
        title: item.title,
        prompt: String(item.prompt || '').trim(),
        characters: (item.characters || []).map((entity) => ({ name: entity.name, url: entity.url || '' })),
        scenes: (item.scenes || []).map((entity) => ({ name: entity.name, url: entity.url || '' })),
        items: (item.items || []).map((entity) => ({ name: entity.name, url: entity.url || '' })),
        imageUrl: item.imageUrl || '',
      })),
    }
  )
)

const selectStyle = (style) => {
  selectedStyle.value = style
  persistPayload()
}

const buildStyledPrompt = (prompt) => {
  const basePrompt = String(prompt || '').trim()
  const style = String(selectedStyle.value || '').trim()
  if (!basePrompt) return ''
  if (!style) return basePrompt
  return `${style}，${basePrompt}，${style}`
}

const referenceInputId = (sectionId, category, name) =>
  `manga-ref-${sectionId}-${category}-${String(name || '').replace(/[^\w\u4e00-\u9fff-]+/g, '-')}`

const referenceGallery = (item) => {
  if (!item) return []
  return [
    ...(item.characters || []).map((entity) => ({ category: '人物', name: entity.name, url: entity.url || '' })),
    ...(item.scenes || []).map((entity) => ({ category: '场景', name: entity.name, url: entity.url || '' })),
    ...(item.items || []).map((entity) => ({ category: '物品', name: entity.name, url: entity.url || '' })),
  ].filter((asset) => asset.name && asset.url)
}

const pickReferenceFile = (sectionId, category, name) => {
  const el = document.getElementById(referenceInputId(sectionId, category, name))
  if (el) el.click()
}

const handleReferenceUpload = async (event, section, category, entity) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !entity) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  entity.uploading = true
  try {
    const res = await uploadToCos(file, 'ai-manga-reference', { timeout: 90 * 1000 })
    entity.url = res?.data?.url || res?.url || ''
    entity.fileName = file.name
    persistPayload()
    ElMessage.success(`${entity.name} 参考图已上传`)
  } catch (e) {
    ElMessage.error(String(e || '参考图上传失败'))
  } finally {
    entity.uploading = false
  }
}

const mergePreparedSection = (target, prepared) => {
  const mergeEntities = (existing, next) => {
    const existingMap = new Map((existing || []).map((item) => [item.name, item]))
    return normalizeEntityGroup(next).map((item) => {
      const old = existingMap.get(item.name)
      return old ? { ...item, url: old.url || '', fileName: old.fileName || '', uploading: false } : item
    })
  }
  target.rawPrompt = prepared.raw_prompt || target.rawPrompt
  target.prompt = prepared.prompt || target.prompt
  target.characters = mergeEntities(target.characters, prepared.characters)
  target.scenes = mergeEntities(target.scenes, prepared.scenes)
  target.items = mergeEntities(target.items, prepared.items)
  target.preparedAt = Date.now()
}

const prepareSections = async (sectionIds = []) => {
  const targets = sectionIds.length ? sections.value.filter((item) => sectionIds.includes(item.id)) : sections.value
  const requestSections = targets
    .map((item) => ({
      id: item.id,
      index: item.index,
      title: item.title,
      prompt: String(item.rawPrompt || item.prompt || '').trim(),
    }))
    .filter((item) => item.prompt)
  if (!requestSections.length) return

  targets.forEach((item) => {
    item.preparing = true
    item.error = ''
  })
  try {
    const res = await prepareAiMangaStoryboardSections({ sections: requestSections })
    const preparedSections = res.data.sections || []
    for (const prepared of preparedSections) {
      const target = sections.value.find((item) => item.id === prepared.id)
      if (target) mergePreparedSection(target, prepared)
    }
    persistPayload()
  } catch (e) {
    ElMessage.error(String(e || '分镜提示词优化失败'))
  } finally {
    targets.forEach((item) => {
      item.preparing = false
    })
  }
}

const prepareOneSection = async (item) => {
  if (!item || item.preparing) return
  await prepareSections([item.id])
}

const copyPrompt = async (text) => {
  try {
    await navigator.clipboard.writeText(String(text || ''))
    ElMessage.success('提示词已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const copyStyledPrompt = async (item) => {
  await copyPrompt(buildStyledPrompt(item?.prompt || ''))
}

const generateOneImage = async (item) => {
  if (!item || item.generating) return
  const prompt = buildStyledPrompt(item.prompt)
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
      reference_assets: [
        ...(item.characters || []).map((entity) => ({ category: '人物', label: entity.name, url: entity.url || '' })),
        ...(item.scenes || []).map((entity) => ({ category: '场景', label: entity.name, url: entity.url || '' })),
        ...(item.items || []).map((entity) => ({ category: '物品', label: entity.name, url: entity.url || '' })),
      ],
    })
    item.imageUrl = res.data.image_url || ''
    item.prompt = res.data.prompt || item.prompt
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
    await prepareSections()
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

onMounted(async () => {
  const needPrepareIds = sections.value.filter((item) => !item.preparedAt).map((item) => item.id)
  if (needPrepareIds.length) {
    await prepareSections(needPrepareIds)
  }
})

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
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.style-picker {
  min-width: 320px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(255, 220, 184, 0.12);
  background: rgba(255, 255, 255, 0.03);
}
.style-label {
  display: inline-flex;
  margin-bottom: 10px;
  color: #ffcb87;
  font-size: 12px;
  letter-spacing: 0.1em;
}
.style-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.style-option {
  border: 1px solid rgba(255, 212, 154, 0.16);
  border-radius: 999px;
  padding: 8px 12px;
  color: #f3e7d8;
  background: rgba(255, 255, 255, 0.03);
}
.style-option.active {
  color: #1c130d;
  border-color: transparent;
  background: linear-gradient(135deg, #ffd6a6, #ffb97c);
}
.style-tip {
  margin: 10px 0 0;
  color: #cdbba8;
  font-size: 12px;
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
.prompt-card-actions {
  display: inline-flex;
  gap: 10px;
  flex-wrap: wrap;
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
.prep-tip {
  margin: 0 0 12px;
  color: #ffcb87;
  font-size: 12px;
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
.entity-groups {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}
.entity-group {
  padding: 14px;
  border-radius: 16px;
  border: 1px solid rgba(255, 220, 184, 0.1);
  background: rgba(255, 255, 255, 0.02);
}
.entity-title {
  margin: 0 0 10px;
  color: #ffe3bc;
  font-size: 13px;
  letter-spacing: 0.06em;
}
.entity-list {
  display: grid;
  gap: 10px;
}
.entity-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(13, 14, 20, 0.56);
  border: 1px solid rgba(255, 220, 184, 0.08);
}
.entity-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  color: #f6efe7;
}
.entity-meta span {
  word-break: break-all;
}
.entity-thumb {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  object-fit: cover;
  border: 1px solid rgba(255, 220, 184, 0.12);
}
.entity-empty {
  margin: 0;
  color: #b8aba0;
  font-size: 13px;
}
.file-hidden {
  display: none;
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
.styled-prompt-preview {
  margin: 0 0 12px;
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
.reference-gallery {
  margin-top: 14px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(255, 220, 184, 0.1);
  background: rgba(255, 248, 238, 0.03);
}
.reference-gallery-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: #ffe6c7;
}
.reference-gallery-head small {
  color: #cdbba8;
}
.reference-gallery-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
  gap: 10px;
}
.reference-card {
  overflow: hidden;
  border-radius: 14px;
  border: 1px solid rgba(255, 220, 184, 0.12);
  background: rgba(12, 13, 20, 0.66);
}
.reference-card-image {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  object-fit: cover;
}
.reference-card-meta {
  display: grid;
  gap: 4px;
  padding: 10px;
  color: #f7f2ea;
}
.reference-card-meta strong {
  font-size: 13px;
  word-break: break-word;
}
.reference-card-tag {
  display: inline-flex;
  width: fit-content;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  color: #1c130d;
  background: linear-gradient(135deg, #ffd6a6, #ffb97c);
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
  .entity-chip,
  .prompt-card-head,
  .image-card-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
