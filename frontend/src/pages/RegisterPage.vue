<template>
  <div class="page-shell py-4">
    <el-card class="surface-card auth-card shadow-sm" shadow="never">
      <div class="title-block">
        <h2 class="fw-bold">创建账号</h2>
        <p class="mb-3">设置你的专属账号并绑定邮箱。</p>
      </div>
      <el-alert
        title="密码规则：至少8位，需包含大写字母、小写字母和数字"
        type="info"
        :closable="false"
        show-icon
        class="mb-3"
      />
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="auth-form pt-1">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="邮箱" prop="email"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="邮箱验证码" prop="email_code">
          <div class="d-flex gap-2 w-100 flex-wrap">
            <el-input v-model="form.email_code" />
            <el-button type="primary" plain @click="sendCode">发送验证码</el-button>
          </div>
        </el-form-item>
        <div class="actions mt-2">
          <el-button type="primary" class="main-btn" @click="submit">注册</el-button>
          <el-button link @click="$router.push('/login')">去登录</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { sendEmailCode, registerUser } from '../api/auth'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', email: '', password: '', email_code: '' })
const usernamePattern = /^[A-Za-z0-9_]{3,20}$/
const passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度应为3-20位', trigger: 'blur' },
    { pattern: usernamePattern, message: '用户名仅支持字母/数字/下划线', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (!value || value.endsWith('.com')) {
          callback()
          return
        }
        callback(new Error('邮箱必须以.com结尾'))
      },
      trigger: 'blur',
    },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    {
      validator: (_, value, callback) => {
        if (!value || passwordPattern.test(value)) {
          callback()
          return
        }
        callback(new Error('密码至少8位，且包含大小写字母和数字'))
      },
      trigger: 'blur',
    },
  ],
  email_code: [
    { required: true, message: '请输入邮箱验证码', trigger: 'blur' },
    { min: 6, max: 6, message: '验证码为6位', trigger: 'blur' },
  ],
}

const sendCode = async () => {
  if (!form.username || !usernamePattern.test(form.username)) {
    return ElMessage.error('请先输入合法用户名（3-20位字母/数字/下划线）')
  }
  if (!form.email.endsWith('.com')) return ElMessage.error('邮箱必须以.com结尾')
  try {
    await sendEmailCode({ username: form.username, email: form.email, scene: 'register' })
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e)
  }
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await registerUser(form)
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (e) {
    ElMessage.error(e)
  }
}
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
