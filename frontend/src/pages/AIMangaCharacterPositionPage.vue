<template>
  <div class="director-shell">
    <header class="director-topbar">
      <div class="topbar-brand">
        <span class="sidebar-tag">Director Stage</span>
        <div>
          <h2>AI漫剧导演台</h2>
          <p>空间、人物、镜头一体化站位编辑。</p>
        </div>
      </div>
      <nav class="topbar-nav">
        <button class="nav-btn" type="button" @click="$router.push('/ai-manga')">AI漫剧创作</button>
        <button class="nav-btn active" type="button" @click="$router.push('/ai-manga/character-position')">人物站位</button>
        <button class="nav-btn" type="button" @click="$router.push('/ai-customer')">AI章鱼助手</button>
      </nav>
    </header>

    <main class="director-workspace">
      <aside class="asset-panel">
        <section class="panel-section">
          <div class="section-head">
            <p>AI 场景</p>
            <span>{{ sceneState.scene.name }}</span>
          </div>
          <el-input
            v-model="scenePrompt"
            type="textarea"
            :rows="4"
            resize="none"
            placeholder="生成一个古风议事厅，中间有一张长桌，左右各四把椅子。"
          />
          <div class="button-grid">
            <el-button type="primary" class="solid-btn" @click="generateSceneFromText">文本生成空间</el-button>
            <el-button plain class="ghost-btn" @click="applyTextCommand">文本修改空间</el-button>
          </div>
          <input ref="topViewInputRef" class="file-hidden" type="file" accept="image/*" @change="handleTopViewUpload" />
          <el-button class="wide-btn" plain @click="topViewInputRef?.click()">上传俯视全景图</el-button>
          <p v-if="topViewName" class="file-note">{{ topViewName }}</p>
        </section>

        <section class="panel-section">
          <div class="section-head">
            <p>基础物体</p>
            <span>{{ sceneState.objects.length }} 个</span>
          </div>
          <div class="asset-grid">
            <button v-for="asset in assetTemplates" :key="asset.type" type="button" class="asset-btn" @click="addObject(asset.type)">
              <span class="asset-swatch" :style="{ background: asset.color }"></span>
              {{ asset.label }}
            </button>
          </div>
        </section>

        <section class="panel-section">
          <div class="section-head">
            <p>线条人物</p>
            <span>{{ sceneState.characters.length }} 人</span>
          </div>
          <el-button class="wide-btn" type="primary" @click="addCharacter">加入线条人物</el-button>
          <div class="character-list">
            <button
              v-for="character in sceneState.characters"
              :key="character.id"
              type="button"
              class="list-row"
              :class="{ active: selectedKind === 'character' && selectedId === character.id }"
              @click="selectCharacter(character.id)"
            >
              {{ character.name }}
              <span>{{ character.height.toFixed(2) }}m</span>
            </button>
          </div>
        </section>
      </aside>

      <section class="stage-panel">
        <div class="stage-toolbar">
          <div class="tool-group">
            <button type="button" class="tool-btn" :class="{ active: transformMode === 'translate' }" @click="setTransformMode('translate')">移动</button>
            <button type="button" class="tool-btn" :class="{ active: transformMode === 'rotate' }" @click="setTransformMode('rotate')">旋转</button>
            <button type="button" class="tool-btn" :class="{ active: transformMode === 'scale' }" @click="setTransformMode('scale')">缩放</button>
          </div>
          <div class="tool-group">
            <button type="button" class="tool-btn" @click="duplicateSelected">复制</button>
            <button type="button" class="tool-btn danger" @click="deleteSelected">删除</button>
            <button type="button" class="tool-btn" @click="saveSceneLocal">保存</button>
            <button type="button" class="tool-btn" @click="loadSceneLocal">加载</button>
            <button type="button" class="tool-btn" @click="exportSceneJson">导出 JSON</button>
            <button type="button" class="tool-btn primary" @click="generatePreview">生成镜头画面</button>
          </div>
        </div>

        <div ref="canvasWrapRef" class="canvas-wrap">
          <div class="camera-chip">主镜头 · {{ activeCamera.shotType }} · {{ activeCamera.aspect }}</div>
        </div>

        <div class="preview-strip">
          <div class="preview-copy">
            <p>当前镜头</p>
            <span>{{ cameraSummary }}</span>
          </div>
          <img v-if="previewImageUrl" :src="previewImageUrl" alt="当前镜头生成预览" class="preview-image" />
          <div v-else class="preview-empty">等待生成</div>
        </div>
      </section>

      <aside class="property-panel">
        <section class="panel-section">
          <div class="section-head">
            <p>属性</p>
            <span>{{ selectedTitle }}</span>
          </div>

          <div v-if="selectedObject" class="form-stack">
            <el-input v-model="selectedObject.name" label="名称" />
            <div class="field-grid">
              <label>位置 X<el-input-number v-model="selectedObject.position.x" :step="0.1" @change="syncSceneToThree" /></label>
              <label>位置 Y<el-input-number v-model="selectedObject.position.y" :step="0.1" @change="syncSceneToThree" /></label>
              <label>位置 Z<el-input-number v-model="selectedObject.position.z" :step="0.1" @change="syncSceneToThree" /></label>
            </div>
            <div class="field-grid">
              <label>宽度<el-input-number v-model="selectedObject.size.width" :min="0.1" :step="0.1" @change="syncSceneToThree" /></label>
              <label>高度<el-input-number v-model="selectedObject.size.height" :min="0.1" :step="0.1" @change="syncSceneToThree" /></label>
              <label>深度<el-input-number v-model="selectedObject.size.depth" :min="0.1" :step="0.1" @change="syncSceneToThree" /></label>
            </div>
            <div class="field-grid">
              <label>旋转 Y<el-input-number v-model="selectedObject.rotation.y" :step="5" @change="syncSceneToThree" /></label>
              <label>缩放 X<el-input-number v-model="selectedObject.scale.x" :min="0.1" :step="0.1" @change="syncSceneToThree" /></label>
              <label>缩放 Z<el-input-number v-model="selectedObject.scale.z" :min="0.1" :step="0.1" @change="syncSceneToThree" /></label>
            </div>
            <label class="color-field">颜色<input v-model="selectedObject.material.color" type="color" @input="syncSceneToThree" /></label>
          </div>

          <div v-else-if="selectedCharacter" class="form-stack">
            <el-input v-model="selectedCharacter.name" @change="syncSceneToThree" />
            <div class="field-grid">
              <label>位置 X<el-input-number v-model="selectedCharacter.position.x" :step="0.1" @change="syncSceneToThree" /></label>
              <label>位置 Z<el-input-number v-model="selectedCharacter.position.z" :step="0.1" @change="syncSceneToThree" /></label>
              <label>身高<el-input-number v-model="selectedCharacter.height" :min="0.8" :step="0.05" @change="resizeCharacterPose" /></label>
            </div>
            <input ref="characterImageInputRef" class="file-hidden" type="file" accept="image/*" @change="handleCharacterImageUpload" />
            <el-button plain class="wide-btn" @click="characterImageInputRef?.click()">上传人物图片</el-button>
            <div v-if="selectedCharacter.referenceImage" class="reference-preview">
              <img :src="selectedCharacter.referenceImage" :alt="selectedCharacter.name" />
              <span>已绑定人物参考图</span>
            </div>
            <p v-if="selectedJointName" class="joint-note">当前关节：{{ jointLabels[selectedJointName] || selectedJointName }}</p>
          </div>

          <div v-else class="empty-state">选择物体、人物或关节后编辑。</div>
        </section>

        <section class="panel-section">
          <div class="section-head">
            <p>拍摄相机</p>
            <span>{{ activeCamera.name }}</span>
          </div>
          <div class="form-stack">
            <div class="field-grid">
              <label>位置 X<el-input-number v-model="activeCamera.position.x" :step="0.1" @change="syncSceneToThree" /></label>
              <label>位置 Y<el-input-number v-model="activeCamera.position.y" :step="0.1" @change="syncSceneToThree" /></label>
              <label>位置 Z<el-input-number v-model="activeCamera.position.z" :step="0.1" @change="syncSceneToThree" /></label>
            </div>
            <div class="field-grid">
              <label>目标 X<el-input-number v-model="activeCamera.target.x" :step="0.1" @change="syncSceneToThree" /></label>
              <label>目标 Y<el-input-number v-model="activeCamera.target.y" :step="0.1" @change="syncSceneToThree" /></label>
              <label>目标 Z<el-input-number v-model="activeCamera.target.z" :step="0.1" @change="syncSceneToThree" /></label>
            </div>
            <label class="slider-field">FOV<el-slider v-model="activeCamera.fov" :min="18" :max="85" @input="syncSceneToThree" /></label>
            <el-select v-model="activeCamera.aspect" @change="syncSceneToThree">
              <el-option v-for="item in aspectOptions" :key="item" :label="item" :value="item" />
            </el-select>
            <el-select v-model="activeCamera.shotType" @change="syncSceneToThree">
              <el-option v-for="item in shotTypeOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
        </section>
      </aside>
    </main>

    <el-dialog v-model="jsonDialogVisible" title="Scene JSON" width="760px">
      <el-input v-model="sceneJsonText" type="textarea" :rows="18" resize="none" />
      <template #footer>
        <el-button @click="loadFromJsonText">加载 JSON</el-button>
        <el-button type="primary" @click="copySceneJson">复制 JSON</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { TransformControls } from 'three/examples/jsm/controls/TransformControls.js'

