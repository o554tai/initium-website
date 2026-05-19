#!/usr/bin/env python3
"""
Inject Meta Pixel + GA4 + Google Ads conversion tracking into all INITIUM HTML pages.
Usage:
    python3 scripts/inject-tracking.py

Before running, edit tracking-config.json with your actual IDs.
"""
import json
import re
from pathlib import Path

CONFIG_FILE = Path("tracking-config.json")
ROOT = Path(".")

ALL_PAGES = [p for p in ROOT.glob("*.html") if p.is_file()]


def build_snippet(config):
    meta_id = config["meta_pixel_id"]
    ga4_id = config["ga4_measurement_id"]
    gads_id = config["google_ads_conversion_id"]
    gads_label = config["google_ads_conversion_label"]

    snippets = []

    # 1. Meta Pixel base code
    if "REPLACE" not in meta_id:
        snippets.append(f"""<!-- Meta Pixel Code -->
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
<!-- End Meta Pixel Code -->""")

    # 2. GA4 base code
    if "REPLACE" not in ga4_id:
        snippets.append(f"""<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{ga4_id}', {{ 'send_page_view': true }});
</script>
<!-- End Google tag -->""")

    # 3. Google Ads conversion + remarketing tag
    if "REPLACE" not in gads_id:
        snippets.append(f"""<!-- Google Ads Conversion + Remarketing -->
<script async src="https://www.googletagmanager.com/gtag/js?id={gads_id}"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', '{gads_id}');
</script>
<!-- End Google Ads tag -->""")

    return "\n".join(snippets)


def remove_old_tracking(text):
    """Strip all previously injected tracking blocks."""
    # Meta Pixel
    text = re.sub(r"<!-- Meta Pixel Code -->.*?<!-- End Meta Pixel Code -->", "", text, flags=re.DOTALL)
    text = re.sub(r"<script>\s*!function\(f,b,e,v,n,t,s\).*?fbq\('track', 'PageView'\);\s*</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<noscript>.*?facebook\.com/tr\?id=.*?&ev=PageView&noscript=1.*?</noscript>", "", text, flags=re.DOTALL)
    # GA4
    text = re.sub(r"<!-- Google tag \(gtag\.js\) -->.*?<!-- End Google tag -->", "", text, flags=re.DOTALL)
    # Google Ads
    text = re.sub(r"<!-- Google Ads Conversion \+ Remarketing -->.*?<!-- End Google Ads tag -->", "", text, flags=re.DOTALL)
    return text


def inject_into_page(page_path, snippet):
    text = page_path.read_text(encoding="utf-8")
    text = remove_old_tracking(text)

    if not snippet.strip():
        print(f"  ⚠️  Skipped {page_path.name} — no valid IDs configured")
        return

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
    missing = []

    if "REPLACE" in config.get("meta_pixel_id", ""):
        missing.append("meta_pixel_id")
    if "REPLACE" in config.get("ga4_measurement_id", ""):
        missing.append("ga4_measurement_id")
    if "REPLACE" in config.get("google_ads_conversion_id", ""):
        missing.append("google_ads_conversion_id")

    if missing:
        print(f"⚠️  WARNING: These IDs are still placeholders: {', '.join(missing)}")
        print("   Edit tracking-config.json with real IDs before running ads.\n")

    snippet = build_snippet(config)
    print(f"Injecting tracking into {len(ALL_PAGES)} pages...\n")

    for page in sorted(ALL_PAGES):
        inject_into_page(page, snippet)

    print("\n✅ Done. Commit and push to deploy.")
    print("\nNext steps:")
    print("  1. Edit tracking-config.json with real IDs")
    print("  2. Re-run: python3 scripts/inject-tracking.py")
    print("  3. git add . && git commit -m 'Add tracking IDs' && git push")
    print("  4. Install Meta Pixel Helper + Tag Assistant to verify")


if __name__ == "__main__":
    main()
