#!/usr/bin/env python3
"""Hourly property news updater for INITIUM Pulse page.
Fetches fresh articles from ST, CNA, EdgeProp via Google News RSS.
Only keeps articles published within last 48h for the carousel.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import unescape
from xml.etree import ElementTree as ET

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
DATA_FILE = os.path.join(REPO_DIR, "data", "property-news.json")
BLOG_HTML = os.path.join(REPO_DIR, "blog.html")
ARCHIVE_HTML = os.path.join(REPO_DIR, "news-archive.html")

# Source brand logos — used as card thumbnails since article hero images
# are blocked by paywalls / bot protection.
SOURCE_LOGOS = {
    "ST": "assets/images/blog/logos/st-logo.svg",
    "CNA": "assets/images/blog/logos/cna-logo.svg",
    "EdgeProp": "assets/images/blog/logos/edgeprop-logo.svg",
}

HOURS_FRESH = 48
DAYS_KEEP = 7  # Prune articles older than this


def now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def fmt_date(ts: float) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%a, %d %b %Y")


def pick_source_logo(article: dict) -> str:
    """Return the source brand logo for the article card thumbnail."""
    tag = article.get("source_tag", "ST")
    return SOURCE_LOGOS.get(tag, SOURCE_LOGOS["ST"])


def fetch_google_news_rss(query: str) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-SG&gl=SG&ceid=SG:en"
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        articles = []
        cutoff_ts = now_ts() - (HOURS_FRESH * 3600)
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            src_el = item.find("source")
            if title_el is None or link_el is None:
                continue
            title = unescape(title_el.text or "").strip()
            link = link_el.text or ""
            source = src_el.text if src_el is not None else ""
            pub_date = pub_el.text if pub_el is not None else ""
            # Parse pub date
            pub_ts = None
            for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
                try:
                    pub_ts = datetime.strptime(pub_date, fmt).replace(tzinfo=timezone.utc).timestamp()
                    break
                except ValueError:
                    continue
            if pub_ts is None:
                pub_ts = now_ts()
            # Skip articles published more than 48h ago
            if pub_ts < cutoff_ts:
                continue
            articles.append({
                "title": title,
                "url": link,
                "source": source,
                "pub_date": pub_date,
                "pub_ts": pub_ts,
                "fetched_ts": now_ts(),
            })
        return articles
    except Exception as e:
        print(f"  RSS fetch error ({query[:40]}): {e}")
        return []


def is_property_article(title: str) -> bool:
    t = title.lower()
    skip = [
        "football", "soccer", "sport", "sports", "basketball", "tennis", "golf",
        "f1", "formula 1", "world cup", "pga", "olympic", "nba", "nfl",
        "cricket", "rugby", "boxing", "marathon", "athletics", "swimming",
        "agricultural", "agriculture", "cape verde", "ireland", "china to buy",
        "trade war", "cyberattack", "hacking", "terror", "murder", "killed",
        "plane crash", "virus", "covid", "pandemic", "vaccine",
        "stock market", "crypto", "bitcoin", "wall street",
        "nazi", "epstein", "solomon islands", "us scraps", "troop", "poland",
        "new zealand state farming", "nature credit", "lianhe zaobao",
        "faq: what hikers", "volcano trekking", "insurance",
        "cna homepage", "thai police", "weapons cache",
        "intellectual property",
    ]
    if any(s in t for s in skip):
        return False
    # Reject generic homepage / portal landing pages
    generic_portal_titles = [
        "for sale and for rent",
        "property | for sale",
        "property | for rent",
        "property listings",
        "find property",
        "property portal",
        "real estate listings",
        "latest property news",
        "property news - edgeprop",
    ]
    if any(g in t for g in generic_portal_titles):
        return False
    prop_patterns = [
        r'\bproperty\b', r'\bproperties\b', r'\breal estate\b',
        r'\bhdb\b',
        r'\bcondo\b', r'\bcondos\b', r'\bcondominium\b', r'\bcondominiums\b',
        r'\brental\b', r'\brentals\b', r'\btenancy\b', r'\blease\b', r'\bleases\b',
        r'\bland sale\b', r'\blanded\b', r'\bland parcel\b', r'\bland bid\b',
        r'\bgls\b', r'\bgovernment land sale\b',
        r'\bresale\b', r'\blaunch\b', r'\blaunches\b', r'\blaunched\b', r'\blaunching\b',
        r'\babsd\b', r'\bbto\b', r'\bura\b', r'\bmop\b',
        r'\bshophouse\b', r'\bshophouses\b',
        r'\bdevelopment\b', r'\bdevelopments\b', r'\bdeveloper\b', r'\bdevelopers\b',
        r'\bprivate home\b', r'\bprivate homes\b', r'\bpublic housing\b',
        r'\bcollective sale\b', r'\ben bloc\b', r'\benbloc\b',
        r'\bproperty market\b', r'\bproperty agency\b', r'\bproperty agent\b', r'\bproperty agents\b',
        r'\bproperty prices\b', r'\bproperty tax\b', r'\bproperty investment\b',
        r'\bmortgage\b', r'\bstamp duty\b', r'\bcooling measure\b', r'\bcooling measures\b',
        r'\bsrr\b', r'\btdsr\b', r'\bgsr\b', r'\bssr\b',
        r'\bhousing\b', r'\bpsf\b', r'\bper sq ft\b',
        r'\bresidences\b', r'\bresidence\b', r'\bfreehold\b', r'\bleasehold\b', r'\b99-year\b',
        r'\bredevelopment\b', r'\bredevelop\b', r'\bupgrade\b', r'\bupgrading\b',
        r'\bnew launch\b', r'\bmillion dollar\b',
        r'\bhome prices\b', r'\bhome sales\b', r'\bhome buyers?\b', r'\bhome owners?\b',
        r'\bnew home\b', r'\bnew homes\b',
        r'\bflat\b', r'\bflats\b',
        r'\bec\b', r'\bexecutive condo\b', r'\bexecutive condos\b', r'\bexecutive condominium\b', r'\bexecutive condominiums\b',
        r'\bsky\b.*\bcondo\b', r'\bestate\b.*\bcondo\b', r'\bestate\b.*\blaunch\b',
        r'\bprofit\b', r'\bmil profit\b', r'\bmillion profit\b', r'\breap\b', r'\brakes\b',
        r'\bprices from\b', r'\bprices of\b', r'\btop\b', r'\bhandover\b',
        r'\byishun\b', r'\bpunggol\b', r'\bsengkang\b', r'\btampines\b', r'\bjurong\b',
        r'\blentor\b', r'\bnovena\b', r'\bbukit\b',
        r'\bhouse\b', r'\bhouses\b', r'\bowner\b', r'\bowners\b',
        r'\bpropnex\b', r'\bera\b', r'\bhuttons\b', r'\brealty\b',
        r'\bturf club\b.*\bhome\b', r'\bhome\b.*\bturf club\b',
        r'\bhong kong\b.*\bhome\b', r'\bhong kong\b.*\bproperty\b',
        r'\bresidential\b', r'\bresidential development\b',
        r'\bproperty ladder\b', r'\brts link\b.*\bproperty\b',
        r'\bbuyer\b', r'\bbuyers\b', r'\bseller\b', r'\bsellers\b',
    ]
    return any(re.search(p, t) for p in prop_patterns)


def clean_title(title: str) -> str:
    return re.sub(r"\s*-\s*(The Straits Times|CNA|EdgeProp\.sg)$", "", title).strip()


def make_excerpt(title: str) -> str:
    words = title.split()
    if len(words) > 12:
        return " ".join(words[:12]) + "..."
    return title


def load_articles() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  JSON load error: {e}")
        return []


def save_articles(articles: list[dict]):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)


def dedupe_by_url(articles: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for a in articles:
        u = a.get("url", "")
        if u and u not in seen:
            seen.add(u)
            out.append(a)
    return out


def build_card_html(article: dict) -> str:
    title = clean_title(article["title"])
    display_title = title if len(title) < 90 else title[:87] + "..."
    excerpt = make_excerpt(title)
    tag = article.get("source_tag", "News")
    img = pick_source_logo(article)
    date_str = fmt_date(article.get("pub_ts", article.get("fetched_ts", now_ts())))
    url = article.get("url", "#")
    source_name = "ST" if tag == "ST" else ("CNA" if tag == "CNA" else "EdgeProp")
    read_text = f"Read on {source_name} →"
    return (
        f'      <a href="{url}" target="_blank" rel="noopener" class="news-card">\n'
        f'        <div class="news-img">\n'
        f'          <img src="{img}" alt="{source_name}" loading="lazy">\n'
        f'          <span class="news-source">{tag}</span>\n'
        f'        </div>\n'
        f'        <div class="news-body">\n'
        f'          <h3 class="news-title">{display_title}</h3>\n'
        f'          <p class="news-excerpt">{excerpt}</p>\n'
        f'          <div class="news-meta">\n'
        f'            <span>{date_str}</span>\n'
        f'            <span>·</span>\n'
        f'            <span class="source-link">{read_text}</span>\n'
        f'          </div>\n'
        f'        </div>\n'
        f'      </a>'
    )


def classify_articles(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Classify by PUBLICATION date, not fetch date."""
    cutoff = now_ts() - (HOURS_FRESH * 3600)
    fresh = [a for a in articles if a.get("pub_ts", 0) > cutoff]
    archived = [a for a in articles if a.get("pub_ts", 0) <= cutoff]
    # Sort by newest published first
    fresh.sort(key=lambda a: a.get("pub_ts", 0), reverse=True)
    archived.sort(key=lambda a: a.get("pub_ts", 0), reverse=True)
    return fresh, archived


