import { getAccessToken, getRefreshToken, readSession, replaceTokens, clearAuthStorage, type TokenPair } from '@/auth/session'

interface Envelope<T> { code: number; message: string; data: T }
export type AppRequestOptions = Omit<UniApp.RequestOptions, 'url' | 'success' | 'fail'> & { auth?: boolean; retried?: boolean }
export class ApiError extends Error {
  constructor(readonly code: number, message: string) { super(message); this.name = 'ApiError' }
}
let baseUrl = '/api'
// #ifndef H5
baseUrl = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api'
// #endif
export function getApiBaseUrl() { return baseUrl }
let onExpired = () => {}
let checkIdentity = () => true
export function setAuthExpiredHandler(handler: () => void, identityCheck = () => true) { onExpired = handler; checkIdentity = identityCheck }
function expireSession() { clearAuthStorage(); onExpired() }
export function invalidateSession(expectedToken: string) { if (getAccessToken() === expectedToken) expireSession() }
let refreshPromise: Promise<boolean> | null = null
let refreshingToken = ''
export function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (refreshPromise && refreshingToken === refreshToken) return refreshPromise
  if (!refreshToken) return Promise.resolve(false)
  const task = new Promise<boolean>((resolve) => {
    uni.request({
      url: `${baseUrl}/auth/refresh`, method: 'POST', data: { refresh_token: refreshToken }, timeout: 15000,
      success(response) {
        const body = response.data as Envelope<{ tokens: TokenPair }> | undefined
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0 && getRefreshToken() === refreshToken) {
          try { replaceTokens(body.data.tokens); resolve(true) } catch { resolve(false) }
        } else resolve(false)
      },
      fail: () => resolve(false),
    })
  }).finally(() => { if (refreshPromise === task) { refreshPromise = null; refreshingToken = '' } })
  refreshPromise = task
  refreshingToken = refreshToken
  return refreshPromise
}
export function request<T>(path: string, options: AppRequestOptions = {}): Promise<T> {
  const { auth = false, retried = false, ...requestOptions } = options
  if (auth && !checkIdentity()) return Promise.reject(new ApiError(1004, '账户已切换，请重新发起请求。'))
  const token = auth ? getAccessToken() : ''
  const owner = auth ? readSession()?.user.id : undefined
  if (auth && !token) return Promise.reject(new ApiError(1004, '请先登录账户。'))
  return new Promise<T>((resolve, reject) => {
    uni.request({
      timeout: 15000, ...requestOptions, url: `${baseUrl}${path}`,
      header: { ...requestOptions.header, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      success(response) {
        void (async () => {
          const body = response.data as Envelope<T> | undefined
          if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) { resolve(body.data); return }
          const code = body?.code ?? response.statusCode
          if (auth && response.statusCode === 401 && getAccessToken() === token) {
            if (!retried && (code === 1004 || code === 401) && readSession() && await refreshAccessToken()) {
              if (readSession()?.user.id !== owner) { reject(new ApiError(1004, '账户已切换，请重新发起请求。')); return }
              resolve(await request<T>(path, { ...options, retried: true })); return
            }
            invalidateSession(token)
          }
          reject(new ApiError(code, body?.message || `请求失败（HTTP ${response.statusCode}）`))
        })().catch(reject)
      },
      fail: () => reject(new ApiError(-1, '无法连接本机后端，请确认服务已启动后重试。')),
    })
  })
}
