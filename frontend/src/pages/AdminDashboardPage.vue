<template>
  <div class="admin-shell">
    <aside class="admin-sidebar">
      <div class="side-head">
        <h2>管理后台</h2>
        <p v-if="adminUser">{{ adminUser.username }}</p>
      </div>

      <button class="side-btn" :class="{ active: activeModule === 'stats' }" @click="activeModule = 'stats'">
        信息统计
      </button>
      <button class="side-btn" :class="{ active: activeModule === 'page' }" @click="activeModule = 'page'">
        页面管理
      </button>
      <button class="side-btn" :class="{ active: activeModule === 'users' }" @click="activeModule = 'users'">
        用户信息
      </button>
      <button class="side-btn" :class="{ active: activeModule === 'script' }" @click="activeModule = 'script'">
        剧本优化
      </button>
    </aside>

    <main class="admin-main">
      <header class="main-head">
        <h3>{{ moduleTitle }}</h3>
        <el-button type="danger" plain @click="handleLogout">退出后台</el-button>
      </header>

      <section v-if="activeModule === 'stats'" class="panel-card">
        <el-row :gutter="12">
          <el-col :xs="24" :sm="8">
            <el-card class="metric-card" shadow="never">
              <el-statistic title="注册用户总数" :value="total" />
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card class="metric-card" shadow="never">
              <el-statistic title="背景图已配置" :value="configuredBackgrounds" />
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="8">
            <el-card class="metric-card" shadow="never">
              <el-statistic title="当前管理员" :value="adminUser ? 1 : 0" />
            </el-card>
          </el-col>
        </el-row>
      </section>

      <section v-if="activeModule === 'page'" class="panel-card">
        <div class="panel-tip">页面管理：管理背景图片（统一上传到 COS）</div>
        <div class="bg-list">
          <div class="bg-row" v-for="item in backgroundItems" :key="item.scene">
            <div class="bg-row-left">
              <p class="bg-label fw-semibold">{{ item.label }}</p>
              <div class="bg-thumb">
                <img
                  v-if="item.image_url"
                  :src="thumbSrc(item.image_url, item.updated_at)"
                  alt="background preview"
                  @error="item.image_url = ''"
                />
                <span v-else>待上传图片</span>
              </div>
            </div>
            <div class="bg-row-right">
              <el-input v-model="item.image_url" placeholder="请输入背景图 URL，留空表示使用默认背景" />
              <input
                :id="`bg-upload-${item.scene}`"
                type="file"
                accept="image/*"
                class="file-hidden"
                @change="handleBackgroundUpload(item, $event)"
              />
              <div class="bg-actions">
                <el-button class="main-btn" type="primary" @click="saveBackground(item)">保存</el-button>
                <el-button plain :loading="item.uploading" @click="pickBackgroundFile(item.scene)">上传图片</el-button>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-row">
          <div class="bg-row-left">
            <p class="bg-label fw-semibold">用户默认头像</p>
            <div class="bg-thumb avatar-thumb">
              <img
                v-if="defaultAvatarUrl"
                :src="thumbSrc(defaultAvatarUrl)"
                alt="default avatar"
                @error="defaultAvatarUrl = '/octopus-avatar.svg'"
              />
              <span v-else>待上传图片</span>
            </div>
          </div>
          <div class="bg-row-right">
            <el-input v-model="defaultAvatarUrl" placeholder="请输入默认头像 URL，留空使用系统默认" />
            <input
              id="default-avatar-upload"
              type="file"
              accept="image/*"
              class="file-hidden"
              @change="handleDefaultAvatarUpload"
            />
            <div class="bg-actions">
              <el-button class="main-btn" type="primary" @click="saveDefaultAvatar">保存</el-button>
              <el-button plain :loading="defaultAvatarUploading" @click="pickDefaultAvatarFile">
                上传图片
              </el-button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="activeModule === 'users'" class="panel-card">
        <div class="user-header">
          <span class="fw-semibold">注册用户信息</span>
          <div class="user-filter">
            <el-input v-model="keyword" clearable placeholder="用户名/邮箱" @keyup.enter="loadUsers(1)" />
            <el-button @click="loadUsers(1)">搜索</el-button>
          </div>
        </div>

        <el-table :data="users" style="width: 100%" stripe>
          <el-table-column prop="username" label="用户名" min-width="120" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column prop="is_active" label="状态" width="90">
            <template #default="scope">
              <el-tag :type="scope.row.is_active ? 'success' : 'danger'">{{ scope.row.is_active ? '启用' : '停用' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="date_joined" label="注册时间" min-width="170" />
          <el-table-column label="操作" width="100">
            <template #default="scope">
              <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pager-wrap">
          <el-pagination
            background
            layout="prev, pager, next"
            :current-page="page"
            :page-size="pageSize"
            :total="total"
            @current-change="loadUsers"
          />
        </div>
      </section>

      <section v-if="activeModule === 'script'" class="panel-card">
        <h4 class="placeholder-title">剧本优化默认提示词</h4>
        <p class="placeholder-sub">修改后会同步到网站剧本优化页面输入框默认内容。</p>
        <el-form label-width="130px" class="mt-3">
          <el-form-item label="剧本分镜提示词">
            <el-input v-model="scriptStoryboardPrompt" type="textarea" :rows="4" />
          </el-form-item>
          <el-form-item label="段落分镜提示词">
            <el-input v-model="scriptParagraphPrompt" type="textarea" :rows="4" />
          </el-form-item>
        </el-form>
        <el-button type="primary" class="main-btn" :loading="savingPrompts" @click="saveScriptPrompts">保存设置</el-button>
      </section>
    </main>

    <el-dialog v-model="editVisible" title="编辑用户" width="460px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="用户名"><el-input v-model="editForm.username" /></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="editForm.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { uploadToCos } from '../api/storage'
import {
  getConsoleConfigs,
  consoleLogout,
  consoleMe,
  getConsoleBackgrounds,
  getConsoleUsers,
  updateConsoleBackground,
  updateConsoleConfig,
  updateConsoleUser,
} from '../api/console'

const router = useRouter()
const adminUser = ref(null)
const activeModule = ref('stats')

const moduleTitle = computed(() => {
  if (activeModule.value === 'stats') return '信息统计'
  if (activeModule.value === 'page') return '页面管理'
  if (activeModule.value === 'users') return '用户信息'
  return '剧本优化'
})

const backgroundItems = ref([
  { scene: 'login', label: '登录页面背景图', image_url: '', uploading: false },
  { scene: 'home', label: '首页背景图', image_url: '', uploading: false },
  { scene: 'script_optimizer', label: '剧本优化页背景图', image_url: '', uploading: false },
  { scene: 'profile', label: '用户信息页背景图', image_url: '', uploading: false },
])

const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const configuredBackgrounds = computed(() => backgroundItems.value.filter((item) => !!item.image_url).length)
const defaultAvatarUrl = ref('')
const defaultAvatarUploading = ref(false)
const scriptStoryboardPrompt = ref('')
const scriptParagraphPrompt = ref('')
const savingPrompts = ref(false)

const editVisible = ref(false)
const editForm = reactive({ id: null, username: '', email: '', is_active: true })

const loadAdminMe = async () => {
  const res = await consoleMe()
  adminUser.value = res.data.user
}

const loadBackgrounds = async () => {
  const res = await getConsoleBackgrounds()
  const map = Object.fromEntries(res.data.map((item) => [item.scene, item]))
  backgroundItems.value = backgroundItems.value.map((item) => ({
    ...item,
    image_url: map[item.scene]?.image_url || '',
    updated_at: map[item.scene]?.updated_at || '',
  }))
}

const loadConfigs = async () => {
  const res = await getConsoleConfigs()
  const map = Object.fromEntries(res.data.map((item) => [item.key, item.value]))
  defaultAvatarUrl.value = map.default_avatar_url || ''
  scriptStoryboardPrompt.value = map.storyboard_default_prompt || ''
  scriptParagraphPrompt.value = map.paragraph_default_prompt || ''
}

const saveBackground = async (item) => {
  try {
    await updateConsoleBackground(item.scene, { image_url: item.image_url || '' })
    item.updated_at = new Date().toISOString()
    ElMessage.success('背景图已更新')
  } catch (e) {
    ElMessage.error(e)
  }
}

const saveDefaultAvatar = async () => {
  try {
    await updateConsoleConfig('default_avatar_url', { value: defaultAvatarUrl.value || '' })
    ElMessage.success('默认头像已更新')
  } catch (e) {
    ElMessage.error(e)
  }
}

const pickBackgroundFile = (scene) => {
  const input = document.getElementById(`bg-upload-${scene}`)
  if (input) input.click()
}
const pickDefaultAvatarFile = () => {
  const input = document.getElementById('default-avatar-upload')
  if (input) input.click()
}

const formatSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

const loadImage = (file) =>
  new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('图片读取失败'))
    img.src = URL.createObjectURL(file)
  })

