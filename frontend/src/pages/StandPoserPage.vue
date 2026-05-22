<template>
  <div class="poser-shell">
    <header class="poser-topbar">
      <div>
        <p class="eyebrow">STAND POSER</p>
        <h1>3D站位生成器</h1>
      </div>
      <div class="topbar-tools">
        <el-input v-model="store.sceneName" class="scene-name" maxlength="120" placeholder="场景名称" />
        <el-input v-model="loadSceneId" class="scene-id" placeholder="场景ID" />
        <el-button plain @click="loadScene">加载场景</el-button>
        <el-button type="primary" :loading="savingScene" @click="saveScene">保存场景</el-button>
        <el-button :type="cameraPreview ? 'warning' : 'default'" plain @click="toggleCameraPreview">摄像机预览</el-button>
        <el-button type="success" :loading="shooting" @click="captureShot">拍摄</el-button>
      </div>
    </header>

    <main class="poser-workspace">
      <aside class="side-panel character-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">CharacterUploadPanel</p>
            <h2>角色资产</h2>
          </div>
        </div>

        <el-form label-position="top" class="upload-form">
          <el-form-item label="角色名">
            <el-input v-model="characterName" maxlength="80" placeholder="例如：顾知夏" />
          </el-form-item>
          <el-form-item label="GLB模型">
            <input ref="modelInputRef" class="file-hidden" type="file" accept=".glb,model/gltf-binary" @change="handleModelFileChange" />
            <button class="file-picker" type="button" @click="modelInputRef?.click()">
              <span>{{ modelFile?.name || '选择 .glb 文件' }}</span>
            </button>
          </el-form-item>
          <el-button class="w-100" type="primary" :loading="uploadingCharacter" @click="uploadCharacter">上传角色</el-button>
        </el-form>

        <div class="asset-list">
          <article v-for="item in store.characters" :key="item.id" class="asset-card">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ formatSize(item.file_size) }}</span>
            </div>
            <div class="asset-actions">
              <el-button size="small" plain @click="store.addPlacement(item)">加入场景</el-button>
              <el-button size="small" plain @click="generateModel(item)">生成</el-button>
            </div>
          </article>
          <div v-if="!store.characters.length" class="empty-hint">上传 GLB 后会显示在这里。</div>
        </div>
      </aside>

      <section class="viewport-panel">
        <div class="viewport-title">
          <div>
            <p class="eyebrow">ThreeViewport</p>
            <h2>3D 网格空间</h2>
          </div>
          <span>{{ transformMode === 'translate' ? '移动模式' : '旋转模式' }}</span>
        </div>
        <div ref="viewportRef" class="three-viewport"></div>
        <div class="viewport-toolbar">
          <button type="button" :class="{ active: transformMode === 'translate' }" @click="setTransformMode('translate')">移动</button>
          <button type="button" :class="{ active: transformMode === 'rotate' }" @click="setTransformMode('rotate')">旋转</button>
          <button type="button" @click="selectCamera">选择摄像机</button>
          <button type="button" @click="resetView">重置视角</button>
        </div>
      </section>

      <aside class="side-panel property-panel">
        <div class="panel-head">
          <div>
            <p class="eyebrow">ScenePropertyPanel</p>
            <h2>{{ selectedType === 'camera' ? '摄像机属性' : '角色属性' }}</h2>
          </div>
        </div>

        <div v-if="selectedType === 'character' && selectedPlacement" class="property-stack">
          <label>角色</label>
          <el-input :model-value="selectedPlacement.name" disabled />
          <label>姿势</label>
          <el-select v-model="selectedPlacement.pose" @change="syncSelectedPlacement">
            <el-option label="自然站立" value="自然站立" />
            <el-option label="对话站姿" value="对话站姿" />
            <el-option label="警戒站姿" value="警戒站姿" />
            <el-option label="坐姿参考" value="坐姿参考" />
          </el-select>
          <VectorEditor title="位置" :value="selectedPlacement.position" :step="0.1" @change="syncSelectedPlacement" />
          <VectorEditor title="旋转" :value="selectedPlacement.rotation" :step="1" @change="syncSelectedPlacement" />
          <VectorEditor title="缩放" :value="selectedPlacement.scale" :step="0.05" @change="syncSelectedPlacement" />
        </div>

        <div v-else class="property-stack">
          <label>摄像机 FOV</label>
          <el-input-number v-model="store.camera.fov" :min="15" :max="90" :step="1" @change="syncCameraFromStore" />
          <VectorEditor title="摄像机位置" :value="store.camera.position" :step="0.1" @change="syncCameraFromStore" />
          <VectorEditor title="摄像机旋转" :value="store.camera.rotation" :step="1" @change="syncCameraFromStore" />
          <div class="resolution-grid">
            <label>分辨率宽</label>
            <el-input-number v-model="store.resolution.width" :min="320" :max="4096" :step="64" />
            <label>分辨率高</label>
            <el-input-number v-model="store.resolution.height" :min="240" :max="4096" :step="64" />
          </div>
        </div>

        <div class="shot-result" v-if="lastShotUrl">
          <strong>最近拍摄</strong>
          <a :href="lastShotUrl" target="_blank" rel="noreferrer">查看 PNG</a>
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted, ref, resolveComponent, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'

