#!/usr/bin/env python3
"""
Inject Meta Pixel + GA4 tracking code into all INITIUM HTML pages.
Usage:
    python3 scripts/inject-tracking.py

Before running, edit tracking-config.json with your actual IDs.
"""
import json
import re
from pathlib import Path

CONFIG_FILE = Path("tracking-config.json")
ROOT = Path(".")

# Pages that get FULL tracking (Pixel + GA4 + conversion events)
KEY_PAGES = [
    "index.html",
    "new-launch-landing.html",
    "new-launches.html",
    "contact.html",
    "services.html",
    "about.html",
    "join.html",
    "virtual-tours.html",
]

# Pages that get ONLY base Pixel + GA4 (no extra events)
ALL_PAGES = [p for p in ROOT.glob("*.html") if p.is_file()]


def build_snippet(config):
    meta_id = config["meta_pixel_id"]
    ga4_id = config["ga4_measurement_id"]

    # Meta Pixel base code
    meta_pixel = f"""<!-- Meta Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{meta_id}');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none"
src="https://www.facebook.com/tr?id={meta_id}&ev=PageView&noscript=1"/></noscript>
<!-- End Meta Pixel Code -->"""

    # GA4 base code
    ga4 = f"""<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{ga4_id}', {{ 'send_page_view': true }});
</script>
<!-- End Google tag -->"""

    return meta_pixel + "\n" + ga4


def inject_into_page(page_path, snippet):
    text = page_path.read_text(encoding="utf-8")

    # Remove old tracking snippets if present
    text = re.sub(r"<!-- Meta Pixel Code -->.*?<!-- End Meta Pixel Code -->", "", text, flags=re.DOTALL)
    text = re.sub(r"<!-- Google tag \(gtag\.js\) -->.*?<!-- End Google tag -->", "", text, flags=re.DOTALL)
    text = re.sub(r"<script>\s*!function\(f,b,e,v,n,t,s\).*?fbq\('track', 'PageView'\);\s*</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<noscript>.*?facebook\.com/tr\?id=.*?&ev=PageView&noscript=1.*?</noscript>", "", text, flags=re.DOTALL)

    # Inject after </title> tag
    if "</title>" in text:
        text = text.replace("</title>", "</title>\n" + snippet, 1)
    elif "<head>" in text:
        text = text.replace("<head>", "<head>\n" + snippet, 1)
    else:
        print(f"  ⚠️  Skipped {page_path.name} — no <head> or </title> found")
        return

    page_path.write_text(text, encoding="utf-8")
    print(f"  ✓ {page_path.name}")


def main():
    if not CONFIG_FILE.exists():
        print(f"❌ {CONFIG_FILE} not found. Create it first.")
        return

    config = json.loads(CONFIG_FILE.read_text())

    if "REPLACE" in config["meta_pixel_id"]:
        print("⚠️  WARNING: meta_pixel_id is still a placeholder.")
        print("   Edit tracking-config.json with your real Pixel ID before running ads.")

    if "REPLACE" in config["ga4_measurement_id"]:
        print("⚠️  WARNING: ga4_measurement_id is still a placeholder.")
        print("   Edit tracking-config.json with your real GA4 ID before running ads.")

    snippet = build_snippet(config)
    print(f"\nInjecting tracking into {len(ALL_PAGES)} pages...\n")

    for page in sorted(ALL_PAGES):
        inject_into_page(page, snippet)

    print("\n✅ Done. Commit and push to deploy.")
    print("\nNext steps:")
    print("  1. Edit tracking-config.json with real IDs")
    print("  2. Re-run: python3 scripts/inject-tracking.py")
    print("  3. git add . && git commit -m 'Add tracking' && git push")
    print("  4. Install Meta Pixel Helper Chrome extension to verify")


if __name__ == "__main__":
    main()
