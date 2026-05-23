<template>
  <div class="admin-shell">
    <aside class="sidebar">
      <div class="brand">
        <h1>管理后台</h1>
        <p v-if="adminUser">{{ adminUser.username }}</p>
      </div>
      <button class="side-btn" :class="{ active: activeSection === 'configs' }" type="button" @click="selectSection('configs')">
        AI剧本配置
      </button>
      <button class="side-btn" :class="{ active: activeSection === 'users' }" type="button" @click="selectSection('users')">
        用户信息
      </button>
    </aside>

    <main class="main">
      <header class="main-head">
        <div>
          <p class="eyebrow">{{ activeSection === 'configs' ? 'SCRIPT PROMPT SETTINGS' : 'USER MANAGEMENT' }}</p>
          <h2>{{ activeSection === 'configs' ? 'AI剧本创作配置' : '用户信息管理' }}</h2>
        </div>
        <el-button type="danger" plain @click="handleLogout">退出后台</el-button>
      </header>

      <template v-if="activeSection === 'configs'">
        <section class="panel">
          <div class="panel-head">
            <div>
              <h3>模型设置</h3>
              <p>保留现有 AI 配置结构，前台可选择剧本模型，并可独立配置生图模型。</p>
            </div>
            <el-button class="main-btn" type="primary" :loading="savingModels" @click="saveModelConfigs">保存模型配置</el-button>
          </div>

          <div class="model-grid">
            <div class="model-box">
              <h4>助手模型</h4>
              <el-form label-width="92px">
                <el-form-item label="API地址">
                  <el-input v-model="forms.ai_assistant_base_url" placeholder="https://api.deepseek.com/v1" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="forms.ai_assistant_api_key" show-password placeholder="请输入 API Key" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="forms.ai_assistant_model" placeholder="deepseek-reasoner" />
                </el-form-item>
              </el-form>
            </div>

            <div class="model-box">
              <h4>剧本模型</h4>
              <el-form label-width="92px">
                <el-form-item label="API地址">
                  <el-input v-model="forms.ai_manga_base_url" placeholder="默认可复用助手模型 API 地址" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="forms.ai_manga_api_key" show-password placeholder="默认可复用助手模型 API Key" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="forms.ai_manga_model" placeholder="deepseek-reasoner" />
                </el-form-item>
              </el-form>
            </div>

            <div class="model-box">
              <h4>图文识别模型</h4>
              <el-form label-width="92px">
                <el-form-item label="API地址">
                  <el-input v-model="forms.ai_manga_vision_base_url" placeholder="https://ark.cn-beijing.volces.com/api/v3" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="forms.ai_manga_vision_api_key" show-password placeholder="请输入 ARK API Key" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="forms.ai_manga_vision_model" placeholder="doubao-seed-2-0-mini-260428" />
                </el-form-item>
              </el-form>
            </div>

            <div class="model-box">
              <h4>生图模型 · GPT-Image-2</h4>
              <el-form label-width="92px">
                <el-form-item label="API地址">
                  <el-input v-model="forms.ai_image_base_url" placeholder="https://api.apimart.ai/v1" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="forms.ai_image_api_key" show-password placeholder="请输入 Apimart API Key" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="forms.ai_image_model" placeholder="gpt-image-2" />
                </el-form-item>
              </el-form>
            </div>

            <div class="model-box">
              <h4>生图模型 · Doubao</h4>
              <el-form label-width="92px">
                <el-form-item label="API地址">
                  <el-input v-model="forms.ai_image_doubao_base_url" placeholder="https://ark.cn-beijing.volces.com/api/v3" />
                </el-form-item>
                <el-form-item label="API Key">
                  <el-input v-model="forms.ai_image_doubao_api_key" show-password placeholder="请输入 ARK API Key" />
                </el-form-item>
                <el-form-item label="模型名称">
                  <el-input v-model="forms.ai_image_doubao_model" placeholder="doubao-seedream-5-0-260128" />
                </el-form-item>
              </el-form>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <div>
              <h3>解析规则与风格提示词</h3>
              <p>前台识别剧本时，会把解析规则和所选风格提示词一起发送给模型。</p>
            </div>
            <el-button class="main-btn" type="primary" :loading="savingPrompts" @click="savePromptConfigs">保存提示词</el-button>
          </div>

          <el-form label-position="top">
            <el-form-item label="剧本解析规则">
              <el-input
                v-model="forms.ai_manga_storyboard_prompt"
                type="textarea"
                :rows="9"
                placeholder="设置剧本文档解析、提示词分组和每组时长规则"
              />
            </el-form-item>
            <div class="prompt-grid">
              <el-form-item label="3D风格提示词">
                <el-input
                  v-model="forms.ai_manga_3d_style_prompt"
                  type="textarea"
                  :rows="8"
                  placeholder="设置 3D 风格专用提示词"
                />
              </el-form-item>
              <el-form-item label="真人风格提示词">
                <el-input
                  v-model="forms.ai_manga_real_style_prompt"
                  type="textarea"
                  :rows="8"
                  placeholder="设置真人风格专用提示词"
                />
              </el-form-item>
              <el-form-item label="反打画面提示词">
                <el-input
                  v-model="forms.ai_image_reverse_prompt"
                  type="textarea"
                  :rows="12"
                  placeholder="设置生出反打画面的默认提示词"
                />
              </el-form-item>
            </div>
          </el-form>
        </section>
      </template>

      <section v-else class="panel">
        <div class="panel-head">
          <div>
            <h3>用户信息</h3>
            <p>查看站内用户资料、账号状态和积分余额。</p>
          </div>
          <div class="user-tools">
            <el-input v-model="userSearch" clearable placeholder="搜索用户名或邮箱" @keyup.enter="loadUsers" @clear="loadUsers" />
            <el-button class="main-btn" type="primary" :loading="loadingUsers" @click="loadUsers">查询</el-button>
          </div>
        </div>

        <el-table v-loading="loadingUsers" :data="users" class="user-table" row-key="id">
          <el-table-column prop="id" label="ID" width="72" />
          <el-table-column label="用户" min-width="190">
            <template #default="{ row }">
              <div class="user-cell">
                <span class="avatar-dot">{{ row.username?.slice(0, 1)?.toUpperCase() }}</span>
                <div>
                  <strong>{{ row.username }}</strong>
                  <span>{{ row.email }}</span>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="积分" width="120">
            <template #default="{ row }">{{ formatPoints(row.points) }}</template>
          </el-table-column>
          <el-table-column label="白名单" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_whitelisted ? 'success' : 'info'" effect="plain">{{ row.is_whitelisted ? '已开通' : '未开通' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'danger'" effect="dark">{{ row.is_active ? '启用' : '禁用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="权限" width="120">
            <template #default="{ row }">
              <el-tag :type="row.is_staff ? 'warning' : 'info'" effect="plain">{{ row.is_staff ? '管理员' : '普通用户' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="注册时间" min-width="170">
            <template #default="{ row }">{{ formatDate(row.date_joined) }}</template>
          </el-table-column>
          <el-table-column label="最近登录" min-width="170">
            <template #default="{ row }">{{ formatDate(row.last_login) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }">
              <el-button size="small" plain @click="openUserEditor(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </main>

    <el-dialog v-model="editDialogVisible" title="编辑用户信息" width="620px">
      <el-form label-width="86px" class="user-form">
        <el-form-item label="用户ID">
          <el-input :model-value="userForm.id" disabled />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" maxlength="20" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
        <el-form-item label="头像URL">
          <el-input v-model="userForm.avatar_url" placeholder="可留空" />
        </el-form-item>
        <el-form-item label="用户签名">
          <el-input v-model="userForm.signature" maxlength="120" />
        </el-form-item>
        <el-form-item label="用户积分">
          <el-input-number v-model="userForm.points" :min="0" :precision="2" :step="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="账号状态">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
        <el-form-item label="功能白名单">
          <el-switch v-model="userForm.is_whitelisted" :disabled="userForm.is_staff" active-text="已开通" inactive-text="未开通" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingUser" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import {
  consoleLogout,
  consoleMe,
  getConsoleConfigs,
  getConsoleUsers,
  updateConsoleConfig,
  updateConsoleUser,
} from '../api/console'

const router = useRouter()
const adminUser = ref(null)
const activeSection = ref('configs')
const savingModels = ref(false)
const savingPrompts = ref(false)
const loadingUsers = ref(false)
const savingUser = ref(false)
const userSearch = ref('')
const users = ref([])
const editDialogVisible = ref(false)

const forms = reactive({
  ai_assistant_base_url: '',
  ai_assistant_api_key: '',
  ai_assistant_model: '',
  ai_manga_base_url: '',
  ai_manga_api_key: '',
  ai_manga_model: '',
  ai_manga_vision_base_url: '',
  ai_manga_vision_api_key: '',
  ai_manga_vision_model: '',
  ai_image_base_url: '',
  ai_image_api_key: '',
  ai_image_model: '',
  ai_image_doubao_base_url: '',
  ai_image_doubao_api_key: '',
  ai_image_doubao_model: '',
  ai_image_reverse_prompt: '',
  ai_manga_storyboard_prompt: '',
  ai_manga_3d_style_prompt: '',
  ai_manga_real_style_prompt: '',
})

const userForm = reactive({
  id: '',
  username: '',
  email: '',
  avatar_url: '',
  signature: '',
  points: 0,
  is_active: true,
  is_staff: false,
  is_whitelisted: false,
})

const assignConfigs = (items) => {
  ;(items || []).forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(forms, item.key)) {
      forms[item.key] = item.value || ''
    }
  })
}