const STORAGE_KEY = 'ai_manga_character_position_scene'

const canvasWrapRef = ref(null)
const topViewInputRef = ref(null)
const characterImageInputRef = ref(null)
const scenePrompt = ref('生成一个古风议事厅，中间有一张长桌，左右各四把椅子，后方有屏风。')
const topViewName = ref('')
const previewImageUrl = ref('')
const transformMode = ref('translate')
const selectedKind = ref('')
const selectedId = ref('')
const selectedJointName = ref('')
const jsonDialogVisible = ref(false)
const sceneJsonText = ref('')

const assetTemplates = [
  { type: 'table', label: '桌子', color: '#8b5a2b', size: { width: 2.6, height: 0.75, depth: 1.1 } },
  { type: 'chair', label: '椅子', color: '#b8844b', size: { width: 0.55, height: 0.95, depth: 0.55 } },
  { type: 'sofa', label: '沙发', color: '#4f7a8a', size: { width: 2.1, height: 0.85, depth: 0.8 } },
  { type: 'wall', label: '墙体', color: '#d7c8af', size: { width: 4, height: 2.6, depth: 0.18 } },
  { type: 'door', label: '门', color: '#7b5130', size: { width: 1, height: 2.1, depth: 0.12 } },
  { type: 'cabinet', label: '柜子', color: '#72543a', size: { width: 1.2, height: 1.8, depth: 0.45 } },
]
const aspectOptions = ['16:9', '9:16', '1:1', '4:3', '3:4']
const shotTypeOptions = ['远景', '全景', '中景', '近景', '特写', '过肩镜头', '低机位', '高机位', '俯视', '仰视']
const jointLabels = {
  head: '头部',
  neck: '颈部',
  chest: '胸口',
  pelvis: '骨盆',
  leftShoulder: '左肩',
  leftElbow: '左肘',
  leftHand: '左手',
  rightShoulder: '右肩',
  rightElbow: '右肘',
  rightHand: '右手',
  leftKnee: '左膝',
  leftFoot: '左脚',
  rightKnee: '右膝',
  rightFoot: '右脚',
}
const skeletonLinks = [
  ['head', 'neck'],
  ['neck', 'chest'],
  ['chest', 'pelvis'],
  ['chest', 'leftShoulder'],
  ['leftShoulder', 'leftElbow'],
  ['leftElbow', 'leftHand'],
  ['chest', 'rightShoulder'],
  ['rightShoulder', 'rightElbow'],
  ['rightElbow', 'rightHand'],
  ['pelvis', 'leftKnee'],
  ['leftKnee', 'leftFoot'],
  ['pelvis', 'rightKnee'],
  ['rightKnee', 'rightFoot'],
]

