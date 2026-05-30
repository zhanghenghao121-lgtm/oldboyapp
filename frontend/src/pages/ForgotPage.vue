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
      <el-space wrap class="mb-3">
        <el-tag type="warning" effect="light">验证码 6 位</el-tag>
        <el-tag type="danger" effect="light">重置后请重新登录</el-tag>
      </el-space>
      <el-form :model="form" label-width="90px" class="auth-form pt-1">
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="邮箱验证码">
          <div class="d-flex gap-2 w-100 flex-wrap">
            <el-input v-model="form.email_code" maxlength="6" placeholder="请输入6位验证码" />
            <el-button type="primary" plain :loading="sendingCode" :disabled="codeCooldown > 0" @click="sendCode">
              {{ codeCooldown > 0 ? `${codeCooldown}秒后重发` : '发送验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="form.new_password" type="password" show-password placeholder="至少8位，含大小写字母和数字" />
        </el-form-item>
        <div class="actions mt-2">
          <el-button type="primary" class="main-btn" :loading="submitting" @click="submit">重置密码</el-button>
          <el-button link @click="$router.push('/login')">去登录</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { sendEmailCode, resetPassword } from '../api/auth'

const form = reactive({ email: '', email_code: '', new_password: '' })
const passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/
const sendingCode = ref(false)
const submitting = ref(false)
const codeCooldown = ref(0)
let codeTimer = null

const stopCodeTimer = () => {
  if (codeTimer) window.clearInterval(codeTimer)
  codeTimer = null
}

const startCodeCooldown = (seconds = 60) => {
  stopCodeTimer()
  codeCooldown.value = seconds
  codeTimer = window.setInterval(() => {
    codeCooldown.value -= 1
    if (codeCooldown.value <= 0) {
      codeCooldown.value = 0
      stopCodeTimer()
    }
  }, 1000)
}

const sendCode = async () => {
  if (codeCooldown.value > 0) return
  if (!form.email.endsWith('.com')) return ElMessage.error('邮箱必须以.com结尾')
  sendingCode.value = true
  try {
    await sendEmailCode({ email: form.email, scene: 'reset' })
    startCodeCooldown()
    ElMessage.success('验证码已发送')
  } catch (e) {
    if (String(e || '').includes('60秒')) startCodeCooldown()
    ElMessage.error(e)
  } finally {
    sendingCode.value = false
  }
}

const submit = async () => {
  if (!form.email.endsWith('.com')) {
    ElMessage.error('邮箱必须以.com结尾')
    return
  }
  if (!form.email_code.trim()) {
    ElMessage.error('请输入邮箱验证码')
    return
  }
  if (!passwordPattern.test(form.new_password)) {
    ElMessage.error('密码必须至少8位，且包含大小写字母和数字，例如 Zhh12345')
    return
  }
  submitting.value = true
  try {
    await resetPassword(form)
    ElMessage.success('重置成功，请登录')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    submitting.value = false
  }
}

onBeforeUnmount(stopCodeTimer)
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
</style>
