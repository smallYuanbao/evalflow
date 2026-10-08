// 统一请求封装:请求前参数注入 / 请求后错误码兼容
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

// 请求「前」钩子:统一参数注入
function onRequest(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  // 以后要注入的公共参数都在这加,例如:
  // const token = getToken(); if (token) headers.set('Authorization', `Bearer ${token}`)
  // headers.set('X-Request-Id', crypto.randomUUID())
  return { ...init, headers }
}

// 请求「后」钩子:异常错误码兼容处理
async function onResponse(resp: Response): Promise<Response> {
  if (resp.ok) return resp
  let detail = ''
  try {
    const body = await resp.json()
    detail = typeof body?.detail === 'string' ? body.detail : ''
  } catch {
    /* 忽略非 JSON 错误体 */
  }
  const msg = detail || ERROR_MESSAGES[resp.status] || `请求失败(${resp.status})`
  throw new ApiError(resp.status, msg)
}

// 统一请求入口:所有接口都走这里(init 可带 signal,由 useRequest 传入)
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response
  try {
    resp = await fetch(`${BASE}${path}`, onRequest(init))
  } catch (e) {
    // 主动取消(AbortController)原样抛出,交给 useRequest 判断;其余是网络层失败
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError(0, '网络异常,请确认后端已启动')
  }
  resp = await onResponse(resp)
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}
