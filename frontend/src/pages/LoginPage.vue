<template>
  <div class="login-shell" :style="pageStyle">
    <div class="floating-title">Login_</div>
    <section class="login-card">
      <aside class="poster">
        <div class="orbit orbit-a"></div>
        <div class="orbit orbit-b"></div>
        <div class="avatar-badge">章</div>
        <p class="poster-tip">Octopus Creative Portal</p>
      </aside>

      <main class="form-wrap">
        <h2>Welcome back to <span>school,</span></h2>
        <p class="social-row">
          <button class="social-btn" type="button">Google</button>
          <button class="social-btn" type="button">Facebook</button>
        </p>
        <div class="or-line">OR</div>

        <el-form ref="formRef" :model="form" :rules="rules" class="login-form">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名 / 邮箱" size="large" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" type="password" show-password placeholder="密码" size="large" />
          </el-form-item>
        </el-form>

        <p class="helper">
          Don’t have account sign up,
          <button type="button" @click="$router.push('/register')">here</button>
        </p>
        <button class="login-btn" type="button" @click="submit">Login</button>
        <button class="forgot-btn" type="button" @click="$router.push('/forgot')">忘记密码</button>
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const formRef = ref()
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const form = reactive({ username: '', password: '' })

const rules = {
  username: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(120deg, rgba(255,212,166,0.9), rgba(245,119,171,0.78)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = res.data.login || fallbackBg
  } catch {
    backgroundUrl.value = fallbackBg
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
  }
}

onMounted(loadBackground)
</script>

<style scoped>
.login-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px 16px;
  position: relative;
}
.floating-title {
  position: absolute;
  left: 34px;
  top: 38px;
  color: #fff;
  font-weight: 800;
  font-size: clamp(44px, 8vw, 68px);
  letter-spacing: 6px;
}
.login-card {
  width: min(1020px, 100%);
  min-height: 620px;
  border-radius: 28px;
  padding: 10px;
  background: #f6dce5;
  border: 10px solid #fff;
  box-shadow: 0 24px 44px rgba(43, 18, 50, 0.26);
  display: grid;
  grid-template-columns: 34% 66%;
}
.poster {
  border-radius: 22px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, #e54396, #f7aa3f);
  display: grid;
  place-items: center;
}
.avatar-badge {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  border: 5px solid #fff;
  background: rgba(0, 0, 0, 0.26);
  color: #fff;
  font-size: 72px;
  display: grid;
  place-items: center;
  font-weight: 700;
  z-index: 3;
}
.poster-tip {
  position: absolute;
  bottom: 20px;
  color: #fff;
  letter-spacing: 1px;
  font-weight: 600;
}
.orbit {
  position: absolute;
  border: 4px solid rgba(255, 255, 255, 0.92);
  border-radius: 50%;
}
.orbit-a {
  width: 180px;
  height: 460px;
  transform: rotate(20deg);
}
.orbit-b {
  width: 190px;
  height: 500px;
  transform: rotate(-24deg);
}
.form-wrap {
  padding: 28px 34px;
}
.form-wrap h2 {
  margin: 8px 0 20px;
  font-size: clamp(28px, 4vw, 48px);
}
.form-wrap h2 span {
  color: #ef8037;
}
.social-row {
  display: flex;
  gap: 14px;
}
.social-btn {
  border: 2px solid #1c1a1d;
  border-radius: 10px;
  background: #f5d9e2;
  height: 46px;
  min-width: 164px;
  font-size: 24px;
}
.or-line {
  font-size: 34px;
  margin: 12px 0;
  font-weight: 700;
  text-align: center;
}
:deep(.login-form .el-input__wrapper) {
  border-radius: 14px;
  box-shadow: inset 0 0 0 2px #000;
  background: #f6dce5;
  min-height: 58px;
}
.helper {
  margin: 8px 0 10px;
  font-size: 20px;
}
.helper button {
  border: none;
  background: transparent;
  color: #e8579f;
  font-size: 20px;
  cursor: pointer;
}
.login-btn {
  width: min(280px, 100%);
  margin-top: 6px;
  border: 2px solid #101014;
  border-radius: 18px;
  background: #f6dce5;
  box-shadow: 8px 8px 0 #101014;
  height: 64px;
  font-size: 44px;
  letter-spacing: 6px;
}
.forgot-btn {
  margin-top: 20px;
  border: none;
  background: transparent;
  color: #3a3a3f;
  font-size: 18px;
  text-decoration: underline;
}
@media (max-width: 980px) {
  .floating-title {
    display: none;
  }
  .login-card {
    grid-template-columns: 1fr;
  }
  .poster {
    min-height: 250px;
  }
}
</style>
