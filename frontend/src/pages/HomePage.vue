<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="side-aura side-aura-top"></div>
      <div class="side-aura side-aura-bottom"></div>
      <div class="side-brand">
        <span class="brand-badge">Neon Console</span>
        <h2>章鱼工作台</h2>
        <p>智能服务工作区</p>
      </div>

      <button class="side-btn active" type="button">AI章鱼助手</button>
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
          <h3>AI章鱼助手</h3>
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
        <div class="panel-card">
          <h4>AI章鱼助手 · 霓虹会话台</h4>
          <p>支持文本对话、图片视频文档上传，并可在无法回答时自动转人工处理。</p>
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
const user = ref(null)
const defaultAvatar = ref('')
const fallbackAvatar = '/octopus-avatar.svg'
const avatarLoadFailed = ref(false)
const pointsDialogVisible = ref(false)
const pointsLogs = ref([])
const pointsLoading = ref(false)

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
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(135, 201, 255, 0.26);
  background: rgba(18, 31, 78, 0.58);
  color: #eef7ff;
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}
.side-btn.active {
  border-color: rgba(146, 226, 255, 0.66);
  box-shadow: 0 0 18px rgba(74, 193, 255, 0.24);
}
.main-panel {
  position: relative;
  overflow: hidden;
  padding: 24px;
}
.neon-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
}
.blob {
  position: absolute;
  border-radius: 999px;
  filter: blur(18px);
  opacity: 0.4;
}
.blob-a {
  width: 260px;
  height: 260px;
  left: 10%;
  top: 14%;
  background: rgba(71, 211, 255, 0.3);
}
.blob-b {
  width: 320px;
  height: 320px;
  right: 8%;
  top: 6%;
  background: rgba(255, 123, 226, 0.2);
}
.blob-c {
  width: 360px;
  height: 360px;
  left: 36%;
  bottom: -12%;
  background: rgba(115, 117, 255, 0.18);
}
.main-header,
.main-content {
  position: relative;
  z-index: 1;
}
.main-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}
.headline .kicker {
  margin: 0 0 8px;
  color: #8fd6ff;
  font-size: 12px;
  letter-spacing: 2px;
}
.headline h3 {
  margin: 0;
  color: #f5fbff;
  font-size: clamp(26px, 4vw, 38px);
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
}
.head-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.points-pill {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border: 1px solid rgba(132, 210, 255, 0.34);
  border-radius: 999px;
  background: rgba(9, 19, 54, 0.6);
  color: #eaf6ff;
  cursor: pointer;
}
.points-label {
  color: #9ecdf7;
}
.points-value {
  font-weight: 700;
}
.avatar-entry {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(10, 18, 49, 0.58);
  border: 1px solid rgba(134, 208, 255, 0.2);
  cursor: pointer;
}
.name {
  color: #eef7ff;
}
.panel-card {
  padding: clamp(22px, 4vw, 34px);
  border-radius: 28px;
  border: 1px solid rgba(137, 208, 255, 0.22);
  background: linear-gradient(145deg, rgba(17, 24, 61, 0.92), rgba(10, 18, 48, 0.86));
  box-shadow: 0 28px 90px rgba(0, 0, 0, 0.3);
}
.panel-card h4 {
  margin: 0 0 10px;
  color: #f4fbff;
  font-size: 24px;
}
.panel-card > p {
  margin: 0;
  color: #aac0e8;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 14px;
  margin-top: 24px;
}
.feature-item {
  padding: 18px;
  border-radius: 20px;
  border: 1px solid rgba(140, 208, 255, 0.18);
  background: rgba(18, 31, 76, 0.58);
}
.feature-item span {
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(77, 193, 255, 0.18);
  color: #9fe0ff;
  font-weight: 700;
}
.feature-item p {
  margin: 14px 0 0;
  color: #e8f4ff;
}
.entry-row {
  margin-top: 24px;
}
.main-btn {
  min-width: 170px;
}
.points-empty {
  padding: 30px 0;
  text-align: center;
  color: #8ea7cd;
}
.points-log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.points-log-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(12, 19, 53, 0.6);
}
.points-log-desc,
.points-log-time,
.points-log-balance,
.points-log-amount {
  margin: 0;
}
.points-log-desc {
  color: #eef7ff;
}
.points-log-time,
.points-log-balance {
  color: #96b1d7;
  font-size: 12px;
}
.points-log-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.points-log-amount {
  color: #ffd776;
  font-weight: 700;
}
.points-log-amount.refund {
  color: #79e7b2;
}
@media (max-width: 900px) {
  .workspace-shell {
    grid-template-columns: 1fr;
  }
  .main-header {
    flex-direction: column;
    align-items: flex-start;
  }
  .head-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
