import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/Register.vue') },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { auth: true } },
  { path: '/resume/upload', name: 'ResumeUpload', component: () => import('../views/ResumeUpload.vue'), meta: { auth: true } },
  { path: '/interview/:id', name: 'Interview', component: () => import('../views/Interview.vue'), meta: { auth: true } },
  { path: '/interview/:id/report', name: 'Report', component: () => import('../views/Report.vue'), meta: { auth: true } },
  { path: '/', redirect: '/dashboard' }
  // 步 22/收尾按正主补路由：/profile /position-match（全带 meta.auth）
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 守卫：访问需登录页（meta.auth）但没登录 → 踢回登录页
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.auth && !authStore.isLoggedIn) {
    next('/login')
  } else {
    next()
  }
})

export default router
