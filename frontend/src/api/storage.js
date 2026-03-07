import http from './http'

export const uploadToCos = (file, folder = 'uploads', options = {}) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('folder', folder)
  const timeout = Number(options.timeout || 0)
  return http.post('/storage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...(timeout > 0 ? { timeout } : {}),
  })
}
