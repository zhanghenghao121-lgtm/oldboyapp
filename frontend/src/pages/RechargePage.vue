<template>
  <div class="page-shell recharge-shell">
    <el-card class="surface-card recharge-card" shadow="never">
      <div class="top-actions">
        <el-button @click="$router.push('/home')">返回首页</el-button>
      </div>
      <div class="title-block">
        <h2>积分充值中心</h2>
        <p>开发者微信号：{{ wechatId }}</p>
      </div>
      <div class="status-line">
        <span class="pill">即将上线</span>
        <p>如需充值请添加开发者微信沟通处理。</p>
      </div>
      <div v-if="qrUrl" class="qr-wrap">
        <img :src="qrUrl" alt="微信二维码" class="qr-image" />
      </div>
      <div class="actions">
        <el-button class="main-btn" type="primary" @click="$router.push('/script-optimizer')">返回剧本优化</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { getSiteBackgrounds } from '../api/site'

const wechatId = ref('Dsdfcc2000')
const qrUrl = ref('')

const loadRechargeConfig = async () => {
  try {
    const res = await getSiteBackgrounds()
    wechatId.value = res.data.recharge_wechat_id || 'Dsdfcc2000'
    qrUrl.value = res.data.recharge_qr_url || ''
  } catch {
    wechatId.value = 'Dsdfcc2000'
    qrUrl.value = ''
  }
}

onMounted(loadRechargeConfig)
</script>

<style scoped>
.recharge-shell {
  min-height: 100vh;
}
.recharge-card {
  width: min(680px, 100%);
}
.top-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 8px;
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
.qr-wrap {
  margin: 14px 0 18px;
  padding: 10px;
  border-radius: 14px;
  border: 1px solid rgba(145, 213, 255, 0.35);
  background: rgba(18, 29, 82, 0.48);
  display: flex;
  justify-content: center;
}
.qr-image {
  display: block;
  width: min(320px, 100%);
  border-radius: 10px;
  object-fit: contain;
}
</style>
