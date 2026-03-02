<template>
  <div class="page-shell ai-cs-shell">
    <el-card class="surface-card ai-cs-card" shadow="never">
      <header class="chat-head">
        <div>
          <h2>AI章鱼助手</h2>
          <p>一个个性化的助手</p>
        </div>
        <div class="head-actions">
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
      <div v-if="!humanReplies.length" class="replies-empty">暂未收到人工回复</div>
      <div v-else class="replies-list">
        <div v-for="item in humanReplies" :key="item.id" class="reply-item">
          <p class="reply-item-title">针对问题：{{ item.question }}</p>
          <p class="reply-item-content">人工回复：{{ item.admin_reply }}</p>
          <p class="reply-item-time">{{ formatDate(item.replied_at) }}</p>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAiCustomerHistory, getAiCustomerHumanReplies } from '../api/aiCustomer'
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
