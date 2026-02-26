<template>
  <div class="page-shell" :style="pageStyle">
    <el-card class="surface-card auth-card" shadow="never">
      <div class="title-block">
        <h2>欢迎回来</h2>
        <p>登录后进入章鱼工作台。</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="auth-form">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input type="password" show-password v-model="form.password" /></el-form-item>
        <el-form-item label="图形验证码" prop="captcha_code">
          <div class="row">
            <el-input v-model="form.captcha_code" />
            <img :src="captchaImg" class="captcha" @click="loadCaptcha" />
          </div>
          <p class="captcha-tip">点击图片可刷新验证码</p>
        </el-form-item>
        <div class="actions">
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
.auth-form { margin-top: 6px; }
.row{display:flex;gap:10px;width:100%}
.captcha{
  width:180px;height:56px;border:1px solid var(--line-soft);border-radius:12px;cursor:pointer;object-fit:cover;
}
.captcha-tip{margin:8px 0 0;color:var(--ink-700);font-size:12px}
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
@media (max-width: 640px) {
  .captcha { width: 150px; height: 50px; }
}
</style>
