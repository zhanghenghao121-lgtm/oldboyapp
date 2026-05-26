<template>
  <div class="storyboard-shell">
    <header class="topbar">
      <div class="brand">
        <span>DIRECTOR DESK</span>
        <h1>AI故事板</h1>
      </div>
      <div class="top-actions">
        <el-button plain @click="$router.push('/ai-image')">AI生图</el-button>
        <el-button plain @click="settingsDialogRef?.open()">设置</el-button>
      </div>
    </header>

    <main class="workspace">
      <aside class="story-column">
        <section class="control-section">
          <h2>剧情拆解</h2>
          <el-input v-model="title" placeholder="项目标题" maxlength="100" />
          <el-input
            v-model="storyText"
            type="textarea"
            resize="none"
            :rows="12"
            placeholder="输入一段剧情，AI 将先按场景拆分，再递归拆成可由一张九宫格故事板表达的小段。"
          />
          <div class="select-grid">
            <el-select v-model="analysisModel" placeholder="拆解模型">
              <el-option v-for="model in analysisModels" :key="model.id" :label="model.label" :value="model.id" />
            </el-select>
            <el-select v-model="imageModel" placeholder="生图模型">
              <el-option v-for="model in imageModels" :key="model.id" :label="model.label" :value="model.model" />
            </el-select>
            <el-select v-model="stylePreset" placeholder="画面风格">
              <el-option v-for="style in styleOptions" :key="style" :label="style" :value="style" />
            </el-select>
            <el-select v-model="aspectRatio">
              <el-option label="横屏 16:9" value="16:9" />
              <el-option label="竖屏 9:16" value="9:16" />
              <el-option label="方形 1:1" value="1:1" />
            </el-select>
          </div>
          <el-button class="primary-action" type="primary" :loading="analyzing" @click="createAndAnalyze">
            拆解为故事板
          </el-button>
        </section>

        <section v-if="segments.length" class="segment-section">
          <div class="section-title">
            <h2>剧情小段</h2>
            <span>{{ leafSegments.length }} 段</span>
          </div>
          <div v-for="scene in segments" :key="scene.id" class="scene-block">
            <div class="scene-label">
              <strong>{{ scene.title }}</strong>
              <small>{{ scene.scene_name }} {{ scene.time_of_day }}</small>
            </div>
            <button
              v-for="leaf in leavesOf(scene)"
              :key="leaf.id"
              class="leaf-button"
              :class="{ active: selectedLeaf?.id === leaf.id }"
              type="button"
              @click="selectedLeaf = leaf"
            >
              <span>{{ leaf.title }}</span>
              <small>{{ leaf.grid_feasibility_score || '-' }} / 100</small>
            </button>
          </div>
        </section>
      </aside>

      <section class="production-column">
        <div v-if="!selectedLeaf" class="blank-state">
          <h2>从剧情开始制作九宫格</h2>
          <p>完成拆解后，选择一个剧情小段，为场景、人物与道具上传参考图片，再生成连续九格分镜。</p>
        </div>

        <template v-else>
          <header class="segment-head">
            <div>
              <span>{{ selectedLeaf.scene_name }} · {{ selectedLeaf.mood || '场景段落' }}</span>
              <h2>{{ selectedLeaf.title }}</h2>
              <p>{{ selectedLeaf.summary || selectedLeaf.original_text }}</p>
            </div>
            <strong class="score">{{ selectedLeaf.grid_feasibility_score }}<small>九格适配度</small></strong>
          </header>

          <section class="asset-panel">
            <div class="section-title">
              <div>
                <h3>素材参考</h3>
                <p>上传模型识别出的场景、人物和关键道具，九格镜头会保持参考一致。</p>
              </div>
              <span>{{ uploadedCount }} / {{ requiredAssets.length }}</span>
            </div>
            <div v-if="requiredAssets.length" class="asset-grid">
              <label v-for="asset in requiredAssets" :key="asset.key" class="asset-card" :class="{ uploaded: savedAsset(asset) }">
                <input type="file" accept="image/*" @change="(event) => uploadAsset(event, asset)" />
                <img v-if="savedAsset(asset)" :src="savedAsset(asset).image_url" :alt="asset.name" />
                <div v-else class="asset-placeholder">{{ asset.typeLabel }}</div>
                <strong>{{ asset.name }}</strong>
                <p>{{ asset.description }}</p>
                <span>{{ uploadingKey === asset.key ? '上传中...' : savedAsset(asset) ? '替换图片' : '上传参考图' }}</span>
              </label>
            </div>
            <div v-else class="empty-inline">该段落没有识别到必须上传的参考素材，可以直接生成分镜。</div>
            <el-button type="primary" :loading="generatingPanels" @click="createPanels">生成九格分镜提示词</el-button>
          </section>

          <section v-if="panels.length" class="panel-board">
            <div class="section-title board-title">
              <div>
                <h3>九格分镜</h3>
                <p>每格独立生成，最终由系统稳定排版合成为一张故事板图。</p>
              </div>
              <div class="board-actions">
                <el-button type="primary" :loading="generatingImages" @click="createImages">生成九张分镜图</el-button>
                <el-button plain :disabled="!imagesReady" :loading="composing" @click="composeGrid">合成九宫格</el-button>
              </div>
            </div>
            <div class="nine-grid">
              <article v-for="panel in panels" :key="panel.panel_no" class="shot-card">
                <div class="shot-image">
                  <img v-if="panel.image_url" :src="panel.image_url" :alt="`分镜 ${panel.panel_no}`" />
                  <span v-else>{{ panel.generation_task_id ? '生成中' : panel.shot_type || '待生成' }}</span>
                  <strong>{{ panel.panel_no }}</strong>
                </div>
                <h4>{{ panel.screen_description }}</h4>
                <p>{{ panel.image_prompt }}</p>
              </article>
            </div>
          </section>

          <section v-if="selectedLeaf.grid_image_url" class="grid-result">
            <div class="section-title">
              <h3>最终九宫格故事板</h3>
              <el-button type="primary" plain @click="openGrid">打开大图</el-button>
            </div>
            <img :src="selectedLeaf.grid_image_url" alt="九宫格故事板成图" />
          </section>
        </template>
      </section>
    </main>
    <UserSettingsDialog ref="settingsDialogRef" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  analyzeStoryboardProject,
  composeStoryboardGrid,
  createStoryboardProject,
  generateStoryboardImages,
  generateStoryboardPanels,
  getStoryboardConfig,
  refreshStoryboardImages,
  saveStoryboardAsset,
} from '../api/storyboard'
import { uploadToCos } from '../api/storage'
import UserSettingsDialog from '../components/UserSettingsDialog.vue'

