#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PID_FILE="${PID_FILE:-$PROJECT_ROOT/logs/backend.pid}"

if [ ! -f "$PID_FILE" ]; then
  echo "PID file not found: $PID_FILE"
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  echo "Stopping backend PID $PID"
  kill "$PID"
else
  echo "Backend process $PID is not running."
fi

rm -f "$PID_FILE"
