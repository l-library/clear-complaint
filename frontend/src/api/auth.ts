import { request } from '@/request'
import type { AuthUser, TokenPair } from '@/auth/session'

export interface AuthResponse {
  user: AuthUser
  tokens: TokenPair
  profile_complete: boolean
}

export function login(phone: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/login', {
    method: 'POST',
    data: { phone, password },
  })
}

export interface RegisterPayload {
  phone: string
  password: string
  consent_version: string
  accept_privacy: boolean
  accept_sensitive: boolean
}

export function register(payload: RegisterPayload): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/register', {
    method: 'POST',
    data: payload,
  })
}

export function logout(refreshToken: string): Promise<null> {
  return request<null>('/auth/logout', {
    method: 'POST',
    data: { refresh_token: refreshToken },
    auth: true,
  })
}
