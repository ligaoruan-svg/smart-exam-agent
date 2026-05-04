/**
 * stores/auth.js - 用户鉴权状态
 *
 * 跟原 mock 版本接口完全兼容（login / register / logout / user / token / isLoggedIn）
 * 但底层换成真实后端调用。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, getToken, setToken } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(getToken())
  const user = ref(JSON.parse(localStorage.getItem('gk_user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function persistUser(u) {
    user.value = u
    if (u) localStorage.setItem('gk_user', JSON.stringify(u))
    else localStorage.removeItem('gk_user')
  }

  /** 登录：username + password */
  async function login(username, password) {
    const r = await authApi.login(username, password)
    token.value = r.token
    persistUser(r.user)
    // 登录后顺便拉一次完整 me
    try {
      const me = await authApi.me()
      persistUser(me)
    } catch {}
    return { token: r.token, user: user.value }
  }

  /** 注册：username + password */
  async function register(username, password, email, code) {
    const r = await authApi.register({
      username,
      password,
      email,
      code,
      nickname: username,
    })
    token.value = r.token
    persistUser(r.user)
    try {
      const me = await authApi.me()
      persistUser(me)
    } catch {}
    return { token: r.token, user: user.value }
  }

  /** 拉最新用户信息 */
  async function fetchMe() {
    if (!getToken()) {
      persistUser(null)
      return null
    }
    try {
      const me = await authApi.me()
      persistUser(me)
      return me
    } catch {
      return null
    }
  }

  function logout() {
    token.value = ''
    persistUser(null)
    setToken(null)
    // 清理前端缓存，防止切换账号后残留旧 session 数据
    sessionStorage.removeItem('gk_card_state_v1')
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    register,
    fetchMe,
    logout,
  }
})
