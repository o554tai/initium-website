#!/usr/bin/env python3
"""
INITIUM Ops Hub — Database layer
Uses Supabase REST API when SUPABASE_URL + SUPABASE_SERVICE_KEY are set.
Falls back to local JSON files if env vars are missing.

This bypasses all IPv6 / pooler / psycopg2 connection issues entirely.
"""
import os
import json
import uuid
import requests
from datetime import datetime
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────────
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or ""
USE_REST = bool(SUPABASE_URL and SUPABASE_KEY)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# ── JSON fallback paths ─────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
LEADS_JSON = BASE_DIR / "leads.json"
BRIEFS_JSON = BASE_DIR / "briefs.json"
AGENT_TOKENS_JSON = BASE_DIR / "agent_tokens.json"


def _load_json(path):
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── REST helpers ────────────────────────────────────────────────────────────
def _rest_get(table, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.get(url, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _rest_post(table, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, headers=HEADERS, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _rest_patch(table, row_id, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    r = requests.patch(url, headers=HEADERS, json=payload, timeout=20)
    r.raise_for_status()
    return r.json()


def _rest_delete(table, row_id):
    url = f"{SUPABASE_URL}/rest/v1/{table}?id=eq.{row_id}"
    r = requests.delete(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return True


# ═════════════════════════════════════════════════════════════════════════════
#  LEADS
# ═════════════════════════════════════════════════════════════════════════════

def save_lead(data: dict) -> str:
    lead_id = data.get("id") or str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    payload = {
        "id": lead_id,
        "client_name": data.get("client_name", ""),
        "contact": data.get("contact", ""),
        "source": data.get("source", ""),
        "enquiry_type": data.get("enquiry_type", ""),
        "status": data.get("status", "new"),
        "budget": data.get("budget", ""),
        "area": data.get("area", ""),
        "project_name": data.get("project_name", ""),
        "property_address": data.get("property_address", ""),
        "agent_name": data.get("agent_name", ""),
        "notes": data.get("notes", ""),
        "created_at": data.get("created_at") or now,
        "updated_at": now,
    }

    if USE_REST:
        try:
            _rest_post("ops_leads", payload)
            return lead_id
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                _rest_patch("ops_leads", lead_id, payload)
                return lead_id
            raise
    else:
        leads = _load_json(LEADS_JSON)
        leads.append(payload)
        _save_json(LEADS_JSON, leads)
        return lead_id


def load_leads() -> list:
    if USE_REST:
        try:
            return _rest_get("ops_leads", {"select": "*", "order": "created_at.desc"})
        except Exception:
            return []
    else:
        return _load_json(LEADS_JSON)


def get_lead(lead_id: str) -> dict | None:
    if USE_REST:
        try:
            rows = _rest_get("ops_leads", {"id": f"eq.{lead_id}"})
            return rows[0] if rows else None
        except Exception:
            return None
    else:
        for l in _load_json(LEADS_JSON):
            if l.get("id") == lead_id:
                return l
        return None


def update_lead(lead_id: str, data: dict) -> bool:
    now = datetime.utcnow().isoformat()
    payload = {k: v for k, v in data.items() if k != "id"}
    payload["updated_at"] = now

    if USE_REST:
        _rest_patch("ops_leads", lead_id, payload)
        return True
    else:
        leads = _load_json(LEADS_JSON)
        for i, l in enumerate(leads):
            if l.get("id") == lead_id:
                leads[i].update(payload)
                _save_json(LEADS_JSON, leads)
                return True
        return False


def delete_lead(lead_id: str) -> bool:
    if USE_REST:
        _rest_delete("ops_leads", lead_id)
        return True
    else:
        leads = _load_json(LEADS_JSON)
        leads = [l for l in leads if l.get("id") != lead_id]
        _save_json(LEADS_JSON, leads)
        return True


def lead_stats() -> dict:
    leads = load_leads()
    statuses = {}
    for l in leads:
        s = l.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
    return {"total": len(leads), "by_status": statuses}


# ═════════════════════════════════════════════════════════════════════════════
#  BRIEFS
# ═════════════════════════════════════════════════════════════════════════════

def save_brief(data: dict) -> str:
    brief_id = data.get("id") or str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    payload = {
        "id": brief_id,
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "client_name": data.get("client_name", ""),
        "property_address": data.get("property_address", ""),
        "status": data.get("status", "draft"),
        "agent_name": data.get("agent_name", ""),
        "created_at": data.get("created_at") or now,
        "updated_at": now,
    }

    if USE_REST:
        try:
            _rest_post("ops_briefs", payload)
            return brief_id
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                _rest_patch("ops_briefs", brief_id, payload)
                return brief_id
            raise
    else:
        briefs = _load_json(BRIEFS_JSON)
        briefs.append(payload)
        _save_json(BRIEFS_JSON, briefs)
        return brief_id


def load_briefs() -> list:
    if USE_REST:
        try:
            return _rest_get("ops_briefs", {"select": "*", "order": "created_at.desc"})
        except Exception:
            return []
    else:
        return _load_json(BRIEFS_JSON)


def get_brief(brief_id: str) -> dict | None:
    if USE_REST:
        try:
            rows = _rest_get("ops_briefs", {"id": f"eq.{brief_id}"})
            return rows[0] if rows else None
        except Exception:
            return None
    else:
        for b in _load_json(BRIEFS_JSON):
            if b.get("id") == brief_id:
                return b
        return None


def update_brief(brief_id: str, data: dict) -> bool:
    now = datetime.utcnow().isoformat()
    payload = {k: v for k, v in data.items() if k != "id"}
    payload["updated_at"] = now

    if USE_REST:
        _rest_patch("ops_briefs", brief_id, payload)
        return True
    else:
        briefs = _load_json(BRIEFS_JSON)
        for i, b in enumerate(briefs):
            if b.get("id") == brief_id:
                briefs[i].update(payload)
                _save_json(BRIEFS_JSON, briefs)
                return True
        return False


def delete_brief(brief_id: str) -> bool:
    if USE_REST:
        _rest_delete("ops_briefs", brief_id)
        return True
    else:
        briefs = _load_json(BRIEFS_JSON)
        briefs = [b for b in briefs if b.get("id") != brief_id]
        _save_json(BRIEFS_JSON, briefs)
        return True


def brief_stats() -> dict:
    briefs = load_briefs()
    return {"total": len(briefs)}


# ═════════════════════════════════════════════════════════════════════════════
#  INTEL
# ═════════════════════════════════════════════════════════════════════════════

INTEL_JSON = BASE_DIR / "intel.json"


def save_intel(data: dict) -> str:
    intel_id = data.get("id") or str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    payload = {
        "id": intel_id,
        "title": data.get("title", ""),
        "body": data.get("body", ""),
        "tag": data.get("tag", "market"),
        "tag_label": data.get("tag_label", "Market"),
        "date": data.get("date", ""),
        "source_url": data.get("source_url", ""),
        "agent_name": data.get("agent_name", ""),
        "created_at": data.get("created_at") or now,
        "updated_at": now,
    }

    if USE_REST:
        try:
            _rest_post("ops_intel", payload)
            return intel_id
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                _rest_patch("ops_intel", intel_id, payload)
                return intel_id
            raise
    else:
        intel = _load_json(INTEL_JSON)
        intel.append(payload)
        _save_json(INTEL_JSON, intel)
        return intel_id


def load_intel() -> list:
    if USE_REST:
        try:
            return _rest_get("ops_intel", {"select": "*", "order": "date.desc"})
        except Exception:
            return []
    else:
        return _load_json(INTEL_JSON)


def get_intel(intel_id: str) -> dict | None:
    if USE_REST:
        try:
            rows = _rest_get("ops_intel", {"id": f"eq.{intel_id}"})
            return rows[0] if rows else None
        except Exception:
            return None
    else:
        for item in _load_json(INTEL_JSON):
            if item.get("id") == intel_id:
                return item
        return None


def update_intel(intel_id: str, data: dict) -> bool:
    now = datetime.utcnow().isoformat()
    payload = {k: v for k, v in data.items() if k != "id"}
    payload["updated_at"] = now

    if USE_REST:
        _rest_patch("ops_intel", intel_id, payload)
        return True
    else:
        intel = _load_json(INTEL_JSON)
        for i, item in enumerate(intel):
            if item.get("id") == intel_id:
                intel[i].update(payload)
                _save_json(INTEL_JSON, intel)
                return True
        return False


def delete_intel(intel_id: str) -> bool:
    if USE_REST:
        _rest_delete("ops_intel", intel_id)
        return True
    else:
        intel = _load_json(INTEL_JSON)
        intel = [item for item in intel if item.get("id") != intel_id]
        _save_json(INTEL_JSON, intel)
        return True


def intel_stats() -> dict:
    intel = load_intel()
    return {"total": len(intel)}


# ═════════════════════════════════════════════════════════════════════════════
#  Health check
# ═════════════════════════════════════════════════════════════════════════════

def db_status() -> dict:
    if not USE_REST:
        return {"mode": "json", "connected": True, "message": "Using JSON fallback"}
    try:
        _rest_get("ops_leads", {"select": "id", "limit": 1})
        return {"mode": "supabase_rest", "connected": True, "url": SUPABASE_URL}
    except Exception as e:
        return {"mode": "supabase_rest", "connected": False, "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
#  Agent Meta Token (per-agent Instagram OAuth)
# ═════════════════════════════════════════════════════════════════════════════

def save_agent_meta_token(data: dict) -> str:
    agent_name = data.get("agent_name", "").strip()
    if not agent_name:
        raise ValueError("agent_name is required")
    now = datetime.utcnow().isoformat()
    tokens = _load_json(AGENT_TOKENS_JSON)
    existing = [t for t in tokens if t.get("agent_name") != agent_name]
    payload = {
        "agent_name": agent_name,
        "access_token": data.get("access_token", ""),
        "ig_business_account_id": data.get("ig_business_account_id", ""),
        "page_id": data.get("page_id", ""),
        "page_name": data.get("page_name", ""),
        "connected_at": now,
        "updated_at": now,
    }
    existing.append(payload)
    _save_json(AGENT_TOKENS_JSON, existing)
    return agent_name


def get_agent_meta_token(agent_name: str) -> dict | None:
    tokens = _load_json(AGENT_TOKENS_JSON)
    for t in tokens:
        if t.get("agent_name", "").lower() == agent_name.lower():
            return t
    return None


def delete_agent_meta_token(agent_name: str) -> bool:
    tokens = _load_json(AGENT_TOKENS_JSON)
    filtered = [t for t in tokens if t.get("agent_name", "").lower() != agent_name.lower()]
    if len(filtered) == len(tokens):
        return False
    _save_json(AGENT_TOKENS_JSON, filtered)
    return True
