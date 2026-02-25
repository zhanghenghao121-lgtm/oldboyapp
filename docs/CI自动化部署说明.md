# CI 自动化部署说明

## 已实现
- push 到 `main` 后自动部署服务器
- 部署失败自动收集服务器日志并创建 GitHub Issue（标签：`deploy-failed`）

## 你只需要做一次的配置
在 GitHub 仓库 `Settings -> Secrets and variables -> Actions` 添加：
- `SERVER_HOST`：服务器公网 IP 或域名
- `SERVER_PORT`：SSH 端口（默认 22）
- `SERVER_USER`：SSH 用户（例如 `root`）
- `SERVER_SSH_KEY`：私钥内容（建议单独部署密钥）

## 服务器前置条件
- 项目路径固定为：`/root/.openclaw/workspace/oldboyapp`
- `deploy/env.prod` 已存在且填入真实密钥
- 服务器可执行：`docker compose`

## 自动部署执行内容
由脚本 `scripts/server_deploy.sh` 执行：
1. `git pull --ff-only origin main`
2. `docker compose --env-file env.prod up -d --build`
3. `docker compose --env-file env.prod exec -T backend python manage.py migrate`
4. 健康检查：
   - `https://www.oldboyai.com/api/v1/healthz`
   - `https://www.oldboyai.com/api/v1/script-optimizer/ping`

## 失败时自动回传内容
由工作流在服务器执行并收集：
- `docker compose ps`
- backend 日志（300 行）
- nginx 日志（300 行）
