import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { login as loginApi, logout as logoutApi, register as registerApi } from '@/api/auth'
import { refreshAccessToken } from '@/request'
import {
  accessTokenExpiresSoon,
  clearAuthStorage,
  createSession,
  DEMO_STORAGE_KEY,
  getRefreshToken,
  markProfileComplete,
  readSession,
  writeSession,
  type AuthSession,
} from '@/auth/session'

export const useAuthStore = defineStore('auth', () => {
  const session = ref<AuthSession | null>(readSession())
  const demo = ref(uni.getStorageSync(DEMO_STORAGE_KEY) === true)
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(session.value?.tokens.access_token))
  const profileComplete = computed(() => session.value?.profileComplete ?? false)
  const user = computed(() => session.value?.user ?? null)

  function applySession(next: AuthSession) {
    session.value = next
    demo.value = false
    writeSession(next)
    uni.removeStorageSync(DEMO_STORAGE_KEY)
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
      demo.value = false
      clearAuthStorage()
    }
  }

  function enterDemo() {
    session.value = null
    demo.value = true
    writeSession(null)
    uni.setStorageSync(DEMO_STORAGE_KEY, true)
  }

  function clearLocalSession() {
    session.value = null
    demo.value = false
    clearAuthStorage()
  }

  function updateProfileComplete(value: boolean) {
    if (!session.value) return
    markProfileComplete(value)
    session.value = { ...session.value, profileComplete: value }
  }

  async function ensureFreshSession() {
    if (!isLoggedIn.value || !accessTokenExpiresSoon()) return true
    return refreshAccessToken()
  }

  return {
    session,
    demo,
    loading,
    isLoggedIn,
    profileComplete,
    user,
    login,
    register,
    logout,
    enterDemo,
    clearLocalSession,
    updateProfileComplete,
    ensureFreshSession,
  }
})