const loadAdmin = async () => {
  const res = await consoleMe()
  adminUser.value = res.data.user
}

const loadConfigs = async () => {
  const res = await getConsoleConfigs()
  assignConfigs(res.data || [])
}

const loadUsers = async () => {
  loadingUsers.value = true
  try {
    const res = await getConsoleUsers({ q: userSearch.value.trim() })
    users.value = res.data.list || []
  } catch (e) {
    ElMessage.error(String(e || '用户列表加载失败'))
  } finally {
    loadingUsers.value = false
  }
}

const selectSection = async (section) => {
  activeSection.value = section
  if (section === 'users' && !users.value.length) {
    await loadUsers()
  }
}

const saveKeys = async (keys) => {
  await Promise.all(keys.map((key) => updateConsoleConfig(key, { value: forms[key] || '' })))
}

const saveModelConfigs = async () => {
  savingModels.value = true
  try {
    await saveKeys([
      'ai_assistant_base_url',
      'ai_assistant_api_key',
      'ai_assistant_model',
      'ai_manga_base_url',
      'ai_manga_api_key',
      'ai_manga_model',
      'ai_manga_vision_base_url',
      'ai_manga_vision_api_key',
      'ai_manga_vision_model',
      'ai_image_base_url',
      'ai_image_api_key',
      'ai_image_model',
      'ai_image_doubao_base_url',
      'ai_image_doubao_api_key',
      'ai_image_doubao_model',
    ])
    ElMessage.success('模型配置已保存')
  } catch (e) {
    ElMessage.error(String(e || '模型配置保存失败'))
  } finally {
    savingModels.value = false
  }
}

