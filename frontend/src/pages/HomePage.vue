<template>
  <div class="page-shell py-4" :style="pageStyle">
    <el-card class="surface-card home-card shadow-sm" shadow="never">
      <div class="title-block">
        <h2 class="fw-bold">欢迎章鱼</h2>
        <p v-if="user" class="mb-0">当前用户：{{ user.username }} / {{ user.email }}</p>
      </div>
      <el-row :gutter="12" class="mb-2">
        <el-col :xs="24" :sm="12">
          <el-card class="metric-card" shadow="never">
            <el-statistic title="登录状态" value="在线" />
          </el-card>
        </el-col>
        <el-col :xs="24" :sm="12">
          <el-card class="metric-card" shadow="never">
            <el-statistic title="可用模块" :value="1" />
          </el-card>
        </el-col>
      </el-row>
      <el-divider />
      <h3 class="section-title fw-semibold">功能模块</h3>
      <div class="module-list d-flex flex-wrap gap-2">
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
.metric-card { border: 1px solid var(--line-soft); border-radius: 12px; }
</style>
