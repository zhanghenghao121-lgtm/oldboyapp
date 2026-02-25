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

ok=0
for i in {1..20}; do
  if curl -fsS https://www.oldboyai.com/api/v1/healthz > /tmp/oldboyapp_healthz.json; then
    ok=1
    break
  fi
  sleep 3
done

if [[ "$ok" -ne 1 ]]; then
  echo "healthz check failed after retries" >&2
  exit 22
fi

ok=0
for i in {1..20}; do
  if curl -fsS https://www.oldboyai.com/api/v1/script-optimizer/ping > /tmp/oldboyapp_script_optimizer_ping.json; then
    ok=1
    break
  fi
  sleep 3
done

if [[ "$ok" -ne 1 ]]; then
  echo "script-optimizer ping failed after retries" >&2
  exit 23
fi

echo "Deploy success"
