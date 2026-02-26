<template>
  <div class="page-shell">
    <el-card class="surface-card module-card" shadow="never">
      <div class="title-block">
        <h2>剧本优化</h2>
        <p>该模块已创建，后续功能将在本页面持续迭代。</p>
      </div>
      <p class="sub">当前状态：可访问，待接入具体优化能力。</p>
      <el-button class="main-btn" type="primary" @click="$router.push('/home')">返回首页</el-button>
    </el-card>
  </div>
</template>

<style scoped>
.module-card { width: min(680px, 100%); }
.sub { color: var(--ink-700); margin-bottom: 20px; }
</style>
