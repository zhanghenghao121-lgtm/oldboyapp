import http from './http'

export const getAiMangaConfig = () => http.get('/ai-manga/config')

export const generateAiMangaStoryboard = (formData, config = {}) =>
  http.post('/ai-manga/storyboard', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    ...config,
  })

export const recognizeAiMangaPosition = (formData, config = {}) =>
  http.post('/ai-manga/position/recognize', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    ...config,
  })

export const generateAiMangaReversePrompt = (payload) =>
  http.post('/ai-manga/position/reverse-prompt', payload, { timeout: 180000 })

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
