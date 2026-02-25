<template>
  <div class="wrap">
    <el-card class="card">
      <h2>欢迎章鱼</h2>
      <p v-if="user">当前用户：{{ user.username }} / {{ user.email }}</p>
      <el-divider />
      <h3>功能模块</h3>
      <div class="module-list">
        <el-button type="primary" @click="$router.push('/script-optimizer')">剧本优化</el-button>
      </div>
      <el-divider />
      <el-button type="danger" @click="doLogout">退出登录</el-button>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { me, logout } from '../api/auth'

const router = useRouter()
const user = ref(null)

onMounted(async () => {
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
.wrap{display:flex;justify-content:center;padding-top:60px}.card{width:560px}.module-list{display:flex;gap:10px;flex-wrap:wrap}
</style>
