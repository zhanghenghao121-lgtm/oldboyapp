<template>
  <div class="page-shell blogger-shell">
    <el-card class="surface-card blogger-card" shadow="never">
      <header class="head">
        <div>
          <h2>章鱼博主</h2>
          <p>两段式创作：先出图文，再生成视频</p>
        </div>
        <el-button class="neon-btn" @click="$router.push('/home')">返回首页</el-button>
      </header>

      <section class="section-block">
        <h3>Step 1 图文生成</h3>
        <el-form label-width="92px" class="neon-form">
          <el-form-item label="热点来源">
            <el-radio-group v-model="inputMode">
              <el-radio-button label="manual">手动输入</el-radio-button>
              <el-radio-button label="auto">自动热搜</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="热点词">
            <div class="hotword-row">
              <el-input
                v-if="inputMode === 'manual'"
                v-model="manualHotWord"
                maxlength="50"
                placeholder="输入你要创作的热点词"
              />
              <template v-else>
                <el-select
                  v-model="selectedHotWord"
                  :placeholder="hotwords.length ? '请选择热点词' : '点击“获取热搜”后选择'"
                  filterable
                  style="width: 100%"
                >
                  <el-option
                    v-for="item in hotwords"
                    :key="item.word"
                    :label="item.word"
                    :value="item.word"
                  />
                </el-select>
                <el-button class="neon-btn" :loading="hotwordsLoading" @click="loadHotwords(false)">获取热搜</el-button>
                <el-button class="neon-btn" :loading="hotwordsLoading" @click="loadHotwords(true)">重新获取</el-button>
              </template>
            </div>
          </el-form-item>

          <el-form-item label="风格设定">
            <el-input
              v-model="stylePrompt"
              maxlength="400"
              placeholder="例如：热血动漫，霓虹夜景，角色特写"
            />
          </el-form-item>

          <el-form-item label="图片数量">
            <el-slider v-model="imageCount" :min="1" :max="3" show-stops show-input />
          </el-form-item>

          <el-form-item label="图片比例">
            <el-radio-group v-model="ratio">
              <el-radio-button label="9:16">9:16</el-radio-button>
              <el-radio-button label="16:9">16:9</el-radio-button>
            </el-radio-group>
          </el-form-item>

          <el-form-item>
            <el-button class="main-btn" type="primary" :loading="creatingPost" @click="createPost">一键生成图文</el-button>
          </el-form-item>
        </el-form>
      </section>

      <section v-if="postState.postId" class="section-block">
        <div class="status-line">
          <span>任务状态：{{ postStatusLabel }}{{ postStageLabel ? ` / ${postStageLabel}` : '' }}</span>
          <div class="entry-row">
            <el-button class="neon-btn" @click="queryPost">刷新</el-button>
            <el-button
              v-if="isPostGenerating"
              class="neon-btn danger-btn"
              :loading="cancelingPost"
              @click="cancelPostTask"
            >
              取消图文
            </el-button>
          </div>
        </div>
        <div v-if="isPostGenerating" class="gen-status">
          <span class="gen-badge">生成中</span>
          <span class="gen-text">{{ generatingStageLabel }}</span>
          <span class="dot-flow"><i></i><i></i><i></i></span>
        </div>

        <div v-if="postState.errorText" class="error-line">{{ postState.errorText }}</div>
        <h4 v-if="postState.title">标题：{{ postState.title }}</h4>
        <p v-if="postState.copy" class="copy-text">{{ postState.copy }}</p>

        <div v-if="postState.images.length" class="image-grid">
          <button
            v-for="img in postState.images"
            :key="img.id"
            class="img-item"
            :class="{ active: img.cos_key === postState.selectedCoverKey }"
            @click="chooseCover(img.cos_key)"
          >
            <img :src="img.url" alt="cover" />
            <span>设为首帧</span>
          </button>
        </div>

        <div class="entry-row" v-if="postState.status === 'success'">
          <el-button class="main-btn" type="primary" :loading="creatingVideo" @click="createVideo">
            继续生成视频
          </el-button>
        </div>
      </section>

      <section v-if="videoState.taskId" class="section-block">
        <h3>Step 2 视频生成</h3>
        <el-form inline class="video-form">
          <el-form-item label="时长">
            <el-select v-model="videoConfig.duration" style="width: 120px">
              <el-option :value="5" label="5 秒" />
              <el-option :value="8" label="8 秒" />
              <el-option :value="10" label="10 秒" />
            </el-select>
          </el-form-item>
          <el-form-item label="比例">
            <el-select v-model="videoConfig.ratio" style="width: 140px">
              <el-option value="adaptive" label="adaptive" />
              <el-option value="9:16" label="9:16" />
              <el-option value="16:9" label="16:9" />
              <el-option value="1:1" label="1:1" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-switch v-model="videoConfig.generate_audio" active-text="有声视频" />
          </el-form-item>
        </el-form>

        <p class="status-line">视频状态：{{ videoState.statusVideo }}</p>
        <div v-if="isVideoGenerating" class="entry-row">
          <el-button class="neon-btn danger-btn" :loading="cancelingVideo" @click="cancelVideoTask">取消视频</el-button>
        </div>
        <p v-if="videoState.errorText" class="error-line">{{ videoState.errorText }}</p>
        <video v-if="videoState.videoUrl" class="video-player" controls :src="videoState.videoUrl"></video>
        <div v-if="videoState.videoUrl" class="entry-row">
          <a class="download-link" :href="videoState.videoUrl" target="_blank" rel="noreferrer">下载视频</a>
        </div>
      </section>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  cancelBloggerPost,
  cancelBloggerVideo,
  createBloggerPost,
  createBloggerVideo,
  getBloggerHotwords,
  getBloggerPost,
  getBloggerVideoStatus,
  refreshBloggerHotwords,
  selectBloggerCover,
} from '../api/aiBlogger'

