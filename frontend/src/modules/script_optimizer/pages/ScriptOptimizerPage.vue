<template>
  <div class="page-shell optimizer-shell" :style="pageStyle">
    <div class="neon-lights">
      <span class="orb orb-a"></span>
      <span class="orb orb-b"></span>
      <span class="orb orb-c"></span>
    </div>
    <el-card class="surface-card module-card neon-card" shadow="never">
      <header class="panel-head">
        <span></span>
        <el-button class="home-btn" @click="goHome">返回首页</el-button>
      </header>
      <div class="title-block">
        <h2>剧本分镜工作台</h2>
        <p>支持剧本分镜和段落分镜。</p>
      </div>
      <div class="tool-actions">
        <el-button :type="mode === 'storyboard' ? 'primary' : 'default'" class="main-btn mode-btn" @click="mode = 'storyboard'">剧本分镜</el-button>
        <el-button :type="mode === 'paragraph' ? 'primary' : 'default'" class="main-btn mode-btn" @click="mode = 'paragraph'">段落分镜</el-button>
      </div>
      <div class="points-panel">
        <span>当前积分：{{ userPoints.toFixed(2) }}</span>
        <span>预计消耗：{{ estimatedCost.toFixed(2) }}</span>
      </div>

      <el-form label-width="100px" class="mt-3 neon-form">
        <el-form-item label="剧本内容" class="neon-item">
          <el-input
            v-model="script"
            type="textarea"
            :rows="10"
            maxlength="10000"
            show-word-limit
            placeholder="请输入剧本（最多10000字）"
          />
        </el-form-item>
        <el-form-item label="提示词" class="neon-item">
          <el-input
            v-model="prompt"
            type="textarea"
            :rows="3"
            placeholder="可自定义提示词"
          />
        </el-form-item>
      </el-form>

      <div class="d-flex gap-2 mt-2 flex-wrap">
        <el-button type="primary" class="main-btn action-btn" :loading="loading" @click="runOptimize">开始生成</el-button>
      </div>

      <el-divider />
      <h3 class="result-title">输出结果</h3>
      <el-input v-model="result" type="textarea" :rows="14" readonly placeholder="结果将显示在这里" class="neon-item" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { generateParagraphStoryboard, generateStoryboard } from '../../../api/scriptOptimizer'
import { getSiteBackgrounds } from '../../../api/site'
import { me } from '../../../api/auth'

const router = useRouter()
const mode = ref('storyboard')
const loading = ref(false)
const script = ref('')
const result = ref('')
const backgroundUrl = ref('')
const userPoints = ref(0)
const COST_PER_CHAR = 0.01
const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}

const defaultStoryboardPrompt = ref('将输入的剧本生成分镜提示词，模板是分镜号、分镜画面、景别、特效。')
const defaultParagraphPrompt = ref('将输入的剧本按照**秒～**秒的格式，生成15s以内的分镜提示词。')
const prompt = ref(defaultStoryboardPrompt.value)
watch(mode, (val) => {
  prompt.value = val === 'storyboard' ? defaultStoryboardPrompt.value : defaultParagraphPrompt.value
})

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.36), rgba(255,255,255,0.36)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)
const estimatedCost = computed(() => script.value.length * COST_PER_CHAR)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    const version = res.data._version
    backgroundUrl.value = withVersion(res.data.script_optimizer || res.data.home || '', version)
    defaultStoryboardPrompt.value = res.data.script_storyboard_prompt || defaultStoryboardPrompt.value
    defaultParagraphPrompt.value = res.data.script_paragraph_prompt || defaultParagraphPrompt.value
    prompt.value = mode.value === 'storyboard' ? defaultStoryboardPrompt.value : defaultParagraphPrompt.value
  } catch {
    backgroundUrl.value = ''
  }
}

