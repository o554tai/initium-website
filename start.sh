#!/bin/bash
set -e
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
echo "[INITIUM] PORT=$PORT"
echo "[INITIUM] Starting gunicorn on 0.0.0.0:${PORT:-5000}"
exec gunicorn app:app --bind "0.0.0.0:${PORT:-5000}" --workers 2 --access-logfile - --error-logfile -
