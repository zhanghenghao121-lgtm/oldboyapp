import http from './http'

export const uploadToCos = (file, folder = 'uploads') => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('folder', folder)
  return http.post('/storage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}
