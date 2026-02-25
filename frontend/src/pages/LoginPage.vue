<template>
  <div class="wrap">
    <el-card class="card">
      <h2>登录</h2>
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
        <el-form-item label="密码"><el-input type="password" show-password v-model="form.password" /></el-form-item>
        <el-form-item label="图形验证码">
          <div class="row">
            <el-input v-model="form.captcha_code" />
            <img :src="captchaImg" class="captcha" @click="loadCaptcha" />
          </div>
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
import { ElMessage } from 'element-plus'
import { getCaptcha, login } from '../api/auth'

const form = reactive({ username: '', password: '', captcha_id: '', captcha_code: '' })
const captchaImg = ref('')

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
  try {
    await login(form)
    ElMessage.success('登录成功')
    location.href = '/home'
  } catch (e) {
    ElMessage.error(e)
    loadCaptcha()
  }
}

onMounted(loadCaptcha)
</script>

<style scoped>
.wrap{display:flex;justify-content:center;padding-top:60px}.card{width:480px}.row{display:flex;gap:8px;width:100%}.captcha{width:120px;height:40px;border:1px solid #ddd;cursor:pointer}
</style>
