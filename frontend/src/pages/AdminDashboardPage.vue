<template>
  <div class="admin-shell">
    <aside class="sidebar">
      <div class="brand">
        <h1>管理后台</h1>
        <p v-if="adminUser">{{ adminUser.username }}</p>
      </div>
      <button class="side-btn active" type="button">AI剧本配置</button>
      <button class="side-btn" type="button" @click="$router.push('/ai-manga')">返回前台</button>
    </aside>

    <main class="main">
      <header class="main-head">
        <div>
          <p class="eyebrow">SCRIPT PROMPT SETTINGS</p>
          <h2>AI剧本创作配置</h2>
        </div>
        <el-button type="danger" plain @click="handleLogout">退出后台</el-button>
      </header>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h3>模型设置</h3>
            <p>保留现有 AI 配置结构，前台可选择助手模型或剧本模型。</p>
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
          </div>
        </el-form>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { consoleLogout, consoleMe, getConsoleConfigs, updateConsoleConfig } from '../api/console'

const router = useRouter()
const adminUser = ref(null)
const savingModels = ref(false)
const savingPrompts = ref(false)

const forms = reactive({
  ai_assistant_base_url: '',
  ai_assistant_api_key: '',
  ai_assistant_model: '',
  ai_manga_base_url: '',
  ai_manga_api_key: '',
  ai_manga_model: '',
  ai_manga_storyboard_prompt: '',
  ai_manga_3d_style_prompt: '',
  ai_manga_real_style_prompt: '',
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
    await saveKeys(['ai_manga_storyboard_prompt', 'ai_manga_3d_style_prompt', 'ai_manga_real_style_prompt'])
    ElMessage.success('提示词配置已保存')
  } catch (e) {
    ElMessage.error(String(e || '提示词配置保存失败'))
  } finally {
    savingPrompts.value = false
  }
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

:deep(.el-input__wrapper),
:deep(.el-textarea__inner) {
  background: #08101f;
  box-shadow: inset 0 0 0 1px rgba(84, 145, 198, 0.42) !important;
  color: #e8eefc;
}

:deep(.el-form-item__label) {
  color: #cbd8ea;
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
}
</style>
