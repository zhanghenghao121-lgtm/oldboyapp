import http from './http'

export const getAiCustomerHistory = () => http.get('/ai-customer/history')
