<template>
  <div class="page-shell py-4">
    <el-card class="surface-card auth-card" shadow="never">
      <div class="title-block">
        <h2 class="fw-bold">修改密码</h2>
        <p class="mb-3">通过邮箱验证码修改当前账号密码。</p>
      </div>

      <el-alert
        title="验证码 5 分钟有效，修改后请使用新密码重新登录"
        type="warning"
        :closable="false"
        show-icon
        class="mb-3"
      />

      <el-form :model="form" label-width="96px" class="auth-form pt-1">
        <el-form-item label="当前邮箱">
          <el-input :model-value="email" disabled />
        </el-form-item>

        <el-form-item label="邮箱验证码">
          <div class="d-flex gap-2 w-100 flex-wrap">
            <el-input v-model="form.email_code" maxlength="6" placeholder="请输入6位验证码" />
            <el-button type="primary" plain :loading="sendingCode" @click="sendCode">发送验证码</el-button>
          </div>
        </el-form-item>

        <el-form-item label="新密码">
          <el-input v-model="form.new_password" type="password" show-password placeholder="至少8位，含大小写字母和数字" />
        </el-form-item>

        <el-form-item label="确认新密码">
          <el-input v-model="form.confirm_password" type="password" show-password placeholder="请再次输入新密码" />
        </el-form-item>

        <div class="actions mt-2">
          <el-button type="primary" class="main-btn" :loading="submitting" @click="submit">确认修改</el-button>
          <el-button @click="$router.push('/profile')">返回用户信息</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { changePassword, me, sendEmailCode } from '../api/auth'

const router = useRouter()
const email = ref('')
const sendingCode = ref(false)
const submitting = ref(false)

const form = reactive({
  email_code: '',
  new_password: '',
  confirm_password: '',
})

const sendCode = async () => {
  if (!email.value) {
    ElMessage.error('未获取到当前用户邮箱')
    return
  }
  sendingCode.value = true
  try {
    await sendEmailCode({ email: email.value, scene: 'reset' })
    ElMessage.success('验证码已发送')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    sendingCode.value = false
  }
}

const submit = async () => {
  if (!form.email_code.trim()) {
    ElMessage.error('请输入邮箱验证码')
    return
  }
  if (form.new_password !== form.confirm_password) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  submitting.value = true
  try {
    await changePassword({
      email_code: form.email_code.trim(),
      new_password: form.new_password,
      confirm_password: form.confirm_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    router.push('/login')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    const res = await me()
    email.value = (res.data.user?.email || '').trim()
    if (!email.value) {
      ElMessage.error('当前账号未绑定邮箱，无法修改密码')
      router.push('/profile')
    }
  } catch {
    router.push('/login')
  }
})
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
</style>
