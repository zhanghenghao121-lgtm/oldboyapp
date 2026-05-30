import http from './http'

export const getScriptBreakdownProjects = () => http.get('/ai-script-breakdown/projects')
export const createScriptBreakdownProject = (payload) => http.post('/ai-script-breakdown/projects', payload, { timeout: 30000 })
export const getScriptBreakdownProject = (id) => http.get(`/ai-script-breakdown/projects/${id}`, { timeout: 30000 })
export const deleteScriptBreakdownProject = (id) => http.delete(`/ai-script-breakdown/projects/${id}`, { timeout: 30000 })
export const runScriptBreakdownProject = (id) => http.post(`/ai-script-breakdown/projects/${id}/run`, {}, { timeout: 900000 })
export const regenerateScriptSegment = (id) => http.post(`/ai-script-breakdown/segments/${id}/regenerate`, {}, { timeout: 300000 })
export const regenerateScriptPosition = (id) => http.post(`/ai-script-breakdown/segments/${id}/regenerate-position`, {}, { timeout: 180000 })
