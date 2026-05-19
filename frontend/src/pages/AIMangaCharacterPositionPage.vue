<template>
  <div class="position-shell">
    <header class="position-topbar">
      <div class="paper-glow paper-glow-a"></div>
      <div class="paper-glow paper-glow-b"></div>
      <div class="topbar-brand">
        <span class="sidebar-tag">Character Blocking</span>
        <div>
          <h2>AI漫剧</h2>
          <p>为分镜画面规划人物站位与镜头调度。</p>
        </div>
      </div>
      <nav class="topbar-nav">
        <button class="nav-btn" type="button" @click="$router.push('/ai-manga')">AI漫剧创作</button>
        <button class="nav-btn active" type="button" @click="$router.push('/ai-manga/character-position')">人物站位</button>
        <button class="nav-btn" type="button" @click="$router.push('/ai-customer')">AI章鱼助手</button>
      </nav>
    </header>

    <main class="position-main">
      <section class="coming-soon-panel">
        <p class="panel-kicker">COMING SOON</p>
        <h1>人物站位功能暂未开放</h1>
        <p class="panel-sub">后续将在这里支持角色入场位置、相对距离、镜头方向与画面调度配置。</p>
        <div class="panel-actions">
          <el-button class="main-action" type="primary" @click="$router.push('/ai-manga')">返回 AI漫剧创作</el-button>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.position-shell {
  min-height: 100vh;
  background:
    radial-gradient(900px 420px at 18% -4%, rgba(255, 166, 64, 0.14), transparent 65%),
    radial-gradient(780px 380px at 100% 0%, rgba(65, 208, 255, 0.12), transparent 62%),
    linear-gradient(135deg, #120f18, #1d1623 48%, #0f1117);
  color: #f7f2ea;
}
.position-topbar {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 18px 26px;
  border-bottom: 1px solid rgba(255, 209, 153, 0.18);
  background:
    linear-gradient(180deg, rgba(34, 24, 30, 0.96), rgba(18, 16, 24, 0.98)),
    repeating-linear-gradient(
      0deg,
      rgba(255, 255, 255, 0.02) 0,
      rgba(255, 255, 255, 0.02) 1px,
      transparent 1px,
      transparent 12px
    );
}
.paper-glow {
  position: absolute;
  border-radius: 999px;
  filter: blur(30px);
  pointer-events: none;
}
.paper-glow-a {
  width: 180px;
  height: 180px;
  background: rgba(255, 152, 51, 0.2);
  top: -60px;
  left: -30px;
}
.paper-glow-b {
  width: 160px;
  height: 160px;
  background: rgba(68, 209, 255, 0.15);
  top: -34px;
  right: 12%;
}
.topbar-brand {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}
.sidebar-tag {
  display: inline-flex;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 11px;
  letter-spacing: 0.16em;
  color: #ffddaf;
  border: 1px solid rgba(255, 190, 112, 0.28);
  background: rgba(255, 164, 67, 0.08);
  white-space: nowrap;
}
.topbar-brand h2 {
  margin: 0 0 6px;
  font-size: 34px;
  line-height: 1;
  font-family: Georgia, 'Times New Roman', serif;
}
.topbar-brand p {
  margin: 0;
  color: #cebfae;
  line-height: 1.6;
}
.topbar-nav {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.nav-btn {
  min-width: 148px;
  border-radius: 14px;
  border: 1px solid rgba(255, 212, 154, 0.15);
  background: rgba(255, 255, 255, 0.03);
  color: #f2e8dc;
  text-align: center;
  padding: 12px 18px;
}
.nav-btn.active {
  background: linear-gradient(135deg, rgba(255, 162, 72, 0.88), rgba(255, 118, 64, 0.92));
  color: #25120d;
  border-color: transparent;
  box-shadow: 0 14px 32px rgba(255, 120, 50, 0.16);
}
.position-main {
  display: flex;
  min-height: calc(100vh - 95px);
  align-items: center;
  justify-content: center;
  padding: 28px;
}
.coming-soon-panel {
  width: min(760px, 100%);
  padding: 42px;
  border-radius: 24px;
  border: 1px solid rgba(255, 223, 192, 0.12);
  background:
    linear-gradient(140deg, rgba(255, 248, 238, 0.07), rgba(255, 255, 255, 0.025)),
    radial-gradient(circle at top right, rgba(65, 208, 255, 0.1), transparent 34%);
  box-shadow: 0 18px 42px rgba(5, 6, 12, 0.26);
  text-align: center;
}
.panel-kicker {
  margin: 0 0 10px;
  color: #ffcb87;
  letter-spacing: 0.18em;
  font-size: 12px;
}
.coming-soon-panel h1 {
  margin: 0;
  font-size: clamp(32px, 4vw, 48px);
  line-height: 1.1;
  font-family: Georgia, 'Times New Roman', serif;
}
.panel-sub {
  max-width: 560px;
  margin: 16px auto 0;
  color: #d2c6ba;
  line-height: 1.8;
}
.panel-actions {
  margin-top: 26px;
}
.main-action {
  min-width: 168px;
  border: 0;
  background: linear-gradient(135deg, #ff9f4c, #ff6d45);
  box-shadow: 0 14px 28px rgba(255, 121, 68, 0.22);
}

@media (max-width: 1080px) {
  .position-topbar {
    flex-direction: column;
    align-items: stretch;
  }
  .topbar-brand {
    flex-direction: column;
    align-items: flex-start;
  }
  .topbar-nav {
    width: 100%;
  }
  .nav-btn {
    flex: 1 1 180px;
  }
}

@media (max-width: 640px) {
  .position-main {
    align-items: flex-start;
    padding: 20px;
  }
  .coming-soon-panel {
    padding: 28px 20px;
  }
}
</style>
