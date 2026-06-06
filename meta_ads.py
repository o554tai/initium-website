#!/usr/bin/env python3
"""
Meta Marketing API wrapper for INITIUM Ad Launch.
Handles OAuth, campaign creation, creative upload, and insights.
"""

import os
import json
import base64
import requests
import urllib.parse
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# ── Config ──────────────────────────────────────────────────────────────────
META_APP_ID = os.environ.get("META_APP_ID", "").strip()
META_APP_SECRET = os.environ.get("META_APP_SECRET", "").strip()
META_API_VERSION = os.environ.get("META_API_VERSION", "v25.0")
META_REDIRECT_URI = os.environ.get("META_REDIRECT_URI", "").strip()

GRAPH_BASE = f"https://graph.facebook.com/{META_API_VERSION}"


def _get_fernet():
    """Derive a Fernet key from the admin key so we don't need a separate secret."""
    from auth import ADMIN_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"initium-meta-ads-v1",
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(ADMIN_KEY.encode()))
    return Fernet(key)


def encrypt_token(token: str) -> str:
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()


# ── OAuth ────────────────────────────────────────────────────────────────────

def get_oauth_url(state: str) -> str:
    if not META_APP_ID or not META_REDIRECT_URI:
        raise RuntimeError("META_APP_ID and META_REDIRECT_URI must be set")
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": META_REDIRECT_URI,
        "state": state,
        "scope": "ads_management,ads_read,business_management",
        "response_type": "code",
    }
    return f"https://www.facebook.com/{META_API_VERSION}/dialog/oauth?{urllib.parse.urlencode(params)}"


def exchange_code(code: str) -> dict:
    if not META_APP_ID or not META_APP_SECRET or not META_REDIRECT_URI:
        raise RuntimeError("META_APP_ID, META_APP_SECRET and META_REDIRECT_URI must be set")
    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "redirect_uri": META_REDIRECT_URI,
        "code": code,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def refresh_token(refresh_token_str: str) -> dict:
    url = f"{GRAPH_BASE}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": META_APP_ID,
        "client_secret": META_APP_SECRET,
        "fb_exchange_token": refresh_token_str,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Ad Accounts ─────────────────────────────────────────────────────────

