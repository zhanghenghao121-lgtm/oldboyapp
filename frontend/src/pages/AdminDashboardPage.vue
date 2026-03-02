<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="side-head">
        <h2>管理后台</h2>
        <p v-if="adminUser">{{ adminUser.username }}</p>
      </div>

      <button class="side-btn" :class="{ active: activeModule === 'stats' }" @click="activeModule = 'stats'">信息统计</button>
      <button class="side-btn" :class="{ active: activeModule === 'page' }" @click="activeModule = 'page'">页面管理</button>
      <button class="side-btn" :class="{ active: activeModule === 'users' }" @click="activeModule = 'users'">用户信息</button>
      <button class="side-btn" :class="{ active: activeModule === 'script' }" @click="activeModule = 'script'">剧本优化</button>
      <button class="side-btn ai-side-btn" :class="{ active: aiMenuOpen }" @click="toggleAiMenu">
        <span>AI配置</span>
        <span class="submenu-arrow">{{ aiMenuOpen ? '▾' : '▸' }}</span>
      </button>
      <div v-if="aiMenuOpen" class="submenu-wrap">
        <button class="submenu-btn" :class="{ active: activeModule === 'ai_knowledge' }" @click="activeModule = 'ai_knowledge'">AI知识库</button>
        <button class="submenu-btn" :class="{ active: activeModule === 'ai_customer' }" @click="activeModule = 'ai_customer'">AI客服</button>
      </div>

      <button class="side-btn ai-side-btn" :class="{ active: humanMenuOpen || activeModule === 'human_service' }" @click="toggleHumanMenu">
        <span>人工处理</span>
        <span class="menu-right">
          <span v-if="aiUnreadCount > 0" class="unread-badge">{{ aiUnreadCount > 99 ? '99+' : aiUnreadCount }}</span>
          <span class="submenu-arrow">{{ humanMenuOpen ? '▾' : '▸' }}</span>
        </span>
      </button>
      <div v-if="humanMenuOpen" class="submenu-wrap">
        <button class="submenu-btn human-sub-btn" :class="{ active: activeModule === 'human_service' }" @click="activeModule = 'human_service'">
          <span>人工客服</span>
          <span v-if="aiUnreadCount > 0" class="unread-badge">{{ aiUnreadCount > 99 ? '99+' : aiUnreadCount }}</span>
        </button>
      </div>
    </aside>

    <main class="admin-main">
      <header class="main-head">
        <h3>{{ moduleTitle }}</h3>
        <el-button type="danger" plain @click="handleLogout">退出后台</el-button>
      </header>

      <section v-if="activeModule === 'stats'" class="panel-card">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="8">
            <el-card class="metric-card" shadow="never">
              <el-statistic title="注册用户总数" :value="total" />
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card class="metric-card" shadow="never">
              <el-statistic title="当前管理员" :value="adminUser ? 1 : 0" />
            </el-card>
          </el-col>
        </el-row>
      </section>

      <section v-if="activeModule === 'page'" class="panel-card">
        <div class="panel-tip">页面管理：仅保留用户默认头像上传管理（COS）</div>
        <div class="avatar-row">
          <div class="avatar-left">
            <p class="row-label">用户默认头像</p>
            <div class="avatar-thumb">
              <img
                v-if="defaultAvatarUrl"
                :src="thumbSrc(defaultAvatarUrl)"
                alt="default avatar"
                @error="defaultAvatarUrl = '/octopus-avatar.svg'"
              />
              <span v-else>待上传图片</span>
            </div>
          </div>
          <div class="avatar-right">
            <el-input v-model="defaultAvatarUrl" placeholder="请输入默认头像 URL，留空使用系统默认" />
            <input id="default-avatar-upload" type="file" accept="image/*" class="file-hidden" @change="handleDefaultAvatarUpload" />
            <div class="row-actions">
              <el-button class="main-btn" type="primary" @click="saveDefaultAvatar">保存</el-button>
              <el-button plain :loading="defaultAvatarUploading" @click="pickDefaultAvatarFile">上传图片</el-button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeModule === 'users'" class="panel-card">
        <div class="user-header">
          <span class="fw-semibold">注册用户信息</span>
          <div class="user-filter">
            <el-input v-model="keyword" clearable placeholder="用户名/邮箱" @keyup.enter="loadUsers(1)" />
            <el-button @click="loadUsers(1)">搜索</el-button>
          </div>
        </div>
        <el-table :data="users" style="width: 100%" stripe>
          <el-table-column prop="username" label="用户名" min-width="120" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="points" label="积分" width="110">
            <template #default="scope">
              {{ Number(scope.row.points || 0).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="90">
            <template #default="scope">
              <el-tag :type="scope.row.is_active ? 'success' : 'danger'">{{ scope.row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="date_joined" label="注册时间" min-width="170" />
          <el-table-column label="操作" width="100">
            <template #default="scope">
              <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="pager-wrap">
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            @current-change="loadUsers"
          />
        </div>
      </section>

      <section v-if="activeModule === 'script'" class="panel-card">
        <h4 class="placeholder-title">剧本优化默认提示词</h4>
        <p class="placeholder-sub">修改后会同步到网站剧本优化页面输入框默认内容。</p>
        <el-form label-width="130px" class="mt-3">
          <el-form-item label="剧本分镜提示词">
            <el-input v-model="scriptStoryboardPrompt" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="段落分镜提示词">
            <el-input v-model="scriptParagraphPrompt" type="textarea" :rows="4" />
          </el-form-item>
        </el-form>
        <el-button type="primary" class="main-btn" :loading="savingPrompts" @click="saveScriptPrompts">保存设置</el-button>
      </section>

      <section v-if="activeModule === 'ai_customer'" class="panel-card">
        <h4 class="placeholder-title">AI客服配置</h4>
        <el-form label-width="130px" class="mt-3">
          <el-form-item label="启用AI客服">
            <el-switch v-model="aiCsForm.enabled" />
          </el-form-item>
          <el-form-item label="回复语气">
            <el-input v-model="aiCsForm.tone_style" type="textarea" :rows="3" placeholder="例如：温和、专业、简洁" />
          </el-form-item>
          <el-form-item label="系统提示词">
            <el-input v-model="aiCsForm.base_prompt" type="textarea" :rows="5" />
          </el-form-item>
          <el-form-item label="无法回答文案">
            <el-input v-model="aiCsForm.no_answer_text" />
          </el-form-item>
          <el-form-item label="飞书机器人配置页">
            <el-input v-model="aiCsForm.feishu_bot_config_url" placeholder="https://open.feishu.cn/..." />
          </el-form-item>
          <el-form-item label="飞书告警Webhook">
            <el-input v-model="aiCsForm.feishu_webhook_url" placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..." />
          </el-form-item>
        </el-form>
        <div class="row-actions ai-actions">
          <el-button class="main-btn" type="primary" :loading="savingAiSettings" @click="saveAiCsSettings">保存AI客服配置</el-button>
          <el-button plain @click="openFeishuIntegration">集成飞书</el-button>
        </div>
      </section>

      <section v-if="activeModule === 'ai_knowledge'" class="panel-card">
        <h4 class="placeholder-title">AI知识库上传向量化</h4>
        <p class="placeholder-sub">支持 json / csv / xlsx / txt / md，上传后自动向量化存入 Qdrant。</p>
        <div class="kb-upload-row">
          <el-input v-model="knowledgeTitle" placeholder="知识库标题（可选）" />
          <input ref="knowledgeInputRef" type="file" class="file-hidden" accept=".json,.csv,.xlsx,.txt,.md" @change="handleKnowledgeFile" />
          <el-button :loading="uploadingKnowledge" @click="pickKnowledgeFile">上传并向量化</el-button>
        </div>

        <el-table :data="knowledgeDocs" style="width: 100%; margin-top: 12px" stripe>
          <el-table-column prop="title" label="标题" min-width="180" />
          <el-table-column prop="source_name" label="来源文件" min-width="180" />
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="chunk_count" label="分块数" width="90" />
          <el-table-column prop="error_message" label="失败原因" min-width="220" />
        </el-table>
      </section>

      <section v-if="activeModule === 'human_service'" class="panel-card">
        <h4 class="placeholder-title">AI客服转人工工单</h4>
        <div class="row-actions">
          <el-button plain class="neon-btn" @click="loadAiCsTickets">刷新工单</el-button>
          <el-button class="main-btn" :disabled="!selectedTicketIds.length" :loading="syncingKnowledge" @click="batchSyncKnowledge">
            批量加入知识库
          </el-button>
        </div>
        <el-table :data="aiTickets" style="width: 100%; margin-top: 12px" stripe @selection-change="onTicketSelectionChange">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="username" label="用户" width="100" />
          <el-table-column prop="question" label="用户问题" min-width="200" />
          <el-table-column prop="admin_reply" label="人工回复" min-width="180" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag v-if="scope.row.status === 'unread'" type="danger">未读</el-tag>
              <el-tag v-else-if="scope.row.status === 'read'" type="success">已读</el-tag>
              <el-tag v-else type="info">忽略</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="知识库" width="94">
            <template #default="scope">
              <el-tag v-if="scope.row.synced_to_knowledge" type="success">已入库</el-tag>
              <el-tag v-else type="warning">未入库</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="290">
            <template #default="scope">
              <el-button link type="primary" @click="openReplyDialog(scope.row)">回复</el-button>
              <el-button link type="warning" @click="markTicketRead(scope.row.id)">已读</el-button>
              <el-button link type="info" @click="ignoreTicket(scope.row.id)">忽略</el-button>
              <el-button link type="success" :disabled="!scope.row.admin_reply" @click="syncOneTicket(scope.row.id)">加入知识库</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </main>

    <el-dialog v-model="editVisible" title="编辑用户" width="460px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="editForm.username" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
        <el-form-item label="积分">
          <el-input-number v-model="editForm.points" :min="0" :precision="2" :step="1" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="replyVisible" title="回复人工工单" width="520px">
      <el-form label-width="70px">
        <el-form-item label="用户问题">
          <div class="reply-question">{{ replyTarget.question || '—' }}</div>
        </el-form-item>
        <el-form-item label="回复内容">
          <el-input v-model="replyText" type="textarea" :rows="4" placeholder="请输入人工回复内容..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="replyVisible = false">取消</el-button>
        <el-button type="primary" :loading="replying" @click="submitReply">发送回复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { uploadToCos } from '../api/storage'
import {
  getAICsDocs,
  getAICsSettings,
  getAICsTickets,
  getConsoleConfigs,
  consoleLogout,
  consoleMe,
  getConsoleUsers,
  syncAICsTicketsToKnowledge,
  updateAICsSettings,
  updateAICsTicket,
  updateConsoleConfig,
  updateConsoleUser,
  uploadAICsKnowledge,
} from '../api/console'

const router = useRouter()
const adminUser = ref(null)
const activeModule = ref('stats')
const aiMenuOpen = ref(true)
const humanMenuOpen = ref(true)

const moduleTitle = computed(() => {
  if (activeModule.value === 'stats') return '信息统计'
  if (activeModule.value === 'page') return '页面管理'
  if (activeModule.value === 'users') return '用户信息'
  if (activeModule.value === 'script') return '剧本优化'
  if (activeModule.value === 'ai_knowledge') return 'AI知识库'
  if (activeModule.value === 'ai_customer') return 'AI客服'
  return '人工客服'
})

const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const defaultAvatarUrl = ref('')
const defaultAvatarUploading = ref(false)
const scriptStoryboardPrompt = ref('')
const scriptParagraphPrompt = ref('')
const savingPrompts = ref(false)

const editVisible = ref(false)
const editForm = reactive({ id: null, username: '', email: '', points: 0, is_active: true })

const aiCsForm = reactive({
  enabled: true,
  tone_style: '',
  base_prompt: '',
  no_answer_text: '',
  feishu_bot_config_url: '',
  feishu_webhook_url: '',
})
const savingAiSettings = ref(false)
const knowledgeDocs = ref([])
const knowledgeTitle = ref('')
const knowledgeInputRef = ref()
const uploadingKnowledge = ref(false)
const aiTickets = ref([])
const aiUnreadCount = ref(0)
const replyVisible = ref(false)
const replyText = ref('')
const replying = ref(false)
const replyTarget = reactive({ id: null, question: '' })
const selectedTicketIds = ref([])
const syncingKnowledge = ref(false)

const toggleAiMenu = () => {
  aiMenuOpen.value = !aiMenuOpen.value
}

const toggleHumanMenu = () => {
  humanMenuOpen.value = !humanMenuOpen.value
}

const loadAdminMe = async () => {
  const res = await consoleMe()
  adminUser.value = res.data.user
}

const loadConfigs = async () => {
  const res = await getConsoleConfigs()
  const map = Object.fromEntries(res.data.map((item) => [item.key, item.value]))
  defaultAvatarUrl.value = map.default_avatar_url || '/octopus-avatar.svg'
  scriptStoryboardPrompt.value = map.storyboard_default_prompt || ''
  scriptParagraphPrompt.value = map.paragraph_default_prompt || ''
}

const saveDefaultAvatar = async () => {
  try {
    await updateConsoleConfig('default_avatar_url', { value: defaultAvatarUrl.value || '/octopus-avatar.svg' })
    ElMessage.success('默认头像已更新')
  } catch (e) {
    ElMessage.error(e)
  }
}

const pickDefaultAvatarFile = () => {
  const input = document.getElementById('default-avatar-upload')
  if (input) input.click()
}

const loadImage = (file) =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片读取失败'))
    img.src = URL.createObjectURL(file)
  })

const toBlob = (canvas, type, quality) =>
  new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality)
  })

