import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../pages/LoginPage.vue'
import RegisterPage from '../pages/RegisterPage.vue'
import ForgotPage from '../pages/ForgotPage.vue'
import HomePage from '../pages/HomePage.vue'
import OctopusSpacePage from '../pages/OctopusSpacePage.vue'
import ProfilePage from '../pages/ProfilePage.vue'
import ChangePasswordPage from '../pages/ChangePasswordPage.vue'
import StoryboardPage from '../pages/StoryboardPage.vue'
import AIImagePage from '../pages/AIImagePage.vue'
import ScriptBreakdownPage from '../pages/ScriptBreakdownPage.vue'
import AdminLoginPage from '../pages/AdminLoginPage.vue'
import AdminDashboardPage from '../pages/AdminDashboardPage.vue'
import { me } from '../api/auth'
import { consoleMe } from '../api/console'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomePage, meta: { requiresAuth: true } },
    { path: '/login', component: LoginPage },
    { path: '/register', component: RegisterPage },
    { path: '/forgot', component: ForgotPage },
    { path: '/octopus-space', component: OctopusSpacePage, meta: { requiresAuth: true } },
    { path: '/profile', component: ProfilePage, meta: { requiresAuth: true } },
    { path: '/change-password', component: ChangePasswordPage, meta: { requiresAuth: true } },
    { path: '/storyboard', component: StoryboardPage, meta: { requiresAuth: true, requiresWhitelist: true } },
    { path: '/ai-manga', redirect: '/storyboard' },
    { path: '/ai-image', component: AIImagePage, meta: { requiresAuth: true, requiresWhitelist: true } },
    { path: '/script-breakdown', component: ScriptBreakdownPage, meta: { requiresAuth: true, requiresWhitelist: true } },
    { path: '/admin/login', component: AdminLoginPage },
    { path: '/admin/dashboard', component: AdminDashboardPage, meta: { requiresConsoleAuth: true } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
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
