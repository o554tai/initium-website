#!/bin/bash
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
exec gunicorn app:app --bind 0.0.0.0:${PORT:-5000} --workers 2
