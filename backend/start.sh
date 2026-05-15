#!/bin/bash
source /home/hermes/seedance-env/bin/activate
cd "$(dirname "$0")"
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
exec python3 app.py "$@"
