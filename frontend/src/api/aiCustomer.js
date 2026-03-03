import http from './http'

export const getAiCustomerHistory = () => http.get('/ai-customer/history')
export const getAiCustomerHumanReplies = () => http.get('/ai-customer/human-replies')
export const clearAiCustomerHumanReplies = () => http.post('/ai-customer/human-replies/clear')
