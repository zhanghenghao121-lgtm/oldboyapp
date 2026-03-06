import http from './http'

export const getBloggerHotwords = (limit = 50) => http.get(`/ai-blogger/hotwords?limit=${limit}`)
export const refreshBloggerHotwords = () => http.post('/ai-blogger/hotwords/refresh')
export const createBloggerPost = (payload) => http.post('/ai-blogger/posts', payload)
export const getBloggerPost = (postId) => http.get(`/ai-blogger/posts/${postId}`)
export const cancelBloggerPost = (postId) => http.post(`/ai-blogger/posts/${postId}/cancel`)
export const selectBloggerCover = (postId, payload) => http.post(`/ai-blogger/posts/${postId}/select-cover`, payload)
export const createBloggerVideo = (postId, payload) => http.post(`/ai-blogger/posts/${postId}/video`, payload)
export const cancelBloggerVideo = (postId) => http.post(`/ai-blogger/posts/${postId}/video/cancel`)
export const getBloggerVideoStatus = (postId) => http.get(`/ai-blogger/posts/${postId}/video/status`)
