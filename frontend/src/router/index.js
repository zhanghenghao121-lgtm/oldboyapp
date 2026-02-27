import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../pages/LoginPage.vue'
import RegisterPage from '../pages/RegisterPage.vue'
import ForgotPage from '../pages/ForgotPage.vue'
import HomePage from '../pages/HomePage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import AdminLoginPage from '../pages/AdminLoginPage.vue'
import AdminDashboardPage from '../pages/AdminDashboardPage.vue'
import ScriptOptimizerPage from '../modules/script_optimizer/pages/ScriptOptimizerPage.vue'
import { me } from '../api/auth'
import { consoleMe } from '../api/console'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: LoginPage },
    { path: '/register', component: RegisterPage },
    { path: '/forgot', component: ForgotPage },
    { path: '/home', component: HomePage, meta: { requiresAuth: true } },
    { path: '/profile', component: ProfilePage, meta: { requiresAuth: true } },
    { path: '/admin/login', component: AdminLoginPage },
    { path: '/admin/dashboard', component: AdminDashboardPage, meta: { requiresConsoleAuth: true } },
    { path: '/script-optimizer', component: ScriptOptimizerPage, meta: { requiresAuth: true } },
  ],
})

router.beforeEach(async (to) => {
  if (to.meta.requiresConsoleAuth) {
    try {
      await consoleMe()
      return true
    } catch {
      return '/admin/login'
    }
  }
  if (to.meta.requiresAuth) {
    try {
      await me()
      return true
    } catch {
      return '/login'
    }
  }
  return true
})

export default router
