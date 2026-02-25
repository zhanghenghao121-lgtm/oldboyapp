import axios from 'axios'

const http = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  timeout: 15000,
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => Promise.reject(err.response?.data?.message || err.message || '请求失败')
)

export default http
