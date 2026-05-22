import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useStandposerStore = defineStore('standposer', () => {
  const characters = ref([])
  const activeSceneId = ref(null)
  const selectedObjectId = ref('camera')
  const sceneName = ref('未命名站位')
  const resolution = ref({ width: 1280, height: 720 })
  const camera = ref({
    position: { x: 4, y: 3, z: 6 },
    rotation: { x: -18, y: 34, z: 0 },
    fov: 45,
  })
  const placements = ref([])

  const selectedPlacement = computed(() => placements.value.find((item) => item.id === selectedObjectId.value) || null)

  const setCharacters = (items) => {
    characters.value = items || []
  }

  const addCharacter = (character) => {
    characters.value = [character, ...characters.value.filter((item) => item.id !== character.id)]
  }

  const addPlacement = (character) => {
    const id = `character-${character.id}-${Date.now()}`
    placements.value.push({
      id,
      characterId: character.id,
      name: character.name,
      modelUrl: character.model_url,
      position: { x: 0, y: 0, z: 0 },
      rotation: { x: 0, y: 0, z: 0 },
      scale: { x: 1, y: 1, z: 1 },
      pose: '自然站立',
    })
    selectedObjectId.value = id
  }

  const updatePlacement = (id, patch) => {
    const target = placements.value.find((item) => item.id === id)
    if (!target) return
    Object.assign(target, patch)
  }

  const applyScenePayload = (payload) => {
    activeSceneId.value = payload.id || null
    sceneName.value = payload.name || '未命名站位'
    const data = payload.scene_data || {}
    resolution.value = data.resolution || { width: 1280, height: 720 }
    camera.value = data.camera || camera.value
    placements.value = data.placements || []
    selectedObjectId.value = 'camera'
  }

  const buildScenePayload = () => ({
    name: sceneName.value,
    scene_data: {
      version: 1,
      resolution: resolution.value,
      camera: camera.value,
      placements: placements.value,
    },
  })

  return {
    activeSceneId,
    addCharacter,
    addPlacement,
    applyScenePayload,
    buildScenePayload,
    camera,
    characters,
    placements,
    resolution,
    sceneName,
    selectedObjectId,
    selectedPlacement,
    setCharacters,
    updatePlacement,
  }
})
