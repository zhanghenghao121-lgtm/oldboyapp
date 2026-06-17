<template>
  <div class="space-shell page-shell" :style="pageStyle">
    <main class="space-card surface-card">
      <div class="title-block">
        <span>OCTOPUS SPACE</span>
        <h1>章鱼空间</h1>
        <p>等待开发</p>
      </div>
      <el-button class="main-btn back-btn" type="primary" @click="router.push('/')">返回工作台</el-button>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getSiteBackgrounds } from '../api/site'

const router = useRouter()
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')

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

onMounted(loadBackground)
</script>

<style scoped>
.space-shell {
  padding: 28px;
}

.space-card {
  width: min(560px, 100%);
  padding: 38px;
  text-align: center;
}

.title-block span {
  display: block;
  margin-bottom: 10px;
  color: #a8dfff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .18em;
}

.title-block h1 {
  margin: 0;
  color: #f4f6ff;
  font-family: "Orbitron", "ZCOOL KuaiLe", "Plus Jakarta Sans", sans-serif;
  font-size: clamp(38px, 8vw, 56px);
  text-shadow: 0 0 18px rgba(124, 202, 255, 0.62);
}

.title-block p {
  margin: 14px 0 28px;
  color: var(--ink-700);
  font-size: 17px;
}

.back-btn {
  min-height: 44px;
  padding: 0 28px;
  border-radius: 12px;
}
</style>
