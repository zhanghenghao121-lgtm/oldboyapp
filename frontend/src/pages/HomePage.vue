<template>
  <div class="home-shell" :style="pageStyle">
    <header class="home-header container-xl">
      <div class="brand-block">
        <p class="brand-kicker">Octopus Studio</p>
        <h2>创作控制台</h2>
      </div>
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

    <main class="container-xl home-main">
      <div class="hero">
        <p class="hero-kicker">欢迎回来</p>
        <h1>让每一段剧本都拥有电影级分镜表达</h1>
        <p class="hero-sub" v-if="user">{{ user.email }} · {{ user.signature || '今天也要高效创作' }}</p>
      </div>

      <el-row :gutter="14" class="mt-2">
        <el-col :xs="24" :md="8">
          <el-card class="metric-card" shadow="never">
            <p class="metric-label">登录状态</p>
            <h3>在线</h3>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-card class="metric-card" shadow="never">
            <p class="metric-label">可用模块</p>
            <h3>1</h3>
          </el-card>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-card class="metric-card" shadow="never">
            <p class="metric-label">创作模式</p>
            <h3>二次元能量风</h3>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="modules-card mt-3" shadow="never">
        <h3 class="section-title fw-semibold">功能模块</h3>
        <div class="module-list">
          <button class="module-item" @click="$router.push('/script-optimizer')">
            <span>剧本优化</span>
            <small>剧本分镜 / 段落分镜</small>
          </button>
        </div>
      </el-card>
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
const user = ref(null)
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const defaultAvatar = ref('')

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(5,12,29,0.52), rgba(5,12,29,0.52)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = res.data.home || fallbackBg
    defaultAvatar.value = res.data.default_avatar || ''
  } catch {
    backgroundUrl.value = fallbackBg
  }
}

const loadMe = async () => {
  const res = await me()
  user.value = res.data.user
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
    await Promise.all([loadBackground(), loadMe()])
  } catch {
    router.push('/login')
  }
})
</script>

<style scoped>
.home-shell {
  min-height: 100vh;
  color: #eef6ff;
}
.home-header {
  padding: 20px 16px 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.brand-kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 1.3px;
  opacity: 0.74;
}
.brand-block h2 {
  margin: 2px 0 0;
}
.avatar-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 999px;
  padding: 4px 10px 4px 4px;
  cursor: pointer;
}
.avatar-entry .name {
  font-weight: 600;
  color: #fff;
}
.home-main {
  padding: 8px 16px 34px;
}
.hero h1 {
  margin: 8px 0 6px;
  font-size: clamp(28px, 4vw, 42px);
  line-height: 1.15;
}
.hero-kicker {
  margin: 0;
  opacity: 0.82;
}
.hero-sub {
  margin: 0;
  color: #cce3ff;
}
.metric-card {
  border: 1px solid rgba(213, 233, 255, 0.44);
  border-radius: 14px;
  background: rgba(8, 22, 53, 0.46);
  color: #f4f8ff;
}
.metric-label {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.4px;
  color: #aed0ff;
}
.metric-card h3 {
  margin: 0;
}
.modules-card {
  border: 1px solid rgba(213, 233, 255, 0.44);
  border-radius: 18px;
  background: rgba(8, 22, 53, 0.5);
  color: #f4f8ff;
}
.section-title {
  margin: 0 0 12px;
}
.module-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}
.module-item {
  border: 1px solid rgba(167, 210, 255, 0.42);
  background: linear-gradient(140deg, rgba(42, 117, 204, 0.56), rgba(110, 78, 180, 0.44));
  border-radius: 14px;
  color: #fff;
  padding: 14px;
  display: flex;
  flex-direction: column;
  text-align: left;
}
.module-item span {
  font-weight: 700;
}
.module-item small {
  margin-top: 6px;
  color: #e7f2ff;
}
</style>
