<template>
  <div class="page-shell ai-cs-shell">
    <el-card class="surface-card ai-cs-card" shadow="never">
      <header class="chat-head">
        <div>
          <h2>AI章鱼助手</h2>
          <p>一个个性化的助手</p>
        </div>
        <div class="head-actions">
          <el-button class="neon-btn" @click="resumeDialogVisible = true">简历助手</el-button>
          <el-button class="neon-btn reply-btn" @click="openRepliesDialog">
            人工回复
            <span v-if="unreadReplyCount > 0" class="reply-count">{{ unreadReplyCount }}</span>
          </el-button>
          <el-button class="neon-btn" @click="$router.push('/home')">返回首页</el-button>
        </div>
      </header>

      <div class="chat-window" ref="chatWindowRef">
        <div v-for="item in messages" :key="item.id || item.localId" class="msg" :class="item.role">
          <el-avatar
            v-if="item.role === 'assistant'"
            class="msg-avatar"
            :size="34"
            :src="aiAvatar"
          />
          <div class="bubble">
            <p v-if="!item.waiting">{{ item.content }}</p>
            <p v-else class="thinking-line">
              AI思考中<span class="thinking-dots"><i></i><i></i><i></i></span>
            </p>
            <div v-if="item.attachments?.length" class="attach-list">
              <a v-for="(f, idx) in item.attachments" :key="idx" :href="f.url" target="_blank" rel="noreferrer">{{ f.name || f.url }}</a>
            </div>
          </div>
          <el-avatar
            v-if="item.role === 'user'"
            class="msg-avatar"
            :size="34"
            :src="userAvatarSrc"
            @error="handleUserAvatarError"
          />
        </div>
      </div>

      <div class="upload-row">
        <input ref="fileInputRef" type="file" class="file-hidden" multiple @change="handleFiles" />
        <el-button class="neon-btn" @click="pickFiles">上传图片/视频/文档</el-button>
        <span v-if="pendingFiles.length" class="file-tip">已选 {{ pendingFiles.length }} 个文件</span>
      </div>

      <div class="composer">
        <el-input
          v-model="inputText"
          class="neon-input"
          type="textarea"
          :rows="3"
          placeholder="输入你想咨询的问题..."
          @keydown.enter.exact.prevent="send"
        />
        <el-button class="main-btn neon-send-btn" type="primary" :loading="sending" @click="send">发送</el-button>
      </div>
    </el-card>

    <el-dialog v-model="repliesDialogVisible" title="人工回复" width="680px">
      <div v-if="humanReplies.length" class="replies-toolbar">
        <el-button class="neon-btn" :loading="clearingReplies" @click="clearAllReplies">清除全部</el-button>
      </div>
      <div v-if="!humanReplies.length" class="replies-empty">暂未收到人工回复</div>
      <div v-else class="replies-list">
        <div v-for="item in humanReplies" :key="item.id" class="reply-item">
          <p class="reply-item-title">针对问题：{{ item.question }}</p>
          <p class="reply-item-content">人工回复：{{ item.admin_reply }}</p>
          <p class="reply-item-time">{{ formatDate(item.replied_at) }}</p>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="resumeDialogVisible" title="简历助手" width="700px">
      <el-form label-width="96px" class="resume-form">
        <el-form-item label="职位名称">
          <el-input v-model="resumeJobTitle" placeholder="请输入职位名称，例如：Java后端工程师" />
        </el-form-item>
        <el-form-item label="职位截图">
          <div class="resume-upload">
            <input ref="resumeFileInputRef" type="file" class="file-hidden" accept="image/*" multiple @change="handleResumeFiles" />
            <el-button class="neon-btn" @click="pickResumeFiles">上传职位要求截图</el-button>
            <span class="file-tip" v-if="resumeFiles.length">已选 {{ resumeFiles.length }} 张</span>
          </div>
        </el-form-item>
        <el-form-item v-if="resumePreviewUrls.length" label="ROI框选">
          <div class="roi-wrap">
            <div class="roi-thumbs">
              <button
                v-for="(src, idx) in resumePreviewUrls"
                :key="src + idx"
                type="button"
                class="roi-thumb-btn"
                :class="{ active: resumeSelectedIndex === idx }"
                @click="selectResumeImage(idx)"
              >
                <img :src="src" alt="resume-preview" />
              </button>
            </div>
            <div
              ref="roiStageRef"
              class="roi-stage"
              @mousedown.prevent="onRoiMouseDown"
              @mousemove.prevent="onRoiMouseMove"
              @mouseup.prevent="onRoiMouseUp"
              @mouseleave.prevent="onRoiMouseUp"
            >
              <img :src="resumePreviewUrls[resumeSelectedIndex]" class="roi-image" />
              <div
                v-if="resumeDisplayRect.w > 2 && resumeDisplayRect.h > 2"
                class="roi-rect"
                :style="{
                  left: `${resumeDisplayRect.x}px`,
                  top: `${resumeDisplayRect.y}px`,
                  width: `${resumeDisplayRect.w}px`,
                  height: `${resumeDisplayRect.h}px`,
                }"
              />
            </div>
            <div class="roi-actions">
              <el-button class="neon-btn" size="small" @click="clearCurrentRoi">清除当前框选</el-button>
              <span class="file-tip">不框选默认识别整张图</span>
            </div>
          </div>
        </el-form-item>
        <el-form-item>
          <el-alert
            title="生成简历将消耗 10 积分，支持上传多张并可框选岗位要求区域"
            type="warning"
            :closable="false"
            show-icon
          />
        </el-form-item>
        <el-form-item v-if="resumeGenerating">
          <div class="w-100">
            <el-progress :percentage="resumeProgress" :status="resumeStatus === 'failed' ? 'exception' : undefined" />
            <p class="file-tip mt-1">任务状态：{{ resumeStatusText }}</p>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="resumeGenerating" @click="resumeDialogVisible = false">取消</el-button>
        <el-button class="main-btn" type="primary" :loading="resumeGenerating" @click="generateResumePdf">生成简历PDF</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { clearAiCustomerHumanReplies, createResumeAssistantTask, getAiCustomerHistory, getAiCustomerHumanReplies, getResumeAssistantTask } from '../api/aiCustomer'
