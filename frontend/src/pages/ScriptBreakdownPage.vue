<template>
  <div class="breakdown-shell">
    <header class="breakdown-topbar">
      <div class="brand">
        <span>SEEDANCE SCRIPT LAB</span>
        <h1>AI拆剧</h1>
      </div>
      <div class="top-actions">
        <el-button plain @click="$router.push('/storyboard')">返回故事板</el-button>
        <el-button plain @click="settingsDialogRef?.open()">设置</el-button>
      </div>
    </header>

    <main class="breakdown-workspace">
      <aside class="task-column">
        <section class="create-card">
          <div class="section-title">
            <div>
              <h2>新建拆剧任务</h2>
              <p>按场景拆大段，再拆成 Seedance 2.0 可用的 15 秒小段。</p>
            </div>
          </div>
          <el-input v-model="form.title" placeholder="任务名称" maxlength="100" />
          <el-input
            v-model="form.script_text"
            type="textarea"
            resize="none"
            :rows="10"
            placeholder="粘贴完整剧本，AI 会提取场景、角色、道具，并生成小段落分镜提示词。"
          />
          <div class="form-grid">
            <el-segmented v-model="form.selected_style" :options="styleOptions" />
            <el-select v-model="form.analysis_model" placeholder="拆解模型">
              <el-option v-for="model in analysisModels" :key="model.id" :label="model.label" :value="model.id" />
            </el-select>
          </div>
          <div class="asset-editor">
            <div class="asset-head">
              <strong>素材参考</strong>
              <span>{{ form.assets.length }} 个</span>
            </div>
            <div class="asset-inputs">
              <el-select v-model="assetDraft.asset_type">
                <el-option label="场景" value="scene" />
                <el-option label="角色" value="character" />
                <el-option label="道具" value="prop" />
              </el-select>
              <el-input v-model="assetDraft.name" placeholder="素材名称" maxlength="40" />
              <el-input v-model="assetDraft.alias" placeholder="剧本别名，可选" maxlength="40" />
            </div>
            <div class="asset-actions">
              <label class="upload-mini">
                <input type="file" accept="image/*" @change="uploadDraftAsset" />
                {{ uploadingAsset ? '上传中...' : assetDraft.file_url ? '替换图片' : '上传图片' }}
              </label>
              <el-button size="small" plain @click="addAsset">添加素材</el-button>
            </div>
            <div v-if="form.assets.length" class="asset-list">
              <div v-for="(asset, index) in form.assets" :key="`${asset.asset_type}-${asset.name}-${index}`" class="asset-row">
                <span>{{ assetTypeLabel(asset.asset_type) }}</span>
                <strong>{{ asset.name }}</strong>
                <small>{{ asset.alias || '未设置别名' }}</small>
                <button type="button" @click="form.assets.splice(index, 1)">×</button>
              </div>
            </div>
          </div>
          <el-button class="primary-action" type="primary" :loading="running" @click="createAndRun">
            开始AI拆剧
          </el-button>
        </section>

        <section class="history-card">
          <div class="section-title compact">
            <h2>历史任务</h2>
            <el-button text :loading="loadingProjects" @click="loadProjects">刷新</el-button>
          </div>
          <div v-if="!projects.length" class="empty-inline">还没有拆剧任务。</div>
          <button
            v-for="project in projects"
            :key="project.id"
            class="task-button"
            :class="{ active: selectedProject?.id === project.id }"
            type="button"
            @click="loadProject(project.id)"
          >
            <span>{{ project.title }}</span>
            <small>{{ styleLabel(project.selected_style) }} · {{ statusLabel(project.status) }}</small>
          </button>
        </section>
      </aside>

      <section class="detail-column">
        <div v-if="!selectedProject" class="blank-state">
          <h2>把剧本拆成可生成的视频小段</h2>
          <p>每个小段会生成可复制的分镜提示词，并附带开场站位图。</p>
        </div>

        <template v-else>
          <header class="project-head">
            <div>
              <span>{{ styleLabel(selectedProject.selected_style) }} · {{ statusLabel(selectedProject.status) }}</span>
              <h2>{{ selectedProject.title }}</h2>
              <p v-if="selectedProject.error_message">{{ selectedProject.error_message }}</p>
              <p v-else>共 {{ selectedProject.scene_blocks?.length || 0 }} 个场景，{{ segmentCount }} 个小段落。</p>
            </div>
            <div class="project-actions">
              <el-button plain :loading="running" @click="rerunProject">重新拆解</el-button>
              <el-button plain type="danger" @click="removeProject(selectedProject)">删除</el-button>
            </div>
          </header>

          <div v-if="selectedProject.status === 'processing'" class="processing-card" v-loading="true">
            AI 正在执行：资产提取 → 场景拆分 → 15秒小段分镜 → 站位图 → 校验。
          </div>

          <div v-else class="detail-grid">
            <aside class="scene-list">
              <button
                v-for="scene in selectedProject.scene_blocks || []"
                :key="scene.id"
                type="button"
                class="scene-button"
                :class="{ active: activeSceneId === scene.id }"
                @click="activeSceneId = scene.id"
              >
                <strong>{{ scene.scene_number ? `${scene.scene_number} ${scene.scene_name}` : scene.scene_name }}</strong>
                <small>{{ scene.segments?.length || 0 }} 个小段</small>
              </button>
            </aside>

            <section v-if="activeScene" class="segment-list">
              <div class="scene-summary">
                <h3>{{ activeScene.scene_number ? `${activeScene.scene_number} ${activeScene.scene_name}` : activeScene.scene_name }}</h3>
                <p>{{ activeScene.scene_description || activeScene.original_text }}</p>
                <div class="meta-line">
                  <span>地点：{{ activeScene.location || activeScene.scene_name }}</span>
                  <span>时间：{{ activeScene.time_of_day || '未标注' }}</span>
                  <span>角色：{{ (activeScene.characters || []).join('、') || '未识别' }}</span>
                  <span>道具：{{ (activeScene.props || []).join('、') || '无' }}</span>
                </div>
              </div>

              <article v-for="segment in activeScene.segments || []" :key="segment.id" class="segment-card">
                <div class="segment-card-head">
                  <div>
                    <span>小段落 {{ segment.order }} · {{ viewLabel(segment.scene_view) }} · {{ segment.estimated_duration }}秒</span>
                    <h3>{{ segment.segment_title }}</h3>
                  </div>
                  <div class="card-actions">
                    <el-button size="small" type="primary" plain @click="copyText(segment.copy_text)">复制分镜提示词</el-button>
                    <el-button size="small" plain @click="copyText(segment.position_image_prompt)">复制站位图提示词</el-button>
                    <el-button size="small" plain :loading="regeneratingSegmentId === segment.id" @click="regenerateSegment(segment)">重新拆解本段</el-button>
                    <el-button size="small" plain :loading="regeneratingPositionId === segment.id" @click="regeneratePosition(segment)">重生成站位</el-button>
                  </div>
                </div>
                <div class="segment-body">
                  <pre>{{ segment.copy_text }}</pre>
                  <div class="position-panel">
                    <div class="position-head">
                      <strong>开场站位图</strong>
                      <span>{{ segment.position_layout?.scene || activeScene.scene_name }}</span>
                    </div>
                    <svg class="position-map" viewBox="0 0 100 100" role="img">
                      <defs>
                        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                          <path d="M0,0 L6,3 L0,6 Z" fill="#e2ad5c" />
                        </marker>
                      </defs>
                      <rect x="3" y="3" width="94" height="94" rx="5" />
                      <line x1="50" y1="94" x2="50" y2="72" marker-end="url(#arrow)" class="camera-line" />
                      <text x="52" y="92" class="camera-label">camera</text>
                      <g v-for="character in layoutCharacters(segment)" :key="`c-${segment.id}-${character.name}`">
                        <circle :cx="coord(character.x)" :cy="coord(character.y)" r="4.2" class="character-dot" />
                        <text :x="coord(character.x) + 5" :y="coord(character.y) + 1.5" class="map-label">{{ character.name }}</text>
                      </g>
                      <g v-for="prop in layoutProps(segment)" :key="`p-${segment.id}-${prop.name}`">
                        <rect :x="coord(prop.x) - 2.5" :y="coord(prop.y) - 2.5" width="5" height="5" rx="1" class="prop-dot" />
                        <text :x="coord(prop.x) + 4" :y="coord(prop.y) + 1.5" class="map-label prop-label">{{ prop.name }}</text>
                      </g>
                    </svg>
                    <p>{{ segment.position_image_prompt || '暂无站位图提示词' }}</p>
                  </div>
                </div>
              </article>
            </section>
          </div>
        </template>
      </section>
    </main>
    <UserSettingsDialog ref="settingsDialogRef" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createScriptBreakdownProject,
  deleteScriptBreakdownProject,
  getScriptBreakdownProject,
  getScriptBreakdownProjects,
  regenerateScriptPosition,
  regenerateScriptSegment,
  runScriptBreakdownProject,
} from '../api/scriptBreakdown'
import { getStoryboardConfig } from '../api/storyboard'
import { uploadToCos } from '../api/storage'
import UserSettingsDialog from '../components/UserSettingsDialog.vue'

