#!/usr/bin/env bash
# Production deploy: pull -> build -> up (entrypoint migrates+seeds) -> pregen -> smoke.
# Runs ON the server from $APP_DIR (default /opt/speakfill). Requires: git, docker, .env.
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/speakfill}"
cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "missing $APP_DIR/.env (copy .env.example and fill DOMAIN, APP_BASE_URL, keys)" >&2
  exit 1
fi

echo "==> pulling"
git pull --ff-only

echo "==> building + starting"
docker compose up --build -d

echo "==> waiting for api"
for _ in $(seq 1 30); do
  if docker compose exec -T api python -c "import urllib.request,json;print(json.load(urllib.request.urlopen('http://localhost:8000/api/healthz'))['ok'])" 2>/dev/null | grep -q true; then
    break
  fi
  sleep 2
done

echo "==> pre-generating voice prompts (cache misses only)"
docker compose exec -T api python -m scripts.pregen_prompts | tail -1

echo "==> smoke test"
APP_BASE_URL="$(grep -E '^APP_BASE_URL=' .env | cut -d= -f2-)"
python3 scripts/smoke.py "$APP_BASE_URL"

echo "DEPLOY OK: $APP_BASE_URL"
