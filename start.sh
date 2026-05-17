#!/bin/bash
set -e
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
export PORT="${PORT:-5000}"
echo "[INITIUM] PORT=$PORT"
echo "[INITIUM] Starting gunicorn on 0.0.0.0:$PORT"
exec gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --access-logfile - --error-logfile -