const settingsDialogRef = ref(null)
const projects = ref([])
const selectedProject = ref(null)
const activeSceneId = ref('')
const loadingProjects = ref(false)
const running = ref(false)
const uploadingAsset = ref(false)
const regeneratingSegmentId = ref('')
const regeneratingPositionId = ref('')
const analysisModels = ref([])
const form = reactive({
  title: '',
  script_text: '',
  selected_style: 'live_action',
  max_segment_seconds: 15,
  analysis_model: 'deepseek-v4-pro',
  assets: [],
})
const assetDraft = reactive({ asset_type: 'scene', name: '', alias: '', file_url: '' })
const styleOptions = [
  { label: '真人写实', value: 'live_action' },
  { label: '3D动漫', value: 'anime_3d' },
]

const activeScene = computed(() => (selectedProject.value?.scene_blocks || []).find((scene) => scene.id === activeSceneId.value))
const segmentCount = computed(() => (selectedProject.value?.scene_blocks || []).reduce((total, scene) => total + (scene.segments?.length || 0), 0))

watch(selectedProject, (project) => {
  activeSceneId.value = project?.scene_blocks?.[0]?.id || ''
})

const statusLabel = (status) => ({ pending: '待拆解', processing: '拆解中', completed: '已完成', failed: '失败' }[status] || status)
const styleLabel = (style) => ({ live_action: '真人写实', anime_3d: '3D动漫' }[style] || style)
const assetTypeLabel = (type) => ({ scene: '场景', character: '角色', prop: '道具' }[type] || type)
const viewLabel = (view) => ({ front: '正面', reverse: '反打', side: '侧面', closeup: '近景', mixed: '混合' }[view] || view)
const coord = (value) => Math.min(Math.max(Number(value || 0), 0), 100)
const layoutCharacters = (segment) => Array.isArray(segment.position_layout?.characters) ? segment.position_layout.characters : []
const layoutProps = (segment) => Array.isArray(segment.position_layout?.props) ? segment.position_layout.props : []