const inputMode = ref('manual')
const manualHotWord = ref('')
const selectedHotWord = ref('')
const stylePrompt = ref('')
const imageCount = ref(1)
const ratio = ref('9:16')
const hotwords = ref([])
const hotwordsLoading = ref(false)
const hotwordsFetched = ref(false)
const creatingPost = ref(false)
const creatingVideo = ref(false)
const cancelingPost = ref(false)
const cancelingVideo = ref(false)
let postTimer = null
let videoTimer = null
const BLOGGER_TASK_KEY = 'ai_blogger_active_task'

const postState = reactive({
  postId: null,
  status: '',
  statusText: '-',
  stageText: '-',
  title: '',
  copy: '',
  images: [],
  selectedCoverKey: '',
  errorText: '',
})
const isPostGenerating = computed(() => {
  if (!postState.postId) return false
  const status = String(postState.status || '').toLowerCase()
  return !['success', 'failed', 'canceled'].includes(status)
})
const generatingStageLabel = computed(() => {
  const stage = String(postState.stageText || '').toLowerCase()
  if (stage === 'title' || postState.stageText === '标题') return '正在雕刻爆款标题'
  if (stage === 'copy' || postState.stageText === '文案') return '正在打磨高能文案'
  if (stage === 'images' || postState.stageText === '配图') return '正在绘制视觉配图'
  if (stage === 'done' || postState.stageText === '完成') return '即将完成图文作品'
  return '正在生成图文内容'
})
const postStatusLabel = computed(() => {
  const status = String(postState.statusText || '').toLowerCase()
  if (status === 'queued') return '排队中'
  if (status === 'running') return '处理中'
  if (status === 'success') return '成功'
  if (status === 'failed') return '失败'
  if (status === 'canceled') return '已取消'
  return postState.statusText || '-'
})
const postStageLabel = computed(() => {
  const stage = String(postState.stageText || '').toLowerCase()
  if (stage === 'title') return '标题生成'
  if (stage === 'copy') return '文案生成'
  if (stage === 'images') return '配图生成'
  if (stage === 'done') return '完成'
  return postState.stageText || ''
})

const videoConfig = reactive({
  duration: 5,
  ratio: 'adaptive',
  generate_audio: true,
  watermark: false,
})

const videoState = reactive({
  taskId: null,
  statusVideo: 'idle',
  errorText: '',
  videoUrl: '',
})
const isVideoGenerating = computed(() => {
  const status = String(videoState.statusVideo || '').toLowerCase()
  return ['queued', 'running'].includes(status)
})

const persistActiveTask = () => {
  if (!postState.postId) {
    localStorage.removeItem(BLOGGER_TASK_KEY)
    return
  }
  localStorage.setItem(
    BLOGGER_TASK_KEY,
    JSON.stringify({
      postId: postState.postId,
      videoTaskId: videoState.taskId || null,
    })
  )
}

const loadHotwords = async (forceRefresh = false) => {
  if (!forceRefresh && hotwordsFetched.value && hotwords.value.length) {
    if (!selectedHotWord.value) {
      selectedHotWord.value = hotwords.value[0].word || ''
    }
    return
  }
  hotwordsLoading.value = true
  try {
    const res = forceRefresh ? await refreshBloggerHotwords() : await getBloggerHotwords(50)
    hotwords.value = Array.isArray(res.data?.items) ? res.data.items : []
    if (!hotwords.value.length) {
      selectedHotWord.value = ''
      ElMessage.warning('未获取到热搜词，请稍后重试')
      return
    }
    if (!selectedHotWord.value) {
      selectedHotWord.value = hotwords.value[0].word || ''
    }
    hotwordsFetched.value = true
  } catch (e) {
    ElMessage.error(String(e || '获取热点失败'))
  } finally {
    hotwordsLoading.value = false
  }
}

