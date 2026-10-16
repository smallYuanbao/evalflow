// 统一请求封装(axios 实例 + 拦截器):请求前参数注入 / 请求后错误码兼容
import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import { getApiKey } from './key'

// 开发环境默认直连本地后端。
//
// ⚠️ 端口是 **8002,不是 8000**。8000 在本机被 docker 里的 Chroma 占着
// (`docker compose` 把它映射到了宿主机 8000,响应头带 chroma-trace-id),
// 所以后端只能挪到 8002 —— 见 scripts/devguard.mjs 顶部的端口表。
//
// 这个默认值原先是 8000,也就是指向 Chroma:dev 下不设 VITE_API_BASE 时,
// 前端的每个请求都会打到 Chroma 上、换回一个 404。症状看起来是"接口不存在",
// 和病因(连错服务)隔得很远 —— 正是那种要查半天的坑。
//
// 生产走 frontend/.env.production 的 VITE_API_BASE=/api(同源反代),不受这里影响。
export const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8002'

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
  // Ch12 鉴权:已设密钥则每个请求都带 Authorization,后端中间件校验
  const key = getApiKey()
  if (key) config.headers.set('Authorization', `Bearer ${key}`)
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

/**
 * 导出接口的直链(Ch25):给「浏览器原生下载」用——流式落盘、自带进度、不占 JS 内存。
 * 导航请求带不上 Authorization 头,所以已设密钥时改用 ?token=(只有导出端点开这个口子)。
 */
export function exportRunCsvUrl(runId: number): string {
  const key = getApiKey()
  const qs = key ? `?token=${encodeURIComponent(key)}` : ''
  return `${BASE}/runs/${runId}/export${qs}`
}
