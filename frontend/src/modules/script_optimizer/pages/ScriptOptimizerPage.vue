<template>
  <div class="page-shell optimizer-shell" :style="pageStyle">
    <el-card class="surface-card module-card" shadow="never">
      <div class="title-block">
        <h2>剧本分镜工作台</h2>
        <p>支持剧本分镜和段落分镜，默认模型为 deepseek-reasoner。</p>
      </div>
      <div class="tool-actions">
        <el-button :type="mode === 'storyboard' ? 'primary' : 'default'" class="main-btn" @click="mode = 'storyboard'">剧本分镜</el-button>
        <el-button :type="mode === 'paragraph' ? 'primary' : 'default'" class="main-btn" @click="mode = 'paragraph'">段落分镜</el-button>
      </div>

      <el-form label-width="100px" class="mt-3">
        <el-form-item label="剧本内容">
          <el-input
            v-model="script"
            type="textarea"
            :rows="10"
            maxlength="10000"
            show-word-limit
            placeholder="请输入剧本（最多10000字）"
          />
        </el-form-item>
        <el-form-item label="提示词">
          <el-input
            v-model="prompt"
            type="textarea"
            :rows="3"
            placeholder="可自定义提示词"
          />
        </el-form-item>
      </el-form>

      <div class="d-flex gap-2 mt-2 flex-wrap">
        <el-button type="primary" class="main-btn" :loading="loading" @click="runOptimize">开始生成</el-button>
        <el-button @click="$router.push('/home')">返回首页</el-button>
      </div>

      <el-divider />
      <h3 class="result-title">输出结果</h3>
      <el-input v-model="result" type="textarea" :rows="14" readonly placeholder="结果将显示在这里" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { generateParagraphStoryboard, generateStoryboard } from '../../../api/scriptOptimizer'
import { getSiteBackgrounds } from '../../../api/site'
import { me } from '../../../api/auth'

const router = useRouter()
const mode = ref('storyboard')
const loading = ref(false)
const script = ref('')
const result = ref('')
const backgroundUrl = ref('')
const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}

const defaultPrompts = {
  storyboard: '将输入的剧本生成分镜提示词，模板是分镜号、分镜画面、景别、特效。',
  paragraph: '将输入的剧本按照**秒～**秒的格式，生成15s以内的分镜提示词。',
}

const prompt = ref(defaultPrompts.storyboard)
watch(mode, (val) => {
  prompt.value = defaultPrompts[val]
})

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(rgba(255,255,255,0.36), rgba(255,255,255,0.36)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    const version = res.data._version
    backgroundUrl.value = withVersion(res.data.script_optimizer || res.data.home || '', version)
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
  loading.value = true
  try {
    const payload = { script: script.value, prompt: prompt.value }
    const res =
      mode.value === 'storyboard'
        ? await generateStoryboard(payload)
        : await generateParagraphStoryboard(payload)
    result.value = res.data.result
    ElMessage.success('生成完成')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    await Promise.all([loadBackground(), me()])
  } catch {
    router.push('/login')
  }
})
</script>

<style scoped>
.module-card { width: min(680px, 100%); }
.optimizer-shell {
  min-height: 100vh;
}
.tool-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.result-title {
  margin: 0 0 10px;
  color: var(--ink-700);
}
</style>
