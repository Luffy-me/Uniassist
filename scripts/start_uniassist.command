#!/bin/zsh
# Double-click this file in Finder to start UniAssist FastAPI and Telegram.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
API_PID=""
BOT_PID=""

cleanup() {
  [[ -n "$BOT_PID" ]] && kill "$BOT_PID" 2>/dev/null || true
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

cd "$PROJECT_DIR"

if [[ ! -f .venv/bin/activate ]]; then
  echo "UniAssist virtual environment was not found at $PROJECT_DIR/.venv"
  read -r "?Press Return to close..."
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "UniAssist .env file was not found at $PROJECT_DIR/.env"
  read -r "?Press Return to close..."
  exit 1
fi

source .venv/bin/activate
TRACE_WAS_ENABLED=0
[[ $- == *x* ]] && TRACE_WAS_ENABLED=1
set +x
set -a
source .env
set +a
(( TRACE_WAS_ENABLED )) && set -x
mkdir -p "$LOG_DIR"

echo "Starting UniAssist FastAPI…"
uvicorn uniassist.api.app:create_app --factory --host 127.0.0.1 --port 8001 \
  >"$LOG_DIR/fastapi.log" 2>&1 &
API_PID=$!

echo "Waiting for FastAPI to load the document index (this can take up to 4 minutes)…"
for attempt in {1..240}; do
  if curl --silent --fail http://127.0.0.1:8001/health >/dev/null; then
    break
  fi
  if (( attempt % 30 == 0 )); then
    echo "Still loading the document index…"
  fi
  sleep 1
done

if ! curl --silent --fail http://127.0.0.1:8001/health >/dev/null; then
  echo "FastAPI did not start. See $LOG_DIR/fastapi.log"
  exit 1
fi

echo "Starting Telegram bot…"
python -m uniassist.telegram.bot >"$LOG_DIR/telegram.log" 2>&1 &
BOT_PID=$!

echo ""
echo "UniAssist is running."
echo "FastAPI:  http://127.0.0.1:8001/health"
echo "Logs:     $LOG_DIR"
echo ""
echo "Keep this Terminal window open. Press Ctrl+C to stop both services."

wait "$API_PID" "$BOT_PID"
