<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="side-aura side-aura-top"></div>
      <div class="side-aura side-aura-bottom"></div>
      <div class="side-brand">
        <span class="brand-badge">Neon Console</span>
        <h2>章鱼工作台</h2>
        <p>创作工作区</p>
      </div>

      <button
        class="side-btn"
        :class="{ active: activePanel === 'script' }"
        @click="activePanel = 'script'"
      >
        剧本小优
      </button>
      <button
        class="side-btn"
        :class="{ active: activePanel === 'assistant' }"
        @click="activePanel = 'assistant'"
      >
        AI章鱼助手
      </button>
      <button
        class="side-btn"
        :class="{ active: activePanel === 'blogger' }"
        @click="activePanel = 'blogger'"
      >
        章鱼博主
      </button>
    </aside>

    <main class="main-panel">
      <div class="neon-bg">
        <span class="blob blob-a"></span>
        <span class="blob blob-b"></span>
        <span class="blob blob-c"></span>
      </div>
      <header class="main-header">
        <div class="headline">
          <p class="kicker">WELCOME TO</p>
          <h3>{{ panelTitle }}</h3>
        </div>
        <div class="head-right">
          <button class="points-pill" type="button" @click="openPointsDialog">
            <span class="points-label">积分</span>
            <span class="points-value">{{ Number(user?.points || 0).toFixed(2) }}</span>
          </button>
          <el-dropdown @command="onUserAction">
            <div class="avatar-entry">
              <el-avatar :src="avatarSrc" :size="40" @error="handleAvatarError" />
              <span class="name">{{ user?.username || '用户' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">用户信息</el-dropdown-item>
                <el-dropdown-item command="recharge">积分充值</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <section class="main-content">
        <div v-if="activePanel === 'script'" class="panel-card">
          <h4>剧本小优 · 剧本工坊</h4>
          <p>进入剧本小优后，你可以在创作工坊中快速完成剧本分镜和段落分镜。</p>
          <div class="feature-grid">
            <div class="feature-item">
              <span>01</span>
              <p>剧本分镜生成</p>
            </div>
            <div class="feature-item">
              <span>02</span>
              <p>段落分镜拆解</p>
            </div>
            <div class="feature-item">
              <span>03</span>
              <p>提示词可配置</p>
            </div>
            <div class="feature-item">
              <span>04</span>
              <p>积分计费联动</p>
            </div>
          </div>
          <div class="entry-row">
            <el-button type="primary" class="main-btn" @click="$router.push('/script-optimizer')">进入完整剧本优化页</el-button>
          </div>
        </div>

        <div v-if="activePanel === 'assistant'" class="panel-card">
          <h4>AI章鱼助手 · 霓虹会话台</h4>
          <p>一个个性化的助手，支持文本对话、图片视频文档上传，并可在无法回答时转人工处理。</p>
          <div class="feature-grid">
            <div class="feature-item">
              <span>01</span>
              <p>个性化语气回复</p>
            </div>
            <div class="feature-item">
              <span>02</span>
              <p>文档与多媒体附件</p>
            </div>
            <div class="feature-item">
              <span>03</span>
              <p>知识库检索回答</p>
            </div>
            <div class="feature-item">
              <span>04</span>
              <p>自动转人工工单</p>
            </div>
          </div>
          <div class="entry-row">
            <el-button type="primary" class="main-btn" @click="$router.push('/ai-customer')">进入 AI章鱼助手</el-button>
          </div>
        </div>

        <div v-if="activePanel === 'blogger'" class="panel-card">
          <h4>章鱼博主 · 两段式创作台</h4>
          <p>输入热点词或自动获取热搜后，一键生成标题、文案和配图，再继续生成视频成片。</p>
          <div class="feature-grid">
            <div class="feature-item">
              <span>01</span>
              <p>热点词自动抓取</p>
            </div>
            <div class="feature-item">
              <span>02</span>
              <p>标题文案自动生成</p>
            </div>
            <div class="feature-item">
              <span>03</span>
              <p>配图一键产出</p>
            </div>
            <div class="feature-item">
              <span>04</span>
              <p>首帧转视频</p>
            </div>
          </div>
          <div class="entry-row">
            <el-button type="primary" class="main-btn" @click="$router.push('/ai-blogger')">进入章鱼博主</el-button>
          </div>
        </div>
      </section>
    </main>

    <el-dialog v-model="pointsDialogVisible" title="积分使用明细" width="640px" class="points-dialog">
      <div v-loading="pointsLoading">
        <div v-if="!pointsLogs.length" class="points-empty">暂无积分明细</div>
        <div v-else class="points-log-list">
          <div v-for="item in pointsLogs" :key="item.id" class="points-log-item">
            <div class="points-log-left">
              <p class="points-log-desc">{{ item.description || usageTypeText(item.usage_type) }}</p>
              <p class="points-log-time">{{ formatDate(item.created_at) }}</p>
            </div>
            <div class="points-log-right">
              <span class="points-log-amount" :class="{ refund: Number(item.amount) < 0 }">
                {{ Number(item.amount) < 0 ? '+' : '-' }}{{ Math.abs(Number(item.amount)).toFixed(2) }}
              </span>
              <span class="points-log-balance">余额 {{ Number(item.balance_after || 0).toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPointsLogs, me, logout } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const activePanel = ref('script')
const user = ref(null)
const defaultAvatar = ref('')
const fallbackAvatar = '/octopus-avatar.svg'
const avatarLoadFailed = ref(false)
const pointsDialogVisible = ref(false)
const pointsLogs = ref([])
const pointsLoading = ref(false)

const panelTitle = computed(() => {
  if (activePanel.value === 'script') return '剧本小优'
  if (activePanel.value === 'assistant') return 'AI章鱼助手'
  return '章鱼博主'
})
const avatarSrc = computed(() => {
  if (avatarLoadFailed.value) return fallbackAvatar
  return user.value?.avatar_url || defaultAvatar.value || fallbackAvatar
})

const loadMe = async () => {
  const res = await me()
  user.value = res.data.user
}

const loadSiteConfig = async () => {
  try {
    const res = await getSiteBackgrounds()
    defaultAvatar.value = res.data.default_avatar || fallbackAvatar
  } catch {
    defaultAvatar.value = fallbackAvatar
  }
}

const doLogout = async () => {
  await logout()
  ElMessage.success('已退出')
  router.push('/login')
}

const usageTypeText = (usageType) => {
  if (usageType === 'script_storyboard') return '剧本分镜消耗'
  if (usageType === 'paragraph_storyboard') return '段落分镜消耗'
  if (usageType === 'ai_blogger_post') return '章鱼博主图文生成'
  if (usageType === 'ai_blogger_video') return '章鱼博主视频生成'
  if (usageType === 'refund') return '失败退款'
  return '积分变动'
}

const formatDate = (value) => {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(
    d.getHours()
  ).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const openPointsDialog = async () => {
  pointsDialogVisible.value = true
  pointsLoading.value = true
  try {
    const res = await getPointsLogs()
    pointsLogs.value = res.data.list || []
  } catch (e) {
    ElMessage.error(e)
  } finally {
    pointsLoading.value = false
  }
}

const onUserAction = async (command) => {
  if (command === 'profile') return router.push('/profile')
  if (command === 'recharge') return router.push('/recharge')
  if (command === 'logout') {
    try {
      await doLogout()
    } catch (e) {
      ElMessage.error(e)
    }
  }
}

const handleAvatarError = () => {
  avatarLoadFailed.value = true
  return false
}

onMounted(async () => {
  try {
    await Promise.all([loadMe(), loadSiteConfig()])
  } catch {
    router.push('/login')
  }
})
</script>

<style scoped>
.workspace-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 250px 1fr;
  background: #13131c;
}
.sidebar {
  background:
    radial-gradient(220px 160px at 20% 6%, rgba(90, 210, 255, 0.24), transparent 68%),
    radial-gradient(260px 180px at 85% 20%, rgba(255, 120, 220, 0.2), transparent 70%),
    linear-gradient(165deg, #0f1838, #111f4a 44%, #13133a);
  border-right: 1px solid rgba(140, 203, 255, 0.3);
  padding: 22px 14px;
  position: relative;
  z-index: 3;
  overflow: hidden;
}
.side-aura {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
  filter: blur(18px);
  opacity: 0.68;
}
.side-aura-top {
  width: 180px;
  height: 180px;
  top: -80px;
  left: -40px;
  background: rgba(84, 217, 255, 0.35);
}
.side-aura-bottom {
  width: 220px;
  height: 220px;
  right: -90px;
  bottom: -120px;
  background: rgba(255, 99, 217, 0.28);
}
.side-brand h2 {
  margin: 0;
  color: #eef7ff;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  text-shadow: 0 0 12px rgba(88, 204, 255, 0.46);
}
.side-brand p {
  margin: 6px 0 18px;
  color: #a9bfeb;
  font-size: 12px;
  letter-spacing: 1.2px;
}
.brand-badge {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 10px;
  margin-bottom: 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.9px;
  color: #d9f2ff;
  border: 1px solid rgba(145, 225, 255, 0.52);
  background: rgba(58, 133, 212, 0.35);
  box-shadow: 0 0 10px rgba(88, 192, 255, 0.3);
}
.side-btn {
  width: 100%;
  border: 1px solid rgba(146, 190, 255, 0.35);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(25, 39, 86, 0.84), rgba(26, 32, 78, 0.86));
  color: #d7e7ff;
  padding: 12px 12px;
  text-align: left;
  margin-bottom: 10px;
  position: relative;
  overflow: hidden;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}
.side-btn::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 18%, rgba(132, 225, 255, 0.22), transparent 62%);
  transform: translateX(-110%);
  transition: transform 0.35s ease;
}
.side-btn:hover {
  transform: translateY(-1px);
  border-color: rgba(153, 223, 255, 0.62);
  box-shadow: 0 10px 18px rgba(6, 16, 52, 0.5);
}
.side-btn:hover::after {
  transform: translateX(0%);
}
.side-btn.active {
  background: linear-gradient(125deg, #3e9dff, #4f63ff, #53d8ff);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 0 0 1px rgba(176, 226, 255, 0.24), 0 0 22px rgba(73, 187, 255, 0.38);
}
.main-panel {
  position: relative;
  overflow: hidden;
  padding: 18px 22px;
  background:
    radial-gradient(700px 360px at 5% -6%, rgba(84, 185, 255, 0.25), transparent 62%),
    radial-gradient(640px 300px at 100% 0%, rgba(255, 72, 201, 0.22), transparent 62%),
    linear-gradient(135deg, #1a1440, #231459 45%, #121b45 100%);
}
.neon-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.blob {
  position: absolute;
  filter: blur(22px);
  opacity: 0.6;
  border-radius: 50%;
  animation: floaty 9s ease-in-out infinite;
}
.blob-a {
  width: 220px;
  height: 220px;
  left: 8%;
  top: 18%;
  background: rgba(106, 199, 255, 0.45);
}
.blob-b {
  width: 260px;
  height: 260px;
  right: 10%;
  top: 10%;
  background: rgba(255, 90, 226, 0.38);
  animation-delay: 1.5s;
}
.blob-c {
  width: 240px;
  height: 240px;
  right: 25%;
  bottom: -40px;
  background: rgba(255, 188, 74, 0.32);
  animation-delay: 2.6s;
}
.main-header {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.headline .kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 1.8px;
  color: #8ec7ff;
}
.main-header h3 {
  margin: 2px 0 0;
  color: #eef2ff;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  font-size: 28px;
  text-shadow: 0 0 14px rgba(124, 198, 255, 0.45);
}
.avatar-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(166, 210, 255, 0.35);
  border-radius: 999px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
  box-shadow: 0 0 14px rgba(112, 186, 255, 0.22);
}
.avatar-entry .name {
  color: #fff;
  font-weight: 600;
}
.points-pill {
  border: 1px solid rgba(147, 226, 255, 0.6);
  border-radius: 999px;
  min-height: 42px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(128deg, rgba(26, 102, 177, 0.75), rgba(44, 52, 152, 0.78));
  color: #ebf7ff;
  cursor: pointer;
  box-shadow: 0 0 0 1px rgba(180, 229, 255, 0.2), 0 0 16px rgba(92, 200, 255, 0.38);
}
.points-label {
  font-size: 12px;
  opacity: 0.9;
}
.points-value {
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  font-size: 15px;
  letter-spacing: 0.3px;
  text-shadow: 0 0 9px rgba(128, 228, 255, 0.44);
}
.main-content {
  position: relative;
  z-index: 2;
  margin-top: 18px;
}
.panel-card {
  border: 1px solid rgba(114, 146, 255, 0.45);
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(32, 33, 67, 0.82), rgba(20, 16, 52, 0.86));
  padding: 20px;
  color: #d8ddeb;
  box-shadow:
    inset 0 0 0 1px rgba(176, 210, 255, 0.12),
    0 16px 38px rgba(7, 9, 32, 0.5);
}
.panel-card h4 {
  margin: 0 0 8px;
  color: #fff;
  font-size: 24px;
  letter-spacing: 0.6px;
}
.panel-card p {
  margin: 0 0 16px;
  color: #c0c8e5;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}
.feature-item {
  border: 1px solid rgba(151, 182, 255, 0.35);
  border-radius: 12px;
  background: rgba(23, 25, 59, 0.55);
  padding: 10px;
}
.feature-item span {
  color: #61d0ff;
  font-weight: 800;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
}
.feature-item p {
  margin: 6px 0 0;
  font-size: 13px;
  color: #d8def4;
}
.entry-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.points-empty {
  text-align: center;
  color: #b8cde9;
  padding: 24px 0;
}
.points-log-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 420px;
  overflow: auto;
}
.points-log-item {
  border: 1px solid rgba(126, 198, 255, 0.35);
  border-radius: 12px;
  padding: 10px 12px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  background: linear-gradient(130deg, rgba(22, 38, 87, 0.55), rgba(26, 29, 73, 0.58));
}
.points-log-desc {
  margin: 0;
  color: #e8f5ff;
}
.points-log-time {
  margin: 6px 0 0;
  color: #9cbde2;
  font-size: 12px;
}
.points-log-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.points-log-amount {
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
  color: #ffb2d9;
  font-size: 16px;
  font-weight: 800;
}
.points-log-amount.refund {
  color: #8fe8ff;
}
.points-log-balance {
  margin-top: 4px;
  color: #b7d6f4;
  font-size: 12px;
}
@keyframes floaty {
  0% { transform: translateY(0px) translateX(0px); }
  50% { transform: translateY(-14px) translateX(10px); }
  100% { transform: translateY(0px) translateX(0px); }
}
@media (max-width: 900px) {
  .workspace-shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #eceef4;
  }
  .head-right {
    gap: 6px;
  }
  .points-pill {
    min-height: 38px;
    padding: 0 10px;
  }
  .feature-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 640px) {
  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
