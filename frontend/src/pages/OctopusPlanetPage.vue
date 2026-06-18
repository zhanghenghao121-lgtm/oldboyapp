<template>
  <div class="planet-shell">
    <canvas ref="canvasRef" class="planet-canvas" @click="handleCanvasClick" @pointermove="handlePointerMove"></canvas>

    <header class="planet-topbar">
      <button class="ghost-chip" type="button" @click="router.push('/octopus-space')">章鱼记</button>
      <button class="ghost-chip" type="button" @click="router.push('/')">工作台</button>
    </header>

    <section class="planet-toolbar">
      <div class="scope-tabs">
        <button type="button" :class="{ active: scope === 'all' }" @click="setScope('all')">所有用户</button>
        <button type="button" :class="{ active: scope === 'mine' }" @click="setScope('mine')">只看自己</button>
      </div>
      <form class="tag-search" @submit.prevent="runSearch">
        <input v-model="searchTag" maxlength="10" placeholder="搜索标签" />
        <button type="submit">搜索</button>
        <button type="button" @click="clearSearch">清除</button>
      </form>
    </section>

    <section class="planet-caption">
      <p class="eyebrow">OCTOPUS PLANET</p>
      <h1>章鱼星球</h1>
      <span>{{ particles.length }} 个粒子 · {{ searchActive ? '搜索高亮中' : scope === 'mine' ? '只看自己' : '所有发布' }}</span>
    </section>

    <div v-if="hoverParticle" class="particle-tooltip" :style="tooltipStyle">
      <strong>{{ hoverParticle.title }}</strong>
      <span>#{{ hoverParticle.tag }}</span>
    </div>

    <div v-if="loading" class="planet-loading">星球加载中...</div>
    <div v-if="!loading && !particles.length" class="planet-empty">还没有发布到章鱼星球的记事本</div>

    <el-dialog v-model="detailVisible" title="星球记事" width="560px" class="planet-detail-dialog">
      <article v-if="detail" class="planet-detail">
        <p class="eyebrow">{{ detailTags.map((tag) => `#${tag}`).join(' ') }}</p>
        <h2>{{ detail.title }}</h2>
        <small>{{ detail.author?.nickname || '匿名章鱼' }} · {{ formatDate(detail.published_at) }}</small>
        <div v-if="detailImageUrls.length" class="detail-image-block">
          <button v-if="detailImageUrls.length > 1" class="detail-image-stack" type="button" @click="detailImagesExpanded = !detailImagesExpanded">
            <span
              v-for="(url, index) in detailStackImages"
              :key="`${url}-${index}`"
              class="detail-stack-card"
              :style="{ transform: `translate(${index * 8}px, ${index * 8}px)` }"
            >
              <img :src="storageFileUrl(url)" alt="记事本图片" />
            </span>
            <strong>{{ detailImagesExpanded ? '收起' : `展开 ${detailImageUrls.length} 张` }}</strong>
          </button>

          <div v-if="detailImagesExpanded || detailImageUrls.length === 1" class="detail-image-grid">
            <button v-for="(url, index) in detailImageUrls" :key="`${url}-${index}`" type="button" @click="previewImageUrl = url">
              <img :src="storageFileUrl(url)" alt="记事本图片" />
            </button>
          </div>
        </div>
        <p>{{ detail.content_preview || '这本记事暂时没有公开正文预览。' }}</p>
      </article>
    </el-dialog>

    <section v-if="previewImageUrl" class="planet-image-preview" @click.self="previewImageUrl = ''">
      <button class="ghost-chip preview-close" type="button" @click="previewImageUrl = ''">关闭</button>
      <img :src="storageFileUrl(previewImageUrl)" alt="图片预览" />
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'

import {
  getOctopusPlanetParticles,
  getOctopusPlanetPublish,
  searchOctopusPlanet,
} from '../api/octopusPlanet'
import { storageFileUrl } from '../api/storage'

