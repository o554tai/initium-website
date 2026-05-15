#!/usr/bin/env python3
"""
Simple API key auth for INITIUM video generation backend.
Admin creates keys. Team members use keys to access /api/* endpoints.
"""

import json
import secrets
import os
from datetime import datetime
from functools import wraps
from flask import request, jsonify

KEYS_FILE = os.path.join(os.path.dirname(__file__), "keys.json")
ADMIN_KEY_ENV = "INITIUM_ADMIN_KEY"

# Default admin key from env or a random one (printed on first run)
ADMIN_KEY = os.environ.get(ADMIN_KEY_ENV)


def _load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE) as f:
            return json.load(f)
    return {"keys": {}, "created_at": datetime.utcnow().isoformat()}


def _save_keys(data):
    with open(KEYS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def init_admin_key():
    """Ensure admin key exists. Print it on first run."""
    global ADMIN_KEY
    data = _load_keys()
    stored = data.get("admin_key")

    if ADMIN_KEY:
        # Env overrides everything
        if stored != ADMIN_KEY:
            data["admin_key"] = ADMIN_KEY
            _save_keys(data)
        return ADMIN_KEY

    if stored:
        ADMIN_KEY = stored
        return ADMIN_KEY

    # Generate fresh admin key
    ADMIN_KEY = "initium-admin-" + secrets.token_urlsafe(24)
    data["admin_key"] = ADMIN_KEY
    _save_keys(data)
    print(f"\n{'='*60}")
    print("INITIUM ADMIN KEY GENERATED")
    print(f"Key: {ADMIN_KEY}")
    print(f"Store this in your .env or export {ADMIN_KEY_ENV}=...")
    print(f"{'='*60}\n")
    return ADMIN_KEY


def create_team_key(name: str, created_by: str = "admin") -> dict:
    """Create a new team member API key."""
    data = _load_keys()
    key = "initium-" + secrets.token_urlsafe(24)
    entry = {
        "name": name,
        "key": key,
        "active": True,
        "created_by": created_by,
        "created_at": datetime.utcnow().isoformat(),
        "usage_count": 0,
        "last_used": None,
    }
    data["keys"][key] = entry
    _save_keys(data)
    return entry


def revoke_team_key(key: str) -> bool:
    """Revoke a team key."""
    data = _load_keys()
    if key in data["keys"]:
        data["keys"][key]["active"] = False
        _save_keys(data)
        return True
    return False


def delete_team_key(key: str) -> bool:
    """Permanently delete a team key."""
    data = _load_keys()
    if key in data["keys"]:
        del data["keys"][key]
        _save_keys(data)
        return True
    return False


def list_team_keys() -> list:
    """Return all team keys (for admin)."""
    data = _load_keys()
    return list(data["keys"].values())


def validate_key(key: str) -> dict:
    """Validate a team API key. Returns key entry or None."""
    if not key:
        return None
    data = _load_keys()
    entry = data["keys"].get(key)
    if entry and entry.get("active"):
        return entry
    return None


def record_usage(key: str):
    """Increment usage counter for a key."""
    data = _load_keys()
    if key in data["keys"]:
        data["keys"][key]["usage_count"] += 1
        data["keys"][key]["last_used"] = datetime.utcnow().isoformat()
        _save_keys(data)


# ── Flask decorators ──

def require_api_key(f):
    """Decorator: require valid team API key in X-API-Key header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "").strip()
        entry = validate_key(key)
        if not entry:
            return jsonify({"error": "Invalid or missing API key"}), 401
        request.api_key_entry = entry
        return f(*args, **kwargs)
    return decorated


def require_admin_key(f):
    """Decorator: require admin key in X-Admin-Key header."""
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-Admin-Key", "").strip()
        if key != ADMIN_KEY:
            return jsonify({"error": "Invalid or missing admin key"}), 403
        return f(*args, **kwargs)
    return decorated