def prune_old_articles(articles: list[dict]) -> list[dict]:
    """Remove articles older than DAYS_KEEP to keep the DB lean."""
    cutoff = now_ts() - (DAYS_KEEP * 24 * 3600)
    kept = [a for a in articles if a.get("pub_ts", 0) > cutoff]
    removed = len(articles) - len(kept)
    if removed:
        print(f"      Pruned {removed} articles older than {DAYS_KEEP} days")
    return kept


def update_blog_html(fresh: list[dict]):
    # Cap at 50 most recent articles; scroll container shows ~6 at a time
    fresh = fresh[:50]
    with open(BLOG_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    cards_html = "\n\n".join(build_card_html(a) for a in fresh)

    pattern = r'(<div class="news-grid[^"]*" id="newsGrid">)\n\n(.*?)(\n      </div>)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        # Try without the leading newline after open tag
        pattern2 = r'(<div class="news-grid[^"]*" id="newsGrid">)(.*?)(</div>)'
        match = re.search(pattern2, content, re.DOTALL)
        if match:
            old = match.group(0)
            new = match.group(1) + "\n\n" + cards_html + "\n      " + match.group(3)
            content = content.replace(old, new)
        else:
            print("  ERROR: Could not find news-grid in blog.html")
            return False
    else:
        old = match.group(0)
        new = match.group(1) + "\n\n" + cards_html + match.group(3)
        content = content.replace(old, new)

    with open(BLOG_HTML, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def generate_archive_html(archived: list[dict]):
    # Build archive cards (full grid, not carousel)
    cards = []
    for a in archived:
        title = clean_title(a["title"])
        display_title = title if len(title) < 90 else title[:87] + "..."
        excerpt = make_excerpt(title)
        tag = a.get("source_tag", "News")
        img = pick_source_logo(a)
        date_str = fmt_date(a.get("pub_ts", a.get("fetched_ts", now_ts())))
        url = a.get("url", "#")
        cards.append(
            f'      <a href="{url}" class="blog-card" target="_blank" rel="noopener">\n'
            f'        <div class="blog-thumb">\n'
            f'          <img src="{img}" alt="{tag} property news" loading="lazy" style="object-fit:contain;padding:20px;background:#fff;">\n'
            f'        </div>\n'
            f'        <div class="blog-content">\n'
            f'          <span class="blog-tag">{tag}</span>\n'
            f'          <h3 class="blog-title">{display_title}</h3>\n'
            f'          <p class="blog-excerpt">{excerpt}</p>\n'
            f'          <div class="blog-meta">{date_str} &middot; Read on {tag}</div>\n'
            f'        </div>\n'
            f'      </a>'
        )

    archive_grid = "\n\n".join(cards) if cards else '<p style="color:var(--ig-ink-3); text-align:center; padding:60px 0;">No archived articles yet.</p>'

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Property News Archive — INITIUM</title>
<meta name="description" content="Archived property news from The Straits Times, CNA, and EdgeProp.">
<meta name="theme-color" content="#50C878">
<link rel="canonical" href="https://initium.sg/news-archive.html">
<link rel="icon" type="image/svg+xml" href="favicon.svg">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --ig: #50C878;
    --ig-dark: #3DA35F;
    --ig-light: #E8F5EE;
    --ig-surface: #F7F8F5;
    --ig-ink: #1A1A1A;
    --ig-ink-2: #6B7B6E;
    --ig-ink-3: #A8B5AC;
    --font-editorial: 'Playfair Display', serif;
    --font-display: 'Space Grotesk', sans-serif;
    --font-body: 'DM Sans', sans-serif;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: var(--font-body);
    color: var(--ig-ink);
    background: var(--ig-surface);
    overflow-x: hidden;
  }}
  nav {{
    position: fixed;
    top:0; left:0; right:0;
    z-index: 1000;
    padding: 24px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background 0.4s ease, backdrop-filter 0.4s ease;
  }}
  nav.scrolled {{
    background: rgba(247,249,248,0.92);
    backdrop-filter: blur(20px) saturate(1.4);
    -webkit-backdrop-filter: blur(20px) saturate(1.4);
    border-bottom: 1px solid rgba(0,140,101,0.08);
  }}
  .nav-logo {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 16px;
    letter-spacing: 3px;
    color: var(--ig);
    text-decoration: none;
  }}
  .nav-logo img {{ height: 56px; width: auto; display: block; background: transparent; }}
  .nav-links {{
    display: flex;
    gap: 32px;
    list-style: none;
  }}
  .nav-links a {{
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-decoration: none;
    color: var(--ig-ink-2);
    position: relative;
    padding-bottom: 4px;
    transition: color 0.3s ease;
  }}
  .nav-links a::after {{
    content: '';
    position: absolute;
    bottom:0; left:0;
    width: 0; height: 1.5px;
    background: var(--ig);
    transition: width 0.4s cubic-bezier(0.16,1,0.3,1);
  }}
  .nav-links a:hover {{ color: var(--ig); }}
  .nav-links a:hover::after {{ width: 100%; }}
  .nav-links a.active {{ color: var(--ig); }}
  .nav-links a.active::after {{ width: 100%; }}

  .page-hero {{
    position: relative;
    min-height: 40vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 160px 24px 60px;
    background: radial-gradient(ellipse at 50% 40%, #ffffff 0%, var(--ig-surface) 60%, var(--ig-light) 100%);
    overflow: hidden;
  }}
  .page-hero-label {{
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ig);
    margin-bottom: 24px;
  }}
  .page-hero-title {{
    font-family: var(--font-display);
    font-size: clamp(36px, 5vw, 64px);
    font-weight: 700;
    line-height: 1.05;
    letter-spacing: -0.03em;
    color: var(--ig-ink);
    margin-bottom: 16px;
    max-width: 700px;
  }}
  .page-hero-sub {{
    font-size: clamp(15px, 2vw, 18px);
    font-weight: 400;
    color: var(--ig-ink-2);
    max-width: 520px;
    line-height: 1.7;
  }}
  .archive-link {{
    margin-top: 20px;
    font-size: 13px;
    color: var(--ig);
    text-decoration: none;
    border-bottom: 1px solid var(--ig);
    padding-bottom: 2px;
    transition: opacity 0.3s ease;
  }}
  .archive-link:hover {{ opacity: 0.7; }}

  section {{
    position: relative;
    padding: 80px 48px;
  }}
  .section-inner {{
    max-width: 1200px;
    margin: 0 auto;
  }}
  .section-header {{
    margin-bottom: 48px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}
  .section-subheader {{
    font-family: var(--font-display);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--ig);
    margin-bottom: 12px;
  }}
  .section-title {{
    font-family: var(--font-display);
    font-size: clamp(28px, 4vw, 40px);
    font-weight: 700;
    color: var(--ig-ink);
    line-height: 1.2;
  }}
  .archive-count {{
    font-size: 14px;
    color: var(--ig-ink-3);
    font-weight: 500;
  }}
  /* Archive Search */
  .archive-search {{
    margin-bottom: 32px;
    position: relative;
  }}
  .archive-search input {{
    width: 100%;
    max-width: 480px;
    padding: 14px 20px 14px 48px;
    border: 1px solid rgba(0,140,101,0.15);
    border-radius: 16px;
    background: #fff;
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--ig-ink);
    outline: none;
    transition: all 0.3s ease;
  }}
  .archive-search input::placeholder {{
    color: var(--ig-ink-3);
  }}
  .archive-search input:focus {{
    border-color: var(--ig);
    box-shadow: 0 0 0 4px rgba(0,140,101,0.08);
  }}
  .archive-search svg {{
    position: absolute;
    left: 16px;
    top: 50%;
    transform: translateY(-50%);
    width: 18px;
    height: 18px;
    color: var(--ig-ink-3);
    pointer-events: none;
  }}
  .archive-search-clear {{
    position: absolute;
    right: 16px;
    top: 50%;
    transform: translateY(-50%);
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: none;
    background: var(--ig-light);
    color: var(--ig);
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    display: none;
    align-items: center;
    justify-content: center;
    padding: 0;
  }}
  .archive-search-clear.visible {{
    display: flex;
  }}
  .blog-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 32px;
  }}
  .archive-scroll-container {{
    max-height: 640px;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 8px;
    scrollbar-width: thin;
    scrollbar-color: var(--ig-light) transparent;
  }}
  .archive-scroll-container::-webkit-scrollbar {{
    width: 6px;
  }}
  .archive-scroll-container::-webkit-scrollbar-track {{
    background: transparent;
  }}
  .archive-scroll-container::-webkit-scrollbar-thumb {{
    background: var(--ig-light);
    border-radius: 10px;
  }}
  .archive-scroll-container::-webkit-scrollbar-thumb:hover {{
    background: var(--ig);
  }}
  .blog-card {{
    background: #fff;
    border-radius: 24px;
    overflow: hidden;
    border: 1px solid rgba(0,140,101,0.08);
    transition: all 0.4s cubic-bezier(0.16,1,0.3,1);
    text-decoration: none;
    color: inherit;
    display: block;
  }}
  .blog-card:hover {{
    transform: translateY(-6px);
    box-shadow: 0 24px 60px rgba(0,140,101,0.1);
    border-color: rgba(0,140,101,0.2);
  }}
  .blog-thumb {{
    height: 220px;
    background: linear-gradient(135deg, var(--ig-light), var(--ig-surface));
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
  }}
  .blog-thumb img {{
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }}
  .blog-content {{
    padding: 28px;
  }}
  .blog-tag {{
    display: inline-block;
    padding: 6px 14px;
    background: var(--ig-light);
    color: var(--ig-dark);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    border-radius: 100px;
    margin-bottom: 16px;
  }}
  .blog-title {{
    font-family: var(--font-display);
    font-size: 20px;
    font-weight: 600;
    line-height: 1.3;
    color: var(--ig-ink);
    margin-bottom: 10px;
  }}
  .blog-excerpt {{
    font-size: 15px;
    line-height: 1.7;
    color: var(--ig-ink-2);
    margin-bottom: 16px;
  }}
  .blog-meta {{
    font-size: 13px;
    color: var(--ig-ink-3);
  }}

  footer {{
    border-top: 1px solid var(--ig-light);
    padding: 64px 48px 32px;
    max-width: 1200px;
    margin: 0 auto;
  }}
  .footer-main {{
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1fr;
    gap: 48px;
    margin-bottom: 48px;
  }}
  .footer-col {{
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}
  .footer-col-title {{
    font-family: var(--font-display);
    font-size: 14px;
    font-weight: 600;
    color: var(--ig-ink);
    margin-bottom: 4px;
  }}
  .footer-col a {{
    font-size: 14px;
    color: var(--ig-ink-2);
    text-decoration: none;
    transition: color 0.3s ease;
  }}
  .footer-col a:hover {{ color: var(--ig); }}
  .footer-bottom {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 24px;
    border-top: 1px solid var(--ig-light);
  }}
  .footer-copy {{
    font-size: 13px;
    color: var(--ig-ink-3);
  }}
  .footer-legal {{
    display: flex;
    gap: 24px;
  }}
  .footer-legal a {{
    font-size: 13px;
    color: var(--ig-ink-3);
    text-decoration: none;
    transition: color 0.3s ease;
  }}
  .footer-legal a:hover {{ color: var(--ig); }}

  @media (max-width: 900px) {{
    nav {{ padding: 16px 24px; }}
    .nav-links {{ display: none; }}
    section {{ padding: 60px 24px; }}
    .blog-grid {{ grid-template-columns: repeat(2, 1fr); gap: 16px; }}
    .archive-scroll-container {{ max-height: 520px; }}
    footer {{ padding: 48px 24px 24px; }}
    .footer-main {{ grid-template-columns: 1fr 1fr; gap: 32px; }}
    .footer-bottom {{ flex-direction: column; gap: 12px; text-align: center; }}
  }}
  @media (max-width: 600px) {{
    .blog-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<nav id="navbar">
  <a href="index.html" class="nav-logo">
    <img src="logo-nav-crop.png" alt="INITIUM" height="56" style="background:transparent;">
  </a>
  <ul class="nav-links">
    <li><a href="about.html">About</a></li>
    <li><a href="services.html">Services</a></li>
    <li><a href="new-launches.html">New Launches</a></li>
    <li><a href="team.html">Team</a></li>
    <li><a href="join.html">Join Us</a></li>
    <li><a href="blog.html">Pulse</a></li>
    <li><a href="intm-studio.html">INTM Studio</a></li>
    <li><a href="intm-shop.html">INTM Shop</a></li>
    <li><a href="contact.html">Contact</a></li>
  </ul>
</nav>

<div class="page-hero">
  <div class="page-hero-label">Market Watch</div>
  <h1 class="page-hero-title">Property News Archive</h1>
  <p class="page-hero-sub">Past headlines from The Straits Times, CNA, and EdgeProp.</p>
  <a href="blog.html" class="archive-link">&larr; Back to Pulse</a>
</div>

<section style="background:#fff;">
  <div class="section-inner">
    <div class="section-header">
      <div>
        <div class="section-subheader">Archive</div>
        <h2 class="section-title">Past Headlines</h2>
      </div>
      <div class="archive-count">{len(archived)} articles</div>
    </div>
    <div class="archive-scroll-container">
      <div class="archive-search">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input type="text" id="archiveSearch" placeholder="Search keywords... (e.g. HDB, condo, ABSD)" autocomplete="off">
        <button class="archive-search-clear" id="searchClear" aria-label="Clear search">&times;</button>
      </div>
      <div class="blog-grid" id="archiveGrid">

{archive_grid}

      </div>
    </div>
  </div>
</section>

<footer>
  <div class="footer-main">
    <div class="footer-brand">
      <div style="font-family:var(--font-display); font-weight:700; font-size:20px; color:var(--ig);">INITIUM</div>
      <p style="font-size:13px; color:var(--ig-ink-3); margin-top:8px; max-width:240px;">Igniting Journeys</p>
    </div>
    <div class="footer-col">
      <div class="footer-col-title">Explore</div>
      <a href="index.html">Home</a>
      <a href="about.html">About</a>
      <a href="services.html">Services</a>
      <a href="new-launches.html">New Launches</a>
    </div>
    <div class="footer-col">
      <div class="footer-col-title">Company</div>
      <a href="team.html">Team</a>
      <a href="join.html">Join Us</a>
      <a href="blog.html">Pulse</a>
      <a href="contact.html">Contact</a>
    </div>
    <div class="footer-col">
      <div class="footer-col-title">Connect</div>
      <a href="https://wa.me/6588464814" target="_blank">WhatsApp</a>
      <a href="https://www.instagram.com/initium.grp" target="_blank">Instagram</a>
      <a href="mailto:hello@initium.sg">Email</a>
    </div>
  </div>
  <div class="footer-bottom">
    <div class="footer-copy">&copy; 2026 INITIUM. Igniting Journeys.</div>
    <div class="footer-legal">
      <a href="#">Privacy</a>
      <a href="#">Terms</a>
    </div>
  </div>
</footer>

<script>
  // Nav scroll effect
  window.addEventListener('scroll', function() {{
    document.getElementById('navbar').classList.toggle('scrolled', window.scrollY > 40);
  }});

  // Archive search
  (function() {{
    var searchInput = document.getElementById('archiveSearch');
    var searchClear = document.getElementById('searchClear');
    var grid = document.getElementById('archiveGrid');
    var countEl = document.querySelector('.archive-count');
    if (!searchInput || !grid) return;

    var cards = grid.querySelectorAll('.blog-card');
    var originalCount = cards.length;

    function filterArticles(query) {{
      query = query.toLowerCase().trim();
      var visible = 0;

      cards.forEach(function(card) {{
        var title = (card.querySelector('.blog-title') || {{}}).textContent || '';
        var excerpt = (card.querySelector('.blog-excerpt') || {{}}).textContent || '';
        var tag = (card.querySelector('.blog-tag') || {{}}).textContent || '';
        var text = (title + ' ' + excerpt + ' ' + tag).toLowerCase();

        if (!query || text.indexOf(query) !== -1) {{
          card.style.display = '';
          visible++;
        }} else {{
          card.style.display = 'none';
        }}
      }});

      // Toggle empty state
      var existing = grid.querySelector('.archive-empty');
      if (visible === 0) {{
        if (!existing) {{
          var p = document.createElement('p');
          p.className = 'archive-empty';
          p.style.cssText = 'color:var(--ig-ink-3); text-align:center; padding:60px 0; grid-column:1/-1;';
          p.textContent = 'No articles match your search.';
          grid.appendChild(p);
        }}
      }} else if (existing) {{
        existing.remove();
      }}

      // Update count
      if (countEl) {{
        countEl.textContent = visible + (query ? ' of ' + originalCount : '') + ' article' + (visible !== 1 ? 's' : '');
      }}

      // Toggle clear button
      searchClear.classList.toggle('visible', query.length > 0);
    }}

    searchInput.addEventListener('input', function() {{
      filterArticles(this.value);
    }});

    searchClear.addEventListener('click', function() {{
      searchInput.value = '';
      filterArticles('');
      searchInput.focus();
    }});
  }})();
</script>

</body>
</html>'''

    with open(ARCHIVE_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return True


def git_deploy():
    for cmd in [
        ["git", "add", "-A"],
        ["git", "commit", "-m", "Auto: hourly property news update"],
        ["git", "push"],
    ]:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR)
        if result.returncode != 0:
            if "nothing to commit" in result.stdout.lower() or "nothing to commit" in result.stderr.lower():
                continue
            print(f"  Git error ({cmd[1]}): {result.stderr.strip()}")
            return False
    return True


def main():
    print("[1/7] Loading existing articles...")
    existing = load_articles()
    print(f"      {len(existing)} articles in database")

    print("[2/7] Fetching ST property news...")
    st_new = fetch_google_news_rss("site:straitstimes.com Singapore property")
    for a in st_new:
        a["source_tag"] = "ST"
    st_new = [a for a in st_new if is_property_article(a["title"])]
    print(f"      {len(st_new)} property articles")

    print("[3/7] Fetching CNA property news...")
    cna_new = fetch_google_news_rss("site:channelnewsasia.com Singapore property")
    for a in cna_new:
        a["source_tag"] = "CNA"
    cna_new = [a for a in cna_new if is_property_article(a["title"])]
    print(f"      {len(cna_new)} property articles")

    print("[4/7] Fetching EdgeProp news...")
    ep_new = fetch_google_news_rss("site:edgeprop.sg Singapore property")
    for a in ep_new:
        a["source_tag"] = "EdgeProp"
    ep_new = [a for a in ep_new if is_property_article(a["title"])]
    print(f"      {len(ep_new)} property articles")

    # Merge and dedupe
    all_articles = dedupe_by_url(existing + st_new + cna_new + ep_new)
    print(f"\n      Total unique articles: {len(all_articles)}")

    # Prune articles older than 7 days
    print("[5/6] Pruning old articles...")
    all_articles = prune_old_articles(all_articles)

    # Classify by PUBLICATION date
    fresh, archived = classify_articles(all_articles)
    print(f"      Fresh (<48h): {len(fresh)}")
    print(f"      Archived (≥48h): {len(archived)}")

    print("[6/6] Regenerating pages...")
    ok1 = update_blog_html(fresh)
    ok2 = generate_archive_html(archived)
    save_articles(all_articles)
    if not ok1:
        print("      WARNING: blog.html update failed")
    if not ok2:
        print("      WARNING: archive.html generation failed")

    print("[7/7] Done. Changes left uncommitted (daily pusher handles sync).")


if __name__ == "__main__":
    main()