const loadProjects = async () => {
  loadingProjects.value = true
  try {
    const res = await getScriptBreakdownProjects()
    projects.value = res.data.list || []
  } catch (error) {
    ElMessage.error(String(error || 'AI拆剧任务加载失败'))
  } finally {
    loadingProjects.value = false
  }
}

const loadProject = async (id) => {
  const res = await getScriptBreakdownProject(id)
  selectedProject.value = res.data
}

const loadConfig = async () => {
  try {
    const res = await getStoryboardConfig()
    analysisModels.value = res.data.analysis_models || []
    form.analysis_model = res.data.default_analysis_model || form.analysis_model
  } catch (error) {
    ElMessage.error(String(error || '模型配置加载失败'))
  }
}

const uploadDraftAsset = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !file.type.startsWith('image/')) return
  uploadingAsset.value = true
  try {
    const uploaded = await uploadToCos(file, 'images/script-breakdown/assets', { timeout: 120000 })
    assetDraft.file_url = uploaded.data.url
    if (!assetDraft.name) assetDraft.name = file.name.replace(/\.[^.]+$/, '')
    ElMessage.success(uploaded.data.compressed ? '素材已压缩并上传' : '素材已上传')
  } catch (error) {
    ElMessage.error(String(error || '素材上传失败'))
  } finally {
    uploadingAsset.value = false
  }
}

const addAsset = () => {
  if (!assetDraft.name.trim()) {
    ElMessage.warning('请输入素材名称')
    return
  }
  form.assets.push({ ...assetDraft, name: assetDraft.name.trim(), alias: assetDraft.alias.trim() })
  assetDraft.name = ''
  assetDraft.alias = ''
  assetDraft.file_url = ''
}

