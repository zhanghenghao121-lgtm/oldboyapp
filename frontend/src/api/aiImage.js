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
