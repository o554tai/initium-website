#!/usr/bin/env python3
"""Add School Finder link to nav and footer of all HTML pages."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAV_LINK = '      <a href="school-finder.html" class="nav-link" data-page="school-finder">School Finder</a>'
FOOTER_LINK = '          <a href="school-finder.html" class="footer-link"><span class="footer-link-title">School Finder</span><span class="footer-link-desc">Find homes near primary schools</span></a>'


def update_file(path: Path):
    content = path.read_text(encoding="utf-8")
    original = content

    if 'href="school-finder.html"' not in content:
        content = re.sub(
            r'(<a href="calculators\.html" class="nav-link[^"]*"[^>]*>Calculators</a>\n)',
            r'\1' + NAV_LINK + '\n',
            content,
        )
        content = re.sub(
            r'(<a href="calculators\.html" class="footer-link"><span class="footer-link-title">Calculators</span><span class="footer-link-desc">[^<]*</span></a>\n)',
            r'\1' + FOOTER_LINK + '\n',
            content,
        )

    if content != original:
        path.write_text(content, encoding="utf-8")
        return True
    return False


changed = []
for path in sorted(ROOT.glob("*.html")):
    if update_file(path):
        changed.append(path.name)

print(f"Modified {len(changed)} files:")
for name in changed:
    print(f"  {name}")