const savePromptConfigs = async () => {
  savingPrompts.value = true
  try {
    await saveKeys(['ai_manga_storyboard_prompt', 'ai_manga_3d_style_prompt', 'ai_manga_real_style_prompt', 'ai_image_reverse_prompt'])
    ElMessage.success('提示词配置已保存')
  } catch (e) {
    ElMessage.error(String(e || '提示词配置保存失败'))
  } finally {
    savingPrompts.value = false
  }
}

const openUserEditor = (user) => {
  userForm.id = user.id
  userForm.username = user.username || ''
  userForm.email = user.email || ''
  userForm.avatar_url = user.avatar_url || ''
  userForm.signature = user.signature || ''
  userForm.points = Number(user.points || 0)
  userForm.is_active = Boolean(user.is_active)
  userForm.is_staff = Boolean(user.is_staff)
  userForm.is_whitelisted = Boolean(user.is_whitelisted)
  editDialogVisible.value = true
}

const saveUser = async () => {
  if (!userForm.id) return
  savingUser.value = true
  try {
    const payload = {
      username: userForm.username,
      email: userForm.email,
      avatar_url: userForm.avatar_url,
      signature: userForm.signature,
      points: userForm.points,
      is_active: userForm.is_active,
      is_whitelisted: userForm.is_whitelisted,
    }
    const res = await updateConsoleUser(userForm.id, payload)
    const updated = res.data.user
    users.value = users.value.map((item) => (item.id === updated.id ? updated : item))
    editDialogVisible.value = false
    ElMessage.success('用户信息已保存')
  } catch (e) {
    ElMessage.error(String(e || '用户信息保存失败'))
  } finally {
    savingUser.value = false
  }
}