def get_ad_accounts(access_token: str) -> list:
    url = f"{GRAPH_BASE}/me/adaccounts"
    params = {
        "access_token": access_token,
        "fields": "name,account_id,id,business_name,currency,timezone_name",
        "limit": 100,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("data", [])


def get_ad_accounts_with_tier(access_token: str) -> dict:
    """Fetch ad accounts + try a harmless write probe to detect Limited vs Standard tier."""
    accounts = get_ad_accounts(access_token)
    tier = "unknown"
    if accounts:
        # Probe: try to create a dummy campaign (it will fail for Limited tier with a specific error)
        acct_id = accounts[0]["account_id"]
        probe = _probe_write_access(access_token, acct_id)
        tier = probe.get("tier", "unknown")
    return {"accounts": accounts, "tier": tier}


def _probe_write_access(access_token: str, ad_account_id: str) -> dict:
    """Attempt a campaign creation that we immediately delete. Used to detect access tier."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/campaigns"
    payload = {
        "name": "INITIUM_TIER_PROBE_DELETE_ME",
        "objective": "OUTCOME_LEADS",
        "status": "PAUSED",
        "access_token": access_token,
        "special_ad_categories": [],
    }
    try:
        r = requests.post(url, json=payload, timeout=30)
        data = r.json()
        if r.status_code == 200 and data.get("id"):
            # Delete the probe campaign
            try:
                requests.delete(f"{GRAPH_BASE}/{data['id']}?access_token={access_token}", timeout=30)
            except Exception:
                pass
            return {"tier": "standard", "writable": True}
        error = data.get("error", {})
        code = error.get("code", 0)
        subcode = error.get("error_subcode", 0)
        msg = error.get("message", "").lower()
        if code == 200 or "permission" in msg or "authorization" in msg or "access" in msg:
            return {"tier": "limited", "writable": False, "error": error.get("message", "")}
        return {"tier": "unknown", "writable": False, "error": error.get("message", "")}
    except Exception as e:
        return {"tier": "unknown", "writable": False, "error": str(e)}


def list_campaigns(access_token: str, ad_account_id: str, limit: int = 50) -> list:
    url = f"{GRAPH_BASE}/act_{ad_account_id}/campaigns"
    params = {
        "access_token": access_token,
        "fields": "id,name,objective,status,daily_budget,budget_remaining,created_time",
        "limit": limit,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


# ── Campaigns ────────────────────────────────────────────────────────────────

def create_campaign(access_token: str, ad_account_id: str, name: str, objective: str = "OUTCOME_LEADS", daily_budget: int = None, status: str = "PAUSED") -> dict:
    """Create a Meta campaign. Returns campaign object."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/campaigns"
    payload = {
        "name": name,
        "objective": objective,
        "status": status,
        "access_token": access_token,
        "special_ad_categories": [],
    }
    if daily_budget is not None:
        payload["daily_budget"] = int(daily_budget)  # in cents
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def update_campaign_status(access_token: str, campaign_id: str, status: str) -> dict:
    url = f"{GRAPH_BASE}/{campaign_id}"
    payload = {
        "status": status,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Ad Sets ──────────────────────────────────────────────────────────────────

def create_ad_set(
    access_token: str,
    ad_account_id: str,
    campaign_id: str,
    name: str,
    daily_budget: int,
    targeting: dict,
    optimization_goal: str = "LEAD_GENERATION",
    billing_event: str = "IMPRESSIONS",
    status: str = "PAUSED",
) -> dict:
    url = f"{GRAPH_BASE}/act_{ad_account_id}/adsets"
    payload = {
        "name": name,
        "campaign_id": campaign_id,
        "daily_budget": daily_budget,
        "billing_event": billing_event,
        "optimization_goal": optimization_goal,
        "targeting": targeting,
        "status": status,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def build_property_targeting(
    geo_locations: list = None,
    age_min: int = 35,
    age_max: int = 55,
    genders: list = None,
    interests: list = None,
    custom_audiences: list = None,
) -> dict:
    """Build a Meta targeting spec for Singapore property ads."""
    targeting = {
        "geo_locations": {
            "countries": ["SG"],
            "location_types": ["home", "recent"],
        },
        "age_min": age_min,
        "age_max": age_max,
        "publisher_platforms": ["facebook", "instagram"],
        "facebook_positions": ["feed", "marketplace"],
        "instagram_positions": ["stream", "story", "reels"],
    }
    if genders:
        targeting["genders"] = genders
    if interests:
        targeting["interests"] = [{"id": i} if isinstance(i, str) and i.isdigit() else {"name": i} for i in interests]
    if custom_audiences:
        targeting["custom_audiences"] = [{"id": ca} for ca in custom_audiences]
    return targeting


# ── Creatives ────────────────────────────────────────────────────────────────

def upload_image(access_token: str, ad_account_id: str, image_path: str) -> dict:
    """Upload an image to Meta ad library. Returns {hash, url}."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/adimages"
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {"access_token": access_token}
        r = requests.post(url, files=files, data=data, timeout=60)
    r.raise_for_status()
    result = r.json()
    images = result.get("images", {})
    # Return first image hash
    for name, info in images.items():
        return {"hash": info.get("hash"), "url": info.get("url")}
    return result


def upload_image_from_url(access_token: str, ad_account_id: str, image_url: str) -> dict:
    """Upload an image to Meta ad library from a public URL."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/adimages"
    payload = {
        "url": image_url,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    result = r.json()
    images = result.get("images", {})
    for name, info in images.items():
        return {"hash": info.get("hash"), "url": info.get("url")}
    return result


def create_ad_creative(
    access_token: str,
    ad_account_id: str,
    name: str,
    image_hash: str,
    headline: str,
    body: str,
    call_to_action: str = "WHATSAPP_MESSAGE",
    link: str = "https://wa.me/",
    page_id: str = None,
) -> dict:
    """Create a single image ad creative."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/adcreatives"
    object_story_spec = {
        "page_id": page_id,
        "link_data": {
            "image_hash": image_hash,
            "message": body,
            "headline": headline,
            "call_to_action": {"type": call_to_action},
            "link": link,
        }
    }
    payload = {
        "name": name,
        "object_story_spec": object_story_spec,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def create_ad_creative_video(
    access_token: str,
    ad_account_id: str,
    name: str,
    video_id: str,
    headline: str,
    body: str,
    call_to_action: str = "WHATSAPP_MESSAGE",
    link: str = "https://wa.me/",
    page_id: str = None,
    thumbnail_url: str = None,
) -> dict:
    """Create a video ad creative."""
    url = f"{GRAPH_BASE}/act_{ad_account_id}/adcreatives"
    object_story_spec = {
        "page_id": page_id,
        "video_data": {
            "video_id": video_id,
            "message": body,
            "headline": headline,
            "call_to_action": {"type": call_to_action},
            "link": link,
        }
    }
    if thumbnail_url:
        object_story_spec["video_data"]["image_url"] = thumbnail_url
    payload = {
        "name": name,
        "object_story_spec": object_story_spec,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Ads ──────────────────────────────────────────────────────────────────────

def create_ad(
    access_token: str,
    ad_account_id: str,
    ad_set_id: str,
    creative_id: str,
    name: str,
    status: str = "PAUSED",
) -> dict:
    url = f"{GRAPH_BASE}/act_{ad_account_id}/ads"
    payload = {
        "name": name,
        "adset_id": ad_set_id,
        "creative": {"creative_id": creative_id},
        "status": status,
        "access_token": access_token,
    }
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Insights ─────────────────────────────────────────────────────────────────

def get_campaign_insights(access_token: str, campaign_id: str, fields: list = None) -> list:
    if fields is None:
        fields = ["spend", "impressions", "clicks", "ctr", "cpc", "actions", "cost_per_action_type"]
    url = f"{GRAPH_BASE}/{campaign_id}/insights"
    params = {
        "access_token": access_token,
        "fields": ",".join(fields),
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


def get_ad_insights(access_token: str, ad_id: str, fields: list = None) -> list:
    if fields is None:
        fields = ["spend", "impressions", "clicks", "ctr", "cpc", "actions", "cost_per_action_type"]
    url = f"{GRAPH_BASE}/{ad_id}/insights"
    params = {
        "access_token": access_token,
        "fields": ",".join(fields),
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json().get("data", [])


# ── Copy Generation ──────────────────────────────────────────────────────────

AD_COPY_ANGLES = {
    "urgency": {
        "headline": "Sold Your Flat? Collect Condo Keys in Q3.",
        "body": "Your HDB buyer is ready. Your next home should be too. {project}, {location} — TOP Q3 {year}. No rent. No wait. No stress.\n\nReply on WhatsApp for the latest availability.",
    },
    "painkiller": {
        "headline": "Skip Rent. Skip Waiting. Move Straight In.",
        "body": "Most sellers face 2–3 years of BTO limbo or landlord roulette. {project} is different. TOP Q3 {year}. You sell, you collect, you move.\n\nWhatsApp us to book a viewing this week.",
    },
    "financial": {
        "headline": "Your HDB Sale Proceeds + TOP Q3 = Zero-Gap Upgrade.",
        "body": "Why park your sale proceeds in rent when you can own? {project}. Ready for key collection Q3 {year}. Stay in the north. Upgrade to condo. No downtime.\n\nMessage us on WhatsApp for floor plans and pricing.",
    },
    "retargeting": {
        "headline": "Still Looking? Q3 Key Collection Closes Soon.",
        "body": "You browsed {project}. Final units for Q3 {year} key collection. Reply on WhatsApp for latest availability and pricing.\n\nDon't miss your window.",
    },
}


def generate_ad_copy(project: str, location: str, top_year: str = None, angle: str = "urgency") -> dict:
    if angle not in AD_COPY_ANGLES:
        angle = "urgency"
    template = AD_COPY_ANGLES[angle]
    year = top_year or str(datetime.now().year)
    return {
        "headline": template["headline"],
        "body": template["body"].format(project=project, location=location, year=year),
        "angle": angle,
    }


def generate_all_angles(project: str, location: str, top_year: str = None) -> dict:
    year = top_year or str(datetime.now().year)
    return {
        angle: {
            "headline": tpl["headline"],
            "body": tpl["body"].format(project=project, location=location, year=year),
            "angle": angle,
        }
        for angle, tpl in AD_COPY_ANGLES.items()
    }
