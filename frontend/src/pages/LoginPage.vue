<template>
  <div class="page-shell py-4" :style="pageStyle">
    <el-card class="surface-card auth-card shadow-sm" shadow="never">
      <div class="title-block title-center">
        <h2 class="fw-bold">欢迎回来</h2>
        <p class="mb-3">登录后进入章鱼结界。</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="auth-form pt-1">
        <el-form-item label="账号" prop="username" class="anime-input-item">
          <div class="anime-shell">
            <span class="spark spark-a"></span>
            <span class="spark spark-b"></span>
            <el-input v-model="form.username" placeholder="请输入用户名或邮箱" />
          </div>
        </el-form-item>
        <el-form-item label="密码" prop="password" class="anime-input-item">
          <div class="anime-shell">
            <span class="spark spark-a"></span>
            <span class="spark spark-b"></span>
            <el-input type="password" show-password v-model="form.password" placeholder="请输入密码" />
          </div>
        </el-form-item>

        <div class="actions mt-2">
          <el-button type="primary" class="main-btn login-btn" @click="submit">登录</el-button>
          <div class="sub-actions">
            <el-button link @click="$router.push('/forgot')">忘记密码</el-button>
            <el-button link @click="$router.push('/register')">去注册</el-button>
          </div>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '' })
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const rules = {
  username: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}

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
    const version = res.data._version
    backgroundUrl.value = withVersion(res.data.login || fallbackBg, version)
  } catch {
    backgroundUrl.value = withVersion(fallbackBg)
  }
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  try {
    await login(form)
    ElMessage.success('登录成功')
    router.push('/ai-manga')
  } catch (e) {
    ElMessage.error(e)
  }
}

onMounted(loadBackground)
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.title-center {
  text-align: center;
}
.actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}
.login-btn {
  min-height: 44px;
  font-size: 15px;
  border-radius: 12px;
  background: linear-gradient(130deg, #1f86e8, #2e6ee6 45%, #8759f4);
  box-shadow: 0 12px 26px rgba(34, 108, 225, 0.36);
}
.sub-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}
.anime-shell {
  width: 100%;
  position: relative;
}
.anime-shell::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 14px;
  background: linear-gradient(130deg, rgba(76, 219, 255, 0.9), rgba(137, 94, 255, 0.92), rgba(255, 105, 177, 0.9));
  filter: blur(0.5px);
  z-index: 0;
}
.anime-shell::after {
  content: '';
  position: absolute;
  top: -1px;
  right: -1px;
  width: 22px;
  height: 22px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(180, 233, 255, 0.8));
  clip-path: polygon(0 0, 100% 0, 100% 100%);
  border-top-right-radius: 14px;
  z-index: 3;
}
.spark {
  position: absolute;
  border-radius: 999px;
  background: #d5f7ff;
  box-shadow: 0 0 14px rgba(133, 223, 255, 0.92);
  z-index: 3;
  pointer-events: none;
}
.spark-a {
  width: 5px;
  height: 5px;
  top: 10px;
  left: 14px;
  animation: twinkle 1.9s ease-in-out infinite;
}
.spark-b {
  width: 4px;
  height: 4px;
  right: 30px;
  bottom: 12px;
  animation: twinkle 2.4s ease-in-out infinite;
  animation-delay: 0.45s;
}
.anime-input-item :deep(.el-input__wrapper) {
  position: relative;
  z-index: 2;
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid rgba(165, 225, 255, 0.58);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.26),
    0 0 12px rgba(105, 180, 255, 0.34) !important;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.46), rgba(232, 243, 255, 0.24)) !important;
  backdrop-filter: blur(8px);
}
.anime-input-item :deep(.el-input__inner) {
  color: #203554;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.anime-input-item :deep(.el-input__inner::placeholder) {
  color: rgba(40, 62, 92, 0.62);
}
.anime-input-item :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    inset 0 0 0 1px rgba(215, 241, 255, 0.86),
    0 0 0 2px rgba(122, 204, 255, 0.44),
    0 0 20px rgba(116, 167, 255, 0.48) !important;
}
@keyframes twinkle {
  0% { opacity: 0.26; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.25); }
  100% { opacity: 0.26; transform: scale(0.9); }
}
</style>
