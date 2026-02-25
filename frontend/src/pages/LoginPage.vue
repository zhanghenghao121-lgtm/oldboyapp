<template>
  <div class="wrap">
    <el-card class="card">
      <h2>登录</h2>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input type="password" show-password v-model="form.password" /></el-form-item>
        <el-form-item label="图形验证码" prop="captcha_code">
          <div class="row">
            <el-input v-model="form.captcha_code" />
            <img :src="captchaImg" class="captcha" @click="loadCaptcha" />
          </div>
          <p class="captcha-tip">点击图片可刷新验证码</p>
        </el-form-item>
        <el-button type="primary" @click="submit">登录</el-button>
        <el-button link @click="$router.push('/register')">去注册</el-button>
        <el-button link @click="$router.push('/forgot')">忘记密码</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCaptcha, login } from '../api/auth'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '', captcha_id: '', captcha_code: '' })
const captchaImg = ref('')
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  captcha_code: [{ required: true, message: '请输入图形验证码', trigger: 'blur' }],
}

const loadCaptcha = async () => {
  try {
    const res = await getCaptcha()
    form.captcha_id = res.data.captcha_id
    captchaImg.value = res.data.image_base64
  } catch (e) {
    ElMessage.error(e)
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

onMounted(loadCaptcha)
</script>

<style scoped>
.wrap{display:flex;justify-content:center;padding-top:60px}.card{width:520px}.row{display:flex;gap:8px;width:100%}.captcha{width:180px;height:56px;border:1px solid #ddd;cursor:pointer}.captcha-tip{margin:8px 0 0;color:#888;font-size:12px}
</style>
