import { computed, onScopeDispose, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, register as registerApi } from '@/api/auth'
import { refreshAccessToken, setAuthExpiredHandler, ApiError } from '@/request'
import {
  accessTokenExpiresSoon,
  clearAuthStorage,
  createSession,
  getRefreshToken,
  markProfileComplete,
  readSession,
  writeSession,
  type AuthSession,
} from '@/auth/session'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readSession())
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(session.value?.tokens.access_token))
  const profileComplete = computed(() => session.value?.profileComplete ?? false)
  const user = computed(() => session.value?.user ?? null)
  function syncIdentity() {
    const latest = readSession()
    const unchanged = latest?.user.id === session.value?.user.id
    session.value = latest
    return unchanged
  }
  setAuthExpiredHandler(() => { session.value = null }, syncIdentity)
  // #ifdef H5
  const syncTabs = () => { syncIdentity() }
  window.addEventListener('storage', syncTabs)
  onScopeDispose(() => window.removeEventListener('storage', syncTabs))
  // #endif

  function applySession(next: AuthSession) {
    session.value = next
    writeSession(next)
  }

  async function login(phone: string, password: string) {
    loading.value = true
    try {
      const response = await loginApi(phone, password)
      applySession(createSession(response))
      return response.profile_complete
    } finally {
      loading.value = false
    }
  }

  async function register(payload: Parameters<typeof registerApi>[0]) {
    loading.value = true
    try {
      const response = await registerApi(payload)
      applySession(createSession(response))
      return response.profile_complete
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    const refreshToken = getRefreshToken()
    try {
      if (refreshToken) await logoutApi(refreshToken)
    } finally {
      session.value = null
      clearAuthStorage()
    }
  }

  function clearLocalSession() {
    session.value = null
    clearAuthStorage()
  }

  function updateProfileComplete(value: boolean) {
    if (!session.value) return
    markProfileComplete(value)
    session.value = { ...session.value, profileComplete: value }
  }

  async function ensureFreshSession() {
    if (!syncIdentity()) throw new ApiError(1004, '账户已切换，请重新发起请求。')
    if (!isLoggedIn.value) throw new ApiError(1004, '请先登录账户。')
    if (!accessTokenExpiresSoon()) return true
    if (!await refreshAccessToken()) { clearLocalSession(); throw new ApiError(1004, '登录已过期，请重新登录。') }
    session.value = readSession()
    return true
  }

  return {
    session,
    loading,
    isLoggedIn,
    profileComplete,
    user,
    login,
    register,
    logout,
    clearLocalSession,
    updateProfileComplete,
    ensureFreshSession,
  }
})
