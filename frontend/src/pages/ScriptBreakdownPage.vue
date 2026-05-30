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
              <p>先让 AI 从剧本里提取场景、角色、道具；拆完后再上传对应图片。</p>
            </div>
          </div>
          <el-input v-model="form.title" placeholder="任务名称" maxlength="100" />
          <el-input
            v-model="form.script_text"
            type="textarea"
            resize="none"
            :rows="12"
            placeholder="粘贴完整剧本，AI 会先解析场景、角色、道具，再拆成 15 秒左右的小段落分镜提示词。"
          />
          <div class="form-grid">
            <el-segmented v-model="form.selected_style" :options="styleOptions" />
            <el-select v-model="form.analysis_model" placeholder="拆解模型">
              <el-option v-for="model in analysisModels" :key="model.id" :label="model.label" :value="model.id" />
            </el-select>
          </div>
          <div class="flow-note">
            <strong>流程</strong>
            <span>开始AI拆剧 → AI解析素材 → 上传对应图片 → 用 @素材 描述站位 → 选择生图模型生成站位图</span>
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
          <p>拆剧完成后，这里会出现 AI 解析出的素材清单和每个 15 秒小段的站位图生成器。</p>
        </div>

        <template v-else>
          <header class="project-head">
            <div>
              <span>{{ styleLabel(selectedProject.selected_style) }} · {{ statusLabel(selectedProject.status) }}</span>
              <h2>{{ selectedProject.title }}</h2>
              <p v-if="selectedProject.error_message">{{ selectedProject.error_message }}</p>
              <p v-else>共 {{ selectedProject.scene_blocks?.length || 0 }} 个场景，{{ segmentCount }} 个小段落，{{ uploadedAssetCount }} / {{ allAssets.length }} 个素材已上传。</p>
            </div>
            <div class="project-actions">
              <el-button plain :loading="running" @click="rerunProject">重新拆解</el-button>
              <el-button plain type="danger" @click="removeProject(selectedProject)">删除</el-button>
            </div>
          </header>

          <div v-if="selectedProject.status === 'processing'" class="processing-card" v-loading="true">
            AI 正在执行：资产提取 → 场景拆分 → 15秒小段分镜 → 结果校验。
          </div>

          <template v-else>
            <section class="parsed-assets-panel">
              <div class="panel-title">
                <div>
                  <h2>解析素材</h2>
                  <p>AI 已从剧本中提取素材。给对应的场景、角色、道具上传图片后，可在站位描述里用 @素材名 引用。</p>
                </div>
                <span>{{ uploadedAssetCount }} / {{ allAssets.length }} 已上传</span>
              </div>
              <div v-if="!allAssets.length" class="empty-inline">暂无解析素材。可以重新拆解或检查剧本文本。</div>
              <div v-else class="asset-columns">
                <div v-for="group in assetGroups" :key="group.type" class="asset-group">
                  <h3>{{ group.label }}</h3>
                  <article
                    v-for="asset in assetsByType(group.type)"
                    :key="asset.id"
                    class="parsed-asset-card"
                    :class="{ uploaded: asset.file_url }"
                  >
                    <div class="asset-thumb">
                      <img v-if="asset.file_url" :src="asset.file_url" :alt="asset.name" />
                      <span v-else>{{ group.short }}</span>
                    </div>
                    <div class="asset-copy">
                      <strong>@{{ asset.name }}</strong>
                      <small>{{ asset.alias || asset.ai_description || '等待上传对应图片' }}</small>
                    </div>
                    <label class="upload-mini" :class="{ busy: uploadingAssetId === asset.id }">
                      <input type="file" accept="image/*" :disabled="uploadingAssetId === asset.id" @change="uploadParsedAsset($event, asset)" />
                      {{ uploadingAssetId === asset.id ? '上传中...' : asset.file_url ? '替换图片' : '上传图片' }}
                    </label>
                    <button class="asset-delete" type="button" @click="removeAsset(asset)">删除</button>
                  </article>
                  <div v-if="!assetsByType(group.type).length" class="asset-empty">未识别到{{ group.label }}</div>
                </div>
              </div>
            </section>

            <div class="detail-grid">
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
                      <el-button size="small" plain :loading="regeneratingSegmentId === segment.id" @click="regenerateSegment(segment)">重新拆解本段</el-button>
                    </div>
                  </div>
                  <div class="segment-body">
                    <pre>{{ segment.copy_text }}</pre>
                    <div class="position-panel">
                      <div class="position-head">
                        <strong>站位图生成</strong>
                        <span>{{ segment.position_image_url ? '已生成' : segment.position_generation_task_id ? '任务进行中' : '待描述' }}</span>
                      </div>
                      <p class="position-tip">用 @ 引用已上传素材描述开场站位，例如：@{{ sampleAssetName }} 站在画面左侧，面向 @{{ sampleSceneName }} 深处。</p>
                      <div v-if="uploadedAssets.length" class="asset-chips">
                        <button v-for="asset in uploadedAssets" :key="asset.id" type="button" @click="insertAssetMention(segment, asset)">
                          @{{ asset.name }}
                        </button>
                      </div>
                      <div v-else class="no-uploaded-assets">先在上方解析素材区上传场景、角色或道具图片，再在这里 @ 引用。</div>
                      <el-input
                        v-model="positionDrafts[segment.id]"
                        type="textarea"
                        :rows="5"
                        resize="none"
                        placeholder="描述这一小段开始时的角色站位、朝向、距离、道具位置和镜头方向。"
                      />
                      <div class="position-actions">
                        <el-select v-model="positionModels[segment.id]" placeholder="生图模型">
                          <el-option v-for="model in imageModels" :key="model.id" :label="model.label" :value="model.id" />
                        </el-select>
                        <el-button type="primary" :loading="generatingPositionId === segment.id" @click="generatePosition(segment)">生成站位图</el-button>
                        <el-button
                          v-if="segment.position_generation_task_id && !segment.position_image_url"
                          plain
                          :loading="refreshingPositionId === segment.id"
                          @click="refreshPosition(segment)"
                        >
                          刷新结果
                        </el-button>
                      </div>
                      <div v-if="segment.position_image_url" class="position-preview">
                        <img :src="segment.position_image_url" alt="站位图" />
                        <div>
                          <el-button size="small" plain @click="openImage(segment.position_image_url)">预览</el-button>
                          <el-button size="small" plain @click="downloadImage(segment.position_image_url)">下载</el-button>
                          <el-button size="small" plain @click="copyText(segment.position_image_prompt)">复制生图提示词</el-button>
                        </div>
                      </div>
                      <details v-if="segment.position_image_prompt" class="prompt-details">
                        <summary>查看本次生图提示词</summary>
                        <pre>{{ segment.position_image_prompt }}</pre>
                      </details>
                    </div>
                  </div>
                </article>
              </section>
            </div>
          </template>
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
  deleteScriptBreakdownAsset,
  deleteScriptBreakdownProject,
  generateScriptPositionImage,
  getScriptBreakdownProject,
  getScriptBreakdownProjects,
  refreshScriptPositionImage,
  regenerateScriptSegment,
  runScriptBreakdownProject,
  updateScriptBreakdownAsset,
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
const uploadingAssetId = ref('')
const regeneratingSegmentId = ref('')
const generatingPositionId = ref('')
const refreshingPositionId = ref('')
const analysisModels = ref([])
const imageModels = ref([])
const defaultImageModel = ref('gpt-image-2')
const positionDrafts = reactive({})
const positionModels = reactive({})