const compressImageBeforeUpload = async (file) => {
  const mime = file.type || 'image/jpeg'
  if (!mime.startsWith('image/')) return file
  const img = await loadImage(file)
  const maxW = 1920
  const maxH = 1920
  let { width, height } = img
  const ratio = Math.min(maxW / width, maxH / height, 1)
  width = Math.round(width * ratio)
  height = Math.round(height * ratio)

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0, width, height)

  const targetType = mime === 'image/png' ? 'image/webp' : mime
  const quality = targetType === 'image/jpeg' || targetType === 'image/webp' ? 0.82 : undefined
  const blob = await toBlob(canvas, targetType, quality)
  URL.revokeObjectURL(img.src)
  if (!blob || blob.size >= file.size) return file
  const extMap = { 'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp' }
  const ext = extMap[targetType] || 'jpg'
  const nextName = file.name.replace(/\.[^.]+$/, '') + `.${ext}`
  return new File([blob], nextName, { type: targetType })
}

const handleDefaultAvatarUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) return ElMessage.warning('请上传图片文件')
  if (file.size > 5 * 1024 * 1024) return ElMessage.warning('默认头像不能超过5MB')

  defaultAvatarUploading.value = true
  try {
    const compressed = await compressImageBeforeUpload(file)
    const res = await uploadToCos(compressed, 'images/avatars')
    defaultAvatarUrl.value = res.data.url
    await updateConsoleConfig('default_avatar_url', { value: defaultAvatarUrl.value })
    ElMessage.success('默认头像上传并保存成功')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    defaultAvatarUploading.value = false
  }
}

