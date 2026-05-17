#!/usr/bin/env python3
"""
Robust EcoProp scraper with multiple fallback strategies.
1. Try API directly (fastest)
2. Try extracting from Nuxt SSR HTML
3. Use Playwright as last resort
Auto-commits and pushes on success.
"""

import asyncio
import json
import os
import re
import sys
import time
import hashlib
from pathlib import Path
from datetime import datetime

import requests

# Paths
OUTPUT_FILE = Path("/home/hermes/initium-website/ecoprop_projects.json")
CACHE_FILE = Path("/home/hermes/ecoprop_projects.json")
LOCK_FILE = Path("/tmp/ecoprop_scraper.lock")

def acquire_lock():
    if LOCK_FILE.exists():
        pid = LOCK_FILE.read_text().strip()
        try:
            os.kill(int(pid), 0)
            print(f"[{datetime.now()}] Another scraper instance running (PID {pid}). Exiting.")
            sys.exit(0)
        except (OSError, ValueError):
            pass
    LOCK_FILE.write_text(str(os.getpid()))

def release_lock():
    LOCK_FILE.unlink(missing_ok=True)

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
    """Strategy 1: Direct API call."""
    timestamp = str(int(time.time() * 1000))
    all_projects = []
    total_count = None

    for page_no in [1, 2, 3, 4, 5, 6, 7, 8]:
        params = {
            "lang": "en", "timestamp": timestamp, "country": "Singapore",
            "type": "", "soldOut": "", "minPrice": "", "maxPrice": "",
            "bedrooms": "", "projectType": "", "tenure": "",
            "completionStatus": "", "projectArea": "", "category": "",
            "minArea": "", "maxArea": "", "projectName": "", "location": "",
            "pageNo": str(page_no), "pageSize": "500", "pointJson": "",
            "year": "", "orderRule": "projectName", "distance": "",
            "total": "web", "vrCall": "",
        }
        signature = generate_api_signature(params)
        form_data = {**params, "signature": signature, "appSource": "web"}

        try:
            resp = requests.post(
                "https://api.singmap.com/c-api/project/queryProjectList",
                data=form_data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                    "Referer": "https://www.ecoprop.com/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                timeout=15
            )
            data = resp.json()
        except Exception as e:
            print(f"[{datetime.now()}] API page {page_no} error: {e}")
            return None

        if data.get("code") != "0":
            print(f"[{datetime.now()}] API error: {data.get('msg')}")
            return None

        projects = data.get("datas", {}).get("lists", [])
        if total_count is None:
            total_count = data.get("datas", {}).get("count", 0)

        all_projects.extend(projects)
        print(f"[{datetime.now()}] API page {page_no}: {len(projects)} projects (total: {len(all_projects)}/{total_count})")

        if len(projects) == 0 or len(all_projects) >= total_count:
            break

    return all_projects

def fetch_via_html():
    """Strategy 2: Extract from Nuxt SSR HTML."""
    try:
        resp = requests.get(
            "https://www.ecoprop.com/new-launch-properties",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=30
        )
        text = resp.text

        # Try to find and parse __NUXT__ data
        nuxt_match = re.search(r'window\.__NUXT__\s*=\s*(function\(.*?\)\{return\s+(.+?)\}\(.*?\)\);', text, re.DOTALL)
        if nuxt_match:
            # This is obfuscated - let's try a different regex
            pass

        # Look for raw JSON with project data
        # Try simpler patterns
        for pattern in [
            r'"projectList":\s*(\[.*?\])',
            r'"lists":\s*(\[.*?\])',
        ]:
            # Use non-greedy with a limit to avoid catastrophic backtracking
            match = re.search(pattern, text[:200000])  # Limit search to first 200KB
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    continue

        print(f"[{datetime.now()}] HTML strategy: no parseable project data found")
        return None
    except Exception as e:
        print(f"[{datetime.now()}] HTML strategy error: {e}")
        return None

async def fetch_via_playwright():
    """Strategy 3: Playwright browser automation."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(f"[{datetime.now()}] Playwright not installed")
        return None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            page = await browser.new_page()

            # Intercept API response
            api_response = None
            def handle_response(response):
                nonlocal api_response
                if "queryProjectList" in response.url:
                    api_response = response

            page.on("response", handle_response)

            await page.goto('https://www.ecoprop.com/new-launch-properties', wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(3000)

            if api_response:
                data = await api_response.json()
                if data.get("code") == "0":
                    projects = data.get("datas", {}).get("lists", [])
                    await browser.close()
                    print(f"[{datetime.now()}] Playwright: captured {len(projects)} projects from network")
                    return projects

            # Fallback: try to extract from page JS context
            result = await page.evaluate('''() => {
                try {
                    const nuxt = window.__NUXT__;
                    if (nuxt && nuxt.state) {
                        // Look for project data in state
                        const state = nuxt.state;
                        for (let key of Object.keys(state)) {
                            const val = state[key];
                            if (val && val.lists && Array.isArray(val.lists)) {
                                return val.lists;
                            }
                        }
                    }
                    return null;
                } catch(e) {
                    return null;
                }
            }''')

            await browser.close()

            if result and isinstance(result, list):
                print(f"[{datetime.now()}] Playwright: extracted {len(result)} projects from JS state")
                return result

            print(f"[{datetime.now()}] Playwright: no data extracted")
            return None
    except Exception as e:
        print(f"[{datetime.now()}] Playwright error: {e}")
        return None

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
        'scraped_at': datetime.utcnow().isoformat(),
        'projects': projects,
    }

    # Save to both locations
    OUTPUT_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
    CACHE_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

    print(f"[{datetime.now()}] Saved {len(projects)} projects")

    # Git commit and push
    try:
        import subprocess
        os.chdir("/home/hermes/initium-website")
        subprocess.run(["git", "add", "ecoprop_projects.json"], check=True, capture_output=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"Auto-update EcoProp projects: {len(projects)} projects"],
                check=True, capture_output=True
            )
            subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
            print(f"[{datetime.now()}] Committed and pushed to GitHub")
        else:
            print(f"[{datetime.now()}] No changes to commit")
    except Exception as e:
        print(f"[{datetime.now()}] Git error: {e}")

async def main():
    acquire_lock()
    try:
        print(f"[{datetime.now()}] Starting EcoProp scraper...")

        # Strategy 1: API
        raw_projects = fetch_via_api()
        if raw_projects is not None:
            projects = clean_projects(raw_projects)
            save_and_commit(projects)
            print(f"[{datetime.now()}] SUCCESS via API: {len(projects)} projects")
            return

        # Strategy 2: HTML
        raw_projects = fetch_via_html()
        if raw_projects is not None:
            projects = clean_projects(raw_projects)
            save_and_commit(projects)
            print(f"[{datetime.now()}] SUCCESS via HTML: {len(projects)} projects")
            return

        # Strategy 3: Playwright
        raw_projects = await fetch_via_playwright()
        if raw_projects is not None:
            projects = clean_projects(raw_projects)
            save_and_commit(projects)
            print(f"[{datetime.now()}] SUCCESS via Playwright: {len(projects)} projects")
            return

        print(f"[{datetime.now()}] ALL STRATEGIES FAILED - keeping existing data")

    finally:
        release_lock()

if __name__ == '__main__':
    asyncio.run(main())
