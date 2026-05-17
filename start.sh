#!/bin/bash
set -e
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
export PORT="${PORT:-5000}"
echo "[INITIUM] PORT=$PORT"
echo "[INITIUM] Starting test app on 0.0.0.0:$PORT"
python3 test_app.py