const form = reactive({
  title: '',
  script_text: '',
  selected_style: 'live_action',
  max_segment_seconds: 15,
  analysis_model: 'deepseek-v4-pro',
})

const styleOptions = [
  { label: '真人写实', value: 'live_action' },
  { label: '3D动漫', value: 'anime_3d' },
]
const assetGroups = [
  { type: 'scene', label: '场景', short: '景' },
  { type: 'character', label: '角色', short: '角' },
  { type: 'prop', label: '道具', short: '物' },
]

const activeScene = computed(() => (selectedProject.value?.scene_blocks || []).find((scene) => scene.id === activeSceneId.value))
const segmentCount = computed(() => (selectedProject.value?.scene_blocks || []).reduce((total, scene) => total + (scene.segments?.length || 0), 0))
const allAssets = computed(() => selectedProject.value?.assets || [])
const uploadedAssets = computed(() => allAssets.value.filter((asset) => asset.file_url))
const uploadedAssetCount = computed(() => uploadedAssets.value.length)
const assetsByType = (type) => allAssets.value.filter((asset) => asset.asset_type === type)
const sampleAssetName = computed(() => uploadedAssets.value[0]?.name || '角色名')
const sampleSceneName = computed(() => assetsByType('scene')[0]?.name || '场景名')

