#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_ROOT"

echo "== Runtime =="
python --version
pip --version
git --version

echo "== .env =="
if [ -f ".env" ]; then
  echo ".env exists"
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
else
  echo ".env is missing. Copy .env.example to .env."
  exit 1
fi

echo "== Required Variables =="
for name in APP_NAME APP_ENV AGENT_SERVICE_HOST AGENT_SERVICE_PORT REDIS_HOST REDIS_PORT WORKSPACE_BACKEND WORKSPACE_BASEDIR; do
  if [ -z "${!name:-}" ]; then
    echo "Missing required variable: $name"
    exit 1
  fi
  echo "$name=${!name}"
done

echo "Backend will bind to ${AGENT_SERVICE_HOST}:${AGENT_SERVICE_PORT}"

echo "== Redis =="
if command -v redis-cli >/dev/null 2>&1; then
  redis-cli -h "${REDIS_HOST:-127.0.0.1}" -p "${REDIS_PORT:-6379}" ping
else
  python - <<'PY'
import os
import socket

host = os.getenv("REDIS_HOST", "127.0.0.1")
port = int(os.getenv("REDIS_PORT", "6379"))
with socket.create_connection((host, port), timeout=3):
    print(f"Redis TCP connection ok: {host}:{port}")
PY
fi

echo "Environment check passed."