const toBlob = (canvas, type, quality) =>
  new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), type, quality)
  })

const compressImageBeforeUpload = async (file) => {
  const mime = file.type || 'image/jpeg'
  if (!mime.startsWith('image/')) return file

  const img = await loadImage(file)
  const maxW = 1920
  const maxH = 1920
  let { width, height } = img
  const ratio = Math.min(maxW / width, maxH / height, 1)
  width = Math.round(width * ratio)
  height = Math.round(height * ratio)

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0, width, height)

  const targetType = mime === 'image/png' ? 'image/webp' : mime
  const quality = targetType === 'image/jpeg' || targetType === 'image/webp' ? 0.82 : undefined
  const blob = await toBlob(canvas, targetType, quality)
  URL.revokeObjectURL(img.src)

  if (!blob) return file
  if (blob.size >= file.size) return file

  const extMap = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
  }
  const ext = extMap[targetType] || 'jpg'
  const nextName = file.name.replace(/\.[^.]+$/, '') + `.${ext}`
  return new File([blob], nextName, { type: targetType })
}

const handleBackgroundUpload = async (item, event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  const isImage = file.type.startsWith('image/')
  const limit = 10 * 1024 * 1024
  if (!isImage) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.size > limit) {
    ElMessage.warning('图片大小不能超过10MB')
    return
  }

  item.uploading = true
  try {
    const compressed = await compressImageBeforeUpload(file)
    const res = await uploadToCos(compressed, 'images/backgrounds')
    item.image_url = res.data.url
    await updateConsoleBackground(item.scene, { image_url: item.image_url || '' })
    item.updated_at = new Date().toISOString()
    const before = formatSize(file.size)
    const after = formatSize(compressed.size)
    ElMessage.success(`上传并保存成功（已存入COS，${before} -> ${after}）`)
  } catch (e) {
    ElMessage.error(e)
  } finally {
    item.uploading = false
  }
}

