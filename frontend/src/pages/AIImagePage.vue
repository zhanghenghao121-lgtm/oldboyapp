<template>
  <div class="image-shell">
    <aside class="tool-rail">
      <div class="brand-block">
        <p class="eyebrow">AI IMAGE</p>
        <h1>AI生图</h1>
      </div>
      <div class="tool-card">
        <strong>站位贴图</strong>
        <span>抠图角色自由摆放合成</span>
      </div>
      <el-button plain class="back-btn" @click="$router.push('/storyboard')">返回故事板</el-button>
    </aside>

    <main class="studio">
      <header class="studio-head">
        <div>
          <p class="eyebrow">LAYER COMPOSER</p>
          <h2>场景站位贴图</h2>
        </div>
        <el-button plain @click="settingsDialogRef?.open()">设置</el-button>
      </header>

      <StickerComposer />
    </main>
    <UserSettingsDialog ref="settingsDialogRef" />
  </div>
</template>

<script setup>
import { defineAsyncComponent, ref } from 'vue'

import UserSettingsDialog from '../components/UserSettingsDialog.vue'

const StickerComposer = defineAsyncComponent(() => import('../components/StickerComposer.vue'))
const settingsDialogRef = ref(null)
</script>

<style scoped>
.image-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 260px 1fr;
  background: #0a0f14;
  color: #eef4f0;
}

.tool-rail {
  padding: 24px 16px;
  border-right: 1px solid rgba(145, 184, 169, 0.28);
  background: #0d1717;
}

.brand-block h1,
.studio-head h2 {
  margin: 0;
}

.eyebrow {
  margin: 0 0 7px;
  color: #9dd6bd;
  font-size: 12px;
  letter-spacing: 0.08em;
}

.tool-card {
  width: 100%;
  min-height: 76px;
  margin-top: 12px;
  padding: 14px;
  border: 1px solid #6ee7ac;
  border-radius: 8px;
  background: #16342b;
  color: #dfeee8;
  text-align: left;
}

.tool-card strong,
.tool-card span {
  display: block;
}

.tool-card span {
  margin-top: 6px;
  color: #8ba69d;
  font-size: 13px;
}

.back-btn {
  width: 100%;
  margin-top: 18px;
}

.studio {
  padding: 24px;
}

.studio-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 960px) {
  .image-shell {
    grid-template-columns: 1fr;
  }

  .studio-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