const runOptimize = async () => {
  if (!script.value.trim()) {
    ElMessage.warning('请先输入剧本内容')
    return
  }
  if (script.value.length > 10000) {
    ElMessage.warning('剧本最多10000字')
    return
  }
  if (estimatedCost.value > userPoints.value) {
    try {
      await ElMessageBox.confirm(
        '积分不够，是否需要充值？',
        '积分不足',
        {
          confirmButtonText: '是，去充值',
          cancelButtonText: '否，继续编辑',
          customClass: 'anime-neon-message-box',
        }
      )
      router.push('/recharge')
    } catch {
      // user chose to stay on current page
    }
    return
  }

  loading.value = true
  try {
    const payload = { script: script.value, prompt: prompt.value }
    const res =
      mode.value === 'storyboard'
        ? await generateStoryboard(payload)
        : await generateParagraphStoryboard(payload)
    result.value = res.data.result
    if (typeof res.data.remaining_points === 'number') {
      userPoints.value = res.data.remaining_points
    } else {
      const meRes = await me()
      userPoints.value = Number(meRes.data.user.points || 0)
    }
    ElMessage.success('生成完成')
  } catch (e) {
    const message = String(e || '')
    if (message.includes('积分不足')) {
      try {
        await ElMessageBox.confirm(
          '积分不够，是否需要充值？',
          '积分不足',
          {
            confirmButtonText: '是，去充值',
            cancelButtonText: '否，继续编辑',
            customClass: 'anime-neon-message-box',
          }
        )
        router.push('/recharge')
      } catch {
        // user chose to stay on current page
      }
      return
    }
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

const hasUnsavedContent = computed(() => {
  const hasScript = !!script.value.trim()
  const hasPromptChanged = mode.value === 'storyboard'
    ? prompt.value.trim() !== defaultStoryboardPrompt.value.trim()
    : prompt.value.trim() !== defaultParagraphPrompt.value.trim()
  const hasResult = !!result.value.trim()
  return hasScript || hasPromptChanged || hasResult
})

const goHome = async () => {
  if (!hasUnsavedContent.value) {
    router.push('/home')
    return
  }
  try {
    await ElMessageBox.confirm(
      '检测到你有未保存的内容，仍然返回首页吗？',
      '离开确认',
      {
        confirmButtonText: '仍然退出',
        cancelButtonText: '继续编辑',
        type: 'warning',
      }
    )
    router.push('/home')
  } catch {
    // user canceled
  }
}

onMounted(async () => {
  try {
    const [, meRes] = await Promise.all([loadBackground(), me()])
    userPoints.value = Number(meRes.data.user.points || 0)
  } catch {
    router.push('/login')
  }
})
</script>

<style scoped>
.module-card { width: min(760px, 100%); }
.optimizer-shell {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
}
.neon-lights {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}
.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(18px);
  opacity: 0.58;
  animation: drift 9s ease-in-out infinite;
}
.orb-a {
  width: 220px;
  height: 220px;
  left: 6%;
  top: 15%;
  background: rgba(80, 215, 255, 0.38);
}
.orb-b {
  width: 260px;
  height: 260px;
  right: 8%;
  top: 8%;
  background: rgba(255, 84, 214, 0.34);
  animation-delay: 1.2s;
}
.orb-c {
  width: 240px;
  height: 240px;
  right: 24%;
  bottom: -60px;
  background: rgba(255, 184, 75, 0.28);
  animation-delay: 2.2s;
}
.neon-card {
  position: relative;
  z-index: 2;
  border: 1px solid rgba(143, 168, 255, 0.45);
  background: linear-gradient(150deg, rgba(24, 23, 57, 0.86), rgba(15, 12, 38, 0.88));
  box-shadow: inset 0 0 0 1px rgba(168, 222, 255, 0.16), 0 20px 46px rgba(4, 8, 29, 0.58);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.home-btn {
  border: 1px solid rgba(160, 228, 255, 0.9);
  border-radius: 999px;
  color: #eaf3ff;
  background: linear-gradient(130deg, rgba(65, 193, 255, 0.9), rgba(121, 102, 255, 0.9), rgba(255, 82, 208, 0.88));
  box-shadow: 0 0 0 1px rgba(206, 241, 255, 0.36), 0 0 18px rgba(108, 201, 255, 0.52);
}
.home-btn:hover {
  transform: translateY(-1px);
  filter: brightness(1.05);
}
.tool-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.points-panel {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.points-panel span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  color: #e7f3ff;
  font-size: 13px;
  border: 1px solid rgba(134, 204, 255, 0.46);
  background: linear-gradient(130deg, rgba(36, 98, 165, 0.48), rgba(42, 40, 117, 0.52));
  box-shadow: inset 0 0 0 1px rgba(166, 225, 255, 0.12), 0 0 14px rgba(101, 194, 255, 0.22);
}
.mode-btn {
  border-radius: 12px;
  min-width: 112px;
}
.neon-form :deep(.el-form-item__label) {
  color: #b7c5ee;
  font-weight: 700;
}
.neon-item :deep(.el-input__wrapper),
.neon-item :deep(.el-textarea__inner) {
  border-radius: 12px;
  border: 1px solid rgba(149, 194, 255, 0.55);
  background: linear-gradient(145deg, rgba(22, 22, 52, 0.8), rgba(14, 14, 36, 0.84));
  box-shadow: inset 0 0 0 1px rgba(183, 214, 255, 0.12), 0 0 14px rgba(95, 182, 255, 0.25);
  color: #eef3ff;
}
.neon-item :deep(.el-input__inner),
.neon-item :deep(.el-textarea__inner) {
  color: #edf2ff;
}
.neon-item :deep(.el-input__inner::placeholder),
.neon-item :deep(.el-textarea__inner::placeholder) {
  color: rgba(192, 206, 241, 0.72);
}
.neon-item :deep(.el-input__wrapper.is-focus),
.neon-item :deep(.el-textarea__inner:focus) {
  box-shadow: inset 0 0 0 1px rgba(201, 237, 255, 0.5), 0 0 0 2px rgba(110, 203, 255, 0.25), 0 0 20px rgba(97, 187, 255, 0.42);
}
.action-btn {
  min-width: 128px;
}
.result-title {
  margin: 0 0 10px;
  color: #d8e4ff;
  text-shadow: 0 0 10px rgba(114, 193, 255, 0.34);
}
@keyframes drift {
  0% { transform: translateY(0) translateX(0); }
  50% { transform: translateY(-16px) translateX(12px); }
  100% { transform: translateY(0) translateX(0); }
}
</style>
