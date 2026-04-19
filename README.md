# OldboyApp

当前保留模块：
- 注册、登录、忘记密码、用户信息、退出登录
- 文件上传到 COS
- AI 客服
- 管理后台

## 本地启动

### 后端
```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### 前端
```bash
cd frontend
npm i
npm run dev
```

## 部署（Docker）
```bash
cd deploy
cp env.prod.example env.prod
# 修改 env.prod 密钥
docker compose --env-file env.prod up -d --build
```

## 管理后台
- 访问路径：`/admin/login`（例如 `https://oldboyai.com/admin/login`）
- 初始账号：`root`
- 初始密码：`zhang2000`
- 功能：
  - 登录页、首页背景图管理
  - 注册用户信息管理（用户名、邮箱、状态）
