// 统一请求封装(axios 实例 + 拦截器):请求前参数注入 / 请求后错误码兼容
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'

const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// 统一错误类型:带状态码,上层可按 status 分支
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// 错误码 → 友好文案(后端是 FastAPI,错误体形如 {"detail": "..."})
const ERROR_MESSAGES: Record<number, string> = {
  400: '请求参数有误',
  401: '未登录或登录已过期',
  403: '没有权限',
  404: '资源不存在',
  422: '参数校验失败',
  500: '服务器开小差了',
}

// axios 实例:baseURL 统一,拦截器承载「请求前 / 请求后」两个钩子
const http = axios.create({ baseURL: BASE })

// 请求「前」钩子:统一参数注入(axios request 拦截器)
http.interceptors.request.use((config) => {
  config.headers.set('Content-Type', 'application/json')
  // 以后要注入的公共参数都在这加,例如:
  // const token = getToken(); if (token) config.headers.set('Authorization', `Bearer ${token}`)
  // config.headers.set('X-Request-Id', crypto.randomUUID())
  return config
})

// 请求「后」钩子:异常错误码兼容处理(axios response 拦截器,只处理 rejected)
http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    // 主动取消(AbortController)原样抛出,交给 useRequest 判断;其余才是真错误
    if (error.code === 'ERR_CANCELED') throw error
    if (error.response) {
      const { status, data } = error.response
      const detail = (data as { detail?: unknown } | null)?.detail
      const msg = typeof detail === 'string' ? detail : ERROR_MESSAGES[status] || `请求失败(${status})`
      throw new ApiError(status, msg)
    }
    // 没有 response:网络层失败(断网/CORS/后端没起)
    throw new ApiError(0, '网络异常,请确认后端已启动')
  },
)

// 统一请求入口:所有接口都走这里(config 可带 signal 由 useRequest 传入;POST 用 data 传体,axios 自动 JSON.stringify)
export async function request<T>(path: string, config?: AxiosRequestConfig): Promise<T> {
  const resp = await http.request<T>({ url: path, ...config })
  if (resp.status === 204) return undefined as T
  return resp.data
}
