<template>
  <div class="page-shell py-4">
    <el-card class="surface-card auth-card shadow-sm" shadow="never">
      <div class="title-block">
        <h2 class="fw-bold">找回密码</h2>
        <p class="mb-3">通过邮箱验证码重置账号密码。</p>
      </div>
      <el-alert
        title="邮箱必须以 .com 结尾，验证码5分钟内有效"
        type="warning"
        :closable="false"
        show-icon
        class="mb-3"
      />
      <el-form :model="form" label-width="90px" class="auth-form pt-1">
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="邮箱验证码">
          <div class="d-flex gap-2 w-100 flex-wrap">
            <el-input v-model="form.email_code" />
            <el-button type="primary" plain @click="sendCode">发送验证码</el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码"><el-input type="password" show-password v-model="form.new_password" /></el-form-item>
        <div class="actions mt-2">
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
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