const saveScriptPrompts = async () => {
  savingPrompts.value = true
  try {
    await updateConsoleConfig('storyboard_default_prompt', { value: scriptStoryboardPrompt.value || '' })
    await updateConsoleConfig('paragraph_default_prompt', { value: scriptParagraphPrompt.value || '' })
    ElMessage.success('默认提示词已保存')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    savingPrompts.value = false
  }
}

const thumbSrc = (url) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${Date.now()}`
}

const loadUsers = async (targetPage = page.value) => {
  page.value = targetPage
  try {
    const res = await getConsoleUsers({ page: page.value, page_size: pageSize.value, keyword: keyword.value })
    users.value = res.data.list || []
    total.value = Number(res.data.total || 0)
  } catch (e) {
    ElMessage.error(e)
  }
}

const openEdit = (row) => {
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.points = Number(row.points || 0)
  editForm.is_active = row.is_active
  editVisible.value = true
}

const saveUser = async () => {
  if (!editForm.id) return
  try {
    await updateConsoleUser(editForm.id, {
      username: editForm.username,
      email: editForm.email,
      points: Number(editForm.points || 0),
      is_active: editForm.is_active,
    })
    ElMessage.success('用户信息已更新')
    editVisible.value = false
    loadUsers(page.value)
  } catch (e) {
    ElMessage.error(e)
  }
}

const loadAiCsSettings = async () => {
  try {
    const res = await getAICsSettings()
    Object.assign(aiCsForm, res.data || {})
  } catch (e) {
    ElMessage.error(e)
  }
}

const saveAiCsSettings = async () => {
  savingAiSettings.value = true
  try {
    await updateAICsSettings({ ...aiCsForm })
    ElMessage.success('AI客服配置已保存')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    savingAiSettings.value = false
  }
}

const openFeishuIntegration = () => {
  const url = (aiCsForm.feishu_bot_config_url || '').trim()
  if (!url) {
    ElMessage.warning('请先在上方填写飞书机器人配置地址')
    return
  }
  window.open(url, '_blank')
}

const loadAiCsDocs = async () => {
  try {
    const res = await getAICsDocs()
    knowledgeDocs.value = res.data || []
  } catch (e) {
    ElMessage.error(e)
  }
}

const pickKnowledgeFile = () => {
  if (knowledgeInputRef.value) knowledgeInputRef.value.click()
}

const handleKnowledgeFile = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return

  uploadingKnowledge.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('title', knowledgeTitle.value || '')
    const res = await uploadAICsKnowledge(formData)
    ElMessage.success(`向量化成功，分块 ${res.data.chunk_count} 条`)
    knowledgeTitle.value = ''
    await loadAiCsDocs()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    uploadingKnowledge.value = false
  }
}

const loadAiCsTickets = async () => {
  try {
    const res = await getAICsTickets()
    aiTickets.value = res.data.list || []
    aiUnreadCount.value = Number(res.data.unread_count || 0)
  } catch (e) {
    ElMessage.error(e)
  }
}

const onTicketSelectionChange = (rows) => {
  selectedTicketIds.value = (rows || []).map((item) => item.id)
}

const markTicketRead = async (id) => {
  try {
    await updateAICsTicket(id, { action: 'read' })
    ElMessage.success('已标记为已读')
    await loadAiCsTickets()
  } catch (e) {
    ElMessage.error(e)
  }
}

const ignoreTicket = async (id) => {
  try {
    await updateAICsTicket(id, { action: 'ignore' })
    ElMessage.success('已忽略该工单')
    await loadAiCsTickets()
  } catch (e) {
    ElMessage.error(e)
  }
}

const openReplyDialog = (row) => {
  replyTarget.id = row.id
  replyTarget.question = row.question
  replyText.value = row.admin_reply || ''
  replyVisible.value = true
}

const submitReply = async () => {
  if (!replyTarget.id) return
  if (!replyText.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replying.value = true
  try {
    await updateAICsTicket(replyTarget.id, { action: 'reply', reply: replyText.value.trim() })
    ElMessage.success('回复已发送并标记已读')
    replyVisible.value = false
    await loadAiCsTickets()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    replying.value = false
  }
}

const syncOneTicket = async (ticketId) => {
  syncingKnowledge.value = true
  try {
    const res = await syncAICsTicketsToKnowledge({ ticket_ids: [ticketId] })
    ElMessage.success(`入库成功，共 ${res.data.count} 条`)
    await Promise.all([loadAiCsDocs(), loadAiCsTickets()])
  } catch (e) {
    ElMessage.error(e)
  } finally {
    syncingKnowledge.value = false
  }
}

const batchSyncKnowledge = async () => {
  if (!selectedTicketIds.value.length) return
  syncingKnowledge.value = true
  try {
    const res = await syncAICsTicketsToKnowledge({ ticket_ids: selectedTicketIds.value })
    ElMessage.success(`批量入库成功，共 ${res.data.count} 条`)
    selectedTicketIds.value = []
    await Promise.all([loadAiCsDocs(), loadAiCsTickets()])
  } catch (e) {
    ElMessage.error(e)
  } finally {
    syncingKnowledge.value = false
  }
}

const handleLogout = async () => {
  try {
    await consoleLogout()
  } catch (e) {
    ElMessage.warning(typeof e === 'string' ? e : '登录态已失效，返回登录页')
  } finally {
    router.push('/admin/login')
  }
}

onMounted(async () => {
  try {
    await loadAdminMe()
  } catch {
    router.push('/admin/login')
    return
  }

  await Promise.allSettled([
    loadConfigs(),
    loadUsers(1),
    loadAiCsSettings(),
    loadAiCsDocs(),
    loadAiCsTickets(),
  ])
})
</script>

<style scoped>
.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 250px 1fr;
  background:
    radial-gradient(900px 380px at 8% -8%, rgba(91, 192, 255, 0.2), transparent 62%),
    radial-gradient(680px 320px at 100% 0%, rgba(255, 103, 223, 0.16), transparent 62%),
    linear-gradient(145deg, #161236, #1f1452 45%, #11193f);
}
.admin-sidebar {
  background: linear-gradient(170deg, rgba(13, 24, 62, 0.96), rgba(20, 24, 68, 0.96));
  border-right: 1px solid rgba(130, 195, 255, 0.28);
  padding: 24px 14px;
  box-shadow: inset -1px 0 0 rgba(175, 226, 255, 0.08);
}
.side-head h2 {
  margin: 0;
  color: #eff8ff;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  text-shadow: 0 0 14px rgba(97, 202, 255, 0.45);
}
.side-head p { margin: 6px 0 16px; color: #b3c9ef; }
.side-btn {
  width: 100%;
  border: 1px solid rgba(141, 195, 255, 0.36);
  background: linear-gradient(130deg, rgba(25, 43, 96, 0.86), rgba(21, 30, 76, 0.9));
  color: #dceaff;
  border-radius: 12px;
  text-align: left;
  padding: 11px 12px;
  margin-bottom: 10px;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.side-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(160, 222, 255, 0.58);
  box-shadow: 0 10px 20px rgba(6, 12, 44, 0.45);
}
.side-btn.active {
  border-color: transparent;
  color: #fff;
  background: linear-gradient(125deg, #41bcff, #4a65ff, #5edbff);
  box-shadow: 0 0 0 1px rgba(172, 232, 255, 0.2), 0 0 22px rgba(84, 196, 255, 0.36);
}
.ai-side-btn {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.menu-right {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.submenu-arrow {
  font-size: 12px;
  opacity: 0.85;
}
.submenu-wrap {
  margin: -4px 0 8px;
  padding: 8px 6px 2px 8px;
  border-left: 1px dashed rgba(151, 209, 255, 0.35);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.submenu-btn {
  width: 100%;
  min-height: 34px;
  border: 1px solid rgba(133, 189, 255, 0.34);
  border-radius: 10px;
  background: rgba(27, 43, 100, 0.62);
  color: #cfe2ff;
  text-align: left;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}
.submenu-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(161, 222, 255, 0.54);
  box-shadow: 0 8px 16px rgba(9, 14, 50, 0.34);
}
.submenu-btn.active {
  border-color: transparent;
  color: #fff;
  background: linear-gradient(126deg, rgba(73, 169, 255, 0.95), rgba(80, 98, 255, 0.95));
  box-shadow: 0 0 0 1px rgba(172, 232, 255, 0.18), 0 0 16px rgba(96, 196, 255, 0.32);
}
.human-sub-btn .unread-badge {
  margin-left: 8px;
}
.unread-badge {
  min-width: 20px;
  height: 20px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  background: linear-gradient(130deg, #ff446f, #ff6c79);
  box-shadow: 0 0 10px rgba(255, 85, 123, 0.6);
}
.admin-main { padding: 18px 20px; }
.main-head { display: flex; align-items: center; justify-content: space-between; }
.main-head h3 {
  margin: 0;
  color: #eef5ff;
  text-shadow: 0 0 12px rgba(103, 206, 255, 0.4);
}
.panel-card {
  margin-top: 14px;
  border: 1px solid rgba(122, 168, 255, 0.32);
  border-radius: 16px;
  background: linear-gradient(145deg, rgba(28, 33, 74, 0.86), rgba(20, 19, 59, 0.88));
  padding: 16px;
  color: #d8e0f4;
  box-shadow: inset 0 0 0 1px rgba(167, 218, 255, 0.1), 0 14px 30px rgba(7, 10, 36, 0.4);
}
.panel-tip { margin-bottom: 12px; color: #aec0e3; }
.metric-card {
  border-radius: 12px;
  border: 1px solid rgba(118, 171, 255, 0.34);
  background: linear-gradient(135deg, rgba(31, 42, 94, 0.72), rgba(29, 32, 78, 0.74));
}
:deep(.metric-card .el-statistic__head) {
  color: #d7e8ff;
  font-family: "Plus Jakarta Sans", "PingFang SC", sans-serif;
  font-weight: 700;
  letter-spacing: 0.2px;
}
:deep(.metric-card .el-statistic__content) {
  color: #f4fbff;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  font-weight: 800;
  text-shadow: 0 0 12px rgba(104, 206, 255, 0.34);
}
.avatar-row { display: grid; grid-template-columns: 170px 1fr; gap: 12px; }
.row-label { margin: 0 0 8px; color: #e8edf8; font-weight: 600; }
.avatar-thumb {
  height: 82px;
  border-radius: 10px;
  border: 1px dashed rgba(124, 188, 255, 0.58);
  background: rgba(18, 26, 64, 0.82);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a8badd;
}
.avatar-thumb img { width: 100%; height: 100%; object-fit: contain; background: #171921; }
.row-actions { margin-top: 8px; display: flex; gap: 10px; flex-wrap: wrap; }
.ai-actions {
  margin-top: 18px;
  padding-top: 4px;
  position: relative;
  z-index: 2;
}
.file-hidden { display: none; }
.user-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.user-filter { display: flex; gap: 8px; }
.pager-wrap { margin-top: 14px; display: flex; justify-content: flex-end; }
.placeholder-title { margin: 0; }
.placeholder-sub { margin-top: 8px; color: #b2c4e8; }
.kb-upload-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}
.neon-btn {
  border-color: rgba(146, 213, 255, 0.5);
  color: #d8eeff;
  background: rgba(21, 44, 95, 0.7);
}
.reply-question {
  width: 100%;
  border: 1px solid rgba(123, 192, 255, 0.35);
  border-radius: 10px;
  padding: 8px 10px;
  color: #dbeeff;
  background: rgba(21, 31, 78, 0.65);
  min-height: 56px;
  white-space: pre-wrap;
}

:deep(.el-table) {
  --el-table-bg-color: rgba(21, 28, 72, 0.5);
  --el-table-tr-bg-color: rgba(21, 28, 72, 0.5);
  --el-table-striped-bg-color: rgba(18, 24, 64, 0.72);
  --el-table-border-color: rgba(125, 170, 255, 0.3);
  --el-table-header-bg-color: rgba(36, 56, 122, 0.5);
  --el-table-header-text-color: #e8f3ff;
  --el-table-row-hover-bg-color: rgba(64, 125, 211, 0.2);
  color: #dce8ff;
}
:deep(.el-table__body tr > td.el-table__cell) {
  background-color: rgba(21, 28, 72, 0.5);
}
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: rgba(18, 24, 64, 0.72);
}
:deep(.el-input__wrapper),
:deep(.el-textarea__inner),
:deep(.el-input-number .el-input__wrapper) {
  background: rgba(16, 32, 77, 0.75);
  box-shadow: inset 0 0 0 1px rgba(117, 187, 255, 0.45) !important;
  color: #eaf5ff;
}
:deep(.el-form-item__label) {
  color: #c6dbf7;
}
:deep(.el-button) {
  border-radius: 10px;
}
:deep(.main-btn.el-button) {
  border: none;
  background: linear-gradient(130deg, #47bfff, #4c69ff, #5ad7ff);
  color: #fff;
  box-shadow: 0 0 0 1px rgba(171, 232, 255, 0.24), 0 10px 22px rgba(39, 109, 220, 0.4);
}
@media (max-width: 980px) {
  .admin-shell { grid-template-columns: 1fr; }
  .admin-sidebar { border-right: 0; border-bottom: 1px solid rgba(142, 201, 255, 0.28); }
  .avatar-row { grid-template-columns: 1fr; }
  .kb-upload-row { grid-template-columns: 1fr; }
}
</style>
