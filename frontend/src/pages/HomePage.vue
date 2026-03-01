<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="side-brand">
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

      <button class="side-btn disabled" disabled>后续功能（待设计）</button>
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
      </header>

      <section class="main-content">
        <div v-if="activePanel === 'script'" class="panel-card">
          <h4>剧本小优 · 霓虹控制台</h4>
          <p>切换到剧本小优后，你可以在二次元风创作场中快速完成剧本分镜和段落分镜。</p>
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
              <p>AI客服问答</p>
            </div>
          </div>
          <div class="entry-row">
            <el-button type="primary" class="main-btn" @click="$router.push('/script-optimizer')">进入完整剧本优化页</el-button>
            <el-button class="main-btn ghost-btn" @click="$router.push('/ai-customer')">进入 AI 客服</el-button>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { me, logout } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const activePanel = ref('script')
const user = ref(null)
const defaultAvatar = ref('')
const fallbackAvatar = '/octopus-avatar.svg'
const avatarLoadFailed = ref(false)

const panelTitle = computed(() => (activePanel.value === 'script' ? '剧本小优' : '工作台'))
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
  background: #ffffff;
  border-right: 1px solid #e9edf4;
  padding: 24px 14px;
  position: relative;
  z-index: 3;
}
.side-brand h2 {
  margin: 0;
  color: #1a2444;
  font-family: "Orbitron", "Plus Jakarta Sans", sans-serif;
}
.side-brand p {
  margin: 6px 0 18px;
  color: #7a84a2;
  font-size: 12px;
  letter-spacing: 1.2px;
}
.side-btn {
  width: 100%;
  border: 1px solid #dde4f0;
  border-radius: 10px;
  background: #fff;
  color: #2b3140;
  padding: 12px 10px;
  text-align: left;
  margin-bottom: 10px;
}
.side-btn.active {
  background: linear-gradient(130deg, #5f53ff, #3cc9ff, #ff4dc5);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 10px 24px rgba(69, 120, 255, 0.35);
}
.side-btn.disabled {
  opacity: 0.55;
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
.ghost-btn {
  background: linear-gradient(130deg, rgba(56, 161, 243, 0.56), rgba(73, 80, 200, 0.58));
  border: 1px solid rgba(161, 218, 255, 0.42);
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
