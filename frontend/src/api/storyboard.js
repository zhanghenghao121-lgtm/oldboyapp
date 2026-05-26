import http from './http'

export const getStoryboardConfig = () => http.get('/storyboard/config')
export const createStoryboardProject = (payload) => http.post('/storyboard/projects', payload, { timeout: 30000 })
export const analyzeStoryboardProject = (id) => http.post(`/storyboard/projects/${id}/analyze`, {}, { timeout: 600000 })
export const getStoryboardSegments = (id) => http.get(`/storyboard/projects/${id}/segments`, { timeout: 30000 })
export const saveStoryboardAsset = (segmentId, payload) => http.post(`/storyboard/segments/${segmentId}/assets`, payload, { timeout: 30000 })
export const deleteStoryboardAsset = (segmentId, assetId) => http.delete(`/storyboard/segments/${segmentId}/assets/${assetId}`, { timeout: 30000 })
export const generateStoryboardPanels = (segmentId, model) => http.post(`/storyboard/segments/${segmentId}/generate-panels`, { model }, { timeout: 600000 })
export const generateStoryboardImages = (segmentId, model) => http.post(`/storyboard/segments/${segmentId}/generate-panel-images`, { model }, { timeout: 600000 })
export const refreshStoryboardImages = (segmentId) => http.get(`/storyboard/segments/${segmentId}/panel-images/refresh`, { timeout: 120000 })
export const composeStoryboardGrid = (segmentId) => http.post(`/storyboard/segments/${segmentId}/compose-grid`, {}, { timeout: 180000 })
export const updateStoryboardPanel = (panelId, payload) => http.patch(`/storyboard/panels/${panelId}`, payload, { timeout: 30000 })
export const regenerateStoryboardPanel = (panelId, payload) => http.post(`/storyboard/panels/${panelId}/regenerate`, payload, { timeout: 180000 })
