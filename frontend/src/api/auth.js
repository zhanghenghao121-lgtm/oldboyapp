import http from './http'

export const sendEmailCode = (payload) => http.post('/auth/email-code', payload)
export const registerUser = (payload) => http.post('/auth/register', payload)
export const getCaptcha = () => http.get('/auth/captcha')
export const login = (payload) => http.post('/auth/login', payload)
export const me = () => http.get('/auth/me')
export const logout = () => http.post('/auth/logout')
export const resetPassword = (payload) => http.post('/auth/reset-password', payload)
