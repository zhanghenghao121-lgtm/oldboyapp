import http from './http'

export const generateStoryboard = (payload) => http.post('/script-optimizer/storyboard', payload)
export const generateParagraphStoryboard = (payload) => http.post('/script-optimizer/paragraph-storyboard', payload)
