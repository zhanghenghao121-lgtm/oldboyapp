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
