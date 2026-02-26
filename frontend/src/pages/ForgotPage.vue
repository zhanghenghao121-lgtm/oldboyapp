<template>
  <div class="page-shell">
    <el-card class="surface-card auth-card" shadow="never">
      <div class="title-block">
        <h2>找回密码</h2>
        <p>通过邮箱验证码重置账号密码。</p>
      </div>
      <el-form :model="form" label-width="90px" class="auth-form">
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="邮箱验证码">
          <div class="row"><el-input v-model="form.email_code" /><el-button @click="sendCode">发送验证码</el-button></div>
        </el-form-item>
        <el-form-item label="新密码"><el-input type="password" show-password v-model="form.new_password" /></el-form-item>
        <div class="actions">
          <el-button type="primary" class="main-btn" @click="submit">重置密码</el-button>
          <el-button link @click="$router.push('/login')">去登录</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { sendEmailCode, resetPassword } from '../api/auth'

const form = reactive({ email: '', email_code: '', new_password: '' })

const sendCode = async () => {
  if (!form.email.endsWith('.com')) return ElMessage.error('邮箱必须以.com结尾')
  try {
    await sendEmailCode({ email: form.email, scene: 'reset' })
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e)
  }
}

const submit = async () => {
  try {
    await resetPassword(form)
    ElMessage.success('重置成功，请登录')
  } catch (e) {
    ElMessage.error(e)
  }
}
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.auth-form { margin-top: 6px; }
.row{display:flex;gap:10px;width:100%}
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