import {
  createStandposerCharacter,
  createStandposerScene,
  generateStandposerCharacterModel,
  getStandposerCharacters,
  getStandposerScene,
  updateStandposerScene,
  uploadStandposerShot,
} from '../api/standposer'
import { useStandposerStore } from '../stores/standposer'

const VectorEditor = defineComponent({
  props: {
    title: { type: String, required: true },
    value: { type: Object, required: true },
    step: { type: Number, default: 0.1 },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const ElInputNumber = resolveComponent('el-input-number')
    const update = () => emit('change')
    return () =>
      h('div', { class: 'vector-editor' }, [
        h('label', props.title),
        h('div', { class: 'vector-grid' }, ['x', 'y', 'z'].map((axis) =>
          h('div', { class: 'axis-field' }, [
            h('span', axis.toUpperCase()),
            h(ElInputNumber, {
              modelValue: props.value[axis],
              'onUpdate:modelValue': (value) => {
                props.value[axis] = Number(value || 0)
                update()
              },
              step: props.step,
              precision: props.step < 1 ? 2 : 0,
              controlsPosition: 'right',
            }),
          ])
        )),
      ])
  },
})

const store = useStandposerStore()
const viewportRef = ref(null)
const modelInputRef = ref(null)
const modelFile = ref(null)
const characterName = ref('')
const loadSceneId = ref('')
const uploadingCharacter = ref(false)
const savingScene = ref(false)
const shooting = ref(false)
const lastShotUrl = ref('')
const cameraPreview = ref(false)
const transformMode = ref('translate')

let renderer
let scene
let editCamera
let orbitControls
let transformControls
let animationFrame
let loader
let cameraRig
let cameraMarker
let cameraHelper
let captureCamera
let raycaster
let pointer
const objectMap = new Map()
const selectableObjects = []

const selectedPlacement = computed(() => store.selectedPlacement)
const selectedType = computed(() => (store.selectedObjectId === 'camera' ? 'camera' : 'character'))

const formatSize = (value) => {
  const size = Number(value || 0)
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

const createPlaceholder = (name) => {
  const group = new THREE.Group()
  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.35, 1.1, 8, 16),
    new THREE.MeshStandardMaterial({ color: '#58a6ff', roughness: 0.48 })
  )
  body.position.y = 0.9
  const label = new THREE.Mesh(
    new THREE.BoxGeometry(0.8, 0.06, 0.8),
    new THREE.MeshStandardMaterial({ color: '#f5c84b', roughness: 0.5 })
  )
  label.position.y = 0.05
  group.add(body, label)
  group.name = name
  return group
}

