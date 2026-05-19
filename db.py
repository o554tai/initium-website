#!/usr/bin/env python3
"""
INITIUM Ops Hub — Database layer
Uses PostgreSQL when DATABASE_URL is set, otherwise falls back to JSON files.
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path

# Try PostgreSQL
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PG = True
except ImportError:
    HAS_PG = False

DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG = HAS_PG and DATABASE_URL

# JSON fallback paths
LEADS_FILE = Path("leads.json")
BRIEFS_FILE = Path("briefs.json")

# ── PostgreSQL helpers ──

def _pg_conn():
    # Try sslmode=require first, fallback to default if that fails
    # (Supabase pooler sometimes needs different SSL handling)
    try:
        return psycopg2.connect(DATABASE_URL, sslmode="require")
    except psycopg2.OperationalError as e:
        err_str = str(e)
        if "sslmode" in err_str.lower() or "ssl" in err_str.lower() or "certificate" in err_str.lower():
            return psycopg2.connect(DATABASE_URL)
        raise


def _ensure_tables():
    if not USE_PG:
        return
    create_sql = """
    CREATE TABLE IF NOT EXISTS ops_leads (
        id TEXT PRIMARY KEY,
        client_name TEXT NOT NULL,
        contact TEXT,
        source TEXT,
        enquiry_type TEXT DEFAULT 'buy',
        status TEXT DEFAULT 'new',
        agent_name TEXT,
        budget TEXT,
        area TEXT,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE TABLE IF NOT EXISTS ops_briefs (
        id TEXT PRIMARY KEY,
        client_name TEXT NOT NULL,
        contact TEXT,
        property TEXT,
        area TEXT,
        viewing_date TEXT,
        agent_name TEXT,
        status TEXT DEFAULT 'active',
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    with _pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(create_sql)
        conn.commit()


def _row_to_dict(row):
    return dict(row) if row else None


# ── Leads ──

def load_leads(status=None, enquiry_type=None, agent=None):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                q = "SELECT * FROM ops_leads WHERE 1=1"
                params = []
                if status:
                    q += " AND status = %s"
                    params.append(status.lower())
                if enquiry_type:
                    q += " AND enquiry_type = %s"
                    params.append(enquiry_type.lower())
                if agent:
                    q += " AND LOWER(agent_name) LIKE %s"
                    params.append(f"%{agent.lower()}%")
                q += " ORDER BY created_at DESC"
                cur.execute(q, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    # JSON fallback
    if LEADS_FILE.exists():
        try:
            with open(LEADS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def save_lead(data: dict):
    data["id"] = data.get("id") or str(uuid.uuid4())[:8]
    data.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    data.setdefault("updated_at", datetime.utcnow().isoformat() + "Z")
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ops_leads (id, client_name, contact, source, enquiry_type, status, agent_name, budget, area, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        client_name = EXCLUDED.client_name,
                        contact = EXCLUDED.contact,
                        source = EXCLUDED.source,
                        enquiry_type = EXCLUDED.enquiry_type,
                        status = EXCLUDED.status,
                        agent_name = EXCLUDED.agent_name,
                        budget = EXCLUDED.budget,
                        area = EXCLUDED.area,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                """, (
                    data["id"], data.get("client_name", ""), data.get("contact", ""),
                    data.get("source", ""), data.get("enquiry_type", "buy"),
                    data.get("status", "new"), data.get("agent_name", ""),
                    data.get("budget", ""), data.get("area", ""), data.get("notes", ""),
                    data["created_at"], data["updated_at"]
                ))
            conn.commit()
        return data
    # JSON fallback
    leads = load_leads()
    for i, l in enumerate(leads):
        if l.get("id") == data["id"]:
            leads[i] = data
            break
    else:
        leads.insert(0, data)
    with open(LEADS_FILE, "w") as f:
        json.dump(leads, f, indent=2, default=str)
    return data


def get_lead(lead_id):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ops_leads WHERE id = %s", (lead_id,))
                return _row_to_dict(cur.fetchone())
    for l in load_leads():
        if l.get("id") == lead_id:
            return l
    return None


def update_lead(lead_id, data: dict):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                sets = []
                params = []
                for key in ["client_name", "contact", "source", "enquiry_type", "status", "agent_name", "budget", "area", "notes"]:
                    if key in data:
                        sets.append(f"{key} = %s")
                        params.append(str(data[key]).strip())
                if not sets:
                    return get_lead(lead_id)
                sets.append("updated_at = NOW()")
                q = f"UPDATE ops_leads SET {', '.join(sets)} WHERE id = %s"
                params.append(lead_id)
                cur.execute(q, params)
            conn.commit()
        return get_lead(lead_id)
    leads = load_leads()
    for l in leads:
        if l.get("id") == lead_id:
            for key in ["client_name", "contact", "source", "enquiry_type", "status", "agent_name", "budget", "area", "notes"]:
                if key in data:
                    l[key] = str(data[key]).strip()
            l["updated_at"] = datetime.utcnow().isoformat() + "Z"
            with open(LEADS_FILE, "w") as f:
                json.dump(leads, f, indent=2, default=str)
            return l
    return None


def delete_lead(lead_id):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ops_leads WHERE id = %s", (lead_id,))
            conn.commit()
        return True
    leads = load_leads()
    for i, l in enumerate(leads):
        if l.get("id") == lead_id:
            leads.pop(i)
            with open(LEADS_FILE, "w") as f:
                json.dump(leads, f, indent=2, default=str)
            return True
    return False


def lead_stats():
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT status, COUNT(*) AS cnt FROM ops_leads GROUP BY status")
                rows = cur.fetchall()
                total = sum(r["cnt"] for r in rows)
                return {"total": total, "by_status": {r["status"]: r["cnt"] for r in rows}}
    from collections import Counter
    leads = load_leads()
    c = Counter(l.get("status", "unknown") for l in leads)
    return {"total": len(leads), "by_status": dict(c)}


# ── Briefs ──

def load_briefs(status=None, agent=None):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                q = "SELECT * FROM ops_briefs WHERE 1=1"
                params = []
                if status:
                    q += " AND status = %s"
                    params.append(status.lower())
                if agent:
                    q += " AND LOWER(agent_name) LIKE %s"
                    params.append(f"%{agent.lower()}%")
                q += " ORDER BY created_at DESC"
                cur.execute(q, params)
                return [_row_to_dict(r) for r in cur.fetchall()]
    if BRIEFS_FILE.exists():
        try:
            with open(BRIEFS_FILE) as f:
                return json.load(f)
        except:
            return []
    return []


def save_brief(data: dict):
    data["id"] = data.get("id") or str(uuid.uuid4())[:8]
    data.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    data.setdefault("updated_at", datetime.utcnow().isoformat() + "Z")
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ops_briefs (id, client_name, contact, property, area, viewing_date, agent_name, status, notes, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        client_name = EXCLUDED.client_name,
                        contact = EXCLUDED.contact,
                        property = EXCLUDED.property,
                        area = EXCLUDED.area,
                        viewing_date = EXCLUDED.viewing_date,
                        agent_name = EXCLUDED.agent_name,
                        status = EXCLUDED.status,
                        notes = EXCLUDED.notes,
                        updated_at = NOW()
                """, (
                    data["id"], data.get("client_name", ""), data.get("contact", ""),
                    data.get("property", ""), data.get("area", ""), data.get("viewing_date", ""),
                    data.get("agent_name", ""), data.get("status", "active"), data.get("notes", ""),
                    data["created_at"], data["updated_at"]
                ))
            conn.commit()
        return data
    briefs = load_briefs()
    for i, b in enumerate(briefs):
        if b.get("id") == data["id"]:
            briefs[i] = data
            break
    else:
        briefs.insert(0, data)
    with open(BRIEFS_FILE, "w") as f:
        json.dump(briefs, f, indent=2, default=str)
    return data


def get_brief(brief_id):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM ops_briefs WHERE id = %s", (brief_id,))
                return _row_to_dict(cur.fetchone())
    for b in load_briefs():
        if b.get("id") == brief_id:
            return b
    return None


def update_brief(brief_id, data: dict):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                sets = []
                params = []
                for key in ["client_name", "contact", "property", "area", "viewing_date", "agent_name", "status", "notes"]:
                    if key in data:
                        sets.append(f"{key} = %s")
                        params.append(str(data[key]).strip())
                if not sets:
                    return get_brief(brief_id)
                sets.append("updated_at = NOW()")
                q = f"UPDATE ops_briefs SET {', '.join(sets)} WHERE id = %s"
                params.append(brief_id)
                cur.execute(q, params)
            conn.commit()
        return get_brief(brief_id)
    briefs = load_briefs()
    for b in briefs:
        if b.get("id") == brief_id:
            for key in ["client_name", "contact", "property", "area", "viewing_date", "agent_name", "status", "notes"]:
                if key in data:
                    b[key] = str(data[key]).strip()
            b["updated_at"] = datetime.utcnow().isoformat() + "Z"
            with open(BRIEFS_FILE, "w") as f:
                json.dump(briefs, f, indent=2, default=str)
            return b
    return None


def delete_brief(brief_id):
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM ops_briefs WHERE id = %s", (brief_id,))
            conn.commit()
        return True
    briefs = load_briefs()
    for i, b in enumerate(briefs):
        if b.get("id") == brief_id:
            briefs.pop(i)
            with open(BRIEFS_FILE, "w") as f:
                json.dump(briefs, f, indent=2, default=str)
            return True
    return False


def brief_stats():
    if USE_PG:
        _ensure_tables()
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT status, COUNT(*) AS cnt FROM ops_briefs GROUP BY status")
                rows = cur.fetchall()
                total = sum(r["cnt"] for r in rows)
                return {"total": total, "by_status": {r["status"]: r["cnt"] for r in rows}}
    from collections import Counter
    briefs = load_briefs()
    c = Counter(b.get("status", "unknown") for b in briefs)
    return {"total": len(briefs), "by_status": dict(c)}
