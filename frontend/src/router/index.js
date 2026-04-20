import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../pages/LoginPage.vue'
import RegisterPage from '../pages/RegisterPage.vue'
import ForgotPage from '../pages/ForgotPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import ChangePasswordPage from '../pages/ChangePasswordPage.vue'
import RechargePage from '../pages/RechargePage.vue'
import AICustomerPage from '../pages/AICustomerPage.vue'
import AIMangaPage from '../pages/AIMangaPage.vue'
import AdminLoginPage from '../pages/AdminLoginPage.vue'
import AdminDashboardPage from '../pages/AdminDashboardPage.vue'
import { me } from '../api/auth'
import { consoleMe } from '../api/console'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ai-customer' },
    { path: '/login', component: LoginPage },
    { path: '/register', component: RegisterPage },
    { path: '/forgot', component: ForgotPage },
    { path: '/home', redirect: '/ai-customer' },
    { path: '/profile', component: ProfilePage, meta: { requiresAuth: true } },
    { path: '/change-password', component: ChangePasswordPage, meta: { requiresAuth: true } },
    { path: '/recharge', component: RechargePage, meta: { requiresAuth: true } },
    { path: '/ai-customer', component: AICustomerPage, meta: { requiresAuth: true } },
    { path: '/ai-manga', component: AIMangaPage, meta: { requiresAuth: true } },
    { path: '/admin/login', component: AdminLoginPage },
    { path: '/admin/dashboard', component: AdminDashboardPage, meta: { requiresConsoleAuth: true } },
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

router.afterEach((to) => {
  document.title = to.path.startsWith('/admin') ? 'OldBoyAdmin' : 'OldBoyAI'
})

export default router
