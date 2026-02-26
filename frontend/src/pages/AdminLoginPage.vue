<template>
  <div class="page-shell admin-shell">
    <el-card class="surface-card admin-login-card" shadow="never">
      <div class="title-block">
        <h2>管理后台登录</h2>
        <p>仅管理员可访问后台配置。</p>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码" prop="password"><el-input type="password" show-password v-model="form.password" /></el-form-item>
        <div class="actions">
          <el-button type="primary" class="main-btn" @click="submit">登录后台</el-button>
          <el-button link @click="$router.push('/login')">返回网站登录</el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { consoleLogin } from '../api/console'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  try {
    await consoleLogin(form)
    ElMessage.success('后台登录成功')
    router.push('/admin/dashboard')
  } catch (e) {
    ElMessage.error(e)
  }
}
</script>

<style scoped>
.admin-shell {
  background:
    radial-gradient(700px 260px at 5% -5%, rgba(14, 102, 106, 0.22), transparent 58%),
    radial-gradient(660px 260px at 100% 0%, rgba(227, 124, 65, 0.18), transparent 58%),
    linear-gradient(130deg, #ebf4fb, #f7efe5);
}
.admin-login-card {
  width: min(560px, 100%);
}
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
