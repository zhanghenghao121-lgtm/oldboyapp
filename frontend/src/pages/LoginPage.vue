<template>
  <div class="page-shell py-4" :style="pageStyle">
    <el-card class="surface-card auth-card shadow-sm" shadow="never">
      <div class="title-block title-center">
        <h2 class="fw-bold">欢迎回来</h2>
        <p class="mb-3">登录后进入章鱼结界。</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px" class="auth-form pt-1">
        <el-form-item label="用户名" prop="username" class="anime-input-item">
          <div class="anime-shell">
            <span class="spark spark-a"></span>
            <span class="spark spark-b"></span>
            <el-input v-model="form.username" placeholder="请输入用户名" />
          </div>
        </el-form-item>
        <el-form-item label="密码" prop="password" class="anime-input-item">
          <div class="anime-shell">
            <span class="spark spark-a"></span>
            <span class="spark spark-b"></span>
            <el-input type="password" show-password v-model="form.password" placeholder="请输入密码" />
          </div>
        </el-form-item>

        <el-form-item label="结界认证">
          <div class="energy-entry">
            <el-tag v-if="energyVerified" type="success" effect="dark" class="verify-tag">结界稳定</el-tag>
            <el-tag v-else type="warning" effect="dark" class="verify-tag">待验证</el-tag>
            <el-button class="main-btn" type="primary" @click="openEnergyDialog">开启结界</el-button>
          </div>
          <p class="captcha-tip mb-0">拖动能量晶片封印缺口，完成后可登录</p>
        </el-form-item>

        <div class="actions mt-2">
          <el-button type="primary" class="main-btn login-btn" @click="submit">登录</el-button>
          <div class="sub-actions">
            <el-button link @click="$router.push('/forgot')">忘记密码</el-button>
            <el-button link @click="$router.push('/register')">去注册</el-button>
          </div>
        </div>
      </el-form>
    </el-card>

    <el-dialog v-model="energyDialogVisible" title="结界认证" width="560px" :close-on-click-modal="false">
      <div class="energy-panel">
        <p class="energy-title">拖动能量晶片，封印缺口</p>
        <div class="energy-stage" :class="{ shaking: stageShake }" v-if="energyBg" :style="stageStyle">
          <div class="energy-rune"></div>
          <span
            v-for="dot in energyParticles"
            :key="dot.id"
            class="energy-dot"
            :style="{
              left: `${dot.x}%`,
              top: `${dot.y}%`,
              width: `${dot.size}px`,
              height: `${dot.size}px`,
              animationDelay: `${dot.delay}ms`,
              animationDuration: `${dot.duration}ms`,
            }"
          />
          <img :src="energyBg" class="energy-bg" />
          <img :src="energyPiece" class="energy-piece" :style="pieceStyle" />
        </div>
        <div class="energy-ctrl mt-3">
          <el-slider
            v-model="sliderX"
            :min="0"
            :max="sliderMax"
            @input="onSliderInput"
            :show-tooltip="false"
          />
          <div class="d-flex gap-2 mt-2">
            <el-button plain :class="{ spinning: refreshing }" @click="loadEnergySlider">刷新</el-button>
            <el-button type="primary" class="main-btn" :loading="verifying" :disabled="sliderX <= 0" @click="verifyEnergy">验证结界</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getEnergySlider, login, verifyEnergySlider } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const formRef = ref()
const form = reactive({ username: '', password: '' })
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const energyDialogVisible = ref(false)
const energyVerified = ref(false)
const captchaTicket = ref('')
const verifying = ref(false)
const refreshing = ref(false)
const stageShake = ref(false)
const sliderX = ref(0)
const energyToken = ref('')
const energyBg = ref('')
const energyPiece = ref('')
const energyY = ref(0)
const energyW = ref(320)
const energyH = ref(160)
const pieceSize = ref(44)
const track = ref([])
const trackStartAt = ref(0)
const energyParticles = ref([])

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.24), rgba(255,255,255,0.24)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const sliderMax = computed(() => Math.max(0, energyW.value - pieceSize.value))
const stageStyle = computed(() => ({ width: `${energyW.value}px`, height: `${energyH.value}px` }))
const pieceStyle = computed(() => ({ left: `${sliderX.value}px`, top: `${energyY.value}px`, width: `${pieceSize.value}px`, height: `${pieceSize.value}px` }))

