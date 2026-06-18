<template>
  <div class="octopus-shell" :style="pageStyle">
    <aside class="octopus-sidebar">
      <button class="brand-chip" type="button" @click="router.push('/')">
        <span>OLD BOY</span>
        <strong>章鱼空间</strong>
      </button>
      <nav class="feature-nav" aria-label="章鱼空间功能">
        <button class="feature-item active" type="button">
          <span class="feature-mark">记</span>
          <span>
            <strong>章鱼记</strong>
            <small>文件夹与记事本</small>
          </span>
        </button>
      </nav>
      <div class="sidebar-note">
        <p>把灵感先收进深海，等它发光。</p>
        <small>{{ folders.length }} 个文件夹 · {{ totalNotes }} 本记事</small>
      </div>
    </aside>

    <main class="octopus-stage">
      <section class="stage-hero">
        <div>
          <p class="eyebrow">OCTOPUS MEMOIR</p>
          <h1>章鱼记</h1>
          <p class="hero-copy">创建文件夹，沉淀你的项目资料、灵感片段和工作备忘。每一本记事本都会自动保存最后的发光瞬间。</p>
        </div>
        <button class="ghost-home" type="button" @click="router.push('/')">返回工作台</button>
      </section>

      <section class="library-panel">
        <header class="library-head">
          <div>
            <p class="eyebrow">{{ currentFolder ? 'NOTEBOOKS' : 'FOLDERS' }}</p>
            <h2>{{ currentFolder ? currentFolder.name : '文件夹列表' }}</h2>
          </div>
          <div class="head-actions">
            <button v-if="currentFolder" class="soft-btn" type="button" @click="backToFolders">返回文件夹</button>
            <button class="primary-glow" type="button" @click="currentFolder ? createNote() : createFolder()">
              {{ currentFolder ? '创建记事本' : '创建新文件夹' }}
            </button>
          </div>
        </header>

        <div class="tool-strip">
          <label class="search-box">
            <span>模糊查询</span>
            <input v-model="searchText" type="search" :placeholder="currentFolder ? '搜索标题或内容' : '搜索文件夹名称'" @input="scheduleSearch" />
          </label>
          <label class="sort-box">
            <span>创建时间</span>
            <select v-model="sortOrder" @change="reloadCurrent">
              <option value="created_desc">最新创建优先</option>
              <option value="created_asc">最早创建优先</option>
            </select>
          </label>
        </div>

        <div v-if="!currentFolder" class="card-grid folder-grid" :class="{ loading }">
          <article
            v-for="folder in folders"
            :key="folder.id"
            class="memory-card folder-card"
            :class="{ 'has-cover': folder.cover_url }"
            :style="coverCardStyle(folder)"
            @click="openFolder(folder)"
          >
            <div class="card-orbit"></div>
            <div class="card-icon">F</div>
            <h3>{{ folder.name }}</h3>
            <p>{{ folder.note_count }} 本记事本</p>
            <small>创建于 {{ formatDate(folder.created_at) }}</small>
            <el-dropdown class="card-menu" trigger="click" @command="(command) => handleFolderCommand(command, folder)" @click.stop>
              <button class="dots-btn" type="button" @click.stop>...</button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="cover">编辑封面</el-dropdown-item>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </article>
          <div v-if="!folders.length && !loading" class="empty-state">
            <strong>还没有文件夹</strong>
            <span>从左上角创建一个新文件夹，给想法找个栖息地。</span>
          </div>
        </div>

        <div v-else class="card-grid note-grid" :class="{ loading: noteLoading }">
          <article
            v-for="note in notes"
            :key="note.id"
            class="memory-card note-card"
            :class="{ 'has-cover': note.cover_url }"
            :style="coverCardStyle(note)"
            @click="openNote(note)"
          >
            <div class="card-orbit"></div>
            <div class="card-icon">N</div>
            <h3>{{ note.title }}</h3>
            <p>{{ notePreview(note) }}</p>
            <small>创建于 {{ formatDate(note.created_at) }}</small>
            <el-dropdown class="card-menu" trigger="click" @command="(command) => handleNoteCommand(command, note)" @click.stop>
              <button class="dots-btn" type="button" @click.stop>...</button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="cover">编辑封面</el-dropdown-item>
                  <el-dropdown-item command="rename">重命名</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </article>
          <div v-if="!notes.length && !noteLoading" class="empty-state">
            <strong>这个文件夹还是空的</strong>
            <span>创建一个记事本，把第一段想法写进去。</span>
          </div>
        </div>
      </section>
    </main>

    <transition name="editor-pop">
      <section v-if="editorVisible" class="editor-overlay" @click.self="closeEditor">
        <article class="editor-card">
          <header class="editor-head">
            <div>
              <p class="eyebrow">FLOATING NOTEBOOK</p>
              <input v-model="editorDraft.title" class="title-input" maxlength="120" placeholder="记事本名称" @input="markDirty" />
            </div>
            <button class="close-btn" type="button" @click="closeEditor">关闭</button>
          </header>

          <div class="font-toolbar">
            <label>
              <span>字体</span>
              <select v-model="editorDraft.font_family" @change="markDirty">
                <option v-for="font in fontOptions" :key="font.value" :value="font.value">{{ font.label }}</option>
              </select>
            </label>
            <label>
              <span>字号</span>
              <input v-model.number="editorDraft.font_size" min="12" max="42" type="number" @input="markDirty" />
            </label>
            <label>
              <span>颜色</span>
              <input v-model="editorDraft.text_color" type="color" @input="markDirty" />
            </label>
            <small>{{ dirty ? '有未保存内容，关闭会自动保存' : '内容已同步' }}</small>
          </div>

          <div
            ref="editorRef"
            class="note-editor"
            contenteditable="true"
            spellcheck="false"
            :style="editorStyle"
            @input="handleEditorInput"
          ></div>

          <footer class="editor-actions">
            <button class="danger-btn" type="button" :disabled="saving" @click="deleteEditingNote">删除</button>
            <button class="primary-glow" type="button" :disabled="saving" @click="saveDraft()">{{ saving ? '保存中...' : '保存' }}</button>
          </footer>
        </article>
      </section>
    </transition>

    <input ref="coverInputRef" class="cover-file-input" type="file" accept="image/*" @change="handleCoverFileChange" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { getSiteBackgrounds } from '../api/site'
