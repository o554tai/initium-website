#!/bin/bash
set -e
cd /home/hermes/initium-website

echo "[$(date)] Running EcoProp scraper..."
/usr/bin/python3 ecoprop_scraper_v2.py

echo "[$(date)] Running SingMap scraper (backup)..."
/usr/bin/python3 singmap_scraper.py

echo "[$(date)] Done."
