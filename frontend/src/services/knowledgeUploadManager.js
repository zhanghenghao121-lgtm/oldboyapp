import {
  completeAICsKnowledgeUpload,
  getAICsKnowledgeUploadStatus,
  initAICsKnowledgeUpload,
  uploadAICsKnowledgeChunk,
} from '../api/console'

const KB_RESUME_KEY = 'ai_kb_resume_upload'

const state = {
  status: 'idle', // idle | running | success | error
  uploadId: '',
  fileName: '',
  progress: 0,
  uploadedChunks: 0,
  totalChunks: 0,
  resumed: false,
  error: '',
}

const listeners = new Set()
let runningPromise = null

const emit = () => {
  const snapshot = { ...state }
  listeners.forEach((fn) => {
    try {
      fn(snapshot)
    } catch {
      // ignore listener errors
    }
  })
}

const setState = (patch) => {
  Object.assign(state, patch)
  emit()
}

const getKnowledgeFingerprint = (file) => `${file.name}__${file.size}__${file.lastModified}`

const chunkRangeSize = (fileSize, chunkSize, chunkIndex, totalChunks) => {
  const start = chunkIndex * chunkSize
  const end = chunkIndex === totalChunks - 1 ? fileSize : Math.min(start + chunkSize, fileSize)
  return Math.max(end - start, 0)
}

const updateUploadProgress = (committedBytes, totalBytes, inChunkLoaded = 0) => {
  const value = ((committedBytes + inChunkLoaded) / Math.max(totalBytes, 1)) * 100
  setState({ progress: Number(Math.min(100, Math.max(0, value)).toFixed(2)) })
}

const runUpload = async (file, title = '') => {
  const fingerprint = getKnowledgeFingerprint(file)
  const initRes = await initAICsKnowledgeUpload({
    file_name: file.name,
    file_size: file.size,
    title,
    fingerprint,
  })

  const uploadId = initRes.data?.upload_id
  const chunkSize = Number(initRes.data?.chunk_size || 0)
  const totalChunks = Number(initRes.data?.total_chunks || 0)
  if (!uploadId || !chunkSize || !totalChunks) {
    throw new Error('初始化分片上传失败')
  }

  const uploadedSet = new Set((initRes.data?.uploaded_chunks || []).map((i) => Number(i)))
  setState({
    status: 'running',
    uploadId,
    fileName: file.name,
    totalChunks,
    uploadedChunks: uploadedSet.size,
    resumed: uploadedSet.size > 0,
    error: '',
  })
  localStorage.setItem(KB_RESUME_KEY, JSON.stringify({ upload_id: uploadId, fingerprint }))

  let committedBytes = 0
  for (const idx of uploadedSet) {
    committedBytes += chunkRangeSize(file.size, chunkSize, idx, totalChunks)
  }
  updateUploadProgress(committedBytes, file.size, 0)

  for (let idx = 0; idx < totalChunks; idx += 1) {
    if (uploadedSet.has(idx)) continue
    const start = idx * chunkSize
    const end = Math.min(start + chunkSize, file.size)
    const blob = file.slice(start, end)
    const formData = new FormData()
    formData.append('upload_id', uploadId)
    formData.append('chunk_index', String(idx))
    formData.append('chunk_total', String(totalChunks))
    formData.append('chunk', blob, `${file.name}.part${idx}`)
    await uploadAICsKnowledgeChunk(formData, (evt) => {
      const loaded = Number(evt?.loaded || 0)
      updateUploadProgress(committedBytes, file.size, Math.min(loaded, blob.size))
    })
    committedBytes += blob.size
    uploadedSet.add(idx)
    setState({ uploadedChunks: uploadedSet.size })
    updateUploadProgress(committedBytes, file.size, 0)
  }

  const statusRes = await getAICsKnowledgeUploadStatus(uploadId)
  if ((statusRes.data?.uploaded_chunks || []).length < totalChunks) {
    throw new Error('分片状态校验失败，请重试')
  }

  const completeRes = await completeAICsKnowledgeUpload({ upload_id: uploadId, title })
  localStorage.removeItem(KB_RESUME_KEY)
  setState({ status: 'success', progress: 100 })
  return completeRes
}

export const subscribeKnowledgeUpload = (listener) => {
  listeners.add(listener)
  listener({ ...state })
  return () => listeners.delete(listener)
}

export const getKnowledgeUploadState = () => ({ ...state })

export const startKnowledgeUploadTask = async (file, title = '') => {
  if (runningPromise) return runningPromise
  setState({
    status: 'running',
    fileName: file?.name || '',
    progress: 0,
    uploadedChunks: 0,
    totalChunks: 0,
    resumed: false,
    error: '',
  })
  runningPromise = runUpload(file, title)
    .catch((err) => {
      setState({ status: 'error', error: String(err || '上传失败') })
      throw err
    })
    .finally(() => {
      runningPromise = null
    })
  return runningPromise
}
