import http from './http'

export const getAiCustomerHistory = () => http.get('/ai-customer/history')
export const getAiCustomerHumanReplies = () => http.get('/ai-customer/human-replies')
export const clearAiCustomerHumanReplies = () => http.post('/ai-customer/human-replies/clear')
export const generateResumeAssistant = (payload) => http.post('/ai-customer/resume-assistant/generate', payload)
export const createResumeAssistantTask = (payload) => http.post('/ai-customer/resume-assistant/tasks', payload)
export const getResumeAssistantTask = (taskId) => http.get(`/ai-customer/resume-assistant/tasks/${taskId}`)
