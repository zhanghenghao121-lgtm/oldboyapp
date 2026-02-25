#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/root/.openclaw/workspace/oldboyapp"
DEPLOY_DIR="$PROJECT_DIR/deploy"

cd "$DEPLOY_DIR"
if [[ ! -f env.prod ]]; then
  echo "env.prod not found. Please create from env.prod.example first." >&2
  exit 2
fi

docker compose --env-file env.prod up -d --build

docker compose --env-file env.prod exec -T backend python manage.py migrate

curl -fsS https://www.oldboyai.com/api/v1/healthz > /tmp/oldboyapp_healthz.json
curl -fsS https://www.oldboyai.com/api/v1/script-optimizer/ping > /tmp/oldboyapp_script_optimizer_ping.json

echo "Deploy success"
