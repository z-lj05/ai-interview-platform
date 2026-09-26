import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  // 初始化从 localStorage 读回 = 刷新页面后恢复登录态（双写的一半）
  const token = ref(localStorage.getItem('token') || '')
  const userEmail = ref(localStorage.getItem('userEmail') || '')
  const userId = ref(localStorage.getItem('userId') || '')
  const userName = ref(localStorage.getItem('userName') || '')

  const isLoggedIn = computed(() => !!token.value)

  // 登录/注册成功后调用；data = 后端返回的裸货
  function setAuth(data) {
    token.value = data.access_token
    userEmail.value = data.user?.email || ''
    userId.value = data.user?.id || ''
    const u = data.user || {}
    userName.value = ((u.last_name || '') + (u.first_name || '')).trim() || u.email || ''
    // 双写：内存 + localStorage（刷新后靠读回恢复）
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('userEmail', userEmail.value)
    localStorage.setItem('userId', userId.value)
    localStorage.setItem('userName', userName.value)
  }

  function logout() {
    token.value = ''
    userEmail.value = ''
    userId.value = ''
    userName.value = ''
    localStorage.removeItem('token')
    localStorage.removeItem('userEmail')
    localStorage.removeItem('userId')
    localStorage.removeItem('userName')
  }

  return { token, userEmail, userId, userName, isLoggedIn, setAuth, logout }
})
