# OldboyApp Auth MVP

实现内容：
- 注册（用户名/邮箱唯一、密码强度、邮箱验证码）
- 登录（图形验证码 + Session）
- 忘记密码（邮箱验证码 + 新密码规则）
- 当前用户信息、退出登录
- 文件上传到 COS（登录后）

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