import { me } from '../api/auth'
import { uploadToCos } from '../api/storage'

const router = useRouter()
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const pendingFiles = ref([])
const fileInputRef = ref()
const chatWindowRef = ref()
const userAvatar = ref('/octopus-avatar.svg')
const aiAvatar = '/octopus-avatar.svg'
const userAvatarFailed = ref(false)
const fallbackAvatar = '/octopus-avatar.svg'
const userAvatarSrc = computed(() => (userAvatarFailed.value ? fallbackAvatar : (userAvatar.value || fallbackAvatar)))
const repliesDialogVisible = ref(false)
const humanReplies = ref([])
const clearingReplies = ref(false)
const resumeDialogVisible = ref(false)
const resumeGenerating = ref(false)
const resumeJobTitle = ref('')
const resumeFiles = ref([])
const resumePreviewUrls = ref([])
const resumeSelectedIndex = ref(0)
const roiStageRef = ref()
const roiDrawing = ref(false)
const roiStartPoint = ref({ x: 0, y: 0 })
const resumeDisplayRect = ref({ x: 0, y: 0, w: 0, h: 0 })
const resumeRoiMap = ref({})
const resumeProgress = ref(0)
const resumeStatus = ref('idle')
const resumeTaskId = ref(null)
let resumePollTimer = null
const resumeFileInputRef = ref()
const userId = ref('')
const seenReplyVersionMap = ref({})
const seenReplyStorageKey = computed(() => `ai_cs_seen_replies:${userId.value || 'guest'}`)
const unreadReplyCount = computed(() =>
  humanReplies.value.filter((item) => {
    const version = item?.replied_at || ''
    return seenReplyVersionMap.value[String(item.id)] !== version
  }).length
)

const loadSeenReplies = () => {
  try {
    const raw = localStorage.getItem(seenReplyStorageKey.value)
    const data = raw ? JSON.parse(raw) : {}
    seenReplyVersionMap.value = data && typeof data === 'object' ? data : {}
  } catch {
    seenReplyVersionMap.value = {}
  }
}

const persistSeenReplies = () => {
  try {
    localStorage.setItem(seenReplyStorageKey.value, JSON.stringify(seenReplyVersionMap.value))
  } catch {
    // ignore storage failure
  }
}

const markRepliesAsRead = (items = humanReplies.value) => {
  if (!Array.isArray(items) || !items.length) return
  const nextMap = { ...seenReplyVersionMap.value }
  items.forEach((item) => {
    if (!item || !item.id) return
    nextMap[String(item.id)] = item.replied_at || ''
  })
  seenReplyVersionMap.value = nextMap
  persistSeenReplies()
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatWindowRef.value) {
    chatWindowRef.value.scrollTop = chatWindowRef.value.scrollHeight
  }
}