const defaultPose = (height = 1.72) => {
  const r = height / 1.72
  const scale = (value) => Number((value * r).toFixed(3))
  return {
    head: { x: 0, y: scale(1.72), z: 0 },
    neck: { x: 0, y: scale(1.5), z: 0 },
    chest: { x: 0, y: scale(1.28), z: 0 },
    pelvis: { x: 0, y: scale(0.9), z: 0 },
    leftShoulder: { x: scale(-0.28), y: scale(1.38), z: 0 },
    leftElbow: { x: scale(-0.48), y: scale(1.1), z: scale(0.06) },
    leftHand: { x: scale(-0.45), y: scale(0.82), z: scale(0.1) },
    rightShoulder: { x: scale(0.28), y: scale(1.38), z: 0 },
    rightElbow: { x: scale(0.48), y: scale(1.1), z: scale(0.06) },
    rightHand: { x: scale(0.45), y: scale(0.82), z: scale(0.1) },
    leftKnee: { x: scale(-0.18), y: scale(0.48), z: 0 },
    leftFoot: { x: scale(-0.18), y: scale(0.05), z: scale(0.12) },
    rightKnee: { x: scale(0.18), y: scale(0.48), z: 0 },
    rightFoot: { x: scale(0.18), y: scale(0.05), z: scale(0.12) },
  }
}

const makeObject = (type, overrides = {}) => {
  const template = assetTemplates.find((item) => item.type === type) || assetTemplates[0]
  const id = overrides.id || `${type}_${Date.now()}_${Math.floor(Math.random() * 1000)}`
  return {
    id,
    type,
    name: overrides.name || template.label,
    position: { x: overrides.position?.x ?? 0, y: overrides.position?.y ?? 0, z: overrides.position?.z ?? 0 },
    rotation: { x: 0, y: overrides.rotation?.y ?? 0, z: 0 },
    scale: { x: overrides.scale?.x ?? 1, y: overrides.scale?.y ?? 1, z: overrides.scale?.z ?? 1 },
    size: { ...template.size, ...(overrides.size || {}) },
    material: { color: overrides.material?.color || template.color },
    locked: false,
    visible: true,
  }
}

const makeCharacter = (overrides = {}) => {
  const height = overrides.height || 1.72
  return {
    id: overrides.id || `char_${Date.now()}_${Math.floor(Math.random() * 1000)}`,
    type: 'stickman',
    name: overrides.name || `角色${sceneState.characters.length + 1}`,
    referenceImage: overrides.referenceImage || '',
    position: { x: overrides.position?.x ?? 0, y: 0, z: overrides.position?.z ?? 1.5 },
    rotation: { x: 0, y: overrides.rotation?.y ?? 0, z: 0 },
    height,
    pose: overrides.pose || defaultPose(height),
    visible: true,
  }
}

const createInitialScene = () => ({
  version: '1.0',
  unit: 'meter',
  scene: { name: '议事厅站位', width: 10, depth: 8, height: 3.5, style: 'manga_stage', backgroundColor: '#15121a', sourceImageUrl: '' },
  objects: [
    makeObject('table', { id: 'table_001', name: '中式长桌', position: { x: 0, y: 0, z: 0 } }),
    makeObject('chair', { id: 'chair_l_001', name: '左侧椅子', position: { x: -1.9, y: 0, z: -0.6 }, rotation: { y: 90 } }),
    makeObject('chair', { id: 'chair_r_001', name: '右侧椅子', position: { x: 1.9, y: 0, z: -0.6 }, rotation: { y: -90 } }),
    makeObject('sofa', { id: 'sofa_001', name: '后方沙发', position: { x: 0, y: 0, z: 2.8 } }),
    makeObject('wall', { id: 'wall_back_001', name: '后墙', position: { x: 0, y: 1.3, z: 3.95 }, size: { width: 10, height: 2.6, depth: 0.16 } }),
    makeObject('door', { id: 'door_001', name: '正门', position: { x: 0, y: 1.05, z: -3.95 } }),
  ],
  characters: [],
  cameras: [
    {
      id: 'camera_001',
      name: '主镜头',
      position: { x: 3.2, y: 1.7, z: 4.2 },
      target: { x: 0, y: 1.1, z: 0 },
      fov: 45,
      aspect: '16:9',
      shotType: '中景',
      active: true,
    },
  ],
  lights: [
    { id: 'light_001', type: 'ambient', intensity: 0.75, color: '#ffffff' },
    { id: 'light_002', type: 'directional', position: { x: 2, y: 5, z: 3 }, intensity: 1.1, color: '#ffffff' },
  ],
})

