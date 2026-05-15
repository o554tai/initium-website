#!/bin/bash
export INITIUM_ADMIN_KEY="${INITIUM_ADMIN_KEY:-}"
exec gunicorn app:app