const router = useRouter()
const canvasRef = ref(null)
const loading = ref(false)
const particles = ref([])
const scope = ref('all')
const searchTag = ref('')
const searchActive = ref(false)
const detail = ref(null)
const detailVisible = ref(false)
const detailImagesExpanded = ref(false)
const previewImageUrl = ref('')
const hoverParticle = ref(null)
const pointer = new THREE.Vector2()
const tooltipPosition = ref({ x: 0, y: 0 })

let renderer = null
let scene = null
let camera = null
let raycaster = null
let particleGroup = null
let animationFrame = 0
let resizeObserver = null

const tooltipStyle = computed(() => ({
  left: `${tooltipPosition.value.x + 14}px`,
  top: `${tooltipPosition.value.y + 14}px`,
}))

const detailTags = computed(() => {
  const tags = Array.isArray(detail.value?.tags) && detail.value.tags.length ? detail.value.tags : [detail.value?.tag]
  return tags.filter(Boolean)
})

const detailImageUrls = computed(() =>
  (Array.isArray(detail.value?.image_urls) ? detail.value.image_urls : []).map((url) => String(url || '').trim()).filter(Boolean)
)

const detailStackImages = computed(() => detailImageUrls.value.slice(0, Math.min(detailImageUrls.value.length, 3)))

