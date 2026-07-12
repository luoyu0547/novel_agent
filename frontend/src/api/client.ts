import axios from 'axios'
import type { ApiResponse } from '@/types'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
})

// 请求拦截器：自动从 localStorage 读取 token 并附加到 Authorization 头
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) { config.headers.Authorization = `Bearer ${token}` }
  return config
})

// 响应拦截器：解包统一响应格式；遇到 401 自动跳转到登录页
client.interceptors.response.use(
  (response) => {
    const apiResponse = response.data as ApiResponse<unknown>
    if (apiResponse.code !== 0) {
      return Promise.reject(new Error(apiResponse.message))
    }
    return apiResponse.data as never
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)

export default client
