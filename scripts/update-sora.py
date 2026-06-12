#!/usr/bin/env python3
"""
Fetch latest 3M SORA from MAS API and update the-post.html intel card.
Falls back to cached value if MAS API is down.
Run via cron daily at 09:00 SGT.
"""
import json
import os
import re
import ssl
import time
import urllib.request
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
HTML_PATH = os.path.join(REPO_ROOT, 'the-post.html')
CACHE_PATH = os.path.join(REPO_ROOT, '.sora-cache.json')
API_URL = (
    'https://eservices.mas.gov.sg/api/action/datastore/search.json'
    '?resource_id=5f2b18a8-0883-4769-a635-879c63d3caac'
    '&limit=5&sort=end_of_day%20desc'
)


def fetch_sora(retries=2, timeout=15):
    """Fetch latest 3M SORA from MAS API with retries."""
    ctx = ssl.create_default_context()
    req = urllib.request.Request(API_URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    })

    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                content_type = response.headers.get('Content-Type', '')
                raw = response.read()

            # If API returns HTML (maintenance page), treat as unavailable
            if 'text/html' in content_type:
                last_error = 'HTML maintenance page'
                time.sleep(2 ** attempt)
                continue

            # MAS API returns UTF-8 with BOM
            for encoding in ('utf-8-sig', 'utf-8'):
                try:
                    data = json.loads(raw.decode(encoding))
                    break
                except Exception:
                    continue
            else:
                last_error = 'JSON decode failed'
                time.sleep(2 ** attempt)
                continue

            records = data.get('result', {}).get('records', [])
            if records:
                latest = max(records, key=lambda r: r.get('end_of_day', ''))
                rate = latest.get('sora', '')
                date = latest.get('end_of_day', '')
                if rate:
                    return float(rate), date
        except Exception as e:
            last_error = f'{type(e).__name__}: {e}'
            time.sleep(2 ** attempt)
            continue

    print(f'API unavailable after {retries} attempts ({last_error})')
    return None, None


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {'rate': 3.42, 'date': '2026-06-04'}


def save_cache(rate, date):
    with open(CACHE_PATH, 'w') as f:
        json.dump({
            'rate': rate,
            'date': date,
            'updated': datetime.now().isoformat(),
        }, f)


def update_html(rate, date_str):
    with open(HTML_PATH, 'r') as f:
        html = f.read()

    rate_pct = f'{rate:.2f}%'
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        nice_date = d.strftime('%-d %b %Y')
    except ValueError:
        nice_date = date_str

    # --- Try new JS array format (INTEL_FALLBACK) ---
    # Match the mortgage rates entry in the JS array
    js_pattern = re.compile(
        r"(\{\s*tag\s*:\s*'market'\s*,\s*tag_label\s*:\s*'Market'\s*,\s*date\s*:\s*')"
        r"\d{4}-\d{2}-\d{2}"
        r"('\s*,\s*title\s*:\s*'Mortgage rates: 3M SORA at )"
        r"[0-9.]+%"
        r"('.*?body\s*:\s*')"
        r"[^']*"
        r"('\s*,\s*source_url\s*:\s*''\s*\})",
        re.DOTALL
    )

    js_match = js_pattern.search(html)
    if js_match:
        new_entry = (
            f"{{ tag:'market', tag_label:'Market', date:'{date_str}', "
            f"title:'Mortgage rates: 3M SORA at {rate_pct}', "
            f"body:'Major banks holding 3-year fixed at ~3.55%. "
            f"Expect slight easing in Q3. Forward rates suggest 3.1% by year-end.', "
            f"source_url:'' }}"
        )
        html = html[:js_match.start()] + new_entry + html[js_match.end():]
        with open(HTML_PATH, 'w') as f:
            f.write(html)
        return True

    # --- Fallback: old static HTML format (backwards compatibility) ---
    old_pattern = re.compile(
        r'(\s*)<div class="intel-card">(\s*)<div class="intel-header">(\s*)'
        r'<span class="intel-tag market">Market</span>(\s*)'
        r'<span class="intel-date">[^<]*</span>(\s*)</div>(\s*)'
        r'<div class="intel-title">Mortgage rates:[^<]*</div>(\s*)'
        r'<div class="intel-body">[^<]*</div>(\s*)</div>',
        re.DOTALL
    )

    old_match = old_pattern.search(html)
    if old_match:
        new_card = f'''      <div class="intel-card">
        <div class="intel-header">
          <span class="intel-tag market">Market</span>
          <span class="intel-date">{nice_date}</span>
        </div>
        <div class="intel-title">Mortgage rates: 3M SORA at {rate_pct}</div>
        <div class="intel-body">Major banks holding 3-year fixed at ~3.55%. Expect slight easing in Q3. Forward rates suggest 3.1% by year-end.</div>
      </div>'''
        html = html[:old_match.start()] + '\n' + new_card + html[old_match.end():]
        with open(HTML_PATH, 'w') as f:
            f.write(html)
        return True

    return False


def git_commit_push():
    import subprocess
    try:
        files_to_add = ['the-post.html']
        if os.path.exists(CACHE_PATH):
            files_to_add.append('.sora-cache.json')
        subprocess.run(['git', 'add'] + files_to_add,
                       cwd=REPO_ROOT, check=True, capture_output=True)
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'],
                                cwd=REPO_ROOT, capture_output=True)
        if result.returncode == 0:
            print('No changes to commit.')
            return
        cache = load_cache()
        subprocess.run(['git', 'commit', '-m',
                        f'chore: update SORA to {cache["rate"]:.4f}% ({cache["date"]})'],
                       cwd=REPO_ROOT, check=True, capture_output=True)
        subprocess.run(['git', 'push', 'origin', 'main'],
                       cwd=REPO_ROOT, check=True, capture_output=True)
        print('Pushed to GitHub.')
    except subprocess.CalledProcessError as e:
        print(f'Git error: {e}')


if __name__ == '__main__':
    rate, date = fetch_sora()
    cache = load_cache()

    if rate:
        print(f'Fetched live SORA: {rate:.4f}% on {date}')
        save_cache(rate, date)
    else:
        rate = cache['rate']
        date = cache['date']
        print(f'API unavailable. Using cached SORA: {rate:.4f}% on {date}')

    updated = update_html(rate, date)
    print(f'HTML updated: {updated}')

    if updated:
        git_commit_push()