const handleDefaultAvatarUpload = async (event) => {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  if (!file.type.startsWith('image/')) {
    ElMessage.warning('请上传图片文件')
    return
  }
  if (file.size > 5 * 1024 * 1024) {
    ElMessage.warning('默认头像不能超过5MB')
    return
  }

  defaultAvatarUploading.value = true
  try {
    const compressed = await compressImageBeforeUpload(file)
    const res = await uploadToCos(compressed, 'images/avatars')
    defaultAvatarUrl.value = res.data.url
    await updateConsoleConfig('default_avatar_url', { value: defaultAvatarUrl.value })
    ElMessage.success('默认头像上传并保存成功')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    defaultAvatarUploading.value = false
  }
}

const saveScriptPrompts = async () => {
  savingPrompts.value = true
  try {
    await updateConsoleConfig('storyboard_default_prompt', { value: scriptStoryboardPrompt.value || '' })
    await updateConsoleConfig('paragraph_default_prompt', { value: scriptParagraphPrompt.value || '' })
    ElMessage.success('默认提示词已保存')
  } catch (e) {
    ElMessage.error(e)
  } finally {
    savingPrompts.value = false
  }
}

const thumbSrc = (url, updatedAt) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  const parsed = updatedAt ? Date.parse(updatedAt) : NaN
  const version = Number.isFinite(parsed) ? parsed : Date.now()
  return `${url}${sep}v=${version}`
}

