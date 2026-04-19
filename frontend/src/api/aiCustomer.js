import http from './http'

export const getAiCustomerHistory = (params) => http.get('/ai-customer/history', { params })
export const getAiCustomerSessions = () => http.get('/ai-customer/sessions')
export const getAiCustomerHumanReplies = () => http.get('/ai-customer/human-replies')
export const clearAiCustomerHumanReplies = () => http.post('/ai-customer/human-replies/clear')
