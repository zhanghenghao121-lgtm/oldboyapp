const DRAFTS_KEY = 'ai_manga_storyboard_drafts'
const ACTIVE_PAYLOAD_KEY = 'ai_manga_storyboard_payload'

const safeJsonParse = (raw, fallback) => {
  try {
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

export const listAiMangaDrafts = () => {
  const items = safeJsonParse(localStorage.getItem(DRAFTS_KEY), [])
  return Array.isArray(items) ? items : []
}

export const setActiveStoryboardPayload = (payload) => {
  sessionStorage.setItem(ACTIVE_PAYLOAD_KEY, JSON.stringify(payload || {}))
}

export const getActiveStoryboardPayload = () => safeJsonParse(sessionStorage.getItem(ACTIVE_PAYLOAD_KEY), null)

export const saveAiMangaDraft = ({ name, payload }) => {
  const title = String(name || '').trim() || `分镜草稿 ${new Date().toLocaleString()}`
  const draftPayload = payload || {}
  const sections = Array.isArray(draftPayload.sections) ? draftPayload.sections : []
  const next = {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: title,
    payload: draftPayload,
    shotCount: sections.length,
    updatedAt: Date.now(),
  }
  const items = listAiMangaDrafts().filter((item) => item && item.id)
  items.unshift(next)
  localStorage.setItem(DRAFTS_KEY, JSON.stringify(items.slice(0, 30)))
  return next
}

export const removeAiMangaDraft = (draftId) => {
  const items = listAiMangaDrafts().filter((item) => item?.id !== draftId)
  localStorage.setItem(DRAFTS_KEY, JSON.stringify(items))
}
