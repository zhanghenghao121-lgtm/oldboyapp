<template>
  <div class="workspace-shell">
    <aside class="sidebar">
      <div class="side-brand">
        <h2>Octopus</h2>
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
      <header class="main-header">
        <h3>{{ panelTitle }}</h3>
        <el-dropdown @command="onUserAction">
          <div class="avatar-entry">
            <el-avatar :src="user?.avatar_url || defaultAvatar" :size="40" />
            <span class="name">{{ user?.username || '用户' }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">用户信息</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <section class="main-content">
        <div v-if="activePanel === 'script'" class="panel-card">
          <h4>剧本优化页面</h4>
          <p>已切换至剧本小优工作区。你可以开始剧本分镜与段落分镜创作。</p>
          <el-button type="primary" class="main-btn" @click="$router.push('/script-optimizer')">进入完整剧本优化页</el-button>
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

const panelTitle = computed(() => (activePanel.value === 'script' ? '剧本小优' : '工作台'))

const loadMe = async () => {
  const res = await me()
  user.value = res.data.user
}

const loadSiteConfig = async () => {
  try {
    const res = await getSiteBackgrounds()
    defaultAvatar.value = res.data.default_avatar || ''
  } catch {
    defaultAvatar.value = ''
  }
}

const doLogout = async () => {
  await logout()
  ElMessage.success('已退出')
  router.push('/login')
}

const onUserAction = async (command) => {
  if (command === 'profile') return router.push('/profile')
  if (command === 'logout') {
    try {
      await doLogout()
    } catch (e) {
      ElMessage.error(e)
    }
  }
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
  background: #18191f;
}
.sidebar {
  background: #ffffff;
  border-right: 1px solid #eceef4;
  padding: 24px 14px;
}
.side-brand h2 {
  margin: 0;
  color: #1e2330;
}
.side-brand p {
  margin: 6px 0 18px;
  color: #79839a;
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
  background: linear-gradient(130deg, #2b63d9, #3d86f0);
  border-color: transparent;
  color: #fff;
}
.side-btn.disabled {
  opacity: 0.55;
}
.main-panel {
  padding: 18px 22px;
}
.main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.main-header h3 {
  margin: 0;
  color: #eef2ff;
}
.avatar-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
}
.avatar-entry .name {
  color: #fff;
  font-weight: 600;
}
.main-content {
  margin-top: 18px;
}
.panel-card {
  border: 1px solid #363a49;
  border-radius: 14px;
  background: #22242d;
  padding: 18px;
  color: #d8ddeb;
}
.panel-card h4 {
  margin: 0 0 8px;
  color: #fff;
}
.panel-card p {
  margin: 0 0 16px;
  color: #aeb6cc;
}
@media (max-width: 900px) {
  .workspace-shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: 0;
    border-bottom: 1px solid #eceef4;
  }
}
</style>