const sceneState = reactive(createInitialScene())
const activeCamera = computed(() => sceneState.cameras.find((item) => item.active) || sceneState.cameras[0])
const selectedObject = computed(() => (selectedKind.value === 'object' ? sceneState.objects.find((item) => item.id === selectedId.value) : null))
const selectedCharacter = computed(() => (selectedKind.value === 'character' || selectedKind.value === 'joint' ? sceneState.characters.find((item) => item.id === selectedId.value) : null))
const selectedTitle = computed(() => selectedObject.value?.name || selectedCharacter.value?.name || '未选择')
const cameraSummary = computed(() => {
  const camera = activeCamera.value
  return `位置 ${camera.position.x.toFixed(1)}, ${camera.position.y.toFixed(1)}, ${camera.position.z.toFixed(1)} / FOV ${camera.fov}`
})

let renderer
let threeScene
let editCamera
let orbitControls
let transformControls
let resizeObserver
let dynamicRoot
let floorTexture
let animationId
const objectMap = new Map()
const characterMap = new Map()
const jointMap = new Map()
const lineMap = new Map()
const raycaster = new THREE.Raycaster()
const pointer = new THREE.Vector2()

const copyPlain = (value) => JSON.parse(JSON.stringify(value))

const patchScene = (nextScene) => {
  Object.assign(sceneState, copyPlain(nextScene))
  selectedKind.value = ''
  selectedId.value = ''
  selectedJointName.value = ''
  syncSceneToThree()
}

const makeBox = (width, height, depth, color, position = { x: 0, y: 0, z: 0 }) => {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(width, height, depth), new THREE.MeshStandardMaterial({ color, roughness: 0.72 }))
  mesh.position.set(position.x, position.y, position.z)
  mesh.castShadow = true
  mesh.receiveShadow = true
  return mesh
}

const createObjectGroup = (item) => {
  const group = new THREE.Group()
  group.name = item.name
  group.userData = { kind: 'object', id: item.id }
  const { width, height, depth } = item.size
  const color = item.material.color
  if (item.type === 'chair') {
    group.add(makeBox(width, height * 0.12, depth, color, { x: 0, y: height * 0.45, z: 0 }))
    group.add(makeBox(width, height * 0.58, depth * 0.12, color, { x: 0, y: height * 0.72, z: depth * 0.44 }))
    group.add(makeBox(width * 0.12, height * 0.45, depth * 0.12, color, { x: -width * 0.35, y: height * 0.22, z: -depth * 0.35 }))
    group.add(makeBox(width * 0.12, height * 0.45, depth * 0.12, color, { x: width * 0.35, y: height * 0.22, z: -depth * 0.35 }))
  } else if (item.type === 'sofa') {
    group.add(makeBox(width, height * 0.42, depth, color, { x: 0, y: height * 0.22, z: 0 }))
    group.add(makeBox(width, height * 0.72, depth * 0.14, color, { x: 0, y: height * 0.48, z: depth * 0.42 }))
    group.add(makeBox(width * 0.08, height * 0.38, depth, color, { x: -width * 0.54, y: height * 0.3, z: 0 }))
    group.add(makeBox(width * 0.08, height * 0.38, depth, color, { x: width * 0.54, y: height * 0.3, z: 0 }))
  } else if (item.type === 'table') {
    group.add(makeBox(width, height * 0.12, depth, color, { x: 0, y: height * 0.9, z: 0 }))
    group.add(makeBox(width * 0.06, height * 0.85, depth * 0.06, color, { x: -width * 0.42, y: height * 0.42, z: -depth * 0.38 }))
    group.add(makeBox(width * 0.06, height * 0.85, depth * 0.06, color, { x: width * 0.42, y: height * 0.42, z: -depth * 0.38 }))
    group.add(makeBox(width * 0.06, height * 0.85, depth * 0.06, color, { x: -width * 0.42, y: height * 0.42, z: depth * 0.38 }))
    group.add(makeBox(width * 0.06, height * 0.85, depth * 0.06, color, { x: width * 0.42, y: height * 0.42, z: depth * 0.38 }))
  } else {
    group.add(makeBox(width, height, depth, color, { x: 0, y: height / 2, z: 0 }))
  }
  group.position.set(item.position.x, item.position.y, item.position.z)
  group.rotation.set(THREE.MathUtils.degToRad(item.rotation.x), THREE.MathUtils.degToRad(item.rotation.y), THREE.MathUtils.degToRad(item.rotation.z))
  group.scale.set(item.scale.x, item.scale.y, item.scale.z)
  group.traverse((child) => {
    child.userData = { kind: 'object', id: item.id }
  })
  return group
}

const createCharacterGroup = (character) => {
  const group = new THREE.Group()
  group.name = character.name
  group.userData = { kind: 'character', id: character.id }
  group.position.set(character.position.x, character.position.y, character.position.z)
  group.rotation.y = THREE.MathUtils.degToRad(character.rotation.y || 0)
  const jointMaterial = new THREE.MeshStandardMaterial({ color: '#f7d47f', roughness: 0.35 })
  Object.entries(character.pose).forEach(([name, point]) => {
    const joint = new THREE.Mesh(new THREE.SphereGeometry(name === 'head' ? 0.09 : 0.055, 16, 16), jointMaterial)
    joint.position.set(point.x, point.y, point.z)
    joint.userData = { kind: 'joint', id: character.id, joint: name }
    group.add(joint)
    jointMap.set(`${character.id}:${name}`, joint)
  })
  const lineMaterial = new THREE.LineBasicMaterial({ color: '#f8efe0', linewidth: 2 })
  skeletonLinks.forEach(([from, to]) => {
    const line = new THREE.Line(new THREE.BufferGeometry(), lineMaterial)
    line.userData = { kind: 'character', id: character.id }
    group.add(line)
    lineMap.set(`${character.id}:${from}:${to}`, line)
  })
  updateCharacterLines(character.id)
  return group
}

