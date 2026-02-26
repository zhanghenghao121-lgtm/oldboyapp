import http from './http'

export const getSiteBackgrounds = () => http.get('/site/backgrounds')
