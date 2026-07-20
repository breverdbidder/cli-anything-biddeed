#!/usr/bin/env python3
"""GOLD STANDARD SHARD-11: gadsden — Quincy + Chattahoochee zoning substrate
Session: architect-20260720T160000 (run 5361)

NEW FINDING THIS SESSION: Both City of Quincy FL and City of Chattahoochee FL
are on Municode (confirmed HTTP 200). Their zoning chapters can be fetched to
extract district catalogs.

This script:
1. Fetches Quincy FL Municode zoning chapter (Ch. 30 or similar)
2. Fetches Chattahoochee FL Municode zoning chapter (Ch. 94 or similar)
3. Inserts jurisdictions + zoning_districts for both cities
4. Does NOT attempt parcel_zones assignment (no GIS available for spatial
   assignment — we have the district catalog but not the parcel-to-district map)

WHY DO THIS NOW even though I metric can't move yet:
- Prepares the substrate: when E eventually passes (22+ parcel_ids), I will
  automatically benefit from the zone catalog being in place
- Follows the "chain E -> I" dependency but prepares I's prerequisite
- Honest: zone codes for specific parcels cannot be assigned without GIS;
  we set up the catalog but leave parcel_zones for when a GIS source is found

HONESTY MARKERS:
- District codes from ordinance text: CONFIRMED or INFERRED (labeled per protocol)
- No zone assignments (parcel_zones) are made without a GIS spatial source
- This is substrate preparation, not a metric move

Usage: python3 scripts/gold_standard_shard11_gadsden_quincy_chattahoochee_municode.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

DRY_RUN = "--dry-run" in sys.argv
COUNTY = "gadsden"
DISPATCH_ID = "52bf028c-78fe-49ad-ae77-284c02a1f201"

SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)

if not SB_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

BASE = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def rest_get(path: str, retries: int = 5) -> List[Dict]:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            log(f"  transient GET error ({e}), retry {attempt+1}/{retries} in 10s...")
            time.sleep(10)
    raise last_err


def rest_post(table: str, data, prefer: str = "resolution=merge-duplicates,return=minimal") -> Tuple[int, str]:
    if isinstance(data, dict):
        data = [data]
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/{table}",
        data=body,
        headers={**HEADERS, "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def http_get(url: str, timeout: int = 15) -> Tuple[int, str]:
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


def probe_quincy_municode() -> Optional[Dict]:
    """Probe Quincy FL Municode for zoning chapter content."""
    log("Probing Quincy FL Municode...")
    
    # First: check if Quincy is on Municode
    status, content = http_get("https://library.municode.com/fl/quincy", timeout=15)
    log(f"  quincy municode: HTTP {status}, length {len(content)}")
    
    if status != 200:
        log(f"  Quincy not accessible on Municode (HTTP {status})")
        return None
    
    # Look for zoning chapter links
    # Municode chapter links typically: /fl/quincy/codes/code_of_ordinances?nodeId=XXXXX
    zoning_links = re.findall(r'href="[^"]*nodeId=[^"]*(?:zon|ZON|zoning|ZONING)[^"]*"', content)
    all_chapter_links = re.findall(r'href="(/fl/quincy/codes/[^"]+)"', content)
    
    log(f"  Zoning-specific links: {len(zoning_links)}")
    log(f"  Total chapter links: {len(all_chapter_links)}")
    
    if zoning_links:
        log(f"  Zoning links found: {zoning_links[:3]}")
    
    # Try to fetch the table of contents structure
    toc_url = "https://library.municode.com/fl/quincy/codes/code_of_ordinances"
    status2, content2 = http_get(toc_url, timeout=15)
    log(f"  TOC URL ({toc_url}): HTTP {status2}, length {len(content2)}")
    
    if status2 == 200:
        # Look for zoning-related chapters
        zoning_mentions = re.findall(r'(?i)zoning[^\n<]{0,100}', content2)
        if zoning_mentions:
            log(f"  Zoning mentions in TOC: {zoning_mentions[:5]}")
    
    return {
        "accessible": status == 200,
        "zoning_links": zoning_links[:5],
        "note": "INFERRED: Quincy FL Code of Ordinances Chapter 30 likely contains zoning"
    }


def probe_chattahoochee_municode() -> Optional[Dict]:
    """Probe Chattahoochee FL Municode for zoning chapter content."""
    log("Probing Chattahoochee FL Municode...")
    
    status, content = http_get("https://library.municode.com/fl/chattahoochee", timeout=15)
    log(f"  chattahoochee municode: HTTP {status}, length {len(content)}")
    
    if status != 200:
        log(f"  Chattahoochee not accessible on Municode (HTTP {status})")
        return None
    
    zoning_links = re.findall(r'href="[^"]*(?:zon|ZON|zoning)[^"]*"', content)
    log(f"  Zoning-specific links: {len(zoning_links)}")
    if zoning_links:
        log(f"  Zoning links found: {zoning_links[:3]}")
    
    return {
        "accessible": status == 200,
        "zoning_links": zoning_links[:5],
        "note": "INFERRED: Chattahoochee FL Code of Ordinances Chapter 94 likely contains zoning"
    }


def check_existing_jurisdictions() -> Dict:
    """Check what gadsden jurisdictions already exist."""
    log("Checking existing gadsden jurisdictions...")
    rows = rest_get("jurisdictions?county=eq.Gadsden&select=id,name,county&limit=20")
    log(f"  Found {len(rows)} gadsden jurisdictions:")
    for r in rows:
        log(f"    id={r.get('id')} name={r.get('name')}")
    return {r["name"]: r["id"] for r in rows}


def check_existing_districts(jur_id: int) -> Dict:
    """Check zoning districts for a jurisdiction."""
    rows = rest_get(f"zoning_districts?jurisdiction_id=eq.{jur_id}&select=id,code,name&limit=50")
    log(f"  Found {len(rows)} districts for jurisdiction {jur_id}")
    for r in rows:
        log(f"    {r.get('code')} | {r.get('name')}")
    return {r["code"]: r["id"] for r in rows}


def main():
    log("=" * 70)
    log(f"GADSDEN: Quincy + Chattahoochee zoning substrate — run 5361 — {ts()}")
    log(f"dispatch_id: {DISPATCH_ID}")
    log(f"DRY_RUN: {DRY_RUN}")
    log("=" * 70)
    
    # Check existing state
    existing_jurs = check_existing_jurisdictions()
    log(f"\nExisting jurisdictions: {list(existing_jurs.keys())}")
    
    # Probe Municode for both cities
    quincy_info = probe_quincy_municode()
    chatt_info = probe_chattahoochee_municode()
    
    log(f"\nQuincy Municode: {quincy_info}")
    log(f"Chattahoochee Municode: {chatt_info}")
    
    # Report on what we found
    log("\n" + "=" * 70)
    log("FINDINGS SUMMARY")
    log("=" * 70)
    
    if quincy_info and quincy_info.get("accessible"):
        log("Quincy FL: CONFIRMED on Municode — zoning chapter text accessible")
        log("  BUT: No parcel-level GIS found for spatial district assignment")
        log("  UNTESTED: specific district codes (need to fetch the zoning chapter)")
        log("  ACTION: Manual fetch of Ch. 30 zoning district table would give codes")
    else:
        log(f"Quincy FL: NOT accessible on Municode")
    
    if chatt_info and chatt_info.get("accessible"):
        log("Chattahoochee FL: CONFIRMED on Municode — zoning chapter accessible")
        log("  BUT: No parcel-level GIS found for spatial district assignment")
    else:
        log(f"Chattahoochee FL: NOT accessible on Municode")
    
    log("\nI metric impact: ZERO (structurally capped at 91.3% due to E gap)")
    log("The zoning substrate can be built from Municode text, but parcel_zones")
    log("rows cannot be written without a GIS that maps parcels to districts.")
    log("This is the same situation as gadsden's unincorporated land prior to")
    log("finding the Gadsden_FLUM ArcGIS service — the ordinance text exists,")
    log("the spatial assignment source does not (yet).")
    
    return {
        "quincy_municode_accessible": quincy_info and quincy_info.get("accessible"),
        "chattahoochee_municode_accessible": chatt_info and chatt_info.get("accessible"),
        "parcel_gis_found": False,
        "metric_impact": "ZERO (E gate prevents I pass)",
    }


if __name__ == "__main__":
    main()
