<template>
  <div class="page-shell recharge-shell">
    <el-card class="surface-card recharge-card" shadow="never">
      <div class="title-block">
        <h2>积分充值中心</h2>
        <p>开发者微信号：Dsdfcc2000</p>
      </div>
      <div class="status-line">
        <span class="pill">即将上线</span>
        <p>如需充值请添加开发者微信沟通处理。</p>
      </div>
      <div class="actions">
        <el-button class="main-btn" type="primary" @click="$router.push('/script-optimizer')">返回剧本优化</el-button>
        <el-button @click="$router.push('/home')">回到首页</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
</script>

<style scoped>
.recharge-shell {
  min-height: 100vh;
}
.recharge-card {
  width: min(680px, 100%);
}
.status-line {
  margin: 10px 0 22px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(145, 213, 255, 0.4);
  background: linear-gradient(120deg, rgba(36, 101, 176, 0.4), rgba(49, 38, 119, 0.5));
}
.status-line p {
  margin: 8px 0 0;
  color: #d7e5ff;
}
.pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  height: 26px;
  border-radius: 999px;
  border: 1px solid rgba(153, 225, 255, 0.55);
  color: #ecf6ff;
  background: rgba(93, 190, 255, 0.22);
  box-shadow: 0 0 14px rgba(90, 196, 255, 0.28);
  font-size: 12px;
  font-weight: 700;
}
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
