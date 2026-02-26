import http from './http'

export const consoleLogin = (payload) => http.post('/console/login', payload)
export const consoleMe = () => http.get('/console/me')
export const consoleLogout = () => http.post('/console/logout')

export const getConsoleBackgrounds = () => http.get('/console/backgrounds')
export const updateConsoleBackground = (scene, payload) => http.put(`/console/backgrounds/${scene}`, payload)

export const getConsoleUsers = (params) => http.get('/console/users', { params })
export const updateConsoleUser = (userId, payload) => http.patch(`/console/users/${userId}`, payload)