const buildEnergyParticles = () => {
  energyParticles.value = Array.from({ length: 20 }, (_, idx) => ({
    id: `${Date.now()}-${idx}`,
    x: Math.round(Math.random() * 96 + 2),
    y: Math.round(Math.random() * 90 + 5),
    size: Math.round(Math.random() * 3 + 1),
    delay: Math.round(Math.random() * 800),
    duration: Math.round(Math.random() * 2200 + 1800),
  }))
}

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = res.data.login || fallbackBg
  } catch {
    backgroundUrl.value = fallbackBg
  }
}

const loadEnergySlider = async () => {
  refreshing.value = true
  try {
    const res = await getEnergySlider()
    energyToken.value = res.data.token
    energyBg.value = res.data.bg
    energyPiece.value = res.data.piece
    energyY.value = res.data.y
    energyW.value = res.data.width
    energyH.value = res.data.height
    pieceSize.value = res.data.piece_size
    sliderX.value = 0
    track.value = []
    trackStartAt.value = Date.now()
    stageShake.value = false
    buildEnergyParticles()
  } catch (e) {
    ElMessage.error(e)
  } finally {
    refreshing.value = false
  }
}

const onSliderInput = (value) => {
  if (!trackStartAt.value) trackStartAt.value = Date.now()
  track.value.push({ x: Number(value), t: Date.now() - trackStartAt.value })
}

const openEnergyDialog = async () => {
  energyDialogVisible.value = true
  await loadEnergySlider()
}

const verifyEnergy = async () => {
  if (!energyToken.value) return ElMessage.error('验证码未加载，请刷新')
  verifying.value = true
  try {
    const res = await verifyEnergySlider({ token: energyToken.value, offset_x: sliderX.value, track: track.value })
    captchaTicket.value = res.data.captcha_ticket
    energyVerified.value = true
    energyDialogVisible.value = false
    ElMessage.success('结界稳定！')
  } catch (e) {
    ElMessage.error(e)
    stageShake.value = true
    setTimeout(() => {
      stageShake.value = false
    }, 350)
    await loadEnergySlider()
  } finally {
    verifying.value = false
  }
}

const submit = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  if (!energyVerified.value || !captchaTicket.value) {
    ElMessage.warning('请先完成结界认证')
    await openEnergyDialog()
    return
  }

  try {
    await login({ ...form, captcha_ticket: captchaTicket.value })
    ElMessage.success('登录成功')
    router.push('/home')
  } catch (e) {
    const msg = String(e || '')
    if (msg.includes('结界验证')) {
      energyVerified.value = false
      captchaTicket.value = ''
      await openEnergyDialog()
    }
    ElMessage.error(e)
  }
}

onMounted(loadBackground)
</script>

