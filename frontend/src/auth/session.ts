export interface AuthUser {
  id: number
  phone: string
  is_demo: boolean
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  access_expires_at: string
  refresh_expires_at: string
}

export interface AuthSession {
  user: AuthUser
  tokens: TokenPair
  profileComplete: boolean
  demo: boolean
}

interface AuthResponse {
  user: AuthUser
  tokens: TokenPair
  profile_complete: boolean
}

const STORAGE_KEY = 'clear-complaint-auth-session'
export const DEMO_STORAGE_KEY = 'clear-complaint-demo-mode'

export function readSession(): AuthSession | null {
  try {
    const stored = uni.getStorageSync(STORAGE_KEY) as AuthSession | ''
    if (!stored || !stored.tokens?.access_token) return null
    return stored
  } catch {
    return null
  }
}

export function writeSession(session: AuthSession | null) {
  if (session) {
    uni.setStorageSync(STORAGE_KEY, session)
  } else {
    uni.removeStorageSync(STORAGE_KEY)
  }
}

export function clearAuthStorage() {
  uni.removeStorageSync(STORAGE_KEY)
  uni.removeStorageSync(DEMO_STORAGE_KEY)
}

export function createSession(response: AuthResponse): AuthSession {
  return {
    user: response.user,
    tokens: response.tokens,
    profileComplete: response.profile_complete,
    demo: false,
  }
}

export function getAccessToken(): string {
  return readSession()?.tokens.access_token ?? ''
}

export function getRefreshToken(): string {
  return readSession()?.tokens.refresh_token ?? ''
}

export function accessTokenExpiresSoon(bufferSeconds = 120): boolean {
  const expiresAt = readSession()?.tokens.access_expires_at
  if (!expiresAt) return true
  const timestamp = Date.parse(expiresAt.replace(' ', 'T'))
  if (!Number.isFinite(timestamp)) return true
  return timestamp - Date.now() <= bufferSeconds * 1000
}

export function replaceTokens(tokens: TokenPair) {
  const session = readSession()
  if (!session) return
  writeSession({ ...session, tokens })
}

export function markProfileComplete(value: boolean) {
  const session = readSession()
  if (!session) return
  writeSession({ ...session, profileComplete: value })
}
