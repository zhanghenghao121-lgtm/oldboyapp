import http from './http'

export const getStandposerCharacters = () => http.get('/standposer/characters/')

export const createStandposerCharacter = (payload) => {
  const formData = new FormData()
  formData.append('name', payload.name)
  formData.append('file', payload.file)
  return http.post('/standposer/characters/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

export const generateStandposerCharacterModel = (id) => http.post(`/standposer/characters/${id}/generate-model/`)

export const createStandposerScene = (payload) => http.post('/standposer/scenes/', payload)

export const getStandposerScene = (id) => http.get(`/standposer/scenes/${id}/`)

export const updateStandposerScene = (id, payload) => http.patch(`/standposer/scenes/${id}/`, payload)

export const uploadStandposerShot = (payload) => {
  const formData = new FormData()
  if (payload.scene_id) formData.append('scene_id', payload.scene_id)
  formData.append('image', payload.image)
  formData.append('width', payload.width)
  formData.append('height', payload.height)
  formData.append('camera_state', JSON.stringify(payload.camera_state || {}))
  return http.post('/standposer/shots/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}