const settingsDialogRef = ref(null)
const title = ref('')
const storyText = ref('')
const stylePreset = ref('电影写实')
const aspectRatio = ref('16:9')
const analysisModel = ref('deepseek-v4-pro')
const imageModel = ref('gpt-image-2')
const analysisModels = ref([])
const imageModels = ref([])
const styleOptions = ref(['电影写实', '3D动漫', '国风水墨', '赛博朋克'])
const project = ref(null)
const segments = ref([])
const selectedLeaf = ref(null)
const analyzing = ref(false)
const uploadingKey = ref('')
const generatingPanels = ref(false)
const generatingImages = ref(false)
const composing = ref(false)
let pollTimer = null

const collectLeaves = (segment) => {
  if (segment.is_leaf) return [segment]
  return (segment.children || []).flatMap(collectLeaves)
}
const leavesOf = (scene) => collectLeaves(scene)
const leafSegments = computed(() => segments.value.flatMap(collectLeaves))
const panels = computed(() => selectedLeaf.value?.panels || [])
const assetGroups = {
  characters: { type: 'character', label: '人物' },
  scenes: { type: 'scene', label: '场景' },
  props: { type: 'prop', label: '道具' },
  costumes: { type: 'costume', label: '服装' },
  style_refs: { type: 'style', label: '风格' },
}
const requiredAssets = computed(() =>
  Object.entries(assetGroups).flatMap(([key, config]) =>
    (selectedLeaf.value?.required_assets?.[key] || []).map((item) => ({
      ...item,
      key: `${config.type}:${item.name}`,
      asset_type: config.type,
      typeLabel: config.label,
    }))
  )
)
const savedAsset = (item) => (selectedLeaf.value?.assets || []).find((asset) => asset.asset_type === item.asset_type && asset.name === item.name)
const uploadedCount = computed(() => requiredAssets.value.filter(savedAsset).length)
const imagesReady = computed(() => panels.value.length === 9 && panels.value.every((panel) => panel.image_url))

watch(selectedLeaf, () => stopPolling())

const stopPolling = () => {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = null
}

const loadConfig = async () => {
  try {
    const res = await getStoryboardConfig()
    const data = res.data || {}
    analysisModels.value = data.analysis_models || []
    imageModels.value = data.image_models || []
    styleOptions.value = data.style_options || styleOptions.value
    analysisModel.value = data.default_analysis_model || analysisModel.value
    imageModel.value = data.default_image_model || imageModel.value
  } catch (error) {
    ElMessage.error(String(error || '故事板配置加载失败'))
  }
}

