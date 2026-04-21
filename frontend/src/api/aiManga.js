import http from './http'

export const getAiMangaConfig = () => http.get('/ai-manga/config')

export const generateAiMangaStoryboard = (formData) =>
  http.post('/ai-manga/storyboard', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })

export const prepareAiMangaStoryboardSections = (payload) =>
  http.post('/ai-manga/storyboard-prepare', payload, {
    timeout: 180000,
  })

export const generateAiMangaStoryboardImage = (payload) =>
  http.post('/ai-manga/storyboard-image', payload, {
    timeout: 180000,
  })
