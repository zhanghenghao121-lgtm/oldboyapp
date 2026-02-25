#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/root/.openclaw/workspace/oldboyapp"
DEPLOY_DIR="$PROJECT_DIR/deploy"

cd "$DEPLOY_DIR"

echo "## docker compose ps"
docker compose --env-file env.prod ps || true

echo
 echo "## backend logs"
docker compose --env-file env.prod logs --tail=300 backend || true

echo
 echo "## nginx logs"
docker compose --env-file env.prod logs --tail=300 nginx || true
