#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "$PROJECT_ROOT"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
else
  echo ".env not found. Copy .env.example to .env and configure it first."
  exit 1
fi

HOST="${AGENT_SERVICE_HOST:-0.0.0.0}"
PORT="${AGENT_SERVICE_PORT:-8891}"
PID_FILE="${PID_FILE:-$PROJECT_ROOT/logs/backend.pid}"

mkdir -p "$PROJECT_ROOT/logs"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Backend is already running with PID $(cat "$PID_FILE")."
  exit 0
fi

echo "Starting backend on ${HOST}:${PORT}"
nohup uvicorn backend.app.main:app --host "$HOST" --port "$PORT" > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
echo $! > "$PID_FILE"
echo "Backend PID: $(cat "$PID_FILE")"
echo "Logs: $PROJECT_ROOT/logs/backend.log"