const normalizeLoadedModel = (rawObject, name) => {
  const wrapper = new THREE.Group()
  wrapper.name = name
  wrapper.add(rawObject)
  rawObject.updateMatrixWorld(true)
  const box = new THREE.Box3().setFromObject(rawObject)
  const size = box.getSize(new THREE.Vector3())
  const maxDimension = Math.max(size.x, size.y, size.z, 0.001)
  const scale = 2 / maxDimension
  rawObject.scale.multiplyScalar(scale)
  rawObject.updateMatrixWorld(true)
  const scaledBox = new THREE.Box3().setFromObject(rawObject)
  const center = scaledBox.getCenter(new THREE.Vector3())
  rawObject.position.x -= center.x
  rawObject.position.z -= center.z
  rawObject.position.y -= scaledBox.min.y
  return wrapper
}

const applyPlacementToObject = (placement, object) => {
  object.position.set(placement.position.x, placement.position.y, placement.position.z)
  object.rotation.set(
    THREE.MathUtils.degToRad(placement.rotation.x),
    THREE.MathUtils.degToRad(placement.rotation.y),
    THREE.MathUtils.degToRad(placement.rotation.z)
  )
  object.scale.set(placement.scale.x, placement.scale.y, placement.scale.z)
}

const syncPlacementFromObject = (placement, object) => {
  placement.position.x = Number(object.position.x.toFixed(2))
  placement.position.y = Number(object.position.y.toFixed(2))
  placement.position.z = Number(object.position.z.toFixed(2))
  placement.rotation.x = Number(THREE.MathUtils.radToDeg(object.rotation.x).toFixed(1))
  placement.rotation.y = Number(THREE.MathUtils.radToDeg(object.rotation.y).toFixed(1))
  placement.rotation.z = Number(THREE.MathUtils.radToDeg(object.rotation.z).toFixed(1))
}

const syncCameraFromObject = () => {
  store.camera.position.x = Number(cameraRig.position.x.toFixed(2))
  store.camera.position.y = Number(cameraRig.position.y.toFixed(2))
  store.camera.position.z = Number(cameraRig.position.z.toFixed(2))
  store.camera.rotation.x = Number(THREE.MathUtils.radToDeg(cameraRig.rotation.x).toFixed(1))
  store.camera.rotation.y = Number(THREE.MathUtils.radToDeg(cameraRig.rotation.y).toFixed(1))
  store.camera.rotation.z = Number(THREE.MathUtils.radToDeg(cameraRig.rotation.z).toFixed(1))
}

const syncCameraFromStore = () => {
  if (!cameraRig || !captureCamera) return
  cameraRig.position.set(store.camera.position.x, store.camera.position.y, store.camera.position.z)
  cameraRig.rotation.set(
    THREE.MathUtils.degToRad(store.camera.rotation.x),
    THREE.MathUtils.degToRad(store.camera.rotation.y),
    THREE.MathUtils.degToRad(store.camera.rotation.z)
  )
  captureCamera.fov = store.camera.fov
  captureCamera.aspect = store.resolution.width / store.resolution.height
  captureCamera.updateProjectionMatrix()
  cameraHelper?.update()
}

const attachTransform = (object) => {
  if (!transformControls || !object) return
  transformControls.attach(object)
}

const selectCamera = () => {
  store.selectedObjectId = 'camera'
  attachTransform(cameraRig)
}

const selectPlacement = (id) => {
  store.selectedObjectId = id
  attachTransform(objectMap.get(id))
}

const rebuildSceneObjects = async () => {
  if (!scene || !loader) return
  objectMap.forEach((object) => scene.remove(object))
  objectMap.clear()
  selectableObjects.splice(0, selectableObjects.length)
  if (cameraRig) selectableObjects.push(cameraRig)
  for (const placement of store.placements) {
    let object
    try {
      const gltf = await loader.loadAsync(placement.modelUrl)
      object = normalizeLoadedModel(gltf.scene, placement.name)
    } catch {
      object = createPlaceholder(placement.name)
    }
    object.traverse((child) => {
      child.userData.placementId = placement.id
      if (child.isMesh) {
        child.castShadow = true
        child.receiveShadow = true
      }
    })
    object.userData.placementId = placement.id
    applyPlacementToObject(placement, object)
    scene.add(object)
    objectMap.set(placement.id, object)
    selectableObjects.push(object)
  }
  if (store.selectedObjectId === 'camera') selectCamera()
  else selectPlacement(store.selectedObjectId)
}

