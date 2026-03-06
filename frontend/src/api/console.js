import http from './http'

const TOKEN_KEY = 'console_token'

export const getConsoleToken = () => localStorage.getItem(TOKEN_KEY) || ''
export const setConsoleToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token)
}
export const clearConsoleToken = () => localStorage.removeItem(TOKEN_KEY)
const consoleHeaders = () => ({ headers: { 'X-Console-Token': getConsoleToken() } })

export const consoleLogin = async (payload) => {
  const res = await http.post('/console/login', payload)
  setConsoleToken(res?.data?.token || '')
  return res
}
export const consoleMe = () => http.get('/console/me', consoleHeaders())
export const consoleLogout = async () => {
  try {
    return await http.post('/console/logout', {}, consoleHeaders())
  } finally {
    clearConsoleToken()
  }
}

export const getConsoleConfigs = () => http.get('/console/configs', consoleHeaders())
export const updateConsoleConfig = (key, payload) => http.put(`/console/configs/${key}`, payload, consoleHeaders())

export const getConsoleUsers = (params) => http.get('/console/users', { ...consoleHeaders(), params })
export const updateConsoleUser = (userId, payload) => http.patch(`/console/users/${userId}`, payload, consoleHeaders())

export const getAICsSettings = () => http.get('/console/ai-cs/settings', consoleHeaders())
export const updateAICsSettings = (payload) => http.put('/console/ai-cs/settings', payload, consoleHeaders())
export const getAICsDocs = () => http.get('/console/ai-cs/knowledge/docs', consoleHeaders())
export const cancelAICsDoc = (docId) => http.post(`/console/ai-cs/knowledge/docs/${docId}/cancel`, {}, consoleHeaders())
export const deleteAICsDoc = (docId) => http.delete(`/console/ai-cs/knowledge/docs/${docId}`, consoleHeaders())
export const uploadAICsKnowledge = (formData) => {
  const headers = consoleHeaders().headers
  return http.post('/console/ai-cs/knowledge/upload', formData, {
    headers: { ...headers, 'Content-Type': 'multipart/form-data' },
    timeout: 30 * 60 * 1000,
  })
}
export const initAICsKnowledgeUpload = (payload) => http.post('/console/ai-cs/knowledge/upload/init', payload, consoleHeaders())
export const getAICsKnowledgeUploadStatus = (uploadId) =>
  http.get('/console/ai-cs/knowledge/upload/status', { ...consoleHeaders(), params: { upload_id: uploadId } })
export const uploadAICsKnowledgeChunk = (formData, onUploadProgress) => {
  const headers = consoleHeaders().headers
  return http.post('/console/ai-cs/knowledge/upload/chunk', formData, {
    headers: { ...headers, 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    timeout: 10 * 60 * 1000,
  })
}
export const completeAICsKnowledgeUpload = (payload) =>
  http.post('/console/ai-cs/knowledge/upload/complete', payload, { ...consoleHeaders(), timeout: 30 * 60 * 1000 })
export const getAICsTickets = () => http.get('/console/ai-cs/tickets', consoleHeaders())
export const updateAICsTicket = (ticketId, payload) => http.patch(`/console/ai-cs/tickets/${ticketId}`, payload, consoleHeaders())
export const syncAICsTicketsToKnowledge = (payload) => http.post('/console/ai-cs/tickets/sync-knowledge', payload, consoleHeaders())