const formatPoints = (value) => Number(value || 0).toFixed(2)

const formatDate = (value) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('zh-CN', { hour12: false })
}

const handleLogout = async () => {
  try {
    await consoleLogout()
  } finally {
    router.push('/admin/login')
  }
}

onMounted(async () => {
  try {
    await loadAdmin()
    await loadConfigs()
  } catch {
    router.push('/admin/login')
  }
})
</script>

<style scoped>
.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 240px 1fr;
  background: #08101f;
  color: #e8eefc;
}

.sidebar {
  padding: 22px 14px;
  border-right: 1px solid rgba(74, 139, 196, 0.32);
  background: #0b1426;
}

.brand h1 {
  margin: 0;
  font-size: 24px;
}

.brand p {
  margin: 6px 0 22px;
  color: #93a8c4;
}

.side-btn {
  width: 100%;
  min-height: 40px;
  margin-bottom: 10px;
  border: 1px solid rgba(88, 151, 204, 0.36);
  border-radius: 8px;
  background: #101b30;
  color: #dce8f8;
  text-align: left;
  padding: 0 12px;
}

.side-btn.active {
  background: #1f8fff;
  border-color: transparent;
  color: #fff;
}

.main {
  padding: 22px;
}

.main-head,
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.main-head h2,
.panel h3,
.model-box h4 {
  margin: 0;
}

.eyebrow {
  margin: 0 0 6px;
  color: #7fb8ff;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.panel {
  margin-top: 18px;
  border: 1px solid rgba(74, 139, 196, 0.34);
  border-radius: 8px;
  background: #0d1729;
  padding: 18px;
}

.panel-head p {
  margin: 6px 0 0;
  color: #94a8c2;
}

.model-grid,
.prompt-grid {
  margin-top: 18px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.model-box {
  border: 1px solid rgba(74, 139, 196, 0.28);
  border-radius: 8px;
  background: #0a1222;
  padding: 16px;
}

.model-box h4 {
  margin-bottom: 14px;
}

.main-btn {
  border: 0;
  background: #1f8fff;
}

.user-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-tools .el-input {
  width: 260px;
}

.user-table {
  width: 100%;
  margin-top: 18px;
  border-radius: 8px;
  overflow: hidden;
  background: #0a1222;
}

.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-cell strong,
.user-cell span {
  display: block;
}

.user-cell span {
  color: #8fa4bf;
  font-size: 12px;
  line-height: 1.4;
}

.avatar-dot {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: #1f8fff;
  color: #fff;
  font-weight: 800;
}

.user-form :deep(.el-input-number) {
  width: 180px;
}

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: #08101f;
  box-shadow: inset 0 0 0 1px rgba(84, 145, 198, 0.42) !important;
  color: #e8eefc;
}

:deep(.el-form-item__label) {
  color: #cbd8ea;
}

:deep(.el-table) {
  --el-table-bg-color: #0a1222;
  --el-table-tr-bg-color: #0a1222;
  --el-table-header-bg-color: #101b30;
  --el-table-header-text-color: #dce8f8;
  --el-table-text-color: #dce8f8;
  --el-table-row-hover-bg-color: #13233d;
  --el-table-border-color: rgba(84, 145, 198, 0.24);
}

@media (max-width: 980px) {
  .admin-shell,
  .model-grid,
  .prompt-grid {
    grid-template-columns: 1fr;
  }

  .main-head,
  .panel-head {
    flex-direction: column;
  }

  .user-tools,
  .user-tools .el-input {
    width: 100%;
  }
}
</style>