const syncSelectedPlacement = () => {
  if (!selectedPlacement.value) return
  const object = objectMap.get(selectedPlacement.value.id)
  if (object) applyPlacementToObject(selectedPlacement.value, object)
}

const setTransformMode = (mode) => {
  transformMode.value = mode
  transformControls?.setMode(mode)
}

const initThree = () => {
  const container = viewportRef.value
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#08101f')
  scene.add(new THREE.HemisphereLight('#dce8ff', '#1a2235', 1.8))
  const keyLight = new THREE.DirectionalLight('#ffffff', 2)
  keyLight.position.set(4, 8, 5)
  scene.add(keyLight)
  scene.add(new THREE.GridHelper(16, 16, '#2f6ea7', '#1a314b'))

  editCamera = new THREE.PerspectiveCamera(50, container.clientWidth / container.clientHeight, 0.1, 100)
  editCamera.position.set(6, 5, 8)

  captureCamera = new THREE.PerspectiveCamera(store.camera.fov, store.resolution.width / store.resolution.height, 0.1, 100)
  cameraRig = new THREE.Group()
  cameraRig.userData.selectType = 'camera'
  cameraMarker = new THREE.Group()
  const markerBody = new THREE.Mesh(
    new THREE.BoxGeometry(0.42, 0.28, 0.24),
    new THREE.MeshStandardMaterial({ color: '#f5c84b', roughness: 0.42 })
  )
  const markerLens = new THREE.Mesh(
    new THREE.ConeGeometry(0.18, 0.32, 16),
    new THREE.MeshStandardMaterial({ color: '#7fb8ff', roughness: 0.35 })
  )
  markerLens.rotation.x = Math.PI / 2
  markerLens.position.z = -0.28
  cameraMarker.add(markerBody, markerLens)
  cameraMarker.userData.selectType = 'camera'
  cameraMarker.traverse((child) => {
    child.userData.selectType = 'camera'
  })
  cameraRig.add(cameraMarker)
  cameraRig.add(captureCamera)
  scene.add(cameraRig)
  cameraHelper = new THREE.CameraHelper(captureCamera)
  scene.add(cameraHelper)
  syncCameraFromStore()
  selectableObjects.push(cameraRig)

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2))
  renderer.setSize(container.clientWidth, container.clientHeight)
  renderer.shadowMap.enabled = true
  container.appendChild(renderer.domElement)

  orbitControls = new OrbitControls(editCamera, renderer.domElement)
  orbitControls.enableDamping = true
  transformControls = new TransformControls(editCamera, renderer.domElement)
  transformControls.setMode(transformMode.value)
  transformControls.addEventListener('dragging-changed', (event) => {
    orbitControls.enabled = !event.value
  })
  transformControls.addEventListener('objectChange', () => {
    if (store.selectedObjectId === 'camera') {
      syncCameraFromObject()
      cameraHelper.update()
      return
    }
    const placement = store.placements.find((item) => item.id === store.selectedObjectId)
    const object = objectMap.get(store.selectedObjectId)
    if (placement && object) syncPlacementFromObject(placement, object)
  })
  scene.add(transformControls)

  raycaster = new THREE.Raycaster()
  pointer = new THREE.Vector2()
  loader = new GLTFLoader()
  renderer.domElement.addEventListener('pointerdown', handlePointerDown)
  window.addEventListener('resize', resizeRenderer)
  selectCamera()
  animate()
}

const activeCamera = () => (cameraPreview.value ? captureCamera : editCamera)

const animate = () => {
  animationFrame = requestAnimationFrame(animate)
  orbitControls?.update()
  if (cameraMarker) cameraMarker.visible = !cameraPreview.value
  renderer.render(scene, activeCamera())
}

