import http from './http'

export const getAiImageConfig = () => http.get('/ai-image/config')

export const generateAiImage = (formData, config = {}) =>
  http.post('/ai-image/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 90000,
    ...config,
  })

export const getAiImageTask = (taskId) => http.get(`/ai-image/tasks/${encodeURIComponent(taskId)}`, { timeout: 45000 })

export const cutoutAiImageCharacter = (formData, config = {}) =>
  http.post('/ai-image/cutout', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    ...config,
  })

export const aiImageCutoutAssetUrl = (key) => `/api/v1/ai-image/cutout-asset?key=${encodeURIComponent(key)}`

export const getAiImageCutoutAssets = () => http.get('/ai-image/cutout-assets')

export const deleteAiImageCutoutAsset = (assetId) => http.delete(`/ai-image/cutout-assets/${encodeURIComponent(assetId)}`)