<style scoped>
.auth-card { padding: 10px 6px 4px; }
.title-center {
  text-align: center;
}
.energy-entry {
  width: 100%;
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.verify-tag {
  min-width: 86px;
  text-align: center;
}
.captcha-tip{margin:8px 0 0;color:var(--ink-700);font-size:12px}
.actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 10px;
}
.login-btn {
  min-height: 44px;
  font-size: 15px;
  border-radius: 12px;
  background: linear-gradient(130deg, #1f86e8, #2e6ee6 45%, #8759f4);
  box-shadow: 0 12px 26px rgba(34, 108, 225, 0.36);
}
.sub-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}
.anime-shell {
  width: 100%;
  position: relative;
}
.anime-shell::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 14px;
  background: linear-gradient(130deg, rgba(76, 219, 255, 0.9), rgba(137, 94, 255, 0.92), rgba(255, 105, 177, 0.9));
  filter: blur(0.5px);
  z-index: 0;
}
.anime-shell::after {
  content: '';
  position: absolute;
  top: -1px;
  right: -1px;
  width: 22px;
  height: 22px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.92), rgba(180, 233, 255, 0.8));
  clip-path: polygon(0 0, 100% 0, 100% 100%);
  border-top-right-radius: 14px;
  z-index: 3;
}
.spark {
  position: absolute;
  border-radius: 999px;
  background: #d5f7ff;
  box-shadow: 0 0 14px rgba(133, 223, 255, 0.92);
  z-index: 3;
  pointer-events: none;
}
.spark-a {
  width: 5px;
  height: 5px;
  top: 10px;
  left: 14px;
  animation: twinkle 1.9s ease-in-out infinite;
}
.spark-b {
  width: 4px;
  height: 4px;
  right: 30px;
  bottom: 12px;
  animation: twinkle 2.4s ease-in-out infinite;
  animation-delay: 0.45s;
}
.anime-input-item :deep(.el-input__wrapper) {
  position: relative;
  z-index: 2;
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid rgba(165, 225, 255, 0.58);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.26),
    0 0 12px rgba(105, 180, 255, 0.34) !important;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.46), rgba(232, 243, 255, 0.24)) !important;
  backdrop-filter: blur(8px);
}
.anime-input-item :deep(.el-input__inner) {
  color: #203554;
  font-weight: 600;
  letter-spacing: 0.4px;
}
.anime-input-item :deep(.el-input__inner::placeholder) {
  color: rgba(40, 62, 92, 0.62);
}
.anime-input-item :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    inset 0 0 0 1px rgba(215, 241, 255, 0.86),
    0 0 0 2px rgba(122, 204, 255, 0.44),
    0 0 20px rgba(116, 167, 255, 0.48) !important;
}
.energy-panel {
  padding: 4px;
}
.energy-title {
  margin: 0 0 10px;
  color: var(--ink-700);
  font-weight: 700;
}
.energy-stage {
  position: relative;
  border-radius: 14px;
  border: 1px solid rgba(172, 228, 255, 0.75);
  overflow: hidden;
  box-shadow: 0 12px 34px rgba(18, 67, 138, 0.28);
  background: #0f1832;
}
.energy-stage.shaking {
  animation: stage-shake 0.32s ease-in-out;
}
.energy-rune {
  position: absolute;
  width: 140px;
  height: 140px;
  left: calc(50% - 70px);
  top: calc(50% - 70px);
  border-radius: 50%;
  border: 1px solid rgba(144, 214, 255, 0.34);
  box-shadow: 0 0 24px rgba(110, 190, 255, 0.26);
  animation: rune-pulse 3s ease-in-out infinite;
  z-index: 2;
  pointer-events: none;
}
.energy-dot {
  position: absolute;
  border-radius: 50%;
  background: rgba(140, 222, 255, 0.88);
  filter: blur(0.2px);
  box-shadow: 0 0 8px rgba(114, 208, 255, 0.7);
  animation: dot-float linear infinite;
  z-index: 2;
  pointer-events: none;
}
.energy-bg {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.energy-piece {
  position: absolute;
  z-index: 3;
  border-radius: 10px;
  box-shadow: 0 0 0 1px rgba(236, 248, 255, 0.95), 0 0 20px rgba(88, 208, 255, 0.72);
}
:deep(.el-slider__runway) {
  height: 8px;
  background: rgba(19, 57, 108, 0.22);
}
:deep(.el-slider__bar) {
  background: linear-gradient(130deg, #57b3ff, #8e78ff);
}
:deep(.el-slider__button) {
  border-color: #66bfff;
  box-shadow: 0 0 0 4px rgba(106, 194, 255, 0.18);
}
.spinning {
  animation: btn-spin 0.6s linear;
}
@keyframes rune-pulse {
  0% { opacity: 0.08; transform: scale(0.96); }
  50% { opacity: 0.34; transform: scale(1.03); }
  100% { opacity: 0.08; transform: scale(0.96); }
}
@keyframes dot-float {
  0% { transform: translateY(0px); opacity: 0.2; }
  50% { transform: translateY(-8px); opacity: 0.85; }
  100% { transform: translateY(-14px); opacity: 0.1; }
}
@keyframes stage-shake {
  0% { transform: translateX(0); }
  25% { transform: translateX(-5px); }
  50% { transform: translateX(5px); }
  75% { transform: translateX(-3px); }
  100% { transform: translateX(0); }
}
@keyframes btn-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes twinkle {
  0% { opacity: 0.26; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.25); }
  100% { opacity: 0.26; transform: scale(0.9); }
}
</style>