const resizeRenderer = () => {
  if (!renderer || !viewportRef.value) return
  const width = viewportRef.value.clientWidth
  const height = viewportRef.value.clientHeight
  editCamera.aspect = width / height
  editCamera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

const handlePointerDown = (event) => {
  if (event.button !== 0 || !renderer || cameraPreview.value) return
  const rect = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, editCamera)
  const hits = raycaster.intersectObjects(selectableObjects, true)
  const cameraHit = hits.find((hit) => hit.object.userData.selectType === 'camera')
  if (cameraHit) {
    selectCamera()
    return
  }
  const placementId = hits.find((hit) => hit.object.userData.placementId)?.object.userData.placementId
  if (placementId) selectPlacement(placementId)
}

const resetView = () => {
  editCamera.position.set(6, 5, 8)
  orbitControls.target.set(0, 1, 0)
  orbitControls.update()
}

const toggleCameraPreview = () => {
  cameraPreview.value = !cameraPreview.value
}

const handleModelFileChange = (event) => {
  modelFile.value = event.target.files?.[0] || null
  event.target.value = ''
}

const uploadCharacter = async () => {
  if (!characterName.value.trim() || !modelFile.value) {
    ElMessage.warning('请输入角色名并选择 GLB 模型')
    return
  }
  uploadingCharacter.value = true
  try {
    const res = await createStandposerCharacter({ name: characterName.value.trim(), file: modelFile.value })
    store.addCharacter(res.data)
    characterName.value = ''
    modelFile.value = null
    ElMessage.success('角色资产已上传')
  } catch (e) {
    ElMessage.error(String(e || '角色上传失败'))
  } finally {
    uploadingCharacter.value = false
  }
}

const generateModel = async (character) => {
  try {
    await generateStandposerCharacterModel(character.id)
    ElMessage.success('测试生成任务已创建')
  } catch (e) {
    ElMessage.error(String(e || '生成任务创建失败'))
  }
}

const saveScene = async () => {
  savingScene.value = true
  try {
    const payload = store.buildScenePayload()
    const res = store.activeSceneId
      ? await updateStandposerScene(store.activeSceneId, payload)
      : await createStandposerScene(payload)
    store.applyScenePayload(res.data)
    loadSceneId.value = String(res.data.id)
    await nextTick()
    await rebuildSceneObjects()
    ElMessage.success('场景已保存')
  } catch (e) {
    ElMessage.error(String(e || '场景保存失败'))
  } finally {
    savingScene.value = false
  }
}

const loadScene = async () => {
  if (!loadSceneId.value) {
    ElMessage.warning('请输入场景ID')
    return
  }
  try {
    const res = await getStandposerScene(loadSceneId.value)
    store.applyScenePayload(res.data)
    syncCameraFromStore()
    await rebuildSceneObjects()
    ElMessage.success('场景已加载')
  } catch (e) {
    ElMessage.error(String(e || '场景加载失败'))
  }
}

const canvasToFile = (canvas) =>
  new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('拍摄失败'))
        return
      }
      resolve(new File([blob], `standposer-shot-${Date.now()}.png`, { type: 'image/png' }))
    }, 'image/png')
  })

const captureShot = async () => {
  if (!renderer) return
  shooting.value = true
  const oldSize = new THREE.Vector2()
  renderer.getSize(oldSize)
  try {
    if (cameraMarker) cameraMarker.visible = false
    renderer.setSize(store.resolution.width, store.resolution.height, false)
    captureCamera.aspect = store.resolution.width / store.resolution.height
    captureCamera.updateProjectionMatrix()
    renderer.render(scene, captureCamera)
    const file = await canvasToFile(renderer.domElement)
    const res = await uploadStandposerShot({
      scene_id: store.activeSceneId,
      image: file,
      width: store.resolution.width,
      height: store.resolution.height,
      camera_state: store.camera,
    })
    lastShotUrl.value = res.data.image_url
    window.open(lastShotUrl.value, '_blank', 'noopener,noreferrer')
    ElMessage.success('拍摄 PNG 已上传')
  } catch (e) {
    ElMessage.error(String(e || '拍摄失败'))
  } finally {
    if (cameraMarker) cameraMarker.visible = !cameraPreview.value
    renderer.setSize(oldSize.x, oldSize.y)
    shooting.value = false
  }
}