const updateCharacterLines = (characterId) => {
  const character = sceneState.characters.find((item) => item.id === characterId)
  if (!character) return
  skeletonLinks.forEach(([from, to]) => {
    const line = lineMap.get(`${characterId}:${from}:${to}`)
    const fromJoint = jointMap.get(`${characterId}:${from}`)
    const toJoint = jointMap.get(`${characterId}:${to}`)
    if (!line || !fromJoint || !toJoint) return
    line.geometry.setFromPoints([fromJoint.position.clone(), toJoint.position.clone()])
  })
}

const createCameraMarker = () => {
  const camera = activeCamera.value
  const group = new THREE.Group()
  group.userData = { kind: 'camera', id: camera.id }
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.18, 0.18), new THREE.MeshStandardMaterial({ color: '#74c7ff' }))
  const lens = new THREE.Mesh(new THREE.ConeGeometry(0.1, 0.22, 16), new THREE.MeshStandardMaterial({ color: '#d9f3ff' }))
  lens.rotation.x = Math.PI / 2
  lens.position.z = -0.2
  group.add(body, lens)
  group.position.set(camera.position.x, camera.position.y, camera.position.z)
  group.lookAt(camera.target.x, camera.target.y, camera.target.z)
  return group
}

const rebuildDynamicScene = () => {
  if (!threeScene) return
  if (dynamicRoot) threeScene.remove(dynamicRoot)
  objectMap.clear()
  characterMap.clear()
  jointMap.clear()
  lineMap.clear()
  dynamicRoot = new THREE.Group()
  dynamicRoot.name = 'director-dynamic-root'

  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(sceneState.scene.width, sceneState.scene.depth),
    new THREE.MeshStandardMaterial({ color: '#26202d', roughness: 0.82, side: THREE.DoubleSide })
  )
  floor.rotation.x = -Math.PI / 2
  floor.receiveShadow = true
  dynamicRoot.add(floor)

  if (sceneState.scene.sourceImageUrl) {
    if (floorTexture) floorTexture.dispose()
    floorTexture = new THREE.TextureLoader().load(sceneState.scene.sourceImageUrl)
    const imagePlane = new THREE.Mesh(
      new THREE.PlaneGeometry(sceneState.scene.width, sceneState.scene.depth),
      new THREE.MeshBasicMaterial({ map: floorTexture, transparent: true, opacity: 0.42, side: THREE.DoubleSide })
    )
    imagePlane.rotation.x = -Math.PI / 2
    imagePlane.position.y = 0.01
    dynamicRoot.add(imagePlane)
  }

  sceneState.objects.filter((item) => item.visible).forEach((item) => {
    const group = createObjectGroup(item)
    objectMap.set(item.id, group)
    dynamicRoot.add(group)
  })
  sceneState.characters.filter((item) => item.visible).forEach((item) => {
    const group = createCharacterGroup(item)
    characterMap.set(item.id, group)
    dynamicRoot.add(group)
  })
  dynamicRoot.add(createCameraMarker())
  threeScene.add(dynamicRoot)
  attachSelectedControl()
}

const attachSelectedControl = () => {
  if (!transformControls) return
  transformControls.detach()
  if (selectedKind.value === 'object' && objectMap.has(selectedId.value)) transformControls.attach(objectMap.get(selectedId.value))
  if (selectedKind.value === 'character' && characterMap.has(selectedId.value)) transformControls.attach(characterMap.get(selectedId.value))
  if (selectedKind.value === 'joint') {
    const joint = jointMap.get(`${selectedId.value}:${selectedJointName.value}`)
    if (joint) transformControls.attach(joint)
  }
}

const syncFromTransform = () => {
  if (selectedKind.value === 'object') {
    const object = selectedObject.value
    const group = objectMap.get(selectedId.value)
    if (!object || !group) return
    object.position.x = Number(group.position.x.toFixed(3))
    object.position.y = Number(group.position.y.toFixed(3))
    object.position.z = Number(group.position.z.toFixed(3))
    object.rotation.y = Number(THREE.MathUtils.radToDeg(group.rotation.y).toFixed(1))
    object.scale.x = Number(group.scale.x.toFixed(3))
    object.scale.y = Number(group.scale.y.toFixed(3))
    object.scale.z = Number(group.scale.z.toFixed(3))
  }
  if (selectedKind.value === 'character') {
    const character = selectedCharacter.value
    const group = characterMap.get(selectedId.value)
    if (!character || !group) return
    character.position.x = Number(group.position.x.toFixed(3))
    character.position.y = Number(group.position.y.toFixed(3))
    character.position.z = Number(group.position.z.toFixed(3))
    character.rotation.y = Number(THREE.MathUtils.radToDeg(group.rotation.y).toFixed(1))
  }
  if (selectedKind.value === 'joint') {
    const character = selectedCharacter.value
    const joint = jointMap.get(`${selectedId.value}:${selectedJointName.value}`)
    if (!character || !joint) return
    character.pose[selectedJointName.value] = {
      x: Number(joint.position.x.toFixed(3)),
      y: Number(Math.max(0, joint.position.y).toFixed(3)),
      z: Number(joint.position.z.toFixed(3)),
    }
    updateCharacterLines(character.id)
  }
}

const syncSceneToThree = () => {
  nextTick(() => rebuildDynamicScene())
}