import {
  createOctopusFolder,
  createOctopusNote,
  deleteOctopusFolder,
  deleteOctopusNote,
  getOctopusFolders,
  getOctopusNotes,
  updateOctopusFolder,
  updateOctopusNote,
} from '../api/octopusNotes'
import { storageFileUrl, uploadToCos } from '../api/storage'

const router = useRouter()
const fallbackBg = 'https://zy2000zh-1257453885.cos.ap-shanghai.myqcloud.com/image/1.png'
const backgroundUrl = ref('')
const folders = ref([])
const notes = ref([])
const currentFolder = ref(null)
const searchText = ref('')
const sortOrder = ref('created_desc')
const loading = ref(false)
const noteLoading = ref(false)
const editorVisible = ref(false)
const editingNote = ref(null)
const editorDraft = ref(defaultDraft())
const editorRef = ref(null)
const dirty = ref(false)
const saving = ref(false)
const coverInputRef = ref(null)
const coverUploadTarget = ref(null)
const coverUploading = ref(false)
let searchTimer = null

const fontOptions = [
  { label: '星轨默认', value: 'Plus Jakarta Sans' },
  { label: '未来机械', value: 'Orbitron' },
  { label: '中文手札', value: 'ZCOOL KuaiLe' },
  { label: '宋体长文', value: 'Songti SC' },
  { label: '等宽代码', value: 'Menlo' },
]

function defaultDraft() {
  return {
    id: null,
    title: '',
    content: '',
    font_family: 'Plus Jakarta Sans',
    font_size: 18,
    text_color: '#eaf7ff',
  }
}