watch(
  () => store.placements.map((item) => `${item.id}:${item.modelUrl}`).join('|'),
  () => rebuildSceneObjects()
)

onMounted(async () => {
  initThree()
  try {
    const res = await getStandposerCharacters()
    store.setCharacters(res.data.list || [])
  } catch (e) {
    ElMessage.error(String(e || '角色资产加载失败'))
  }
})

onBeforeUnmount(() => {
  if (animationFrame) cancelAnimationFrame(animationFrame)
  window.removeEventListener('resize', resizeRenderer)
  renderer?.domElement?.removeEventListener('pointerdown', handlePointerDown)
  transformControls?.dispose()
  orbitControls?.dispose()
  renderer?.dispose()
})
</script>

<style scoped>
.poser-shell {
  min-height: 100vh;
  background: #070b16;
  color: #e8eefc;
}

.poser-topbar {
  min-height: 78px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
  border-bottom: 1px solid rgba(71, 138, 196, 0.28);
  background: #0a1020;
}

.poser-topbar h1,
.panel-head h2,
.viewport-title h2 {
  margin: 0;
}

.eyebrow {
  margin: 0 0 4px;
  color: #7fb8ff;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.topbar-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.scene-name {
  width: 190px;
}

.scene-id {
  width: 112px;
}

.poser-workspace {
  height: calc(100vh - 78px);
  display: grid;
  grid-template-columns: 300px minmax(480px, 1fr) 340px;
  gap: 12px;
  padding: 12px;
}

.side-panel,
.viewport-panel {
  min-height: 0;
  border: 1px solid rgba(57, 125, 184, 0.36);
  border-radius: 8px;
  background: #0c1324;
}

.side-panel {
  overflow: auto;
  padding: 14px;
}

.panel-head,
.viewport-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.viewport-panel {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.viewport-title {
  padding: 14px 14px 0;
}

.viewport-title span {
  border-radius: 6px;
  background: #1b2a40;
  color: #cfe0f5;
  padding: 5px 8px;
  font-size: 12px;
}

.three-viewport {
  flex: 1;
  min-height: 0;
}

.three-viewport :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.viewport-toolbar {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.viewport-toolbar button,
.file-picker {
  min-height: 34px;
  border: 1px solid rgba(88, 151, 204, 0.42);
  border-radius: 6px;
  background: #101b30;
  color: #dce8f8;
  padding: 0 12px;
}

.viewport-toolbar button.active {
  background: #f5c84b;
  color: #09111f;
  border-color: transparent;
  font-weight: 700;
}

.file-hidden {
  display: none;
}

.file-picker {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-form {
  margin-bottom: 16px;
}

.asset-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.asset-card {
  border: 1px solid rgba(74, 136, 189, 0.4);
  border-radius: 8px;
  background: #0a1222;
  padding: 12px;
}

.asset-card strong,
.asset-card span {
  display: block;
}

.asset-card span,
.empty-hint {
  color: #8ea2bd;
  font-size: 12px;
}

.asset-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.property-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.property-stack label,
.vector-editor label,
.resolution-grid label {
  color: #cbd8ea;
  font-size: 13px;
}

.vector-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.axis-field {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.axis-field span {
  color: #7fb8ff;
  font-size: 12px;
}

.resolution-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.shot-result {
  margin-top: 16px;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border-top: 1px solid rgba(84, 145, 198, 0.28);
  padding-top: 12px;
}

.shot-result a {
  color: #f5c84b;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: #08101f;
  box-shadow: inset 0 0 0 1px rgba(84, 145, 198, 0.42) !important;
  color: #e8eefc;
}

:deep(.el-form-item__label) {
  color: #cbd8ea;
}

:deep(.el-input-number) {
  width: 100%;
}

@media (max-width: 1160px) {
  .poser-topbar {
    align-items: stretch;
    flex-direction: column;
  }

  .topbar-tools,
  .scene-name,
  .scene-id {
    width: 100%;
  }

  .poser-workspace {
    height: auto;
    grid-template-columns: 1fr;
  }

  .three-viewport {
    min-height: 520px;
  }
}
</style>
