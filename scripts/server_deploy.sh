#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/root/.openclaw/workspace/oldboyapp"
DEPLOY_DIR="$PROJECT_DIR/deploy"
COMPOSE_ENV=(DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0)

cd "$DEPLOY_DIR"
if [[ ! -f env.prod ]]; then
  echo "env.prod not found. Please create from env.prod.example first." >&2
  exit 2
fi

pull_with_retry() {
  local image="$1"
  local ok=0
  for i in {1..5}; do
    if docker pull "$image"; then
      ok=1
      break
    fi
    echo "docker pull $image retry ${i}/5 failed, waiting..."
    sleep 8
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "docker pull failed for $image, continue and try local cache/build" >&2
  fi
}

# Warm critical base images to reduce failures from flaky registry metadata lookups.
pull_with_retry "python:3.12-slim"
pull_with_retry "node:20-alpine"
pull_with_retry "nginx:1.27-alpine"

# Deploy core services first to keep CI stable even when optional OCR image cannot be pulled.
env "${COMPOSE_ENV[@]}" docker compose --env-file env.prod up -d --build mariadb redis backend celery-worker frontend nginx

# Optional OCR service:
# Start only when image already exists locally to avoid Docker Hub timeout blocking deploy.
if docker image inspect andrlange/paddleocr:2.8.0 >/dev/null 2>&1; then
  env "${COMPOSE_ENV[@]}" docker compose --env-file env.prod --profile ocr up -d ocr || true
else
  echo "OCR image not found locally, skip ocr startup"
fi

docker compose --env-file env.prod exec -T backend python manage.py migrate

health_check() {
  local path="$1"
  local out_file="$2"

  # Prefer local loopback checks to avoid public DNS/network flakiness in CI.
  curl -fsS -m 5 "http://127.0.0.1${path}" -H "Host: oldboyai.com" > "${out_file}" \
    || curl -kfsS -m 5 "https://127.0.0.1${path}" -H "Host: oldboyai.com" > "${out_file}"
}

ok=0
for i in {1..20}; do
  if health_check "/api/v1/healthz" "/tmp/oldboyapp_healthz.json"; then
    ok=1
    break
  fi
  sleep 3
done

if [[ "$ok" -ne 1 ]]; then
  echo "healthz check failed after retries" >&2
  exit 22
fi

echo "Deploy success"