const loadHistory = async () => {
  const res = await getAiCustomerHistory()
  if (!res.data.enabled) {
    ElMessage.warning('AI章鱼助手当前未开放')
    router.push('/home')
    return
  }
  messages.value = (res.data.messages || []).map((item) => ({ ...item, waiting: false }))
  await scrollToBottom()
}

const loadMe = async () => {
  const res = await me()
  userAvatar.value = res.data.user?.avatar_url || '/octopus-avatar.svg'
  userAvatarFailed.value = false
  userId.value = String(res.data.user?.id || '')
  loadSeenReplies()
}

const loadHumanReplies = async () => {
  const res = await getAiCustomerHumanReplies()
  humanReplies.value = res.data.list || []
}

const openRepliesDialog = async () => {
  try {
    await loadHumanReplies()
    repliesDialogVisible.value = true
    markRepliesAsRead()
  } catch (e) {
    ElMessage.error(String(e || '获取人工回复失败'))
  }
}

const clearAllReplies = async () => {
  if (!humanReplies.value.length || clearingReplies.value) return
  try {
    await ElMessageBox.confirm('清除后当前人工回复将不再展示，是否继续？', '确认清除', {
      confirmButtonText: '确认清除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  clearingReplies.value = true
  try {
    await clearAiCustomerHumanReplies()
    humanReplies.value = []
    seenReplyVersionMap.value = {}
    persistSeenReplies()
    ElMessage.success('已清除人工回复消息')
  } catch (e) {
    ElMessage.error(String(e || '清除失败'))
  } finally {
    clearingReplies.value = false
  }
}

const formatDate = (value) => {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(
    d.getHours()
  ).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const handleUserAvatarError = () => {
  userAvatarFailed.value = true
  return false
}

const pickFiles = () => {
  if (fileInputRef.value) fileInputRef.value.click()
}

const handleFiles = (event) => {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  pendingFiles.value.push(...files)
}

const pickResumeFiles = () => {
  if (resumeFileInputRef.value) resumeFileInputRef.value.click()
}

const handleResumeFiles = (event) => {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  resumeFiles.value.push(...files)
  resumePreviewUrls.value.push(...files.map((file) => URL.createObjectURL(file)))
  if (resumePreviewUrls.value.length === files.length) {
    resumeSelectedIndex.value = 0
  }
  syncDisplayRectFromRoi()
}

const selectResumeImage = (idx) => {
  resumeSelectedIndex.value = idx
  syncDisplayRectFromRoi()
}

const _clampToStage = (x, y) => {
  const stage = roiStageRef.value
  if (!stage) return { x: 0, y: 0 }
  const rect = stage.getBoundingClientRect()
  return {
    x: Math.max(0, Math.min(x, rect.width)),
    y: Math.max(0, Math.min(y, rect.height)),
  }
}

const onRoiMouseDown = (evt) => {
  const stage = roiStageRef.value
  if (!stage || !resumePreviewUrls.value.length) return
  const rect = stage.getBoundingClientRect()
  const p = _clampToStage(evt.clientX - rect.left, evt.clientY - rect.top)
  roiDrawing.value = true
  roiStartPoint.value = p
  resumeDisplayRect.value = { x: p.x, y: p.y, w: 0, h: 0 }
}

const onRoiMouseMove = (evt) => {
  if (!roiDrawing.value) return
  const stage = roiStageRef.value
  if (!stage) return
  const rect = stage.getBoundingClientRect()
  const p = _clampToStage(evt.clientX - rect.left, evt.clientY - rect.top)
  const sx = roiStartPoint.value.x
  const sy = roiStartPoint.value.y
  const x = Math.min(sx, p.x)
  const y = Math.min(sy, p.y)
  const w = Math.abs(p.x - sx)
  const h = Math.abs(p.y - sy)
  resumeDisplayRect.value = { x, y, w, h }
}

const onRoiMouseUp = () => {
  if (!roiDrawing.value) return
  roiDrawing.value = false
  const stage = roiStageRef.value
  if (!stage) return
  const stageRect = stage.getBoundingClientRect()
  const r = resumeDisplayRect.value
  if (r.w < 8 || r.h < 8) {
    clearCurrentRoi()
    return
  }
  resumeRoiMap.value[String(resumeSelectedIndex.value)] = {
    x: Number((r.x / stageRect.width).toFixed(6)),
    y: Number((r.y / stageRect.height).toFixed(6)),
    w: Number((r.w / stageRect.width).toFixed(6)),
    h: Number((r.h / stageRect.height).toFixed(6)),
  }
}

const clearCurrentRoi = () => {
  delete resumeRoiMap.value[String(resumeSelectedIndex.value)]
  resumeDisplayRect.value = { x: 0, y: 0, w: 0, h: 0 }
}

const syncDisplayRectFromRoi = () => {
  const stage = roiStageRef.value
  if (!stage) {
    setTimeout(syncDisplayRectFromRoi, 50)
    return
  }
  const stageRect = stage.getBoundingClientRect()
  const roi = resumeRoiMap.value[String(resumeSelectedIndex.value)]
  if (!roi) {
    resumeDisplayRect.value = { x: 0, y: 0, w: 0, h: 0 }
    return
  }
  resumeDisplayRect.value = {
    x: roi.x * stageRect.width,
    y: roi.y * stageRect.height,
    w: roi.w * stageRect.width,
    h: roi.h * stageRect.height,
  }
}

const stopResumePolling = () => {
  if (resumePollTimer) {
    clearInterval(resumePollTimer)
    resumePollTimer = null
  }
}

const resumeStatusText = computed(() => {
  if (resumeStatus.value === 'created') return '已创建，等待处理'
  if (resumeStatus.value === 'running') return '处理中'
  if (resumeStatus.value === 'succeeded') return '已完成'
  if (resumeStatus.value === 'failed') return '处理失败'
  return '等待中'
})

const startResumeTaskPolling = (taskId) => {
  stopResumePolling()
  resumeTaskId.value = taskId
  resumePollTimer = setInterval(async () => {
    try {
      const res = await getResumeAssistantTask(taskId)
      const data = res.data || {}
      resumeProgress.value = Number(data.progress || 0)
      resumeStatus.value = data.status || 'running'
      if (data.status === 'succeeded') {
        stopResumePolling()
        resumeGenerating.value = false
        const pdfUrl = data.result?.pdf_url
        if (pdfUrl) window.open(pdfUrl, '_blank')
        ElMessage.success('简历PDF已生成')
        resumeDialogVisible.value = false
        return
      }
      if (data.status === 'failed') {
        stopResumePolling()
        resumeGenerating.value = false
        resumeTaskId.value = null
        ElMessage.error(data.error || '简历生成失败')
      }
    } catch (e) {
      stopResumePolling()
      resumeGenerating.value = false
      ElMessage.error(String(e || '查询任务状态失败'))
    }
  }, 1800)
}

const generateResumePdf = async () => {
  const title = resumeJobTitle.value.trim()
  if (!title) {
    ElMessage.warning('请输入职位名称')
    return
  }
  if (!resumeFiles.value.length) {
    ElMessage.warning('请上传职位要求截图')
    return
  }
  resumeGenerating.value = true
  resumeProgress.value = 0
  resumeStatus.value = 'created'
  try {
    const uploaded = []
    for (const file of resumeFiles.value) {
      if (!file.type.startsWith('image/')) {
        throw new Error(`仅支持图片截图: ${file.name}`)
      }
      if (file.size > 10 * 1024 * 1024) {
        throw new Error(`截图过大(>10MB): ${file.name}`)
      }
      const res = await uploadToCos(file, 'ai-customer/resume')
      uploaded.push(res.data.url)
    }
    const rois = Object.entries(resumeRoiMap.value).map(([imageIndex, rect]) => ({
      image_index: Number(imageIndex),
      rects: [rect],
    }))
    const requestId = `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
    const res = await createResumeAssistantTask({
      job_title: title,
      image_urls: uploaded,
      rois,
      request_id: requestId,
    })
    const task = res.data || {}
    resumeTaskId.value = task.task_id
    resumeProgress.value = Number(task.progress || 0)
    resumeStatus.value = task.status || 'created'
    startResumeTaskPolling(task.task_id)
  } catch (e) {
    const msg = String(e || '简历助手执行失败')
    if (msg.includes('积分不足')) {
      try {
        await ElMessageBox.confirm('积分不足，是否前往充值页面？', '积分不足', {
          confirmButtonText: '去充值',
          cancelButtonText: '取消',
          customClass: 'anime-neon-message-box',
        })
        router.push('/recharge')
      } catch {
        // noop
      }
      return
    }
    ElMessage.error(msg)
  } finally {
    if (!resumeTaskId.value) {
      resumeGenerating.value = false
    }
  }
}

const uploadPendingFiles = async () => {
  if (!pendingFiles.value.length) return []
  const uploaded = []
  for (const file of pendingFiles.value) {
    if (file.size > 10 * 1024 * 1024) {
      throw new Error(`文件过大: ${file.name}`)
    }
    const res = await uploadToCos(file, 'ai-customer')
    uploaded.push({
      name: file.name,
      url: res.data.url,
      type: res.data.content_type,
      size: res.data.size,
    })
  }
  pendingFiles.value = []
  return uploaded
}

const streamChat = async (payload, assistantMsg) => {
  const response = await fetch('/api/v1/ai-customer/chat/stream', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok || !response.body) {
    const text = await response.text()
    throw new Error(text || '流式请求失败')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''

    for (const block of blocks) {
      const line = block.split('\n').find((l) => l.startsWith('data:'))
      if (!line) continue
      const raw = line.replace(/^data:\s*/, '')
      let data
      try {
        data = JSON.parse(raw)
      } catch {
        continue
      }

      if (data.type === 'delta') {
        assistantMsg.waiting = false
        assistantMsg.content += data.content || ''
        await scrollToBottom()
      }
      if (data.type === 'done') {
        assistantMsg.waiting = false
        assistantMsg.content = data.content || assistantMsg.content
        if (data.handover) {
          ElMessage.warning('当前问题已转人工处理')
        }
      }
      if (data.type === 'error') {
        throw new Error(data.message || '流式响应失败')
      }
    }
  }
}

const send = async () => {
  const text = inputText.value.trim()
  if (!text || sending.value) return

  sending.value = true
  try {
    const attachments = await uploadPendingFiles()
    const userMsg = { localId: Date.now(), role: 'user', content: text, attachments, waiting: false }
    messages.value.push(userMsg)
    inputText.value = ''

    const assistantMsg = { localId: Date.now() + 1, role: 'assistant', content: '', attachments: [], waiting: true }
    messages.value.push(assistantMsg)
    await scrollToBottom()

    await streamChat({ message: text, attachments }, assistantMsg)
  } catch (e) {
    const last = messages.value[messages.value.length - 1]
    if (last && last.role === 'assistant' && last.waiting) {
      last.waiting = false
      last.content = '抱歉，当前响应失败，请稍后重试。'
    }
    ElMessage.error(String(e || '发送失败'))
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadHistory(), loadMe(), loadHumanReplies()])
  } catch {
    router.push('/login')
  }
})

watch(seenReplyStorageKey, () => {
  loadSeenReplies()
})

watch(resumeDialogVisible, (visible) => {
  if (!visible && !resumeGenerating.value) {
    stopResumePolling()
    resumeTaskId.value = null
    resumeProgress.value = 0
    resumeStatus.value = 'idle'
    resumeRoiMap.value = {}
    resumeDisplayRect.value = { x: 0, y: 0, w: 0, h: 0 }
    resumePreviewUrls.value.forEach((url) => URL.revokeObjectURL(url))
    resumePreviewUrls.value = []
    resumeFiles.value = []
    resumeJobTitle.value = ''
  }
})
</script>

<style scoped>
.ai-cs-shell { min-height: 100vh; }
.ai-cs-card { width: min(900px, 100%); }
.chat-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.chat-head h2 { margin: 0; }
.chat-head p { margin: 6px 0 0; color: #c1d3f3; }
.head-actions {
  display: inline-flex;
  gap: 8px;
}
.reply-btn {
  position: relative;
}
.reply-count {
  margin-left: 6px;
  min-width: 18px;
  height: 18px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(130deg, #ff5c88, #ff6f63);
  box-shadow: 0 0 10px rgba(255, 97, 137, 0.52);
}
.neon-btn {
  border: 1px solid rgba(164, 223, 255, 0.66);
  color: #ebf8ff;
  background: linear-gradient(125deg, rgba(39, 138, 227, 0.75), rgba(74, 76, 198, 0.72));
  box-shadow: 0 0 0 1px rgba(171, 232, 255, 0.2), 0 0 16px rgba(98, 194, 255, 0.35);
}
.neon-btn:hover {
  filter: brightness(1.05);
}
.chat-window {
  margin-top: 14px;
  height: 460px;
  overflow: auto;
  border-radius: 14px;
  border: 1px solid rgba(133, 195, 255, 0.36);
  background: rgba(15, 24, 57, 0.6);
  padding: 12px;
}
.msg {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.msg-avatar {
  border: 1px solid rgba(158, 220, 255, 0.48);
  box-shadow: 0 0 10px rgba(95, 193, 255, 0.28);
  flex-shrink: 0;
}
.bubble {
  max-width: 78%;
  border-radius: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(126, 195, 255, 0.35);
  background: rgba(34, 50, 105, 0.58);
}
.msg.user .bubble {
  border-color: rgba(158, 221, 255, 0.62);
  background: linear-gradient(120deg, rgba(57, 138, 208, 0.72), rgba(57, 73, 184, 0.72));
}
.bubble p {
  white-space: pre-wrap;
  margin: 0;
  color: #ecf5ff;
}
.thinking-line {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.thinking-dots i {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #9ce5ff;
  box-shadow: 0 0 8px rgba(103, 209, 255, 0.62);
  animation: thinking 1.1s infinite ease-in-out;
}
.thinking-dots i:nth-child(2) { animation-delay: 0.12s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.24s; }
.attach-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.attach-list a {
  color: #92d5ff;
  font-size: 12px;
}
.upload-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.resume-upload {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.roi-wrap {
  width: 100%;
}
.roi-thumbs {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}
.roi-thumb-btn {
  width: 64px;
  height: 64px;
  border: 1px solid rgba(126, 198, 255, 0.35);
  border-radius: 10px;
  overflow: hidden;
  padding: 0;
  background: rgba(19, 30, 72, 0.6);
}
.roi-thumb-btn.active {
  border-color: #69d4ff;
  box-shadow: 0 0 10px rgba(99, 211, 255, 0.45);
}
.roi-thumb-btn img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.roi-stage {
  position: relative;
  width: 100%;
  height: 280px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid rgba(126, 198, 255, 0.35);
  background: rgba(8, 23, 56, 0.62);
  user-select: none;
}
.roi-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}
.roi-rect {
  position: absolute;
  border: 2px solid #6fe4ff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.5), 0 0 14px rgba(97, 219, 255, 0.55);
  background: rgba(102, 225, 255, 0.15);
}
.roi-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.file-tip { color: #abcbef; font-size: 12px; }
.file-hidden { display: none; }
.composer {
  margin-top: 10px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}
.neon-send-btn {
  min-width: 108px;
}
.neon-input :deep(.el-textarea__inner) {
  background: linear-gradient(145deg, rgba(15, 31, 72, 0.92), rgba(19, 26, 70, 0.94));
  border: 1px solid rgba(122, 199, 255, 0.5);
  color: #e9f6ff;
  box-shadow: inset 0 0 0 1px rgba(147, 219, 255, 0.12), 0 0 12px rgba(77, 183, 255, 0.25);
}
.neon-input :deep(.el-textarea__inner:focus) {
  border-color: rgba(141, 224, 255, 0.72);
  box-shadow:
    inset 0 0 0 1px rgba(153, 232, 255, 0.3),
    0 0 0 1px rgba(107, 199, 255, 0.52),
    0 0 18px rgba(79, 189, 255, 0.42);
}
.neon-input :deep(.el-textarea__inner::placeholder) {
  color: #97bcde;
}
.replies-empty {
  text-align: center;
  color: #abc4e8;
  padding: 20px 0;
}
.replies-toolbar {
  margin-bottom: 8px;
  display: flex;
  justify-content: flex-end;
}
.replies-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 460px;
  overflow: auto;
}
.reply-item {
  border: 1px solid rgba(126, 198, 255, 0.35);
  border-radius: 12px;
  padding: 10px 12px;
  background: linear-gradient(130deg, rgba(22, 38, 87, 0.55), rgba(26, 29, 73, 0.58));
}
.reply-item-title,
.reply-item-content {
  margin: 0;
  color: #e9f6ff;
  white-space: pre-wrap;
}
.reply-item-content {
  margin-top: 8px;
}
.reply-item-time {
  margin: 8px 0 0;
  color: #a0bfdf;
  font-size: 12px;
}
@keyframes thinking {
  0%, 80%, 100% { transform: scale(0.75); opacity: 0.55; }
  40% { transform: scale(1); opacity: 1; }
}
@media (max-width: 900px) {
  .composer { grid-template-columns: 1fr; }
  .bubble { max-width: 92%; }
}
</style>
