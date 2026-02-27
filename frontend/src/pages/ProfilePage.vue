<template>
  <div class="page-shell profile-shell" :style="pageStyle">
    <el-card class="surface-card profile-card" shadow="never">
      <header class="profile-header">
        <h2>用户信息</h2>
        <el-dropdown @command="onAction">
          <div class="avatar-entry">
            <el-avatar :src="form.avatar_url || defaultAvatar" :size="44" />
            <span>{{ form.username || '用户' }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="home">返回首页</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>

      <el-form :model="form" label-width="90px" class="mt-2">
        <el-form-item label="头像地址">
          <el-input v-model="form.avatar_url" placeholder="请输入头像 URL" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="form.username" maxlength="20" />
        </el-form-item>
        <el-form-item label="用户邮箱">
          <el-input v-model="form.email" />
        </el-form-item>
        <el-form-item label="用户签名">
          <el-input v-model="form.signature" maxlength="120" show-word-limit />
        </el-form-item>
      </el-form>

      <div class="d-flex gap-2 flex-wrap">
        <el-button type="primary" class="main-btn" :loading="saving" @click="save">保存资料</el-button>
        <el-button @click="$router.push('/home')">返回首页</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { me, logout, updateProfile } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const saving = ref(false)
const backgroundUrl = ref('')
const defaultAvatar = ref('')
const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}
const form = reactive({
  avatar_url: '',
  username: '',
  email: '',
  signature: '',
})

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.3), rgba(255,255,255,0.3)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    const version = res.data._version
    backgroundUrl.value = withVersion(res.data.profile || res.data.home || '', version)
    defaultAvatar.value = res.data.default_avatar || ''
  } catch {
    backgroundUrl.value = ''
  }
}

const loadMe = async () => {
  const res = await me()
  Object.assign(form, res.data.user)
}

const save = async () => {
  saving.value = true
  try {
    await updateProfile(form)
    ElMessage.success('保存成功')
    await loadMe()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
  }
}

const onAction = async (cmd) => {
  if (cmd === 'home') return router.push('/home')
  if (cmd === 'logout') {
    try {
      await logout()
      router.push('/login')
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
.profile-shell {
  min-height: 100vh;
}
.profile-card {
  width: min(720px, 100%);
}
.profile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.avatar-entry {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 8px 4px 4px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
}
</style>
