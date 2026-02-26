<template>
  <div class="page-shell py-4" :style="pageStyle">
    <el-card class="surface-card auth-card shadow-sm" shadow="never">
      <div class="title-block">
        <h2 class="fw-bold">欢迎回来</h2>
        <p class="mb-3">登录后进入章鱼工作台。</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="auth-form pt-1">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input type="password" show-password v-model="form.password" /></el-form-item>
        <el-form-item label="图形验证码" prop="captcha_code">
          <div class="d-flex flex-wrap gap-2 w-100">
            <el-input v-model="form.captcha_code" class="captcha-input" />
            <img :src="captchaImg" class="captcha" @click="loadCaptcha" />
          </div>
          <p class="captcha-tip mb-0">点击图片可刷新验证码，看不清请刷新后再输入</p>
        </el-form-item>
        <div class="actions mt-2">
          <el-button type="primary" class="main-btn" @click="submit">登录</el-button>
          <el-button link @click="$router.push('/register')">去注册</el-button>
          <el-button link @click="$router.push('/forgot')">忘记密码</el-button>
          <el-button link type="primary" @click="$router.push('/admin/login')">管理后台</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCaptcha, login } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '', captcha_id: '', captcha_code: '' })
const captchaImg = ref('')
const backgroundUrl = ref('')
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入图形验证码', trigger: 'blur' }],
}

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.24), rgba(255,255,255,0.24)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadCaptcha = async () => {
  try {
    const res = await getCaptcha()
    form.captcha_id = res.data.captcha_id
    captchaImg.value = res.data.image_base64
  } catch (e) {
    ElMessage.error(e)
  }
}

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = res.data.login || ''
  } catch {
    backgroundUrl.value = ''
  }
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await login(form)
    ElMessage.success('登录成功')
    router.push('/home')
  } catch (e) {
    ElMessage.error(e)
    loadCaptcha()
  }
}

onMounted(async () => {
  await Promise.all([loadCaptcha(), loadBackground()])
})
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.captcha{
  width: 210px;
  height: 64px;
  border: 1px solid #b8cbe4;
  border-radius: 12px;
  cursor: pointer;
  object-fit: cover;
  background: #fff;
  filter: contrast(1.3) saturate(1.2);
  image-rendering: -webkit-optimize-contrast;
}
.captcha-tip{margin:8px 0 0;color:var(--ink-700);font-size:12px}
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
:deep(.captcha-input .el-input__inner) {
  letter-spacing: 2px;
  font-weight: 700;
  font-size: 17px;
  text-transform: uppercase;
}
@media (max-width: 640px) {
  .captcha { width: 170px; height: 56px; }
}
</style>
