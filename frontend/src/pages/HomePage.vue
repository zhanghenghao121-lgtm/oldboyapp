<template>
  <div class="home-shell page-shell" :style="pageStyle">
    <button class="logout-button" type="button" :disabled="loggingOut" @click="handleLogout">
      {{ loggingOut ? '退出中...' : '退出' }}
    </button>

    <main class="home-panel">
      <div class="title-block home-title">
        <span>OCTOPUS WORKBENCH</span>
        <h1>章鱼工作台</h1>
      </div>

      <section class="desk-actions" aria-label="工作台入口">
        <button class="desk-button space-button" type="button" @click="enterFeature('workbench', '/octopus-space')">
          <span class="button-mark">O</span>
          <strong>章鱼空间</strong>
          <small>进入章鱼记</small>
        </button>

        <button class="desk-button planet-button" type="button" @click="enterFeature('workbench', '/octopus-planet')">
          <span class="button-mark">星</span>
          <strong>章鱼星球</strong>
          <small>查看灵感粒子</small>
        </button>

        <button class="desk-button storyboard-button" type="button" @click="enterFeature('storyboard', '/storyboard')">
          <span class="button-mark">AI</span>
          <strong>AI故事板</strong>
          <small>进入创作台</small>
        </button>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logout, me } from '../api/auth'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const currentUser = ref(null)
const loggingOut = ref(false)

const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.22), rgba(255,255,255,0.22)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = withVersion(res.data.login || fallbackBg, res.data._version)
  } catch {
    backgroundUrl.value = withVersion(fallbackBg)
  }
}

const loadUser = async () => {
  try {
    const res = await me()
    currentUser.value = res.data?.user || null
  } catch {
    currentUser.value = null
  }
}

const hasFeature = (feature) => {
  const user = currentUser.value || {}
  if (user.is_staff || user.is_superuser) return true
  if (feature === 'workbench') return Boolean(user.can_access_workbench || user.features?.workbench)
  if (feature === 'storyboard') return Boolean(user.can_access_storyboard || user.features?.storyboard)
  return false
}

const showPermissionDenied = () => {
  ElMessageBox.alert('账号无此功能权限', '权限提示', {
    type: 'warning',
    confirmButtonText: '知道了',
    customClass: 'anime-neon-message-box',
  })
}

const enterFeature = (feature, path) => {
  if (!hasFeature(feature)) {
    showPermissionDenied()
    return
  }
  router.push(path)
}

const handleLogout = async () => {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await logout()
    router.push('/login')
  } catch (error) {
    ElMessage.error(String(error || '退出登录失败'))
  } finally {
    loggingOut.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadBackground(), loadUser()])
})
</script>

<style scoped>
.home-shell {
  position: relative;
  padding: 28px;
}

.logout-button {
  position: absolute;
  top: 24px;
  right: 28px;
  z-index: 2;
  min-height: 40px;
  padding: 0 18px;
  border: 1px solid rgba(232, 244, 255, 0.42);
  border-radius: 999px;
  color: #f7fbff;
  background: rgba(12, 18, 42, 0.62);
  box-shadow: 0 14px 32px rgba(4, 12, 42, 0.24);
  backdrop-filter: blur(12px);
  cursor: pointer;
  font-weight: 800;
}

.logout-button:hover:not(:disabled) {
  border-color: rgba(255, 255, 255, 0.78);
  background: rgba(34, 44, 86, 0.72);
}

.logout-button:disabled {
  opacity: .68;
  cursor: wait;
}

.home-panel {
  width: min(980px, 100%);
  padding: clamp(28px, 6vw, 54px);
  border: 1px solid rgba(154, 188, 255, 0.3);
  border-radius: 26px;
  background: linear-gradient(145deg, rgba(23, 29, 61, 0.86), rgba(18, 13, 45, 0.84));
  box-shadow: var(--shadow-soft);
  backdrop-filter: blur(14px);
}

.home-title {
  text-align: center;
  margin-bottom: clamp(28px, 5vw, 46px);
}

.home-title span {
  display: block;
  margin-bottom: 10px;
  color: #a8dfff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .18em;
}

.home-title h1 {
  margin: 0;
  color: #f4f6ff;
  font-family: "Orbitron", "ZCOOL KuaiLe", "Plus Jakarta Sans", sans-serif;
  font-size: clamp(40px, 7vw, 72px);
  line-height: 1.05;
  text-shadow: 0 0 18px rgba(124, 202, 255, 0.62);
}

.desk-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(18px, 4vw, 34px);
}

.desk-button {
  position: relative;
  min-height: clamp(190px, 26vw, 260px);
  padding: 28px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-end;
  overflow: hidden;
  border: 1px solid rgba(160, 222, 255, 0.42);
  border-radius: 24px;
  color: #fff;
  text-align: left;
  cursor: pointer;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.16),
    0 18px 44px rgba(4, 12, 42, 0.42);
  transition: transform .24s ease, box-shadow .24s ease, border-color .24s ease;
}

.desk-button::before {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.18), transparent 42%),
    linear-gradient(180deg, transparent, rgba(3, 8, 31, 0.32));
  pointer-events: none;
}

.desk-button::after {
  content: "";
  position: absolute;
  right: -42px;
  top: -42px;
  width: 142px;
  height: 142px;
  border: 1px solid rgba(225, 245, 255, 0.34);
  border-radius: 999px;
  box-shadow: 0 0 38px rgba(113, 205, 255, 0.26);
}

.desk-button:hover {
  transform: translateY(-5px);
  border-color: rgba(210, 241, 255, 0.78);
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.22),
    0 24px 58px rgba(4, 12, 42, 0.58),
    0 0 28px rgba(91, 184, 255, 0.28);
}

.space-button {
  background: linear-gradient(135deg, rgba(57, 180, 255, 0.92), rgba(81, 88, 238, 0.92), rgba(132, 75, 232, 0.88));
}

.planet-button {
  background: linear-gradient(135deg, rgba(43, 216, 189, 0.94), rgba(86, 116, 255, 0.92), rgba(255, 214, 92, 0.86));
}

.storyboard-button {
  background: linear-gradient(135deg, rgba(68, 184, 255, 0.94), rgba(139, 89, 255, 0.92), rgba(255, 78, 198, 0.88));
}

.button-mark,
.desk-button strong,
.desk-button small {
  position: relative;
  z-index: 1;
}

.button-mark {
  position: absolute;
  top: 24px;
  left: 26px;
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(231, 248, 255, 0.54);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.16);
  box-shadow: 0 12px 28px rgba(3, 12, 40, 0.2);
  color: #f4fbff;
  font-size: 22px;
  font-weight: 900;
}

.desk-button strong {
  font-size: clamp(28px, 4vw, 40px);
  line-height: 1.05;
}

.desk-button small {
  margin-top: 10px;
  color: rgba(240, 248, 255, 0.82);
  font-size: 15px;
  font-weight: 700;
}

@media (max-width: 760px) {
  .home-shell {
    padding: 72px 18px 18px;
  }

  .logout-button {
    top: 18px;
    right: 18px;
  }

  .desk-actions {
    grid-template-columns: 1fr;
  }

  .desk-button {
    min-height: 170px;
  }
}

@media (min-width: 761px) and (max-width: 1080px) {
  .desk-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
