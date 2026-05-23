import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../pages/LoginPage.vue'
import RegisterPage from '../pages/RegisterPage.vue'
import ForgotPage from '../pages/ForgotPage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import ChangePasswordPage from '../pages/ChangePasswordPage.vue'
import AIMangaPage from '../pages/AIMangaPage.vue'
import AIImagePage from '../pages/AIImagePage.vue'
import AdminLoginPage from '../pages/AdminLoginPage.vue'
import AdminDashboardPage from '../pages/AdminDashboardPage.vue'
import { me } from '../api/auth'
import { consoleMe } from '../api/console'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/ai-manga' },
    { path: '/login', component: LoginPage },
    { path: '/register', component: RegisterPage },
    { path: '/forgot', component: ForgotPage },
    { path: '/profile', component: ProfilePage, meta: { requiresAuth: true } },
    { path: '/change-password', component: ChangePasswordPage, meta: { requiresAuth: true } },
    { path: '/ai-manga', component: AIMangaPage, meta: { requiresAuth: true, requiresWhitelist: true } },
    { path: '/ai-image', component: AIImagePage, meta: { requiresAuth: true, requiresWhitelist: true } },
    { path: '/admin/login', component: AdminLoginPage },
    { path: '/admin/dashboard', component: AdminDashboardPage, meta: { requiresConsoleAuth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/ai-manga' },
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
      const res = await me()
      if (to.meta.requiresWhitelist && !res.data?.user?.feature_allowed) {
        return '/profile'
      }
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