const selectObject = (id) => {
  selectedKind.value = 'object'
  selectedId.value = id
  selectedJointName.value = ''
  attachSelectedControl()
}

const selectCharacter = (id) => {
  selectedKind.value = 'character'
  selectedId.value = id
  selectedJointName.value = ''
  attachSelectedControl()
}

const selectJoint = (id, joint) => {
  selectedKind.value = 'joint'
  selectedId.value = id
  selectedJointName.value = joint
  transformMode.value = 'translate'
  setTransformMode('translate')
  attachSelectedControl()
}

const setTransformMode = (mode) => {
  transformMode.value = mode
  transformControls?.setMode(mode)
}

const addObject = (type) => {
  sceneState.objects.push(makeObject(type, { position: { x: 0, y: 0, z: 0.6 } }))
  syncSceneToThree()
}

const addCharacter = () => {
  const character = makeCharacter()
  sceneState.characters.push(character)
  syncSceneToThree()
  nextTick(() => selectCharacter(character.id))
}

const duplicateSelected = () => {
  if (selectedObject.value) {
    const copy = copyPlain(selectedObject.value)
    copy.id = `${copy.type}_${Date.now()}`
    copy.name = `${copy.name} 副本`
    copy.position.x += 0.5
    copy.position.z += 0.5
    sceneState.objects.push(copy)
    syncSceneToThree()
    nextTick(() => selectObject(copy.id))
  } else if (selectedCharacter.value) {
    const copy = copyPlain(selectedCharacter.value)
    copy.id = `char_${Date.now()}`
    copy.name = `${copy.name} 副本`
    copy.position.x += 0.5
    sceneState.characters.push(copy)
    syncSceneToThree()
    nextTick(() => selectCharacter(copy.id))
  }
}

const deleteSelected = () => {
  if (selectedKind.value === 'object') {
    const index = sceneState.objects.findIndex((item) => item.id === selectedId.value)
    if (index >= 0) sceneState.objects.splice(index, 1)
  }
  if (selectedKind.value === 'character' || selectedKind.value === 'joint') {
    const index = sceneState.characters.findIndex((item) => item.id === selectedId.value)
    if (index >= 0) sceneState.characters.splice(index, 1)
  }
  selectedKind.value = ''
  selectedId.value = ''
  selectedJointName.value = ''
  syncSceneToThree()
}

const resizeCharacterPose = () => {
  if (!selectedCharacter.value) return
  selectedCharacter.value.pose = defaultPose(selectedCharacter.value.height)
  syncSceneToThree()
}

const handleTopViewUpload = (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  topViewName.value = file.name
  sceneState.scene.sourceImageUrl = URL.createObjectURL(file)
  generateSceneFromText()
  ElMessage.success('俯视图已载入为地面参考')
}

const handleCharacterImageUpload = (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || !selectedCharacter.value) return
  selectedCharacter.value.referenceImage = URL.createObjectURL(file)
  ElMessage.success('人物参考图已绑定')
}

const generateSceneFromText = () => {
  const prompt = scenePrompt.value || ''
  const next = createInitialScene()
  next.scene.name = prompt.includes('古风') ? '古风议事厅' : prompt.includes('客厅') ? '客厅站位' : 'AI 生成空间'
  next.scene.sourceImageUrl = sceneState.scene.sourceImageUrl
  if (prompt.includes('沙发')) {
    next.objects.push(makeObject('sofa', { name: '侧边沙发', position: { x: -3, y: 0, z: 1.6 }, rotation: { y: 35 } }))
  }
  if (prompt.includes('书架') || prompt.includes('柜')) {
    next.objects.push(makeObject('cabinet', { name: '书架柜', position: { x: 3.8, y: 0, z: 1.4 } }))
  }
  if (prompt.includes('屏风')) {
    next.objects.push(makeObject('wall', { name: '屏风', position: { x: 0, y: 1.2, z: 3.2 }, size: { width: 3, height: 2.4, depth: 0.12 }, material: { color: '#b49770' } }))
  }
  const chairCount = prompt.match(/四把椅子|4把椅子/) ? 4 : 2
  for (let index = 0; index < chairCount; index += 1) {
    const z = -1.1 + index * 0.72
    next.objects.push(makeObject('chair', { name: `左侧椅子 ${index + 1}`, position: { x: -2.05, y: 0, z }, rotation: { y: 90 } }))
    next.objects.push(makeObject('chair', { name: `右侧椅子 ${index + 1}`, position: { x: 2.05, y: 0, z }, rotation: { y: -90 } }))
  }
  patchScene(next)
  ElMessage.success('已生成可编辑空间')
}

const applyTextCommand = () => {
  const command = scenePrompt.value || ''
  const table = sceneState.objects.find((item) => item.type === 'table')
  const sofa = sceneState.objects.find((item) => item.type === 'sofa')
  if (command.includes('桌子') && (command.includes('放大') || command.includes('变大')) && table) {
    table.scale.x = Number((table.scale.x * 1.2).toFixed(2))
    table.scale.z = Number((table.scale.z * 1.2).toFixed(2))
  }
  if (command.includes('沙发') && command.includes('左') && sofa) sofa.position.x -= 0.5
  if (command.includes('门口')) {
    if (!sceneState.characters.length) sceneState.characters.push(makeCharacter({ name: '角色1' }))
    sceneState.characters[0].position.x = 0
    sceneState.characters[0].position.z = -3.1
  }
  syncSceneToThree()
  ElMessage.success('文本修改已应用')
}

const sceneSnapshot = () => ({
  version: sceneState.version,
  unit: sceneState.unit,
  scene: copyPlain(sceneState.scene),
  objects: copyPlain(sceneState.objects),
  characters: copyPlain(sceneState.characters),
  cameras: copyPlain(sceneState.cameras),
  lights: copyPlain(sceneState.lights),
})

