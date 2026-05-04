import { createRouter, createWebHistory } from 'vue-router'
import Login from '@/views/Login.vue'
import Home from '@/views/Home.vue'
import Landing from '@/views/Landing.vue'
import AdminConsole from '@/views/AdminConsole.vue'
import UserCenter from '@/views/UserCenter.vue'
import DataDashboard from '@/views/DataDashboard.vue'
import QuestionDetail from '@/views/QuestionDetail.vue'
import Pricing from '@/views/Pricing.vue'
import ScoreReport from '@/views/ScoreReport.vue'
import { useAuthStore } from '@/stores/auth'
import { getToken } from '@/api'

const routes = [
  // 根：未登录跳 welcome，已登录跳 chat
  {
    path: '/',
    redirect: () => (getToken() ? '/chat' : '/welcome'),
  },

  // 公开页（不需要登录）
  { path: '/welcome', name: 'welcome', component: Landing },
  { path: '/login',   name: 'login',   component: Login },
  { path: '/pricing', name: 'pricing', component: Pricing },

  // 主应用 tabs (登录后)
  {
    path: '/:tab(chat|practice|download|mistakes|plan)',
    name: 'home',
    component: Home,
    props: true,
    meta: { requiresAuth: true },
  },

  // 后台 (需要 admin)
  {
    path: '/admin',
    name: 'admin',
    component: AdminConsole,
    meta: { requiresAuth: true, requiresAdmin: true },
  },

  // 个人中心 / 数据看板 (登录)
  { path: '/me',        name: 'me',        component: UserCenter,    meta: { requiresAuth: true } },
  { path: '/dashboard', name: 'dashboard', component: DataDashboard, meta: { requiresAuth: true } },

  // 题目详情 / 成绩报告 (登录)
  { path: '/question/:id', name: 'question', component: QuestionDetail, props: true, meta: { requiresAuth: true } },
  { path: '/report/:id',   name: 'report',   component: ScoreReport,   props: true, meta: { requiresAuth: true } },

  // 兜底
  { path: '/:pathMatch(.*)*', redirect: '/welcome' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/* 路由守卫：登录拦截 + admin 角色隔离 */
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // 有 token 但 store 里没 user，拉一次
  if (getToken() && !auth.user) {
    await auth.fetchMe()
  }

  // 已登录访问 login → 跳 chat
  if (to.name === 'login' && auth.isLoggedIn) {
    return next('/chat')
  }

  // 需要登录但没登录
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return next({ path: '/login', query: { redirect: to.fullPath } })
  }

  // 需要 admin 但不是 admin
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return next('/chat')
  }

  next()
})

export default router
