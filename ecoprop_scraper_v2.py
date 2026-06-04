#!/usr/bin/env python3
"""
Robust EcoProp scraper.
Primary: Direct API call (fast, reliable)
Fallback: None - API is the only reliable source
Auto-commits and pushes on success.
"""

import json
import os
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone

import requests

# Paths
OUTPUT_FILE = Path("/home/hermes/initium-website/ecoprop_projects.json")
CACHE_FILE = Path("/home/hermes/ecoprop_projects.json")

# The API blocks short/robot User-Agents. Must use full browser UA.
HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.ecoprop.com/",
    "Origin": "https://www.ecoprop.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}

API_URL = "https://api.singmap.com/c-api/project/queryProjectList"


def generate_api_signature(params):
    base = {"appSource": "web", "lang": "en", "timestamp": params["timestamp"]}
    merged = {**base, **params}
    sorted_keys = sorted(merged.keys())
    sig_str = ""
    for k in sorted_keys:
        if k != "token" and merged[k] is not None:
            sig_str += str(merged[k])
    sig_str += "c1d65f3667324592a071ebec5038f38c"
    return hashlib.md5(sig_str.encode()).hexdigest()


def fetch_via_api():
    """Fetch all projects via EcoProp API."""
    timestamp = str(int(time.time() * 1000))
    all_projects = []
    total_count = None
    page_no = 0

    while True:
        page_no += 1
        params = {
            "lang": "en",
            "timestamp": timestamp,
            "country": "Singapore",
            "type": "",
            "soldOut": "",
            "minPrice": "",
            "maxPrice": "",
            "bedrooms": "",
            "projectType": "",
            "tenure": "",
            "completionStatus": "",
            "projectArea": "",
            "category": "",
            "minArea": "",
            "maxArea": "",
            "projectName": "",
            "location": "",
            "pageNo": str(page_no),
            "pageSize": "500",
            "pointJson": "",
            "year": "",
            "orderRule": "projectName",
            "distance": "",
            "total": "web",
            "vrCall": "",
        }
        signature = generate_api_signature(params)
        form_data = {**params, "signature": signature, "appSource": "web"}

        # Retry up to 3 times per page
        data = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(API_URL, data=form_data, headers=HEADERS, timeout=30)
                data = resp.json()
                break
            except Exception as e:
                print(f"[{datetime.now()}] API page {page_no} attempt {attempt} error: {e}")
                if attempt == 3:
                    return None
                time.sleep(2)

        if data is None or data.get("code") != "0":
            msg = data.get("msg") if data else "No response"
            print(f"[{datetime.now()}] API error: {msg}")
            return None

        projects = data.get("datas", {}).get("lists", [])
        if total_count is None:
            total_count = data.get("datas", {}).get("count", 0)

        all_projects.extend(projects)
        print(f"[{datetime.now()}] Page {page_no}: {len(projects)} projects (total: {len(all_projects)}/{total_count})")

        if len(projects) == 0 or len(all_projects) >= total_count:
            break

    return all_projects


def clean_projects(raw_projects):
    cleaned = []
    for proj in raw_projects:
        cleaned.append({
            'project_name': proj.get('projectName'),
            'district': proj.get('district'),
            'location': proj.get('location'),
            'address': proj.get('streetAddress'),
            'property_type': proj.get('projectType'),
            'tenure': proj.get('tenure'),
            'min_price': proj.get('minPrice'),
            'max_price': proj.get('maxPrice'),
            'currency': proj.get('currencySymbol'),
            'units': proj.get('unitsNum'),
            'completion_date': proj.get('completionDate'),
            'expected_top': proj.get('expTop'),
            'launch_date': proj.get('launchDate'),
            'sold_out': proj.get('soldOut') == 1,
            'latitude': proj.get('latitude'),
            'longitude': proj.get('longitude'),
            'cover_image': f"https://img.singmap.com{proj.get('mainImage')}" if proj.get('mainImage') else None,
        })
    return cleaned


def save_and_commit(projects):
    output = {
        'source': 'ecoprop.com',
        'total': len(projects),
        'scraped_at': datetime.now(timezone.utc).isoformat(),
        'projects': projects,
    }

    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    CACHE_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"[{datetime.now()}] Saved {len(projects)} projects")

    try:
        os.chdir("/home/hermes/initium-website")
        import subprocess
        subprocess.run(["git", "add", "ecoprop_projects.json"], check=True, capture_output=True)
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"Auto-update EcoProp projects: {len(projects)} projects"],
                check=True, capture_output=True
            )
            print(f"[{datetime.now()}] Committed locally (daily pusher handles sync)")
        else:
            print(f"[{datetime.now()}] No changes to commit")
    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")


def main():
    print(f"[{datetime.now()}] Starting EcoProp scraper...")

    raw_projects = fetch_via_api()
    if raw_projects is not None:
        projects = clean_projects(raw_projects)
        save_and_commit(projects)
        print(f"[{datetime.now()}] SUCCESS: {len(projects)} projects")
        return 0

    print(f"[{datetime.now()}] FAILED - keeping existing data")
    return 1


if __name__ == '__main__':
    sys.exit(main())
