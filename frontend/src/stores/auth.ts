import { ref } from 'vue'
import { defineStore } from 'pinia'
import { login as apiLogin, register as apiRegister } from '@/api/auth'
import type { LoginRequest, RegisterRequest } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const userInfo = ref<{ id: number; username: string } | null>(null)

  async function login(data: LoginRequest) {
    const res = await apiLogin(data)
    token.value = res.token
    userInfo.value = { id: res.user_id, username: res.username }
    localStorage.setItem('token', res.token)
  }

  async function register(data: RegisterRequest) {
    const res = await apiRegister(data)
    token.value = res.token
    userInfo.value = { id: res.user_id, username: res.username }
    localStorage.setItem('token', res.token)
  }

  function logout() {
    token.value = null
    userInfo.value = null
    localStorage.removeItem('token')
  }

  function restoreSession() {
    const t = localStorage.getItem('token')
    if (t) token.value = t
  }

  return { token, userInfo, login, register, logout, restoreSession }
})
