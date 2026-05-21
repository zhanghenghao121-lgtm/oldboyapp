import http from './http'

export const getAiMangaConfig = () => http.get('/ai-manga/config')

export const parseAiMangaScenes = (formData) =>
  http.post('/ai-manga/scenes', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })

export const generateAiMangaStoryboard = (formData) =>
  http.post('/ai-manga/storyboard', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
