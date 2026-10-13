#!/usr/bin/env python3
"""Download MOE school data from data.gov.sg and geocode primary schools via OneMap."""
import requests
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DATASET_ID = "d_688b934f82c1059ed0a6993d2a829089"
URL = f"https://data.gov.sg/api/action/datastore_search?resource_id={DATASET_ID}&limit=500"


def geocode(query: str, retries: int = 5):
    """Geocode a query via OneMap with exponential backoff."""
    for attempt in range(retries):
        try:
            sr = requests.get(
                "https://www.onemap.gov.sg/api/common/elastic/search",
                params={"searchVal": query, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1},
                timeout=15,
            )
            if sr.status_code == 429:
                wait = 2 * (2 ** attempt)
                print(f"    429, waiting {wait}s...")
                time.sleep(wait)
                continue
            sr.raise_for_status()
            results = sr.json().get("results", [])
            if results:
                best = results[0]
                return float(best.get("LATITUDE", 0)), float(best.get("LONGITUDE", 0))
            return None, None
        except Exception as e:
            print(f"    Error (attempt {attempt + 1}): {e}")
            time.sleep(1 * (2 ** attempt))
    return None, None


print("Fetching school data...")
r = requests.get(URL, timeout=30)
r.raise_for_status()
data = r.json()
records = data["result"]["records"]
print(f"Got {len(records)} schools")

primary = [r for r in records if "primary" in r.get("mainlevel_code", "").lower()]
print(f"Primary schools: {len(primary)}")

geocoded = []
for i, school in enumerate(primary, 1):
    name = school.get("school_name", "").strip()
    address = school.get("address", "").strip()
    postal = school.get("postal_code", "").strip()
    query = f"{address} SINGAPORE {postal}".strip()

    print(f"[{i}/{len(primary)}] {name}")
    lat, lng = geocode(query)
    if lat is None:
        # fallback: search by school name
        lat, lng = geocode(name)

    geocoded.append({
        "name": name,
        "address": address,
        "postal": postal,
        "lat": lat,
        "lng": lng,
        "zone": school.get("zone_code", ""),
        "type": school.get("type_code", ""),
        "nature": school.get("nature_code", ""),
        "session": school.get("session_code", ""),
        "sap": school.get("sap_ind", "") == "Yes",
        "autonomous": school.get("autonomous_ind", "") == "Yes",
        "gifted": school.get("gifted_ind", "") == "Yes",
        "mrt": school.get("mrt_desc", ""),
        "url": school.get("url_address", ""),
    })
    time.sleep(0.5)

missing = [s for s in geocoded if s["lat"] is None]
print(f"\nGeocoded {len(geocoded) - len(missing)} / {len(geocoded)} schools")
print(f"Missing coordinates: {len(missing)}")
if missing:
    print("Missing:", [s["name"] for s in missing[:20]])

output_path = DATA_DIR / "primary-schools.json"
with open(output_path, "w") as f:
    json.dump(geocoded, f, indent=2)

print(f"Saved to {output_path}")