const loadUsers = async (targetPage = page.value) => {
  page.value = targetPage
  try {
    const res = await getConsoleUsers({ page: page.value, page_size: pageSize.value, keyword: keyword.value })
    users.value = res.data.list
    total.value = res.data.total
  } catch (e) {
    ElMessage.error(e)
  }
}

const openEdit = (row) => {
  editForm.id = row.id
  editForm.username = row.username
  editForm.email = row.email
  editForm.is_active = row.is_active
  editVisible.value = true
}

const saveUser = async () => {
  if (!editForm.id) return
  try {
    await updateConsoleUser(editForm.id, {
      username: editForm.username,
      email: editForm.email,
      is_active: editForm.is_active,
    })
    ElMessage.success('用户信息已更新')
    editVisible.value = false
    loadUsers(page.value)
  } catch (e) {
    ElMessage.error(e)
  }
}

const handleLogout = async () => {
  try {
    await consoleLogout()
  } catch (e) {
    ElMessage.warning(typeof e === 'string' ? e : '登录态已失效，返回登录页')
  } finally {
    router.push('/admin/login')
  }
}

onMounted(async () => {
  try {
    await loadAdminMe()
    await Promise.all([loadBackgrounds(), loadConfigs(), loadUsers(1)])
  } catch {
    router.push('/admin/login')
  }
})
</script>

<style scoped>
.admin-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 250px 1fr;
  background: #1a1b20;
}
.admin-sidebar {
  background: #fff;
  border-right: 1px solid #e9edf4;
  padding: 24px 14px;
}
.side-head h2 {
  margin: 0;
}
.side-head p {
  margin: 6px 0 16px;
  color: #7d8597;
}
.side-btn {
  width: 100%;
  border: 1px solid #dce4f1;
  background: #fff;
  border-radius: 10px;
  text-align: left;
  padding: 11px 10px;
  margin-bottom: 10px;
}
.side-btn.active {
  border-color: transparent;
  color: #fff;
  background: linear-gradient(130deg, #2b63d9, #3c86f0);
}
.admin-main {
  padding: 18px 20px;
}
.main-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.main-head h3 {
  margin: 0;
  color: #eef2ff;
}
.panel-card {
  margin-top: 14px;
  border: 1px solid #343848;
  border-radius: 14px;
  background: #242731;
  padding: 16px;
  color: #d8ddeb;
}
.panel-tip {
  margin-bottom: 12px;
  color: #aab4cb;
}
.metric-card {
  border-radius: 12px;
  border: 1px solid #3b4153;
  background: #2a2f3b;
}
.bg-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bg-row {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #393f50;
}
.bg-row:last-child {
  border-bottom: 0;
}
.bg-row-left,
.bg-row-right {
  min-width: 0;
}
.bg-label {
  margin: 0 0 8px;
  color: #e8edf8;
}
.bg-thumb {
  height: 82px;
  border-radius: 10px;
  border: 1px dashed #5f6d8e;
  background: #1f222b;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8b97b1;
  margin-bottom: 8px;
}
.bg-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-thumb img {
  object-fit: contain;
  background: #171921;
}
.bg-actions {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.file-hidden {
  display: none;
}
.user-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.user-filter {
  display: flex;
  gap: 8px;
}
.pager-wrap {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.placeholder-title {
  margin: 0;
}
.placeholder-sub {
  margin-top: 8px;
  color: #aab4cb;
}
@media (max-width: 980px) {
  .admin-shell {
    grid-template-columns: 1fr;
  }
  .admin-sidebar {
    border-right: 0;
    border-bottom: 1px solid #e9edf4;
  }
  .bg-row {
    grid-template-columns: 1fr;
  }
}
</style>
