<template>
  <div class="page-shell" :style="pageStyle">
    <el-card class="surface-card home-card" shadow="never">
      <div class="title-block">
        <h2>欢迎章鱼</h2>
        <p v-if="user">当前用户：{{ user.username }} / {{ user.email }}</p>
      </div>
      <el-divider />
      <h3 class="section-title">功能模块</h3>
      <div class="module-list">
        <el-button type="primary" class="main-btn" @click="$router.push('/script-optimizer')">剧本优化</el-button>
      </div>
      <el-divider />
      <el-button type="danger" plain @click="doLogout">退出登录</el-button>
    </el-card>
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
const backgroundUrl = ref('')

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.24), rgba(255,255,255,0.24)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = res.data.home || ''
  } catch {
    backgroundUrl.value = ''
  }
}

onMounted(async () => {
  loadBackground()
  try {
    const res = await me()
    user.value = res.data.user
  } catch {
    router.push('/login')
  }
})

const doLogout = async () => {
  try {
    await logout()
    ElMessage.success('已退出')
    router.push('/login')
  } catch (e) {
    ElMessage.error(e)
  }
}
</script>

<style scoped>
.home-card { width: min(700px, 100%); }
.section-title { margin: 0 0 12px; color: var(--ink-700); }
.module-list{display:flex;gap:10px;flex-wrap:wrap}
</style>