const saveSceneLocal = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sceneSnapshot()))
  ElMessage.success('场景已保存')
}

const loadSceneLocal = () => {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    ElMessage.warning('还没有保存过场景')
    return
  }
  patchScene(JSON.parse(raw))
  ElMessage.success('场景已加载')
}

const exportSceneJson = () => {
  sceneJsonText.value = JSON.stringify(sceneSnapshot(), null, 2)
  jsonDialogVisible.value = true
}

const loadFromJsonText = () => {
  try {
    patchScene(JSON.parse(sceneJsonText.value))
    jsonDialogVisible.value = false
    ElMessage.success('JSON 已加载')
  } catch {
    ElMessage.error('JSON 格式错误')
  }
}

const copySceneJson = async () => {
  await navigator.clipboard.writeText(sceneJsonText.value)
  ElMessage.success('Scene JSON 已复制')
}

const makeShotCamera = () => {
  const camera = activeCamera.value
  const [w, h] = camera.aspect.split(':').map(Number)
  const shotCamera = new THREE.PerspectiveCamera(camera.fov, w / h, 0.1, 100)
  shotCamera.position.set(camera.position.x, camera.position.y, camera.position.z)
  shotCamera.lookAt(camera.target.x, camera.target.y, camera.target.z)
  return shotCamera
}

const generatePreview = () => {
  if (!renderer || !threeScene) return
  const originalSize = new THREE.Vector2()
  renderer.getSize(originalSize)
  const shotCamera = makeShotCamera()
  renderer.render(threeScene, shotCamera)
  previewImageUrl.value = renderer.domElement.toDataURL('image/png')
  renderer.setSize(originalSize.x, originalSize.y, false)
  ElMessage.success('当前镜头画面已生成')
}

const handlePointerDown = (event) => {
  if (!renderer || !editCamera || !dynamicRoot) return
  const rect = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, editCamera)
  const hits = raycaster.intersectObjects(dynamicRoot.children, true)
  const hit = hits.find((item) => item.object.userData?.kind)
  if (!hit) return
  const data = hit.object.userData
  if (data.kind === 'joint') selectJoint(data.id, data.joint)
  if (data.kind === 'object') selectObject(data.id)
  if (data.kind === 'character') selectCharacter(data.id)
}

const resizeRenderer = () => {
  if (!renderer || !canvasWrapRef.value || !editCamera) return
  const rect = canvasWrapRef.value.getBoundingClientRect()
  renderer.setSize(rect.width, rect.height)
  editCamera.aspect = rect.width / rect.height
  editCamera.updateProjectionMatrix()
}

const initThree = () => {
  if (!canvasWrapRef.value) return
  threeScene = new THREE.Scene()
  threeScene.background = new THREE.Color('#141018')
  editCamera = new THREE.PerspectiveCamera(52, 1, 0.1, 100)
  editCamera.position.set(5, 5, 6)
  editCamera.lookAt(0, 0, 0)
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.shadowMap.enabled = true
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  canvasWrapRef.value.appendChild(renderer.domElement)
  orbitControls = new OrbitControls(editCamera, renderer.domElement)
  orbitControls.enableDamping = true
  orbitControls.target.set(0, 0.8, 0)
  transformControls = new TransformControls(editCamera, renderer.domElement)
  transformControls.addEventListener('dragging-changed', (event) => {
    orbitControls.enabled = !event.value
  })
  transformControls.addEventListener('objectChange', syncFromTransform)
  threeScene.add(transformControls)
  threeScene.add(new THREE.GridHelper(12, 24, '#5d5367', '#393241'))
  threeScene.add(new THREE.AmbientLight('#ffffff', 0.75))
  const light = new THREE.DirectionalLight('#ffffff', 1.15)
  light.position.set(4, 7, 5)
  light.castShadow = true
  threeScene.add(light)
  renderer.domElement.addEventListener('pointerdown', handlePointerDown)
  resizeObserver = new ResizeObserver(resizeRenderer)
  resizeObserver.observe(canvasWrapRef.value)
  resizeRenderer()
  rebuildDynamicScene()
  const animate = () => {
    animationId = requestAnimationFrame(animate)
    orbitControls.update()
    renderer.render(threeScene, editCamera)
  }
  animate()
}

onMounted(() => {
  nextTick(initThree)
})

onBeforeUnmount(() => {
  if (animationId) cancelAnimationFrame(animationId)
  renderer?.domElement?.removeEventListener('pointerdown', handlePointerDown)
  resizeObserver?.disconnect()
  transformControls?.dispose()
  orbitControls?.dispose()
  renderer?.dispose()
  if (renderer?.domElement?.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement)
})
</script>

