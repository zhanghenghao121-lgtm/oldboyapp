<template>
  <div class="wrap">
    <el-card class="card">
      <h2>注册</h2>
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="密码"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item label="邮箱验证码">
          <div class="row">
            <el-input v-model="form.email_code" />
            <el-button @click="sendCode">发送验证码</el-button>
          </div>
        </el-form-item>
        <el-button type="primary" @click="submit">注册</el-button>
        <el-button link @click="$router.push('/login')">去登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { sendEmailCode, registerUser } from '../api/auth'

const form = reactive({ username: '', email: '', password: '', email_code: '' })

const sendCode = async () => {
  if (!form.email.endsWith('.com')) return ElMessage.error('邮箱必须以.com结尾')
  try {
    await sendEmailCode({ email: form.email, scene: 'register' })
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e)
  }
}

const submit = async () => {
  try {
    await registerUser(form)
    ElMessage.success('注册成功，请登录')
  } catch (e) {
    ElMessage.error(e)
  }
}
</script>

<style scoped>
.wrap{display:flex;justify-content:center;padding-top:60px}.card{width:480px}.row{display:flex;gap:8px;width:100%}
</style>
