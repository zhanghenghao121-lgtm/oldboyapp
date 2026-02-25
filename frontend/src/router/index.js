import { createRouter, createWebHistory } from 'vue-router'
import LoginPage from '../pages/LoginPage.vue'
import RegisterPage from '../pages/RegisterPage.vue'
import ForgotPage from '../pages/ForgotPage.vue'
import HomePage from '../pages/HomePage.vue'
import ScriptOptimizerPage from '../modules/script_optimizer/pages/ScriptOptimizerPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/login' },
    { path: '/login', component: LoginPage },
    { path: '/register', component: RegisterPage },
    { path: '/forgot', component: ForgotPage },
    { path: '/home', component: HomePage },
    { path: '/script-optimizer', component: ScriptOptimizerPage },
  ],
})

export default router