const createAndRun = async () => {
  if (running.value) return
  if (form.script_text.trim().length < 20) {
    ElMessage.warning('请输入至少 20 个字的剧本内容')
    return
  }
  running.value = true
  try {
    const created = await createScriptBreakdownProject({ ...form, title: form.title || '未命名拆剧任务' })
    selectedProject.value = created.data
    await loadProjects()
    const result = await runScriptBreakdownProject(created.data.id)
    selectedProject.value = result.data
    await loadProjects()
    ElMessage.success('AI拆剧完成')
  } catch (error) {
    if (selectedProject.value?.id) await loadProject(selectedProject.value.id).catch(() => {})
    ElMessage.error(String(error || 'AI拆剧失败'))
  } finally {
    running.value = false
  }
}

const rerunProject = async () => {
  if (!selectedProject.value || running.value) return
  running.value = true
  try {
    const result = await runScriptBreakdownProject(selectedProject.value.id)
    selectedProject.value = result.data
    await loadProjects()
    ElMessage.success('AI拆剧已重新完成')
  } catch (error) {
    await loadProject(selectedProject.value.id).catch(() => {})
    ElMessage.error(String(error || '重新拆解失败'))
  } finally {
    running.value = false
  }
}

const removeProject = async (project) => {
  try {
    await ElMessageBox.confirm(`删除拆剧任务“${project.title}”？`, '删除任务', { type: 'warning' })
    await deleteScriptBreakdownProject(project.id)
    if (selectedProject.value?.id === project.id) selectedProject.value = null
    await loadProjects()
    ElMessage.success('任务已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(String(error || '删除失败'))
  }
}

const replaceSegment = (updated) => {
  const scene = (selectedProject.value?.scene_blocks || []).find((item) => item.id === updated.scene_block_id)
  if (!scene) return
  const index = scene.segments.findIndex((segment) => segment.id === updated.id || segment.order === updated.order)
  if (index >= 0) scene.segments.splice(index, 1, updated)
}

const regenerateSegment = async (segment) => {
  regeneratingSegmentId.value = segment.id
  try {
    const res = await regenerateScriptSegment(segment.id)
    replaceSegment(res.data)
    ElMessage.success('小段落已重新拆解')
  } catch (error) {
    ElMessage.error(String(error || '小段落重拆失败'))
  } finally {
    regeneratingSegmentId.value = ''
  }
}

const regeneratePosition = async (segment) => {
  regeneratingPositionId.value = segment.id
  try {
    const res = await regenerateScriptPosition(segment.id)
    replaceSegment(res.data)
    ElMessage.success('站位图已重新生成')
  } catch (error) {
    ElMessage.error(String(error || '站位图重生成失败'))
  } finally {
    regeneratingPositionId.value = ''
  }
}

const copyText = async (text) => {
  if (!text) {
    ElMessage.warning('暂无可复制内容')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择文本复制')
  }
}

onMounted(async () => {
  await Promise.all([loadProjects(), loadConfig()])
})
</script>

<style scoped>
.breakdown-shell { min-height: 100vh; color: #162321; background: #f4f2ec; }
.breakdown-topbar { height: 72px; padding: 0 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #d8d5cc; background: #fbfaf6; }
.brand { display: flex; align-items: baseline; gap: 14px; }
.brand span { font-size: 11px; font-weight: 800; color: #73766e; letter-spacing: .08em; }
.brand h1 { margin: 0; font-size: 27px; }
.top-actions { display: flex; gap: 10px; }
.breakdown-workspace { min-height: calc(100vh - 72px); display: grid; grid-template-columns: 390px 1fr; }
.task-column { padding: 22px 20px; border-right: 1px solid #d8d5cc; background: #fbfaf6; }
.create-card, .history-card, .project-head, .scene-summary, .segment-card, .processing-card { border: 1px solid #ddd9ce; border-radius: 10px; background: #fffdfa; }
.create-card, .history-card { padding: 16px; margin-bottom: 16px; }
.section-title { display: flex; justify-content: space-between; gap: 14px; margin-bottom: 14px; }
.section-title h2, .section-title h3, .project-head h2, .segment-card h3, .scene-summary h3 { margin: 0; }
.section-title p, .project-head p, .scene-summary p { margin: 5px 0 0; color: #68716d; line-height: 1.55; }
.section-title.compact { align-items: center; margin-bottom: 8px; }
.create-card :deep(.el-input), .create-card :deep(.el-textarea), .form-grid { margin-bottom: 10px; }
.form-grid, .asset-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-grid :deep(.el-segmented) { --el-segmented-item-selected-bg-color: #177264; --el-segmented-item-selected-color: #fff; }
.asset-editor { padding: 12px; margin: 4px 0 14px; border: 1px solid #e0dbcf; border-radius: 8px; background: #f8f6ef; }
.asset-head, .asset-actions, .project-actions, .card-actions, .meta-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.asset-head { margin-bottom: 10px; color: #177264; }
.asset-inputs { grid-template-columns: 92px 1fr 1fr; margin-bottom: 10px; }
.upload-mini { height: 28px; padding: 0 10px; display: inline-flex; align-items: center; border: 1px dashed #8db6ad; border-radius: 6px; color: #177264; background: #fff; cursor: pointer; font-size: 12px; font-weight: 700; }
.upload-mini input { display: none; }
.asset-list { display: grid; gap: 6px; margin-top: 10px; }
.asset-row { display: grid; grid-template-columns: 44px 1fr 1fr 22px; gap: 8px; align-items: center; padding: 7px; border-radius: 6px; background: #fff; font-size: 12px; }
.asset-row span { color: #177264; font-weight: 800; }
.asset-row small { color: #68716d; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-row button { border: 0; color: #a9443c; background: transparent; cursor: pointer; }
.primary-action { width: 100%; height: 42px; background: #177264; border-color: #177264; }
.empty-inline { padding: 14px; border-radius: 8px; background: #f0eee8; color: #68716d; }
.task-button, .scene-button { width: 100%; margin-top: 8px; padding: 11px 12px; display: flex; flex-direction: column; gap: 4px; border: 1px solid #ddd9ce; border-radius: 8px; background: #fff; text-align: left; cursor: pointer; }
.task-button small, .scene-button small, .project-head span, .segment-card-head span { color: #177264; font-size: 12px; font-weight: 700; }
.task-button.active, .scene-button.active { border-color: #177264; background: #e8f2ee; }
.detail-column { padding: 24px; overflow: hidden; }
.blank-state { height: calc(100vh - 130px); display: grid; place-content: center; max-width: 520px; margin: 0 auto; text-align: center; color: #68716d; }
.blank-state h2 { color: #162321; }
.project-head { padding: 18px; margin-bottom: 16px; display: flex; justify-content: space-between; gap: 20px; }
.processing-card { padding: 30px; color: #68716d; }
.detail-grid { display: grid; grid-template-columns: 230px 1fr; gap: 16px; }
.scene-list { min-width: 0; }
.segment-list { display: grid; gap: 14px; min-width: 0; }
.scene-summary { padding: 16px; }
.meta-line { justify-content: flex-start; color: #5e6763; font-size: 13px; }
.segment-card { padding: 0; overflow: hidden; }
.segment-card-head { padding: 14px 16px; display: flex; justify-content: space-between; gap: 14px; border-bottom: 1px solid #e4dfd4; background: #fbfaf6; }
.segment-body { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(320px, .95fr); gap: 14px; padding: 16px; }
.segment-body pre { margin: 0; min-height: 230px; padding: 14px; border-radius: 8px; background: #14201f; color: #edf6f2; white-space: pre-wrap; word-break: break-word; line-height: 1.75; font-family: inherit; font-size: 13px; }
.position-panel { padding: 12px; border: 1px solid #d9e2dd; border-radius: 8px; background: #f7fbf8; }
.position-head { display: flex; justify-content: space-between; color: #177264; margin-bottom: 10px; }
.position-map { width: 100%; aspect-ratio: 1.35; border-radius: 8px; background: #edf4ee; }
.position-map rect:first-of-type { fill: #f9f7ef; stroke: #b7c7bf; stroke-width: .7; }
.character-dot { fill: #177264; stroke: #fff; stroke-width: 1; }
.prop-dot { fill: #c67b36; stroke: #fff; stroke-width: .8; }
.map-label { fill: #1b2d29; font-size: 3.3px; font-weight: 700; }
.prop-label { fill: #8b4b20; }
.camera-line { stroke: #e2ad5c; stroke-width: 1.6; }
.camera-label { fill: #9a6b24; font-size: 3px; text-transform: uppercase; letter-spacing: .1em; }
.position-panel p { margin: 10px 0 0; color: #5e6763; font-size: 12px; line-height: 1.55; }
@media (max-width: 1080px) {
  .breakdown-workspace, .detail-grid, .segment-body { grid-template-columns: 1fr; }
  .task-column { border-right: 0; border-bottom: 1px solid #d8d5cc; }
}
</style>
