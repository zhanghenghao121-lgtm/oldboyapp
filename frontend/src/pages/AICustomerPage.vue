<template>
  <div class="page-shell ai-cs-shell">
    <el-card class="surface-card ai-cs-card" shadow="never">
      <header class="chat-head">
        <div>
          <h2>AI章鱼助手</h2>
          <p>一个个性化的助手</p>
        </div>
        <el-button class="neon-btn" @click="$router.push('/home')">返回首页</el-button>
      </header>

      <div class="chat-window" ref="chatWindowRef">
        <div v-for="item in messages" :key="item.id || item.localId" class="msg" :class="item.role">
          <div class="bubble">
            <p>{{ item.content }}</p>
            <div v-if="item.attachments?.length" class="attach-list">
              <a v-for="(f, idx) in item.attachments" :key="idx" :href="f.url" target="_blank" rel="noreferrer">{{ f.name || f.url }}</a>
            </div>
          </div>
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
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getAiCustomerHistory } from '../api/aiCustomer'
import { uploadToCos } from '../api/storage'

const router = useRouter()
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const pendingFiles = ref([])
const fileInputRef = ref()
const chatWindowRef = ref()

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
  messages.value = res.data.messages || []
  await scrollToBottom()
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
        assistantMsg.content += data.content || ''
        await scrollToBottom()
      }
      if (data.type === 'done') {
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
    const userMsg = { localId: Date.now(), role: 'user', content: text, attachments }
    messages.value.push(userMsg)
    inputText.value = ''

    const assistantMsg = { localId: Date.now() + 1, role: 'assistant', content: '', attachments: [] }
    messages.value.push(assistantMsg)
    await scrollToBottom()

    await streamChat({ message: text, attachments }, assistantMsg)
  } catch (e) {
    ElMessage.error(String(e || '发送失败'))
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  try {
    await loadHistory()
  } catch {
    router.push('/login')
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
  margin-bottom: 10px;
}
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
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
@media (max-width: 900px) {
  .composer { grid-template-columns: 1fr; }
  .bubble { max-width: 92%; }
}
</style>