const currentHotWord = () => (inputMode.value === 'manual' ? manualHotWord.value.trim() : selectedHotWord.value.trim())

const clearPostPolling = () => {
  if (postTimer) {
    clearInterval(postTimer)
    postTimer = null
  }
}

const clearVideoPolling = () => {
  if (videoTimer) {
    clearInterval(videoTimer)
    videoTimer = null
  }
}

const queryPost = async () => {
  if (!postState.postId) return
  const res = await getBloggerPost(postState.postId)
  const data = res.data || {}
  postState.status = data.status_text || ''
  postState.statusText = data.status_text || '-'
  postState.stageText = data.stage_text || '-'
  postState.title = data.title || ''
  postState.copy = data.copy || ''
  postState.images = data.images || []
  postState.selectedCoverKey = data.selected_cover_key || ''
  postState.errorText = data.error_text || ''
  persistActiveTask()
  if (['success', 'failed', 'canceled'].includes(String(postState.status || '').toLowerCase())) clearPostPolling()
}

const createPost = async () => {
  const hotWord = currentHotWord()
  if (!hotWord) {
    ElMessage.warning('请先输入或选择热点词')
    return
  }
  creatingPost.value = true
  clearPostPolling()
  clearVideoPolling()
  videoState.taskId = null
  videoState.statusVideo = 'idle'
  videoState.errorText = ''
  videoState.videoUrl = ''
  try {
    const res = await createBloggerPost({
      input_mode: inputMode.value,
      hot_word: hotWord,
      style_prompt: stylePrompt.value.trim(),
      ratio: ratio.value,
      image_count: imageCount.value,
    })
    postState.postId = res.data?.post_id
    persistActiveTask()
    await queryPost()
    postTimer = setInterval(async () => {
      try {
        await queryPost()
      } catch {
        // ignore transient errors
      }
    }, 1800)
  } catch (e) {
    ElMessage.error(String(e || '创建图文任务失败'))
  } finally {
    creatingPost.value = false
  }
}

const chooseCover = async (cosKey) => {
  if (!postState.postId) return
  try {
    await selectBloggerCover(postState.postId, { cos_key: cosKey })
    postState.selectedCoverKey = cosKey
    ElMessage.success('已设置首帧图片')
  } catch (e) {
    ElMessage.error(String(e || '设置首帧失败'))
  }
}

const queryVideo = async () => {
  if (!postState.postId) return
  const res = await getBloggerVideoStatus(postState.postId)
  const data = res.data || {}
  videoState.statusVideo = data.status_video || 'idle'
  videoState.errorText = data.error_text || ''
  videoState.videoUrl = data.video?.url || ''
  persistActiveTask()
  if (['success', 'failed', 'idle', 'canceled'].includes(String(videoState.statusVideo || '').toLowerCase())) clearVideoPolling()
}

const cancelPostTask = async () => {
  if (!postState.postId || cancelingPost.value) return
  cancelingPost.value = true
  try {
    await cancelBloggerPost(postState.postId)
    clearPostPolling()
    postState.status = 'canceled'
    postState.statusText = 'canceled'
    postState.errorText = '已取消图文生成'
    ElMessage.success('已取消图文生成')
    persistActiveTask()
  } catch (e) {
    ElMessage.error(String(e || '取消图文失败'))
  } finally {
    cancelingPost.value = false
  }
}

const cancelVideoTask = async () => {
  if (!postState.postId || cancelingVideo.value) return
  cancelingVideo.value = true
  try {
    await cancelBloggerVideo(postState.postId)
    clearVideoPolling()
    videoState.statusVideo = 'canceled'
    videoState.errorText = '已取消视频生成'
    ElMessage.success('已取消视频生成')
    persistActiveTask()
  } catch (e) {
    ElMessage.error(String(e || '取消视频失败'))
  } finally {
    cancelingVideo.value = false
  }
}

const createVideo = async () => {
  if (!postState.postId) return
  creatingVideo.value = true
  clearVideoPolling()
  try {
    const res = await createBloggerVideo(postState.postId, { ...videoConfig })
    videoState.taskId = res.data?.video_task_id
    persistActiveTask()
    await queryVideo()
    videoTimer = setInterval(async () => {
      try {
        await queryVideo()
      } catch {
        // ignore transient errors
      }
    }, 2500)
  } catch (e) {
    ElMessage.error(String(e || '创建视频任务失败'))
  } finally {
    creatingVideo.value = false
  }
}

watch(inputMode, (next) => {
  if (next === 'manual') {
    selectedHotWord.value = ''
  }
})

