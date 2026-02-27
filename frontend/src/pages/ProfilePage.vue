<template>
  <div class="page-shell profile-shell" :style="pageStyle">
    <el-card class="surface-card profile-card" shadow="never">
      <header class="profile-header">
        <h2>用户信息</h2>
      </header>

      <div class="avatar-panel">
        <div class="avatar-wrap">
          <el-avatar :src="form.avatar_url || defaultAvatar || fallbackAvatar" :size="96" />
          <button class="avatar-edit-btn" type="button" @click="pickAvatar">
            <el-icon><Edit /></el-icon>
          </button>
          <input ref="avatarInputRef" type="file" accept="image/*" class="file-hidden" @change="handleAvatarUpload" />
        </div>
        <p class="avatar-tip">点击头像右下角图标上传（最大 5MB）</p>
      </div>

      <el-form :model="form" label-width="90px" class="mt-2 dark-form">
        <el-form-item label="用户名">
          <el-input v-model="form.username" maxlength="20" show-word-limit />
        </el-form-item>
        <el-form-item label="用户邮箱">
          <el-input v-model="form.email" disabled />
        </el-form-item>
        <el-form-item label="用户签名">
          <el-input v-model="form.signature" maxlength="120" show-word-limit />
        </el-form-item>
      </el-form>

      <div class="d-flex gap-2 flex-wrap justify-content-center">
        <el-button type="primary" class="main-btn" :loading="saving" @click="save">保存资料</el-button>
        <el-button @click="$router.push('/home')">返回首页</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Edit } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { me, updateProfile } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'
import { uploadToCos } from '../api/storage'

const router = useRouter()
const saving = ref(false)
const backgroundUrl = ref('')
const defaultAvatar = ref('')
const fallbackAvatar = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/images/octopus-default.png'
const avatarInputRef = ref()
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
          `linear-gradient(rgba(20,20,24,0.7), rgba(20,20,24,0.7)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : { background: 'linear-gradient(145deg, #1b1b1f, #101013)' }
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

const pickAvatar = () => {
  if (avatarInputRef.value) avatarInputRef.value.click()
}

const handleAvatarUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('头像图片不能超过5MB')
    return
  }

  try {
    const res = await uploadToCos(file, 'images/avatars')
    await updateProfile({ avatar_url: res.data.url })
    form.avatar_url = res.data.url
    ElMessage.success('头像上传成功')
  } catch (e) {
    ElMessage.error(e)
  }
}

const save = async () => {
  saving.value = true
  try {
    await updateProfile({
      username: form.username,
      signature: form.signature,
    })
    ElMessage.success('保存成功')
    await loadMe()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    saving.value = false
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
  width: min(760px, 100%);
  background: rgba(27, 27, 31, 0.88);
  border: 1px solid rgba(134, 134, 145, 0.42);
}
.profile-header h2 {
  margin: 0;
  text-align: center;
  color: #ececf1;
  letter-spacing: 2px;
}
.avatar-panel {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.avatar-wrap {
  position: relative;
}
.avatar-edit-btn {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  border: 1px solid #686874;
  background: #2f2f37;
  color: #f0f0f4;
  display: grid;
  place-items: center;
}
.avatar-tip {
  margin-top: 8px;
  color: #9e9eaa;
  font-size: 12px;
}
.file-hidden {
  display: none;
}
.dark-form {
  margin-top: 8px;
}
.dark-form :deep(.el-form-item__label) {
  color: #ceced6;
}
.dark-form :deep(.el-input__wrapper) {
  background: #23232a;
  box-shadow: inset 0 0 0 1px #4a4a56 !important;
}
.dark-form :deep(.el-input__inner) {
  color: #ececf2;
}
.dark-form :deep(.el-input.is-disabled .el-input__wrapper) {
  background: #1f1f25;
}
</style>