const createAndAnalyze = async () => {
  if (storyText.value.trim().length < 20) {
    ElMessage.warning('请输入至少 20 个字的剧情内容')
    return
  }
  analyzing.value = true
  stopPolling()
  try {
    const created = await createStoryboardProject({
      title: title.value,
      original_story: storyText.value,
      style_preset: stylePreset.value,
      aspect_ratio: aspectRatio.value,
      analysis_model: analysisModel.value,
      image_model: imageModel.value,
    })
    project.value = created.data
    const analyzed = await analyzeStoryboardProject(project.value.id)
    project.value = analyzed.data
    segments.value = analyzed.data.segments || []
    selectedLeaf.value = leafSegments.value[0] || null
    ElMessage.success('剧情已拆解为可制作的故事板小段')
  } catch (error) {
    ElMessage.error(String(error || '剧情拆解失败'))
  } finally {
    analyzing.value = false
  }
}

const uploadAsset = async (event, asset) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !file.type.startsWith('image/')) return
  uploadingKey.value = asset.key
  try {
    const uploaded = await uploadToCos(file, 'images/storyboards/assets', { timeout: 120000 })
    const saved = await saveStoryboardAsset(selectedLeaf.value.id, {
      asset_type: asset.asset_type,
      name: asset.name,
      description: asset.description || '',
      image_url: uploaded.data.url,
    })
    const assets = selectedLeaf.value.assets || []
    const index = assets.findIndex((item) => item.id === saved.data.id)
    if (index >= 0) assets.splice(index, 1, saved.data)
    else assets.push(saved.data)
    ElMessage.success(`${asset.name} 已上传`)
  } catch (error) {
    ElMessage.error(String(error || '素材上传失败'))
  } finally {
    uploadingKey.value = ''
  }
}

const createPanels = async () => {
  generatingPanels.value = true
  stopPolling()
  try {
    const res = await generateStoryboardPanels(selectedLeaf.value.id)
    selectedLeaf.value.panels = res.data.panels || []
    selectedLeaf.value.grid_image_url = ''
    ElMessage.success('九格分镜提示词已生成')
  } catch (error) {
    ElMessage.error(String(error || '分镜生成失败'))
  } finally {
    generatingPanels.value = false
  }
}

const pollImages = async () => {
  if (!selectedLeaf.value || imagesReady.value) {
    generatingImages.value = false
    return
  }
  try {
    const res = await refreshStoryboardImages(selectedLeaf.value.id)
    selectedLeaf.value.panels = res.data.panels || []
    if (imagesReady.value) {
      generatingImages.value = false
      ElMessage.success('九张分镜图已生成')
      return
    }
    pollTimer = window.setTimeout(pollImages, 4500)
  } catch (error) {
    generatingImages.value = false
    ElMessage.error(String(error || '生图任务查询失败'))
  }
}

const createImages = async () => {
  generatingImages.value = true
  stopPolling()
  try {
    const res = await generateStoryboardImages(selectedLeaf.value.id, imageModel.value)
    selectedLeaf.value.panels = res.data.panels || []
    if (imagesReady.value) {
      ElMessage.success('九张分镜图已生成')
      generatingImages.value = false
    } else {
      pollTimer = window.setTimeout(pollImages, 4000)
    }
  } catch (error) {
    generatingImages.value = false
    ElMessage.error(String(error || '分镜图片生成失败'))
  }
}

const composeGrid = async () => {
  composing.value = true
  try {
    const res = await composeStoryboardGrid(selectedLeaf.value.id)
    selectedLeaf.value.grid_image_url = res.data.grid_image_url
    ElMessage.success('九宫格故事板已合成')
  } catch (error) {
    ElMessage.error(String(error || '九宫格合成失败'))
  } finally {
    composing.value = false
  }
}

const openGrid = () => window.open(selectedLeaf.value.grid_image_url, '_blank', 'noopener,noreferrer')