onMounted(async () => {
  const raw = localStorage.getItem(BLOGGER_TASK_KEY)
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    const postId = Number(saved?.postId || 0)
    if (!postId) {
      localStorage.removeItem(BLOGGER_TASK_KEY)
      return
    }
    postState.postId = postId
    videoState.taskId = saved?.videoTaskId || null
    await queryPost()
    if (!['success', 'failed'].includes(String(postState.status || '').toLowerCase())) {
      postTimer = setInterval(async () => {
        try {
          await queryPost()
        } catch {
          // ignore transient errors
        }
      }, 1800)
    }
    if (videoState.taskId) {
      await queryVideo()
      if (!['success', 'failed', 'idle'].includes(String(videoState.statusVideo || '').toLowerCase())) {
        videoTimer = setInterval(async () => {
          try {
            await queryVideo()
          } catch {
            // ignore transient errors
          }
        }, 2500)
      }
    }
  } catch {
    localStorage.removeItem(BLOGGER_TASK_KEY)
  }
})

onBeforeUnmount(() => {
  clearPostPolling()
  clearVideoPolling()
})
</script>

<style scoped>
.blogger-shell { min-height: 100vh; }
.blogger-card { width: min(980px, 100%); }
.head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.head h2 {
  margin: 0;
  color: #eef6ff;
  text-shadow: 0 0 10px rgba(84, 194, 255, 0.4);
}
.head p { margin: 6px 0 0; color: #b3c8f1; }
.section-block {
  margin-top: 14px;
  border: 1px solid rgba(134, 188, 255, 0.38);
  border-radius: 14px;
  padding: 14px;
  background: rgba(15, 24, 58, 0.56);
}
.section-block h3 {
  margin: 0 0 10px;
  color: #e8f2ff;
}
.neon-form :deep(.el-input__wrapper),
.neon-form :deep(.el-select__wrapper) {
  background: rgba(10, 22, 60, 0.84);
  box-shadow: 0 0 0 1px rgba(140, 214, 255, 0.24), 0 0 14px rgba(72, 166, 255, 0.26);
}
.hotword-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
}
.status-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #d5e8ff;
}
.gen-status {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(147, 219, 255, 0.52);
  background: linear-gradient(135deg, rgba(35, 110, 214, 0.3), rgba(72, 196, 255, 0.2));
  box-shadow: 0 0 0 1px rgba(170, 230, 255, 0.16), 0 0 18px rgba(88, 194, 255, 0.28);
}
.gen-badge {
  font-size: 12px;
  font-weight: 700;
  color: #f3fcff;
  letter-spacing: 0.4px;
}
.gen-text {
  color: #cfe9ff;
  font-size: 13px;
}
.dot-flow {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.dot-flow i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #96e2ff;
  opacity: 0.2;
  animation: dotFlow 1.2s infinite ease-in-out;
}
.dot-flow i:nth-child(2) { animation-delay: 0.2s; }
.dot-flow i:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotFlow {
  0%, 80%, 100% { opacity: 0.2; transform: translateY(0); }
  40% { opacity: 1; transform: translateY(-2px); }
}
.error-line {
  margin: 10px 0;
  color: #ff95b3;
}
.copy-text {
  white-space: pre-wrap;
  color: #dce7ff;
}
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 10px;
}
.img-item {
  border: 1px solid rgba(143, 204, 255, 0.4);
  background: rgba(12, 27, 66, 0.78);
  border-radius: 12px;
  padding: 8px;
  color: #d8ebff;
  cursor: pointer;
}
.img-item img {
  width: 100%;
  border-radius: 8px;
  display: block;
}
.img-item span {
  display: inline-flex;
  margin-top: 6px;
  font-size: 12px;
}
.img-item.active {
  box-shadow: 0 0 0 1px rgba(177, 230, 255, 0.38), 0 0 16px rgba(84, 190, 255, 0.42);
}
.entry-row {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.video-form :deep(.el-form-item__label) {
  color: #cde0ff;
}
.video-player {
  width: min(560px, 100%);
  border-radius: 12px;
  border: 1px solid rgba(133, 198, 255, 0.45);
}
.download-link {
  color: #8dd8ff;
  text-decoration: none;
}
.neon-btn {
  border: 1px solid rgba(164, 223, 255, 0.66);
  color: #ebf8ff;
  background: linear-gradient(125deg, rgba(39, 138, 227, 0.75), rgba(74, 76, 198, 0.72));
  box-shadow: 0 0 0 1px rgba(171, 232, 255, 0.2), 0 0 16px rgba(98, 194, 255, 0.35);
}
.danger-btn {
  border-color: rgba(255, 157, 192, 0.58);
  color: #ffe8f1;
  background: linear-gradient(125deg, rgba(205, 52, 118, 0.78), rgba(142, 53, 180, 0.72));
  box-shadow: 0 0 0 1px rgba(255, 186, 214, 0.2), 0 0 16px rgba(255, 106, 170, 0.32);
}
@media (max-width: 768px) {
  .hotword-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
