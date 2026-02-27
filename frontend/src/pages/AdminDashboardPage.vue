<template>
  <div class="admin-dashboard">
    <header class="dash-header container-xl">
      <div>
        <h2 class="fw-bold mb-1">网站管理后台</h2>
        <p v-if="adminUser">当前管理员：{{ adminUser.username }} / {{ adminUser.email }}</p>
      </div>
      <el-button type="danger" plain @click="handleLogout">退出后台</el-button>
    </header>

    <el-row :gutter="12" class="container-xl mx-auto mb-2">
      <el-col :xs="24" :sm="8">
        <el-card class="metric-card" shadow="never">
          <el-statistic title="背景图已配置" :value="configuredBackgrounds" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card class="metric-card" shadow="never">
          <el-statistic title="注册用户总数" :value="total" />
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card class="metric-card" shadow="never">
          <el-statistic title="当前页码" :value="page" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="container-xl mx-auto">
      <el-col :xs="24" :lg="10">
        <el-card shadow="never" class="dash-card">
          <template #header>
            <div>
              <span class="fw-semibold">背景图管理</span>
              <p class="tiny-tip">图片/视频/音频资源请统一上传至 COS 存储</p>
            </div>
          </template>
          <div class="bg-form-item" v-for="item in backgroundItems" :key="item.scene">
            <p class="bg-label fw-semibold">{{ item.label }}</p>
            <div class="bg-thumb">
              <img v-if="item.image_url" :src="item.image_url" alt="background preview" />
              <span v-else>待上传图片</span>
            </div>
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
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="14">
        <el-card shadow="never" class="dash-card">
          <template #header>
            <div class="user-header">
              <span class="fw-semibold">注册用户管理</span>
              <div class="user-filter">
                <el-input v-model="keyword" clearable placeholder="用户名/邮箱" @keyup.enter="loadUsers(1)" />
                <el-button @click="loadUsers(1)">搜索</el-button>
              </div>
            </div>
          </template>

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
        </el-card>
      </el-col>
    </el-row>

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
  consoleLogout,
  consoleMe,
  getConsoleBackgrounds,
  getConsoleUsers,
  updateConsoleBackground,
  updateConsoleUser,
} from '../api/console'

const router = useRouter()
const adminUser = ref(null)

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

const editVisible = ref(false)
const editForm = reactive({ id: null, username: '', email: '', is_active: true })

const loadAdminMe = async () => {
  const res = await consoleMe()
  adminUser.value = res.data.user
}

const loadBackgrounds = async () => {
  const res = await getConsoleBackgrounds()
  const map = Object.fromEntries(res.data.map((item) => [item.scene, item.image_url]))
  backgroundItems.value = backgroundItems.value.map((item) => ({
    ...item,
    image_url: map[item.scene] || '',
  }))
}

const saveBackground = async (item) => {
  try {
    await updateConsoleBackground(item.scene, { image_url: item.image_url || '' })
    ElMessage.success('背景图已更新')
  } catch (e) {
    ElMessage.error(e)
  }
}

const pickBackgroundFile = (scene) => {
  const input = document.getElementById(`bg-upload-${scene}`)
  if (input) input.click()
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
    const before = formatSize(file.size)
    const after = formatSize(compressed.size)
    ElMessage.success(`上传并保存成功（已存入COS，${before} -> ${after}）`)
  } catch (e) {
    ElMessage.error(e)
  } finally {
    item.uploading = false
  }
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
    await Promise.all([loadBackgrounds(), loadUsers(1)])
  } catch {
    router.push('/admin/login')
  }
})
</script>

<style scoped>
.admin-dashboard {
  min-height: 100vh;
  padding: 24px 16px 36px;
  background:
    radial-gradient(900px 340px at 0% 0%, rgba(15, 124, 134, 0.14), transparent 60%),
    radial-gradient(760px 300px at 100% -8%, rgba(227, 124, 65, 0.16), transparent 60%),
    linear-gradient(160deg, #f3f8ff, #f8eee4);
}
.dash-header {
  margin: 0 auto 16px;
  padding-top: 8px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.dash-header p {
  margin: 8px 0 0;
  color: var(--ink-700);
}
.dash-card {
  margin: 0 auto 8px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}
.metric-card {
  border-radius: 12px;
  border: 1px solid var(--line-soft);
  background: rgba(255, 255, 255, 0.92);
}
.bg-form-item {
  padding: 10px 0 14px;
  border-bottom: 1px solid var(--line-soft);
}
.bg-form-item:last-child {
  border-bottom: 0;
}
.bg-label {
  margin: 0 0 8px;
  font-weight: 600;
  color: var(--ink-700);
}
.tiny-tip {
  margin: 4px 0 0;
  color: var(--ink-700);
  font-size: 12px;
}
.bg-thumb {
  height: 120px;
  border-radius: 10px;
  border: 1px dashed #aac4e8;
  background: #f6faff;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6f87a8;
  margin-bottom: 8px;
}
.bg-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
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
@media (max-width: 991px) {
  .dash-header {
    align-items: stretch;
    flex-direction: column;
  }
}
@media (max-width: 767px) {
  .user-header {
    align-items: stretch;
    flex-direction: column;
  }
  .user-filter {
    width: 100%;
  }
}
</style>