onMounted(loadConfig)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.storyboard-shell { min-height: 100vh; color: #14201f; background: #f4f2ec; }
.topbar { height: 72px; padding: 0 30px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #d8d5cc; background: #fbfaf6; }
.brand { display: flex; align-items: baseline; gap: 14px; }
.brand span { font-size: 11px; font-weight: 700; color: #73766e; }
.brand h1 { margin: 0; font-size: 27px; font-weight: 700; letter-spacing: 0; color: #111a19; }
.top-actions { display: flex; gap: 10px; }
.workspace { min-height: calc(100vh - 72px); display: grid; grid-template-columns: 370px 1fr; }
.story-column { border-right: 1px solid #d8d5cc; background: #fbfaf6; padding: 24px 20px; }
.control-section h2, .segment-section h2 { margin: 0 0 16px; font-size: 18px; }
.control-section :deep(.el-input), .control-section :deep(.el-textarea) { margin-bottom: 12px; }
.control-section :deep(.el-input__wrapper), .control-section :deep(.el-textarea__inner), .select-grid :deep(.el-select__wrapper) { box-shadow: 0 0 0 1px #d6d3cb inset; background: #fff; }
.select-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 4px 0 18px; }
.primary-action { width: 100%; height: 44px; background: #177264; border-color: #177264; }
.segment-section { margin-top: 26px; border-top: 1px solid #dedbd2; padding-top: 22px; }
.section-title { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 18px; }
.section-title h2, .section-title h3 { margin: 0 0 5px; font-size: 18px; }
.section-title p { margin: 0; color: #68716d; font-size: 13px; }
.section-title > span { color: #177264; font-weight: 700; font-size: 13px; }
.scene-block { margin: 0 0 18px; }
.scene-label { display: flex; flex-direction: column; gap: 3px; margin-bottom: 8px; }
.scene-label strong { font-size: 14px; }
.scene-label small { color: #6d736e; }
.leaf-button { width: 100%; border: 1px solid #ddd9ce; background: #fff; border-radius: 6px; padding: 11px 12px; margin-bottom: 7px; display: flex; justify-content: space-between; gap: 8px; color: #303836; text-align: left; cursor: pointer; }
.leaf-button.active { color: #0d5f52; background: #e8f2ee; border-color: #5d9e92; }
.production-column { padding: 28px; overflow: hidden; }
.blank-state { height: calc(100vh - 140px); display: grid; place-content: center; text-align: center; max-width: 470px; margin: 0 auto; color: #67706c; }
.blank-state h2 { color: #162321; margin: 0 0 10px; }
.segment-head { display: flex; justify-content: space-between; gap: 30px; margin-bottom: 25px; }
.segment-head span { color: #177264; font-size: 13px; font-weight: 600; }
.segment-head h2 { margin: 7px 0 8px; font-size: 26px; }
.segment-head p { max-width: 740px; margin: 0; color: #5e6763; line-height: 1.55; }
.score { flex: none; min-width: 96px; height: 82px; border-left: 2px solid #177264; padding-left: 16px; color: #177264; font-size: 34px; display: flex; flex-direction: column; }
.score small { color: #66706b; font-size: 12px; font-weight: 500; }
.asset-panel, .panel-board, .grid-result { border-top: 1px solid #d8d5cc; padding: 22px 0; }
.asset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(178px, 1fr)); gap: 12px; margin-bottom: 18px; }
.asset-card { position: relative; min-height: 236px; padding: 9px; border: 1px dashed #bbb7ac; border-radius: 6px; background: #fff; cursor: pointer; display: flex; flex-direction: column; gap: 7px; }
.asset-card.uploaded { border-style: solid; border-color: #73a89e; }
.asset-card input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.asset-card img, .asset-placeholder { width: 100%; height: 98px; object-fit: cover; border-radius: 4px; }
.asset-placeholder { display: grid; place-items: center; background: #eef1ed; color: #65706a; font-weight: 600; }
.asset-card strong { font-size: 14px; }
.asset-card p { margin: 0; min-height: 35px; color: #66706b; font-size: 12px; line-height: 1.45; overflow: hidden; }
.asset-card span { color: #177264; font-size: 12px; font-weight: 600; }
.empty-inline { padding: 18px; background: #efede7; color: #646b68; margin-bottom: 18px; border-radius: 6px; }
.board-title { align-items: center; }
.board-actions { display: flex; gap: 10px; }
.nine-grid { display: grid; grid-template-columns: repeat(3, minmax(180px, 1fr)); gap: 12px; }
.shot-card { background: #fff; border: 1px solid #d8d5cc; border-radius: 6px; padding: 9px; min-width: 0; }
.shot-image { position: relative; aspect-ratio: 16 / 9; display: grid; place-items: center; background: #e7e4dc; color: #69706c; margin-bottom: 9px; overflow: hidden; }
.shot-image img { width: 100%; height: 100%; object-fit: cover; }
.shot-image strong { position: absolute; top: 7px; left: 7px; width: 26px; height: 26px; display: grid; place-items: center; background: #111a19; color: #fff; font-size: 13px; }
.shot-card h4 { height: 40px; margin: 0 0 7px; overflow: hidden; font-size: 13px; line-height: 1.45; }
.shot-card p { height: 52px; overflow: hidden; margin: 0; color: #65706b; font-size: 12px; line-height: 1.45; }
.grid-result img { display: block; width: min(100%, 1100px); border: 1px solid #d6d2c8; background: #111; }
@media (max-width: 980px) {
  .workspace { display: block; }
  .story-column { border-right: 0; border-bottom: 1px solid #d8d5cc; }
  .production-column { padding: 20px; }
  .nine-grid { grid-template-columns: 1fr; }
}
</style>