const withVersion = (url, version) => {
  if (!url) return ''
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}v=${version || Date.now()}`
}

const pageStyle = computed(() =>
  backgroundUrl.value
    ? {
        background:
          `linear-gradient(120deg, rgba(5,12,28,0.7), rgba(14,24,54,0.62)), url(${backgroundUrl.value}) center/cover no-repeat`,
      }
    : {}
)

const totalNotes = computed(() => folders.value.reduce((sum, folder) => sum + Number(folder.note_count || 0), 0))

const editorStyle = computed(() => ({
  fontFamily: `"${editorDraft.value.font_family}", "PingFang SC", "Hiragino Sans GB", sans-serif`,
  fontSize: `${editorDraft.value.font_size || 18}px`,
  color: editorDraft.value.text_color || '#eaf7ff',
}))

const coverCardStyle = (item) => {
  if (!item?.cover_url) return {}
  return {
    backgroundImage: `linear-gradient(180deg, rgba(3, 8, 18, 0.22), rgba(3, 8, 18, 0.84)), url("${storageFileUrl(item.cover_url)}")`,
    backgroundPosition: 'center',
    backgroundSize: 'cover',
  }
}

const loadBackground = async () => {
  try {
    const res = await getSiteBackgrounds()
    backgroundUrl.value = withVersion(res.data.login || fallbackBg, res.data._version)
  } catch {
    backgroundUrl.value = withVersion(fallbackBg)
  }
}

const loadFolders = async () => {
  loading.value = true
  try {
    const res = await getOctopusFolders({ q: searchText.value, order: sortOrder.value })
    folders.value = res.data.list || []
    if (currentFolder.value) {
      currentFolder.value = folders.value.find((folder) => folder.id === currentFolder.value.id) || currentFolder.value
    }
  } catch (error) {
    ElMessage.error(String(error || '文件夹加载失败'))
  } finally {
    loading.value = false
  }
}

const loadNotes = async () => {
  if (!currentFolder.value?.id) return
  noteLoading.value = true
  try {
    const res = await getOctopusNotes(currentFolder.value.id, { q: searchText.value, order: sortOrder.value })
    notes.value = res.data.list || []
  } catch (error) {
    ElMessage.error(String(error || '记事本加载失败'))
  } finally {
    noteLoading.value = false
  }
}

const reloadCurrent = () => {
  if (currentFolder.value) loadNotes()
  else loadFolders()
}

const scheduleSearch = () => {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(reloadCurrent, 220)
}

const promptName = async (title, inputValue, placeholder) => {
  const result = await ElMessageBox.prompt(placeholder, title, {
    inputValue,
    inputPattern: /\S+/,
    inputErrorMessage: '名称不能为空',
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    customClass: 'anime-neon-message-box',
  })
  return String(result.value || '').trim()
}

const createFolder = async () => {
  try {
    const name = await promptName('创建新文件夹', '', '给文件夹起个名字')
    const res = await createOctopusFolder({ name })
    folders.value = [res.data, ...folders.value]
    ElMessage.success('文件夹已创建')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '文件夹创建失败'))
  }
}

const renameFolder = async (folder) => {
  try {
    const name = await promptName('重命名文件夹', folder.name, '新的文件夹名称')
    const res = await updateOctopusFolder(folder.id, { name })
    folders.value = folders.value.map((item) => (item.id === folder.id ? res.data : item))
    if (currentFolder.value?.id === folder.id) currentFolder.value = res.data
    ElMessage.success('文件夹已重命名')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '重命名失败'))
  }
}

const replaceFolder = (nextFolder) => {
  folders.value = folders.value.map((item) => (item.id === nextFolder.id ? nextFolder : item))
  if (currentFolder.value?.id === nextFolder.id) currentFolder.value = nextFolder
}

const editCover = (type, item) => {
  if (coverUploading.value) return
  coverUploadTarget.value = { type, item }
  if (coverInputRef.value) {
    coverInputRef.value.value = ''
    coverInputRef.value.click()
  }
}

const handleCoverFileChange = async (event) => {
  const file = event.target.files?.[0]
  const target = coverUploadTarget.value
  event.target.value = ''
  if (!file || !target?.item?.id) return
  if (!file.type.startsWith('image/')) {
    ElMessage.error('请选择图片文件')
    return
  }
  coverUploading.value = true
  try {
    const uploaded = await uploadToCos(file, 'images/octopus-notes/covers', { timeout: 120000 })
    const coverUrl = uploaded.data.url
    if (target.type === 'folder') {
      const res = await updateOctopusFolder(target.item.id, { cover_url: coverUrl })
      replaceFolder(res.data)
    } else {
      const res = await updateOctopusNote(target.item.id, { cover_url: coverUrl })
      replaceNote(res.data)
    }
    ElMessage.success(uploaded.data.compressed ? '封面已压缩并上传' : '封面已更新')
  } catch (error) {
    ElMessage.error(String(error || '封面上传失败'))
  } finally {
    coverUploading.value = false
    coverUploadTarget.value = null
  }
}

const removeFolder = async (folder) => {
  try {
    await ElMessageBox.confirm(`删除“${folder.name}”及其中所有记事本？`, '删除文件夹', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      customClass: 'anime-neon-message-box',
    })
    await deleteOctopusFolder(folder.id)
    folders.value = folders.value.filter((item) => item.id !== folder.id)
    if (currentFolder.value?.id === folder.id) backToFolders()
    ElMessage.success('文件夹已删除')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '删除失败'))
  }
}

const handleFolderCommand = (command, folder) => {
  if (command === 'cover') editCover('folder', folder)
  if (command === 'rename') renameFolder(folder)
  if (command === 'delete') removeFolder(folder)
}

const openFolder = async (folder) => {
  currentFolder.value = folder
  searchText.value = ''
  notes.value = []
  await loadNotes()
}

const backToFolders = () => {
  currentFolder.value = null
  notes.value = []
  searchText.value = ''
  loadFolders()
}

const createNote = async () => {
  if (!currentFolder.value?.id) return
  try {
    const title = await promptName('创建记事本', '', '给记事本起个名字')
    const res = await createOctopusNote(currentFolder.value.id, { title })
    notes.value = [res.data, ...notes.value]
    currentFolder.value.note_count = Number(currentFolder.value.note_count || 0) + 1
    await openNote(res.data)
    ElMessage.success('记事本已创建')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '记事本创建失败'))
  }
}

const openNote = async (note) => {
  editingNote.value = note
  editorDraft.value = {
    id: note.id,
    title: note.title,
    content: note.content || '',
    font_family: note.font_family || 'Plus Jakarta Sans',
    font_size: note.font_size || 18,
    text_color: note.text_color || '#eaf7ff',
  }
  dirty.value = false
  editorVisible.value = true
  await nextTick()
  if (editorRef.value) editorRef.value.textContent = editorDraft.value.content || ''
}

const handleEditorInput = () => {
  editorDraft.value.content = editorRef.value?.textContent || ''
  markDirty()
}

const markDirty = () => {
  dirty.value = true
}

const replaceNote = (nextNote) => {
  notes.value = notes.value.map((item) => (item.id === nextNote.id ? nextNote : item))
  if (editingNote.value?.id === nextNote.id) editingNote.value = nextNote
}

const saveDraft = async ({ silent = false } = {}) => {
  if (!editorDraft.value.id || saving.value) return
  saving.value = true
  try {
    if (editorRef.value) editorDraft.value.content = editorRef.value.textContent || ''
    const res = await updateOctopusNote(editorDraft.value.id, {
      title: editorDraft.value.title,
      content: editorDraft.value.content,
      font_family: editorDraft.value.font_family,
      font_size: editorDraft.value.font_size,
      text_color: editorDraft.value.text_color,
    })
    replaceNote(res.data)
    dirty.value = false
    if (!silent) ElMessage.success('记事本已保存')
  } catch (error) {
    ElMessage.error(String(error || '保存失败'))
  } finally {
    saving.value = false
  }
}

const closeEditor = async () => {
  if (dirty.value) await saveDraft({ silent: true })
  editorVisible.value = false
  editingNote.value = null
  editorDraft.value = defaultDraft()
}

const renameNote = async (note) => {
  try {
    const title = await promptName('重命名记事本', note.title, '新的记事本名称')
    const res = await updateOctopusNote(note.id, { title })
    replaceNote(res.data)
    ElMessage.success('记事本已重命名')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '重命名失败'))
  }
}

const removeNote = async (note) => {
  try {
    await ElMessageBox.confirm(`删除“${note.title}”？`, '删除记事本', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      customClass: 'anime-neon-message-box',
    })
    await deleteOctopusNote(note.id)
    notes.value = notes.value.filter((item) => item.id !== note.id)
    if (currentFolder.value) currentFolder.value.note_count = Math.max(Number(currentFolder.value.note_count || 1) - 1, 0)
    if (editingNote.value?.id === note.id) {
      editorVisible.value = false
      editingNote.value = null
      dirty.value = false
    }
    ElMessage.success('记事本已删除')
  } catch (error) {
    if (!['cancel', 'close'].includes(error)) ElMessage.error(String(error || '删除失败'))
  }
}

const deleteEditingNote = async () => {
  if (editingNote.value) await removeNote(editingNote.value)
}

const handleNoteCommand = (command, note) => {
  if (command === 'edit') openNote(note)
  if (command === 'cover') editCover('note', note)
  if (command === 'rename') renameNote(note)
  if (command === 'delete') removeNote(note)
}

const notePreview = (note) => {
  const text = String(note.content || '').replace(/\s+/g, ' ').trim()
  return text || '空白页，等你落笔。'
}

const formatDate = (value) => {
  if (!value) return '--'
  return new Date(value).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

onMounted(async () => {
  await Promise.all([loadBackground(), loadFolders()])
})

onBeforeUnmount(() => {
  if (searchTimer) window.clearTimeout(searchTimer)
  if (dirty.value) saveDraft({ silent: true })
})
</script>

<style scoped>
.octopus-shell {
  min-height: 100vh;
  padding: 24px;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 22px;
  color: #eef8ff;
  background:
    radial-gradient(circle at 16% 10%, rgba(69, 221, 255, .22), transparent 34%),
    linear-gradient(145deg, #06111f, #101a3b 48%, #071022);
}

.octopus-sidebar,
.library-panel,
.editor-card {
  border: 1px solid rgba(132, 223, 255, .22);
  background: linear-gradient(155deg, rgba(4, 14, 28, .86), rgba(17, 28, 61, .74));
  box-shadow: 0 24px 70px rgba(0, 10, 30, .42);
  backdrop-filter: blur(18px);
}

.octopus-sidebar {
  position: sticky;
  top: 24px;
  height: calc(100vh - 48px);
  padding: 18px;
  border-radius: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.brand-chip {
  border: 0;
  border-radius: 22px;
  padding: 18px;
  text-align: left;
  color: #f5fbff;
  background:
    linear-gradient(135deg, rgba(58, 216, 255, .28), rgba(255, 82, 205, .16)),
    rgba(255, 255, 255, .04);
  cursor: pointer;
}

.brand-chip span,
.eyebrow {
  display: block;
  color: #7ff3ff;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: .18em;
}

.brand-chip strong {
  display: block;
  margin-top: 8px;
  font-family: "Orbitron", "ZCOOL KuaiLe", sans-serif;
  font-size: 28px;
}

.feature-nav {
  display: grid;
  gap: 10px;
}

.feature-item {
  width: 100%;
  border: 1px solid rgba(125, 231, 255, .24);
  border-radius: 18px;
  padding: 14px;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr);
  gap: 12px;
  align-items: center;
  color: #e9faff;
  background: rgba(255, 255, 255, .04);
  text-align: left;
}

.feature-item.active {
  border-color: rgba(255, 83, 206, .52);
  background: linear-gradient(135deg, rgba(255, 83, 206, .18), rgba(65, 222, 255, .12));
  box-shadow: 0 0 28px rgba(80, 224, 255, .18);
}

.feature-mark {
  width: 44px;
  height: 44px;
  border-radius: 15px;
  display: grid;
  place-items: center;
  background: #071426;
  color: #73faff;
  font-weight: 900;
  box-shadow: inset 0 0 18px rgba(115, 250, 255, .25);
}

.feature-item strong,
.feature-item small {
  display: block;
}

.feature-item small,
.sidebar-note,
.hero-copy,
.memory-card p,
.memory-card small,
.font-toolbar small {
  color: #a9bfd4;
}

.sidebar-note {
  margin-top: auto;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, .05);
  line-height: 1.55;
}

.octopus-stage {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.stage-hero {
  min-height: 210px;
  padding: clamp(24px, 4vw, 42px);
  border: 1px solid rgba(133, 220, 255, .2);
  border-radius: 30px;
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
  background:
    radial-gradient(circle at 12% 24%, rgba(74, 230, 255, .24), transparent 30%),
    radial-gradient(circle at 90% 10%, rgba(255, 78, 198, .2), transparent 28%),
    linear-gradient(135deg, rgba(7, 17, 39, .88), rgba(14, 23, 58, .78));
  box-shadow: 0 30px 80px rgba(0, 8, 30, .36);
}

.stage-hero h1,
.library-head h2 {
  margin: 8px 0 0;
  font-family: "Orbitron", "ZCOOL KuaiLe", sans-serif;
}

.stage-hero h1 {
  font-size: clamp(46px, 8vw, 84px);
  line-height: .95;
  text-shadow: 0 0 26px rgba(93, 232, 255, .6);
}

.hero-copy {
  max-width: 660px;
  margin: 18px 0 0;
  font-size: 16px;
  line-height: 1.8;
}

.ghost-home,
.soft-btn,
.primary-glow,
.danger-btn,
.close-btn {
  border: 0;
  border-radius: 999px;
  min-height: 40px;
  padding: 0 18px;
  color: #f7fbff;
  cursor: pointer;
  font-weight: 800;
}

.ghost-home,
.soft-btn,
.close-btn {
  border: 1px solid rgba(161, 229, 255, .3);
  background: rgba(255, 255, 255, .06);
}

.primary-glow {
  background: linear-gradient(120deg, #34d9ff, #7a67ff 52%, #ff4ec6);
  box-shadow: 0 12px 32px rgba(64, 217, 255, .34);
}

.danger-btn {
  background: linear-gradient(120deg, #3a1620, #a53348);
  box-shadow: 0 12px 28px rgba(255, 86, 120, .22);
}

.library-panel {
  min-height: calc(100vh - 288px);
  border-radius: 30px;
  padding: clamp(18px, 3vw, 28px);
}

.library-head,
.head-actions,
.tool-strip,
.editor-head,
.editor-actions {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: space-between;
}

.library-head {
  margin-bottom: 18px;
}

.library-head h2 {
  font-size: clamp(28px, 4vw, 42px);
}

.tool-strip {
  margin-bottom: 22px;
  padding: 12px;
  border: 1px solid rgba(147, 223, 255, .18);
  border-radius: 20px;
  background: rgba(255, 255, 255, .04);
}

.search-box,
.sort-box,
.font-toolbar label {
  display: grid;
  gap: 6px;
  color: #9fdcf7;
  font-size: 12px;
  font-weight: 800;
}

.search-box {
  flex: 1;
}

.search-box input,
.sort-box select,
.font-toolbar select,
.font-toolbar input,
.title-input {
  min-height: 40px;
  border: 1px solid rgba(144, 224, 255, .22);
  border-radius: 14px;
  padding: 0 12px;
  outline: none;
  color: #effbff;
  background: rgba(3, 10, 24, .64);
}

.search-box input:focus,
.sort-box select:focus,
.title-input:focus,
.font-toolbar select:focus,
.font-toolbar input:focus {
  border-color: #69f0ff;
  box-shadow: 0 0 0 4px rgba(105, 240, 255, .12);
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
  gap: 18px;
}

.card-grid.loading {
  opacity: .62;
  pointer-events: none;
}

.memory-card {
  position: relative;
  aspect-ratio: 1 / 1;
  padding: 18px;
  border: 1px solid rgba(138, 224, 255, .22);
  border-radius: 26px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background:
    linear-gradient(155deg, rgba(16, 35, 68, .86), rgba(7, 14, 31, .92)),
    radial-gradient(circle at 20% 16%, rgba(86, 233, 255, .22), transparent 34%);
  box-shadow: 0 18px 46px rgba(0, 9, 28, .3);
  cursor: pointer;
  transition: transform .24s ease, border-color .24s ease, box-shadow .24s ease;
}

.memory-card:hover {
  transform: translateY(-6px) rotate(-.8deg);
  border-color: rgba(114, 250, 255, .65);
  box-shadow: 0 24px 60px rgba(37, 206, 255, .2);
}

.memory-card.has-cover {
  border-color: rgba(183, 238, 255, .36);
}

.memory-card.has-cover .card-orbit {
  display: none;
}

.card-orbit {
  position: absolute;
  inset: -40% -20% auto auto;
  width: 170px;
  height: 170px;
  border-radius: 50%;
  border: 1px solid rgba(117, 255, 244, .18);
  box-shadow: inset 0 0 34px rgba(101, 238, 255, .16);
}

.note-card {
  background:
    linear-gradient(155deg, rgba(30, 24, 64, .88), rgba(8, 15, 32, .94)),
    radial-gradient(circle at 20% 16%, rgba(255, 84, 206, .18), transparent 34%);
}

.card-icon {
  position: absolute;
  top: 16px;
  left: 16px;
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  color: #071426;
  background: linear-gradient(135deg, #72fff4, #fff1a8);
  font-family: "Orbitron", sans-serif;
  font-weight: 900;
}

.memory-card h3 {
  position: relative;
  margin: 0 34px 8px 0;
  font-size: 24px;
  line-height: 1.18;
  word-break: break-word;
}

.memory-card p {
  position: relative;
  margin: 0 0 8px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.memory-card small {
  position: relative;
}

.card-menu {
  position: absolute;
  right: 14px;
  bottom: 14px;
}

.dots-btn {
  width: 38px;
  height: 32px;
  border: 1px solid rgba(156, 229, 255, .25);
  border-radius: 999px;
  color: #eafaff;
  background: rgba(2, 8, 18, .62);
  cursor: pointer;
  letter-spacing: 2px;
}

.cover-file-input {
  display: none;
}

.empty-state {
  min-height: 220px;
  border: 1px dashed rgba(148, 226, 255, .28);
  border-radius: 24px;
  display: grid;
  place-content: center;
  gap: 8px;
  text-align: center;
  color: #a9bfd4;
}

.empty-state strong {
  color: #f3fbff;
  font-size: 22px;
}

.editor-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  padding: 28px;
  display: grid;
  place-items: center;
  background: radial-gradient(circle at 50% 12%, rgba(88, 224, 255, .18), rgba(1, 5, 16, .78));
  backdrop-filter: blur(10px);
}

.editor-card {
  width: min(1040px, 100%);
  height: min(860px, calc(100vh - 56px));
  border-radius: 30px;
  padding: 20px;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  gap: 14px;
  overflow: hidden;
}

.title-input {
  width: min(620px, 72vw);
  margin-top: 8px;
  border: 0;
  padding: 0;
  background: transparent;
  color: #fff;
  font-family: "Orbitron", "ZCOOL KuaiLe", sans-serif;
  font-size: clamp(26px, 5vw, 48px);
}

.font-toolbar {
  padding: 12px;
  border: 1px solid rgba(147, 223, 255, .16);
  border-radius: 18px;
  display: flex;
  gap: 12px;
  align-items: end;
  flex-wrap: wrap;
  background: rgba(255, 255, 255, .04);
}

.font-toolbar small {
  margin-left: auto;
  padding-bottom: 10px;
}

.note-editor {
  min-height: 0;
  height: 100%;
  overflow: auto;
  border: 1px solid rgba(127, 240, 255, .22);
  border-radius: 24px;
  padding: clamp(18px, 3vw, 30px);
  outline: none;
  white-space: pre-wrap;
  line-height: 1.8;
  background:
    linear-gradient(135deg, rgba(4, 10, 24, .92), rgba(10, 17, 42, .86)),
    repeating-linear-gradient(0deg, transparent 0 34px, rgba(117, 242, 255, .05) 35px);
  caret-color: #64fff4;
  text-shadow: 0 0 12px currentColor;
  box-shadow: inset 0 0 44px rgba(68, 216, 255, .08);
  animation: editor-glow 5s linear infinite;
}

.note-editor:focus {
  border-color: rgba(255, 78, 198, .72);
  box-shadow:
    inset 0 0 52px rgba(68, 216, 255, .12),
    0 0 0 4px rgba(255, 78, 198, .1),
    0 0 32px rgba(91, 238, 255, .18);
}

.note-editor::selection {
  color: #06111f;
  background: #78fff2;
}

.editor-actions {
  position: relative;
  z-index: 2;
  padding-top: 6px;
  border-top: 1px solid rgba(147, 223, 255, .16);
  justify-content: flex-end;
  background: linear-gradient(180deg, rgba(7, 16, 36, .1), rgba(7, 16, 36, .72));
}

.editor-pop-enter-active,
.editor-pop-leave-active {
  transition: opacity .22s ease;
}

.editor-pop-enter-active .editor-card,
.editor-pop-leave-active .editor-card {
  transition: transform .22s ease, opacity .22s ease;
}

.editor-pop-enter-from,
.editor-pop-leave-to {
  opacity: 0;
}

.editor-pop-enter-from .editor-card,
.editor-pop-leave-to .editor-card {
  opacity: 0;
  transform: translateY(18px) scale(.98);
}

@keyframes editor-glow {
  0% { filter: hue-rotate(0deg); }
  100% { filter: hue-rotate(360deg); }
}

@media (max-width: 980px) {
  .octopus-shell {
    grid-template-columns: 1fr;
  }

  .octopus-sidebar {
    position: static;
    height: auto;
  }

  .stage-hero,
  .library-head,
  .tool-strip {
    flex-direction: column;
    align-items: stretch;
  }

  .head-actions {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
