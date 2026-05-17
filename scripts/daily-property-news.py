#!/usr/bin/env python3
"""Daily property news updater for INITIUM Pulse page.
Fetches fresh articles from ST, CNA, EdgeProp via Google News RSS
and updates the Property News carousel on blog.html.
"""
import requests
import xml.etree.ElementTree as ET
import re
from html import unescape
import subprocess
import sys

def fetch_google_news_rss(query):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=en-SG&gl=SG&ceid=SG:en"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        articles = []
        for item in root.findall('.//item'):
            title = item.find('title')
            link = item.find('link')
            pubDate = item.find('pubDate')
            source = item.find('source')
            if title is not None and link is not None:
                t = unescape(title.text or '')
                l = link.text or ''
                s = source.text if source is not None else ''
                d = pubDate.text if pubDate is not None else ''
                if any(y in d for y in ['2020', '2021', '2022', '2023', '2024']):
                    continue
                articles.append({'title': t, 'url': l, 'source': s, 'date': d})
        return articles
    except Exception as e:
        print(f"Error fetching {query}: {e}")
        return []

def pick_best(articles):
    for a in articles:
        title_lower = a['title'].lower()
        skip_words = ['football', 'sport', 'basketball', 'crash', 'train', 'election', 'war', 'iran', 'trump', 'tennis', 'golf']
        if any(x in title_lower for x in skip_words):
            continue
        property_words = ['property', 'home', 'hdb', 'condo', 'rental', 'land', 'flat', 'resale', 'launch', 'absd', 'bto', 'ura', 'ec ', 'executive condo']
        if any(x in title_lower for x in property_words):
            return a
    return articles[0] if articles else None

def make_excerpt(title):
    title = re.sub(r'\s*-\s*(The Straits Times|CNA|EdgeProp\.sg)$', '', title)
    words = title.split()
    if len(words) > 12:
        return ' '.join(words[:12]) + '...'
    return title

def main():
    print("[1/4] Fetching ST property news...")
    st = fetch_google_news_rss("site:straitstimes.com Singapore property")
    print(f"      Found {len(st)} articles")

    print("[2/4] Fetching CNA property news...")
    cna = fetch_google_news_rss("site:channelnewsasia.com Singapore property")
    print(f"      Found {len(cna)} articles")

    print("[3/4] Fetching EdgeProp news...")
    ep = fetch_google_news_rss("site:edgeprop.sg Singapore property")
    print(f"      Found {len(ep)} articles")

    st_article = pick_best(st)
    cna_article = pick_best(cna)
    ep_article = pick_best(ep)

    if not all([st_article, cna_article, ep_article]):
        print("ERROR: Could not fetch enough articles. Aborting.")
        sys.exit(1)

    print(f"\nSelected:")
    print(f"  ST: {st_article['title']}")
    print(f"  CNA: {cna_article['title']}")
    print(f"  EdgeProp: {ep_article['title']}")

    with open('blog.html', 'r') as f:
        content = f.read()

    new_cards = []
    for article, tag in [(st_article, 'ST'), (cna_article, 'CNA'), (ep_article, 'EdgeProp')]:
        title = re.sub(r'\s*-\s*(The Straits Times|CNA|EdgeProp\.sg)$', '', article['title'])
        display_title = title if len(title) < 90 else title[:87] + '...'
        excerpt = make_excerpt(title)
        img_url = {
            'ST': 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=600&h=400&fit=crop',
            'CNA': 'https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=600&h=400&fit=crop',
            'EdgeProp': 'https://images.unsplash.com/photo-1600573472550-8090b5e0745e?w=600&h=400&fit=crop'
        }.get(tag, 'https://images.unsplash.com/photo-1600585154526-990dced4db0d?w=600&h=400&fit=crop')

        new_cards.append(f'''      <a href="{article['url']}" class="blog-card" target="_blank" rel="noopener">
        <div class="blog-thumb">
          <img src="{img_url}" alt="{tag} property news" loading="lazy">
        </div>
        <div class="blog-content">
          <span class="blog-tag">{tag}</span>
          <h3 class="blog-title">{display_title}</h3>
          <p class="blog-excerpt">{excerpt}</p>
          <div class="blog-meta">{article['date'][:16]} &middot; Read on {tag}</div>
        </div>
      </a>''')

    new_carousel_html = '\n\n'.join(new_cards)
    pattern = r'(<div class="news-track" id="newsTrack">)\n\n(.*?)(\n      </div>)'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        old_content = match.group(0)
        new_content = match.group(1) + '\n\n' + new_carousel_html + match.group(3)
        content = content.replace(old_content, new_content)
        with open('blog.html', 'w') as f:
            f.write(content)
        print("\n[4/4] blog.html updated.")
    else:
        print("ERROR: Could not find news-track in blog.html")
        sys.exit(1)

    # Git commit and push
    result = subprocess.run(['git', 'add', 'blog.html'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git add failed: {result.stderr}")
        sys.exit(1)

    result = subprocess.run(['git', 'commit', '-m', 'Auto: daily property news update'], capture_output=True, text=True)
    if result.returncode != 0 and 'nothing to commit' not in result.stdout.lower():
        print(f"git commit failed: {result.stderr}")
        sys.exit(1)

    result = subprocess.run(['git', 'push'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git push failed: {result.stderr}")
        sys.exit(1)

    print("Deployed successfully.")

if __name__ == '__main__':
    main()
