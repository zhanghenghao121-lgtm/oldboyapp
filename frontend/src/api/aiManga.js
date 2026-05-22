import http from './http'

export const getAiMangaConfig = () => http.get('/ai-manga/config')

export const generateAiMangaStoryboard = (formData, config = {}) =>
  http.post('/ai-manga/storyboard', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
    ...config,
  })
