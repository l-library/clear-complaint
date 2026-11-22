/**
 * 统一请求入口，页面和 api/ 只走这里，不直接调 uni.request。
 *
 * H5 走 Vite 代理（/api → localhost:8000）；小程序没有代理，必须给绝对地址，
 * 本地开发用 VITE_API_BASE=http://localhost:8000/api，真机要换成备案过的 HTTPS 域名。
 */

import {
  getAccessToken,
  getRefreshToken,
  readSession,
  replaceTokens,
  clearAuthStorage,
  type TokenPair,
} from '@/auth/session'

interface Envelope<T> {
  code: number;
  message: string;
  data: T;
}

interface RequestExtras {
  auth?: boolean
  retried?: boolean
}

export type AppRequestOptions = Omit<
  UniApp.RequestOptions,
  'url' | 'success' | 'fail'
> &
  RequestExtras

export class ApiError extends Error {
  readonly code: number;

  constructor(code: number, message: string) {
    super(message);
    this.code = code;
  }
}

// H5 走 Vite 代理，用相对路径即可；小程序没有代理，必须给绝对地址：
// 本地开发用 VITE_API_BASE=http://localhost:8000/api，真机换成备案过的 HTTPS 域名。
let baseUrl = "/api";
// #ifndef H5
baseUrl = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";
// #endif

let refreshPromise: Promise<boolean> | null = null

export function getApiBaseUrl() {
  return baseUrl
}

export function refreshAccessToken(): Promise<boolean> {
  if (refreshPromise) return refreshPromise

  const refreshToken = getRefreshToken()
  if (!refreshToken) return Promise.resolve(false)

  refreshPromise = new Promise<boolean>((resolve) => {
    uni.request({
      url: `${baseUrl}/auth/refresh`,
      method: 'POST',
      data: { refresh_token: refreshToken },
      success: (response) => {
        const body = response.data as Envelope<{ tokens: TokenPair }> | undefined
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) {
          replaceTokens(body.data.tokens)
          resolve(true)
          return
        }
        resolve(false)
      },
      fail: () => resolve(false),
    })
  }).finally(() => {
    refreshPromise = null
  })

  return refreshPromise
}

export function request<T>(
  path: string,
  options: AppRequestOptions = {},
): Promise<T> {
  const { auth = false, retried = false, ...requestOptions } = options
  const token = auth ? getAccessToken() : ''

  return new Promise<T>((resolve, reject) => {
    uni.request({
      ...requestOptions,
      url: `${baseUrl}${path}`,
      header: {
        ...(requestOptions.header ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: async (response) => {
        const body = response.data as Envelope<T> | undefined;
        if (response.statusCode >= 200 && response.statusCode < 300 && body?.code === 0) {
          resolve(body.data);
          return;
        }

        const code = body?.code ?? response.statusCode
        if (
          auth &&
          !retried &&
          response.statusCode === 401 &&
          (code === 1004 || code === 401) &&
          readSession()
        ) {
          const refreshed = await refreshAccessToken()
          if (refreshed) {
            try {
              resolve(await request<T>(path, { ...options, retried: true }))
            } catch (error) {
              reject(error)
            }
            return
          }
          clearAuthStorage()
          uni.reLaunch({ url: '/pages/auth/index' })
        }

        reject(new ApiError(code, body?.message ?? `HTTP ${response.statusCode}`));
      },
      fail: (error) => reject(new ApiError(-1, error.errMsg)),
    });
  });
}
