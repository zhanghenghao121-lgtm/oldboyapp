<template>
  <el-dialog v-model="visible" title="设置" width="460px" class="settings-dialog">
    <div class="settings-profile" v-loading="loading">
      <el-avatar :src="user.avatar_url || '/octopus-avatar.svg'" :size="64" />
      <div>
        <h3>{{ user.username || '未登录用户' }}</h3>
        <p>{{ user.email || '-' }}</p>
      </div>
    </div>

    <div class="settings-list">
      <div>
        <span>用户积分</span>
        <strong>{{ Number(user.points || 0).toFixed(2) }}</strong>
      </div>
      <div>
        <span>功能权限</span>
        <div class="feature-tags">
          <el-tag :type="user.can_access_workbench ? 'success' : 'info'" effect="plain">
            工作台{{ user.can_access_workbench ? '已开通' : '未开通' }}
          </el-tag>
          <el-tag :type="user.can_access_storyboard ? 'success' : 'info'" effect="plain">
            故事板{{ user.can_access_storyboard ? '已开通' : '未开通' }}
          </el-tag>
        </div>
      </div>
      <div v-if="user.signature">
        <span>用户签名</span>
        <strong>{{ user.signature }}</strong>
      </div>
    </div>

    <template #footer>
      <el-button plain @click="goProfile">用户信息</el-button>
      <el-button type="danger" plain :loading="loggingOut" @click="handleLogout">退出登录</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { logout, me } from '../api/auth'

const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const loggingOut = ref(false)
const user = reactive({
  username: '',
  email: '',
  avatar_url: '',
  signature: '',
  points: 0,
  feature_allowed: false,
  can_access_workbench: false,
  can_access_storyboard: false,
})

const open = async () => {
  visible.value = true
  loading.value = true
  try {
    const res = await me()
    Object.assign(user, res.data.user || {})
  } catch (e) {
    ElMessage.error(String(e || '获取用户信息失败'))
  } finally {
    loading.value = false
  }
}

const goProfile = () => {
  visible.value = false
  router.push('/profile')
}

const handleLogout = async () => {
  loggingOut.value = true
  try {
    await logout()
    visible.value = false
    router.push('/login')
  } catch (e) {
    ElMessage.error(String(e || '退出登录失败'))
  } finally {
    loggingOut.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.settings-profile {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 4px 0 14px;
}

.settings-profile h3,
.settings-profile p {
  margin: 0;
}

.settings-profile p {
  margin-top: 4px;
  color: #8fa4bf;
}

.settings-list {
  display: grid;
  gap: 10px;
}

.settings-list > div {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(84, 145, 198, 0.28);
  border-radius: 8px;
  background: #0a1222;
}

.settings-list span {
  color: #91a6c0;
}

.settings-list strong {
  color: #e8eefc;
  text-align: right;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}
</style>