const syncPositionState = (project) => {
  for (const scene of project?.scene_blocks || []) {
    for (const segment of scene.segments || []) {
      positionDrafts[segment.id] = segment.position_description || positionDrafts[segment.id] || ''
      positionModels[segment.id] = segment.position_image_model || positionModels[segment.id] || defaultImageModel.value
    }
  }
}

watch(selectedProject, (project) => {
  activeSceneId.value = project?.scene_blocks?.[0]?.id || ''
  syncPositionState(project)
})

const statusLabel = (status) => ({ pending: '待拆解', processing: '拆解中', completed: '已完成', failed: '失败' }[status] || status)
const styleLabel = (style) => ({ live_action: '真人写实', anime_3d: '3D动漫' }[style] || style)
const viewLabel = (view) => ({ front: '正面', reverse: '反打', side: '侧面', closeup: '近景', mixed: '混合' }[view] || view)

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
    imageModels.value = res.data.image_models || []
    form.analysis_model = res.data.default_analysis_model || form.analysis_model
    defaultImageModel.value = res.data.default_image_model || defaultImageModel.value
  } catch (error) {
    ElMessage.error(String(error || '模型配置加载失败'))
  }
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
    ElMessage.success('AI拆剧完成，请上传解析素材图片')
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

const replaceAsset = (updated) => {
  const assets = selectedProject.value?.assets || []
  const index = assets.findIndex((asset) => asset.id === updated.id)
  if (index >= 0) assets.splice(index, 1, updated)
}

const removeAsset = async (asset) => {
  try {
    await ElMessageBox.confirm(`删除解析素材“${asset.name}”？已生成的小段文字不会被删除。`, '删除素材', { type: 'warning' })
    await deleteScriptBreakdownAsset(asset.id)
    const assets = selectedProject.value?.assets || []
    const index = assets.findIndex((item) => item.id === asset.id)
    if (index >= 0) assets.splice(index, 1)
    ElMessage.success('素材已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(String(error || '素材删除失败'))
  }
}

const uploadParsedAsset = async (event, asset) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !file.type.startsWith('image/')) return
  uploadingAssetId.value = asset.id
  try {
    const uploaded = await uploadToCos(file, 'images/script-breakdown/assets', { timeout: 120000 })
    const res = await updateScriptBreakdownAsset(asset.id, { file_url: uploaded.data.url })
    replaceAsset(res.data)
    ElMessage.success(uploaded.data.compressed ? '素材已压缩并上传' : '素材已上传')
  } catch (error) {
    ElMessage.error(String(error || '素材上传失败'))
  } finally {
    uploadingAssetId.value = ''
  }
}

