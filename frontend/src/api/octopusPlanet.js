import http from './http'

export const publishOctopusNote = (payload) =>
  http.post('/octopus-planet/publish', payload, { timeout: 30000 })

export const getOctopusPlanetCommonTags = () =>
  http.get('/octopus-planet/my-common-tags', { timeout: 30000 })

export const addOctopusPlanetTag = (tag) =>
  http.post('/octopus-planet/my-common-tags', { tag }, { timeout: 30000 })

export const getOctopusPlanetParticles = (params = {}) =>
  http.get('/octopus-planet/particles', { params, timeout: 30000 })

export const searchOctopusPlanet = (params = {}) =>
  http.get('/octopus-planet/search', { params, timeout: 30000 })

export const getOctopusPlanetPublish = (publishId) =>
  http.get(`/octopus-planet/publish/${publishId}`, { timeout: 30000 })

export const unpublishOctopusNote = (publishId) =>
  http.delete(`/octopus-planet/publish/${publishId}`, { timeout: 30000 })
