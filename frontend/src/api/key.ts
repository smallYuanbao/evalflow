// 平台 API 密钥存取(Ch12):存 localStorage,请求拦截器统一读取注入。
// 与后端 CHAT_API_KEY(平台调 DeepSeek 的钥匙)是两回事——这是「访问平台」的钥匙。
const STORAGE_KEY = 'evalflow_api_key'

export function getApiKey(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null // 无 localStorage 环境(SSR/测试)静默降级
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(STORAGE_KEY, key)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // 忽略:写入失败只是本次不鉴权,不阻塞页面
  }
}