const replaceSegment = (updated) => {
  const scene = (selectedProject.value?.scene_blocks || []).find((item) => item.id === updated.scene_block_id)
  if (!scene) return
  const index = scene.segments.findIndex((segment) => segment.id === updated.id || segment.order === updated.order)
  if (index >= 0) scene.segments.splice(index, 1, updated)
  positionDrafts[updated.id] = updated.position_description || positionDrafts[updated.id] || ''
  positionModels[updated.id] = updated.position_image_model || positionModels[updated.id] || defaultImageModel.value
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

const insertAssetMention = (segment, asset) => {
  const token = `@${asset.name} `
  const current = positionDrafts[segment.id] || ''
  if (current.includes(`@${asset.name}`)) return
  positionDrafts[segment.id] = `${current}${current && !current.endsWith(' ') && !current.endsWith('\n') ? ' ' : ''}${token}`
}

const generatePosition = async (segment) => {
  const description = String(positionDrafts[segment.id] || '').trim()
  if (description.length < 5) {
    ElMessage.warning('请先描述站位，可以点击素材标签快速插入 @素材名')
    return
  }
  generatingPositionId.value = segment.id
  try {
    const res = await generateScriptPositionImage(segment.id, {
      description,
      model: positionModels[segment.id] || defaultImageModel.value,
    })
    replaceSegment(res.data)
    ElMessage.success(res.data.position_image_url ? '站位图已生成' : '站位图任务已提交，请稍后刷新')
  } catch (error) {
    ElMessage.error(String(error || '站位图生成失败'))
  } finally {
    generatingPositionId.value = ''
  }
}

const refreshPosition = async (segment) => {
  refreshingPositionId.value = segment.id
  try {
    const res = await refreshScriptPositionImage(segment.id)
    replaceSegment(res.data)
    ElMessage.success(res.data.position_image_url ? '站位图已更新' : '站位图仍在生成中')
  } catch (error) {
    ElMessage.error(String(error || '站位图刷新失败'))
  } finally {
    refreshingPositionId.value = ''
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

const openImage = (url) => {
  window.open(url, '_blank', 'noopener,noreferrer')
}

const downloadImage = (url) => {
  const link = document.createElement('a')
  link.href = url
  link.download = 'position-image.png'
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  link.click()
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
.create-card, .history-card, .project-head, .scene-summary, .segment-card, .processing-card, .parsed-assets-panel { border: 1px solid #ddd9ce; border-radius: 10px; background: #fffdfa; }
.create-card, .history-card { padding: 16px; margin-bottom: 16px; }
.section-title, .panel-title { display: flex; justify-content: space-between; gap: 14px; margin-bottom: 14px; }
.section-title h2, .section-title h3, .panel-title h2, .asset-group h3, .project-head h2, .segment-card h3, .scene-summary h3 { margin: 0; }
.section-title p, .panel-title p, .project-head p, .scene-summary p { margin: 5px 0 0; color: #68716d; line-height: 1.55; }
.panel-title span { color: #177264; font-weight: 800; white-space: nowrap; }
.section-title.compact { align-items: center; margin-bottom: 8px; }
.create-card :deep(.el-input), .create-card :deep(.el-textarea), .form-grid { margin-bottom: 10px; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form-grid :deep(.el-segmented) { --el-segmented-item-selected-bg-color: #177264; --el-segmented-item-selected-color: #fff; }
.flow-note { margin: 4px 0 14px; padding: 12px; border: 1px dashed #9abbb3; border-radius: 8px; background: #f6faf7; color: #60706a; font-size: 13px; line-height: 1.55; }
.flow-note strong { display: block; color: #177264; margin-bottom: 2px; }
.primary-action { width: 100%; height: 42px; background: #177264; border-color: #177264; }
.empty-inline { padding: 14px; border-radius: 8px; background: #f0eee8; color: #68716d; }
.task-button, .scene-button { width: 100%; margin-top: 8px; padding: 11px 12px; display: flex; flex-direction: column; gap: 4px; border: 1px solid #ddd9ce; border-radius: 8px; background: #fff; text-align: left; cursor: pointer; }
.task-button small, .scene-button small, .project-head span, .segment-card-head span { color: #177264; font-size: 12px; font-weight: 700; }
.task-button.active, .scene-button.active { border-color: #177264; background: #e8f2ee; }
.detail-column { padding: 24px; overflow: hidden; }
.blank-state { height: calc(100vh - 130px); display: grid; place-content: center; max-width: 560px; margin: 0 auto; text-align: center; color: #68716d; }
.blank-state h2 { color: #162321; }
.project-head { padding: 18px; margin-bottom: 16px; display: flex; justify-content: space-between; gap: 20px; }
.project-actions, .card-actions, .meta-line { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.processing-card { padding: 30px; color: #68716d; }
.parsed-assets-panel { padding: 16px; margin-bottom: 16px; }
.asset-columns { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.asset-group { min-width: 0; }
.asset-group h3 { margin-bottom: 10px; color: #177264; font-size: 16px; }
.parsed-asset-card { display: grid; grid-template-columns: 54px minmax(0, 1fr) auto; gap: 10px; padding: 10px; margin-bottom: 10px; border: 1px solid #e2ded3; border-radius: 9px; background: #fbfaf6; }
.parsed-asset-card.uploaded { border-color: #a8cac1; background: #f5fbf8; }
.asset-thumb { width: 54px; height: 54px; grid-row: span 2; display: grid; place-items: center; border-radius: 8px; overflow: hidden; background: #e8ece7; color: #177264; font-weight: 900; }
.asset-thumb img { width: 100%; height: 100%; object-fit: cover; }
.asset-copy { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
.asset-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.asset-copy small { color: #68716d; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.upload-mini { width: fit-content; min-height: 28px; padding: 0 10px; display: inline-flex; align-items: center; border: 1px dashed #8db6ad; border-radius: 6px; color: #177264; background: #fff; cursor: pointer; font-size: 12px; font-weight: 700; }
.upload-mini.busy { opacity: .65; cursor: wait; }
.upload-mini input { display: none; }
.asset-delete { width: fit-content; min-height: 28px; padding: 0 10px; border: 1px solid #ead2cc; border-radius: 6px; background: #fff8f6; color: #a84737; font-size: 12px; font-weight: 700; cursor: pointer; }
.asset-delete:hover { border-color: #d79a8d; color: #8f3326; }
.asset-empty { padding: 12px; border-radius: 8px; background: #f0eee8; color: #8a8f89; font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: 230px 1fr; gap: 16px; }
.scene-list { min-width: 0; }
.segment-list { display: grid; gap: 14px; min-width: 0; }
.scene-summary { padding: 16px; }
.meta-line { justify-content: flex-start; color: #5e6763; font-size: 13px; }
.segment-card { padding: 0; overflow: hidden; }
.segment-card-head { padding: 14px 16px; display: flex; justify-content: space-between; gap: 14px; border-bottom: 1px solid #e4dfd4; background: #fbfaf6; }
.segment-body { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(340px, .95fr); gap: 14px; padding: 16px; }
.segment-body pre { margin: 0; min-height: 260px; padding: 14px; border-radius: 8px; background: #14201f; color: #edf6f2; white-space: pre-wrap; word-break: break-word; line-height: 1.75; font-family: inherit; font-size: 13px; }
.position-panel { padding: 12px; border: 1px solid #d9e2dd; border-radius: 8px; background: #f7fbf8; }
.position-head { display: flex; justify-content: space-between; color: #177264; margin-bottom: 8px; }
.position-head span { color: #7a817c; font-size: 12px; }
.position-tip, .no-uploaded-assets { margin: 0 0 10px; color: #5e6763; font-size: 12px; line-height: 1.55; }
.asset-chips { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 10px; }
.asset-chips button { border: 1px solid #a8cac1; border-radius: 999px; padding: 4px 9px; background: #fff; color: #177264; font-size: 12px; cursor: pointer; }
.position-actions { display: grid; grid-template-columns: minmax(140px, 1fr) auto auto; gap: 8px; align-items: center; margin-top: 10px; }
.position-actions :deep(.el-button--primary) { background: #177264; border-color: #177264; }
.position-preview { margin-top: 12px; border-radius: 9px; overflow: hidden; border: 1px solid #d7dfda; background: #fff; }
.position-preview img { width: 100%; display: block; aspect-ratio: 16 / 9; object-fit: contain; background: #111; }
.position-preview div { display: flex; gap: 8px; flex-wrap: wrap; padding: 10px; }
.prompt-details { margin-top: 10px; color: #5e6763; font-size: 12px; }
.prompt-details summary { cursor: pointer; color: #177264; font-weight: 800; }
.prompt-details pre { min-height: 0; margin-top: 8px; background: #eef5f1; color: #273430; font-size: 12px; }
@media (max-width: 1180px) {
  .asset-columns { grid-template-columns: 1fr; }
  .breakdown-workspace, .detail-grid, .segment-body { grid-template-columns: 1fr; }
  .task-column { border-right: 0; border-bottom: 1px solid #d8d5cc; }
}
</style>
