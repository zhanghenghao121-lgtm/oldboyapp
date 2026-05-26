import http from './http'

const COMPRESSION_TRIGGER = 15 * 1024 * 1024
const COMPRESSED_TARGET = 9 * 1024 * 1024

const imageFromFile = (file) =>
  new Promise((resolve, reject) => {
    const image = new Image()
    const url = URL.createObjectURL(file)
    image.onload = () => {
      URL.revokeObjectURL(url)
      resolve(image)
    }
    image.onerror = () => {
      URL.revokeObjectURL(url)
      reject(new Error('图片读取失败'))
    }
    image.src = url
  })

const canvasBlob = (canvas, quality) =>
  new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality))

const compressLargeImage = async (file) => {
  if (!file.type.startsWith('image/') || file.size <= COMPRESSION_TRIGGER) {
    return { file, compressed: false }
  }
  const image = await imageFromFile(file)
  let scale = Math.min(1, 4096 / Math.max(image.naturalWidth, image.naturalHeight))
  let blob = null
  for (let attempt = 0; attempt < 6; attempt += 1) {
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height)
    blob = await canvasBlob(canvas, Math.max(0.56, 0.86 - attempt * 0.06))
    if (blob && blob.size <= COMPRESSED_TARGET) break
    scale *= 0.78
  }
  if (!blob) throw new Error('图片压缩失败')
  const filename = file.name.replace(/\.[^.]+$/, '') || 'image'
  return {
    file: new File([blob], `${filename}.jpg`, { type: 'image/jpeg' }),
    compressed: true,
  }
}

export const uploadToCos = async (file, folder = 'uploads', options = {}) => {
  const prepared = await compressLargeImage(file)
  const formData = new FormData()
  formData.append('file', prepared.file)
  formData.append('folder', folder)
  const timeout = Number(options.timeout || 0)
  const response = await http.post('/storage/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    ...(timeout > 0 ? { timeout } : {}),
  })
  return {
    ...response,
    data: {
      ...response.data,
      compressed: prepared.compressed,
    },
  }
}
