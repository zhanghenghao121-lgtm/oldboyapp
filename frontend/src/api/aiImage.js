import http from './http'

export const cutoutAiImageCharacter = (formData, config = {}) =>
  http.post('/ai-image/cutout', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
    ...config,
  })

export const aiImageCutoutAssetUrl = (key) => `/api/v1/ai-image/cutout-asset?key=${encodeURIComponent(key)}`

export const getAiImageCutoutAssets = () => http.get('/ai-image/cutout-assets')

export const deleteAiImageCutoutAsset = (assetId) => http.delete(`/ai-image/cutout-assets/${encodeURIComponent(assetId)}`)

export const getAiImageStickerCompositions = () => http.get('/ai-image/sticker-compositions')

export const createAiImageStickerComposition = (payload) => http.post('/ai-image/sticker-compositions', payload)

export const enhanceAiImageStickerComposition = (payload) =>
  http.post('/ai-image/sticker-compositions/enhance', payload, { timeout: 600000 })

export const deleteAiImageStickerComposition = (compositionId) =>
  http.delete(`/ai-image/sticker-compositions/${encodeURIComponent(compositionId)}`)

export const getSceneInferenceProjects = () => http.get('/scene-inference/projects', { timeout: 30000 })

export const createSceneInferenceProject = (payload) => http.post('/scene-inference/projects', payload, { timeout: 30000 })

export const getSceneInferenceProject = (projectId) => http.get(`/scene-inference/projects/${projectId}`, { timeout: 30000 })

export const deleteSceneInferenceProject = (projectId) => http.delete(`/scene-inference/projects/${projectId}`, { timeout: 30000 })

export const generateSceneInferenceViews = (projectId, payload) =>
  http.post(`/scene-inference/projects/${projectId}/generate-views`, payload, { timeout: 600000 })

export const generateSceneInferencePanorama = (projectId, payload) =>
  http.post(`/scene-inference/projects/${projectId}/generate-panorama`, payload, { timeout: 600000 })

export const refreshSceneInferenceProject = (projectId) =>
  http.get(`/scene-inference/projects/${projectId}/refresh`, { timeout: 120000 })

export const enhanceSceneInferenceScreenshot = (projectId, payload) =>
  http.post(`/scene-inference/projects/${projectId}/screenshot/enhance`, payload, { timeout: 120000 })