const formatDate = (value) => {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const initScene = () => {
  const canvas = canvasRef.value
  if (!canvas) return
  scene = new THREE.Scene()
  camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100)
  camera.position.set(0, 0, 6.4)
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: window.location.search.includes('verifyCanvas=1'),
  })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  raycaster = new THREE.Raycaster()
  particleGroup = new THREE.Group()
  scene.add(particleGroup)

  const shell = new THREE.Mesh(
    new THREE.SphereGeometry(2.55, 48, 32),
    new THREE.MeshBasicMaterial({
      color: 0x4be7ff,
      wireframe: true,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  )
  scene.add(shell)
  scene.add(new THREE.AmbientLight(0xffffff, 1.2))
  resizeScene()
  animate()
}

const resizeScene = () => {
  if (!renderer || !camera || !canvasRef.value) return
  const rect = canvasRef.value.getBoundingClientRect()
  renderer.setSize(rect.width, rect.height, false)
  camera.aspect = rect.width / Math.max(rect.height, 1)
  camera.updateProjectionMatrix()
}

const animate = () => {
  animationFrame = window.requestAnimationFrame(animate)
  if (particleGroup) {
    particleGroup.rotation.y += 0.0028
    particleGroup.rotation.x = Math.sin(Date.now() * 0.00025) * 0.08
  }
  renderer?.render(scene, camera)
}

const updateSceneParticles = () => {
  if (!particleGroup) return
  particleGroup.clear()
  const coreGeometry = new THREE.SphereGeometry(0.045, 18, 18)
  const glowGeometry = new THREE.SphereGeometry(0.12, 18, 18)
  particles.value.forEach((particle) => {
    const highlighted = particle.highlight || (scope.value === 'mine' && particle.is_mine)
    const color = new THREE.Color(particle.color || '#7ff3ff')
    const dimmed = searchActive.value && !highlighted
    const coreMaterial = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: dimmed ? 0.26 : highlighted ? 0.78 : 0.52,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const glowMaterial = new THREE.MeshBasicMaterial({
      color: new THREE.Color(particle.color || '#7ff3ff'),
      transparent: true,
      opacity: dimmed ? 0.08 : highlighted ? 0.28 : 0.16,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    const mesh = new THREE.Mesh(coreGeometry, coreMaterial)
    const glow = new THREE.Mesh(glowGeometry, glowMaterial)
    const size = (particle.size || 1) * (highlighted ? 1.65 : particle.is_mine ? 1.35 : 1)
    mesh.scale.setScalar(size)
    glow.scale.setScalar(size * (highlighted ? 1.38 : 1))
    mesh.position.set(Number(particle.x || 0) * 2.45, Number(particle.y || 0) * 2.45, Number(particle.z || 0) * 2.45)
    glow.position.copy(mesh.position)
    mesh.userData = { particle }
    glow.userData = { particle }
    particleGroup.add(mesh)
    particleGroup.add(glow)
  })
  window.__OCTOPUS_PLANET_PARTICLE_COUNT__ = particles.value.length
}

const loadParticles = async () => {
  loading.value = true
  try {
    const res = await getOctopusPlanetParticles({ scope: scope.value })
    particles.value = res.data.items || []
    searchActive.value = false
    updateSceneParticles()
  } catch (error) {
    ElMessage.error(String(error || '章鱼星球加载失败'))
  } finally {
    loading.value = false
  }
}

const setScope = async (nextScope) => {
  scope.value = nextScope
  if (searchActive.value && searchTag.value.trim()) await runSearch()
  else await loadParticles()
}

const runSearch = async () => {
  const tag = searchTag.value.trim()
  if (!tag) {
    await clearSearch()
    return
  }
  loading.value = true
  try {
    const res = await searchOctopusPlanet({ tag, scope: scope.value })
    particles.value = res.data.items || []
    searchActive.value = true
    updateSceneParticles()
  } catch (error) {
    ElMessage.error(String(error || '标签搜索失败'))
  } finally {
    loading.value = false
  }
}

const clearSearch = async () => {
  searchTag.value = ''
  searchActive.value = false
  await loadParticles()
}

const pickParticle = (event) => {
  if (!renderer || !camera || !particleGroup || !canvasRef.value) return null
  const rect = canvasRef.value.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const hit = raycaster.intersectObjects(particleGroup.children, false)[0]
  return hit?.object?.userData?.particle || null
}

const handlePointerMove = (event) => {
  tooltipPosition.value = { x: event.clientX, y: event.clientY }
  hoverParticle.value = pickParticle(event)
}

const handleCanvasClick = async (event) => {
  const particle = pickParticle(event)
  if (!particle) return
  try {
    const res = await getOctopusPlanetPublish(particle.publish_id)
    detail.value = res.data
    detailImagesExpanded.value = false
    previewImageUrl.value = ''
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(String(error || '粒子详情加载失败'))
  }
}

onMounted(async () => {
  await nextTick()
  initScene()
  resizeObserver = new ResizeObserver(resizeScene)
  if (canvasRef.value) resizeObserver.observe(canvasRef.value)
  await loadParticles()
})

onBeforeUnmount(() => {
  if (animationFrame) window.cancelAnimationFrame(animationFrame)
  resizeObserver?.disconnect()
  renderer?.dispose()
})
</script>

<style scoped>
.planet-shell {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  color: #eef8ff;
  background:
    radial-gradient(circle at 50% 50%, rgba(72, 237, 255, .15), transparent 34%),
    linear-gradient(135deg, #030711, #0b1430 48%, #160d2c);
}

.planet-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  cursor: grab;
}

.planet-topbar,
.planet-toolbar,
.planet-caption,
.particle-tooltip,
.planet-loading,
.planet-empty {
  position: absolute;
  z-index: 2;
}

.planet-topbar {
  top: 22px;
  left: 24px;
  display: flex;
  gap: 10px;
}

.ghost-chip,
.scope-tabs button,
.tag-search button {
  min-height: 36px;
  border: 1px solid rgba(157, 231, 255, .3);
  border-radius: 999px;
  padding: 0 14px;
  color: #f3fbff;
  background: rgba(255, 255, 255, .06);
  cursor: pointer;
  font-weight: 800;
}

.planet-toolbar {
  top: 22px;
  right: 24px;
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border: 1px solid rgba(157, 231, 255, .2);
  border-radius: 20px;
  background: rgba(5, 12, 28, .58);
  backdrop-filter: blur(14px);
}

.scope-tabs,
.tag-search {
  display: flex;
  gap: 8px;
  align-items: center;
}

.scope-tabs button.active,
.tag-search button:hover,
.ghost-chip:hover {
  border-color: rgba(255, 92, 210, .72);
  background: rgba(255, 92, 210, .18);
}

.tag-search input {
  width: 132px;
  min-height: 36px;
  border: 1px solid rgba(157, 231, 255, .26);
  border-radius: 999px;
  padding: 0 12px;
  outline: none;
  color: #effcff;
  background: rgba(1, 8, 20, .68);
}

.planet-caption {
  left: 28px;
  bottom: 28px;
}

.eyebrow {
  margin: 0;
  color: #7ff3ff;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: .18em;
}

.planet-caption h1 {
  margin: 8px 0;
  font-family: "Orbitron", "ZCOOL KuaiLe", sans-serif;
  font-size: clamp(44px, 7vw, 86px);
  line-height: .94;
  text-shadow: 0 0 26px rgba(93, 232, 255, .62);
}

.planet-caption span {
  color: #b8cfe2;
  font-weight: 800;
}

.particle-tooltip {
  max-width: 220px;
  padding: 8px 10px;
  border: 1px solid rgba(127, 243, 255, .3);
  border-radius: 12px;
  background: rgba(1, 8, 20, .78);
  pointer-events: none;
}

.particle-tooltip strong,
.particle-tooltip span {
  display: block;
}

.particle-tooltip span {
  margin-top: 3px;
  color: #7ff3ff;
  font-size: 12px;
}

.planet-loading,
.planet-empty {
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  color: #c7d8e8;
  font-weight: 900;
}

.planet-detail h2 {
  margin: 8px 0;
}

.planet-detail small {
  color: #8aa1b8;
}

.planet-detail p:last-child {
  white-space: pre-wrap;
  line-height: 1.8;
}

.detail-image-block {
  margin: 16px 0;
  display: grid;
  gap: 14px;
}

.detail-image-stack {
  position: relative;
  width: 132px;
  aspect-ratio: 1 / 1;
  border: 0;
  margin: 0 0 18px;
  padding: 0;
  color: #fff;
  background: transparent;
  cursor: pointer;
}

.detail-stack-card {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border: 1px solid rgba(216, 248, 255, .42);
  border-radius: 18px;
  background: #071426;
  box-shadow: 0 14px 34px rgba(0, 7, 24, .34);
}

.detail-stack-card img,
.detail-image-grid img,
.planet-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.detail-image-stack strong {
  position: absolute;
  right: -12px;
  bottom: -20px;
  z-index: 4;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  color: #06111f;
  background: #7ff3ff;
  font-size: 12px;
  font-weight: 900;
}

.detail-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(82px, 1fr));
  gap: 10px;
}

.detail-image-grid button {
  aspect-ratio: 1 / 1;
  overflow: hidden;
  border: 1px solid rgba(216, 248, 255, .28);
  border-radius: 14px;
  padding: 0;
  background: #071426;
  cursor: zoom-in;
}

.planet-image-preview {
  position: fixed;
  inset: 0;
  z-index: 20;
  padding: 28px;
  display: grid;
  place-items: center;
  background: rgba(1, 5, 16, .86);
  backdrop-filter: blur(10px);
}

.planet-image-preview img {
  width: min(92vw, 980px);
  height: min(82vh, 820px);
  border: 1px solid rgba(160, 229, 255, .34);
  border-radius: 22px;
  box-shadow: 0 28px 80px rgba(0, 8, 30, .58);
}

.preview-close {
  position: absolute;
  top: 24px;
  right: 28px;
}

@media (max-width: 820px) {
  .planet-topbar,
  .planet-toolbar {
    left: 16px;
    right: 16px;
  }

  .planet-toolbar {
    top: 70px;
    flex-direction: column;
    align-items: stretch;
  }

  .scope-tabs,
  .tag-search {
    justify-content: space-between;
  }

  .tag-search input {
    width: 100%;
  }
}
</style>
