import http from './http'

export const getScriptBreakdownProjects = () => http.get('/ai-script-breakdown/projects')
export const createScriptBreakdownProject = (payload) => http.post('/ai-script-breakdown/projects', payload, { timeout: 30000 })
export const getScriptBreakdownProject = (id) => http.get(`/ai-script-breakdown/projects/${id}`, { timeout: 30000 })
export const deleteScriptBreakdownProject = (id) => http.delete(`/ai-script-breakdown/projects/${id}`, { timeout: 30000 })
export const runScriptBreakdownProject = (id) => http.post(`/ai-script-breakdown/projects/${id}/run`, {}, { timeout: 900000 })
export const updateScriptBreakdownAsset = (id, payload) => http.patch(`/ai-script-breakdown/assets/${id}`, payload, { timeout: 30000 })
export const deleteScriptBreakdownAsset = (id) => http.delete(`/ai-script-breakdown/assets/${id}`, { timeout: 30000 })
export const regenerateScriptSegment = (id) => http.post(`/ai-script-breakdown/segments/${id}/regenerate`, {}, { timeout: 300000 })
export const generateScriptPositionImage = (id, payload) => http.post(`/ai-script-breakdown/segments/${id}/generate-position-image`, payload, { timeout: 300000 })
export const refreshScriptPositionImage = (id) => http.get(`/ai-script-breakdown/segments/${id}/position-image/refresh`, { timeout: 120000 })
export const regenerateScriptPosition = (id, payload = {}) => http.post(`/ai-script-breakdown/segments/${id}/regenerate-position`, payload, { timeout: 300000 })