<style scoped>
.director-shell {
  min-height: 100vh;
  background:
    radial-gradient(900px 420px at 18% -4%, rgba(255, 166, 64, 0.14), transparent 65%),
    radial-gradient(780px 380px at 100% 0%, rgba(65, 208, 255, 0.12), transparent 62%),
    linear-gradient(135deg, #120f18, #1d1623 48%, #0f1117);
  color: #f7f2ea;
}
.director-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 26px;
  border-bottom: 1px solid rgba(255, 209, 153, 0.18);
  background: rgba(18, 16, 24, 0.96);
}
.topbar-brand {
  display: flex;
  align-items: center;
  gap: 18px;
}
.sidebar-tag {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: #ffddaf;
  border: 1px solid rgba(255, 190, 112, 0.28);
  background: rgba(255, 164, 67, 0.08);
  white-space: nowrap;
}
.topbar-brand h2 {
  margin: 0 0 6px;
  font-size: 30px;
  line-height: 1;
  font-family: Georgia, 'Times New Roman', serif;
}
.topbar-brand p {
  margin: 0;
  color: #cebfae;
  line-height: 1.5;
}
.topbar-nav,
.stage-toolbar,
.tool-group,
.button-grid,
.preview-strip {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.nav-btn,
.tool-btn,
.asset-btn {
  border: 1px solid rgba(255, 212, 154, 0.15);
  background: rgba(255, 255, 255, 0.04);
  color: #f2e8dc;
}
.nav-btn {
  min-width: 148px;
  border-radius: 14px;
  padding: 12px 18px;
}
.nav-btn.active,
.tool-btn.primary,
.solid-btn,
.main-action {
  background: linear-gradient(135deg, rgba(255, 162, 72, 0.92), rgba(255, 118, 64, 0.96));
  color: #25120d;
  border-color: transparent;
}
.director-workspace {
  display: grid;
  grid-template-columns: 300px minmax(420px, 1fr) 330px;
  gap: 14px;
  padding: 16px;
  min-height: calc(100vh - 93px);
}
.asset-panel,
.property-panel,
.stage-panel {
  min-width: 0;
}
.panel-section,
.stage-panel {
  border: 1px solid rgba(255, 223, 192, 0.12);
  background: rgba(255, 247, 238, 0.045);
  box-shadow: 0 18px 42px rgba(5, 6, 12, 0.22);
}
.panel-section {
  padding: 16px;
  border-radius: 18px;
  margin-bottom: 12px;
}
.stage-panel {
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  overflow: hidden;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}
.section-head p {
  margin: 0;
  color: #fff1dc;
  font-weight: 700;
}
.section-head span,
.file-note,
.joint-note,
.preview-copy span {
  color: #cdbba8;
  font-size: 12px;
}
.button-grid {
  margin-top: 10px;
}
.button-grid > * {
  flex: 1 1 120px;
}
.wide-btn {
  width: 100%;
  margin-top: 10px;
}
.ghost-btn {
  border-color: rgba(255, 205, 138, 0.24);
  color: #ffe2b7;
  background: rgba(255, 191, 102, 0.08);
}
.file-hidden {
  display: none;
}
.asset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.asset-btn {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  min-height: 42px;
  border-radius: 12px;
  padding: 0 12px;
}
.asset-swatch {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.2);
}
.character-list,
.form-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.list-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 38px;
  border-radius: 10px;
  border: 1px solid rgba(255, 212, 154, 0.12);
  background: rgba(18, 17, 24, 0.72);
  color: #f7f2ea;
  padding: 0 12px;
}
.list-row.active {
  border-color: rgba(255, 162, 72, 0.9);
  color: #ffcb87;
}
.stage-toolbar {
  justify-content: space-between;
  padding: 12px;
  background: rgba(18, 16, 24, 0.78);
  border-bottom: 1px solid rgba(255, 212, 154, 0.1);
}
.tool-btn {
  min-height: 34px;
  border-radius: 10px;
  padding: 0 12px;
}
.tool-btn.active {
  border-color: rgba(116, 199, 255, 0.75);
  color: #bceaff;
}
.tool-btn.danger {
  color: #ffb2a3;
}
.canvas-wrap {
  position: relative;
  min-height: 560px;
  flex: 1;
}
.canvas-wrap :deep(canvas) {
  display: block;
  width: 100%;
  height: 100%;
}
.camera-chip {
  position: absolute;
  top: 14px;
  left: 14px;
  z-index: 2;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(10, 10, 14, 0.72);
  border: 1px solid rgba(116, 199, 255, 0.24);
  color: #d9f3ff;
  font-size: 12px;
}
.preview-strip {
  justify-content: space-between;
  padding: 12px;
  border-top: 1px solid rgba(255, 212, 154, 0.1);
  background: rgba(18, 16, 24, 0.78);
}
.preview-copy p {
  margin: 0 0 4px;
  font-weight: 700;
}
.preview-image,
.preview-empty {
  width: 180px;
  aspect-ratio: 16 / 9;
  border-radius: 10px;
  border: 1px solid rgba(255, 223, 192, 0.14);
  object-fit: cover;
}
.preview-empty {
  display: grid;
  place-items: center;
  color: #cdbba8;
  background: rgba(12, 12, 18, 0.55);
}
.field-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.field-grid label,
.slider-field,
.color-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: #d8cab7;
  font-size: 12px;
}
.field-grid :deep(.el-input-number) {
  width: 100%;
}
.color-field input {
  width: 100%;
  height: 36px;
  border: 0;
  border-radius: 8px;
  background: transparent;
}
.reference-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(18, 17, 24, 0.72);
}
.reference-preview img {
  width: 52px;
  height: 52px;
  border-radius: 10px;
  object-fit: cover;
}
.empty-state {
  min-height: 120px;
  display: grid;
  place-items: center;
  color: #cdbba8;
  text-align: center;
  border: 1px dashed rgba(255, 218, 176, 0.16);
  border-radius: 14px;
}

@media (max-width: 1220px) {
  .director-workspace {
    grid-template-columns: 280px minmax(420px, 1fr);
  }
  .property-panel {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }
}

@media (max-width: 860px) {
  .director-topbar {
    flex-direction: column;
    align-items: stretch;
  }
  .director-workspace,
  .property-panel {
    grid-template-columns: 1fr;
  }
  .canvas-wrap {
    min-height: 420px;
  }
  .nav-btn {
    flex: 1 1 160px;
  }
}
</style>
