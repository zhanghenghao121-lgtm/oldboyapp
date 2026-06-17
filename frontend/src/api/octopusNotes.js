import http from './http'

const listParams = (params = {}) => ({
  q: params.q || '',
  order: params.order || 'created_desc',
})

export const getOctopusFolders = (params) =>
  http.get('/octopus-note/folders', { params: listParams(params), timeout: 30000 })

export const createOctopusFolder = (payload) =>
  http.post('/octopus-note/folders', payload, { timeout: 30000 })

export const updateOctopusFolder = (folderId, payload) =>
  http.patch(`/octopus-note/folders/${folderId}`, payload, { timeout: 30000 })

export const deleteOctopusFolder = (folderId) =>
  http.delete(`/octopus-note/folders/${folderId}`, { timeout: 30000 })

export const getOctopusNotes = (folderId, params) =>
  http.get(`/octopus-note/folders/${folderId}/notes`, { params: listParams(params), timeout: 30000 })

export const createOctopusNote = (folderId, payload) =>
  http.post(`/octopus-note/folders/${folderId}/notes`, payload, { timeout: 30000 })

export const getOctopusNote = (noteId) =>
  http.get(`/octopus-note/notes/${noteId}`, { timeout: 30000 })

export const updateOctopusNote = (noteId, payload) =>
  http.patch(`/octopus-note/notes/${noteId}`, payload, { timeout: 30000 })

export const deleteOctopusNote = (noteId) =>
  http.delete(`/octopus-note/notes/${noteId}`, { timeout: 30000 })
