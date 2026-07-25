#!/usr/bin/env python3
"""
SHARD-9 COLLIER G — LDC FAR probe for C-4/C-5
dispatch_id: 7425b4a1-fdfc-4f13-a414-cc9cefc81307

Strategy: try the api.municode.com JSON API endpoint found by the 2nd firing session
to get the full text of LDC Sec 4.02.01 Table 2 for C-4/C-5 FAR values.

The 2nd firing confirmed:
- api.municode.com/CodesContent is reachable directly (even though library.municode.com is a dead SPA)
- C-4 row shows "Hotels .60" / "Destination resort .80"
- C-5 shows same pattern

We want to know: does the LDC have any "base" or "unlisted use" FAR for C-4/C-5?
Or are Hotels and Destination Resort the ONLY uses that trigger FAR?

Also probe for MH and RSF density values from Sec 2.03.02 Table 1 (lot standards).
Note: density_regulated for MH/RSF-3/4/5 doesn't help G since FAR is the binding constraint.
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request
import urllib.error

def log(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)

def web_get(url: str, timeout: int = 20) -> tuple[int, str]:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP {e.code}: {e.reason}"
    except Exception as ex:
        return 0, str(ex)


# ── 1. Try api.municode.com directly ─────────────────────────────────────────
log("=== Probing api.municode.com for Collier LDC Sec 4.02.01 ===")

# Known working endpoint from 2nd firing session
mc_endpoints = [
    "https://api.municode.com/CodesContent?productId=13816&nodeId=Ch4.02&format=HTML",
    "https://api.municode.com/CodesContent?productId=13816&nodeId=Ch4.02.01&format=HTML",
    "https://api.municode.com/CodesContent?productId=13816&nodeId=4.02.01&format=HTML",
]

for ep in mc_endpoints:
    log(f"  GET {ep}")
    status, body = web_get(ep, timeout=15)
    log(f"  -> HTTP {status}, body len={len(body)}")
    if status == 200:
        # Look for C-4, C-5, FAR mentions
        lower = body.lower()
        if "floor area" in lower or "c-4" in lower or "c-5" in lower:
            log("  FOUND relevant content!")
            # Extract relevant section
            idx = body.find("Floor Area")
            if idx < 0:
                idx = body.find("C-4")
            if idx >= 0:
                log(f"  Context: {body[max(0,idx-200):idx+500]}")
        else:
            log(f"  Body preview: {body[:300]}")
    else:
        log(f"  Failed: {body[:100]}")

# ── 2. Try elaws.us (may have recovered) ─────────────────────────────────────
log("\n=== Probing elaws.us for Collier LDC Sec 4.02.01 ===")

elaws_endpoints = [
    "http://colliercounty.elaws.us/code/ldc_ch4_4.02.00_sec4.02.01",
    "https://colliercounty.elaws.us/code/ldc_ch4_4.02.00_sec4.02.01",
    "http://colliercounty.elaws.us/code/ldc",
]
for ep in elaws_endpoints:
    log(f"  GET {ep}")
    status, body = web_get(ep, timeout=10)
    log(f"  -> HTTP {status}, body len={len(body)}")
    if status == 200:
        lower = body.lower()
        if "floor area" in lower or "c-4" in lower:
            idx = body.lower().find("floor area")
            log(f"  Context: {body[max(0,idx-100):idx+300]}")
        else:
            log(f"  Body preview: {body[:200]}")

# ── 3. Try Wayback Machine for Collier LDC Table 2 ───────────────────────────
log("\n=== Probing Wayback Machine for Collier LDC archived version ===")

wayback_urls = [
    "https://web.archive.org/web/20251221043346/http://colliercounty.elaws.us/code/ldc_ch4_4.02.00_sec4.02.01",
    "https://web.archive.org/web/2025/http://colliercounty.elaws.us/code/ldc_ch4_4.02.00_sec4.02.01",
]
for ep in wayback_urls[:1]:  # Just try the first
    log(f"  GET {ep}")
    status, body = web_get(ep, timeout=15)
    log(f"  -> HTTP {status}, body len={len(body)}")
    if status == 200 and len(body) > 1000:
        lower = body.lower()
        if "floor area" in lower:
            idx = body.lower().find("floor area")
            log(f"  Context: {body[max(0,idx-100):idx+600]}")
        elif "c-4" in lower or "c-5" in lower:
            idx = body.lower().find("c-4")
            log(f"  C-4 context: {body[max(0,idx-50):idx+200]}")
        else:
            log(f"  Body preview: {body[:300]}")
    else:
        log(f"  Failed or too short: {body[:100]}")

# ── 4. Check Collier county GIS for C-4/C-5 parcel actual DOR use code ───────
log("\n=== Probing FL GIO for C-4/C-5 Collier parcels actual use ===")
# Prior scripts show C-4 parcel_ids include commercial parcels
# DOR use code (DOR_UC) from the FL statewide cadastral can tell us the actual use

arcgis_url = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
    "?where=CO_NO%3D21%20AND%20PARCEL_ID%20IN%20('00205350003','00205360009')"
    "&outFields=PARCEL_ID,DOR_UC,PHY_ADDR1,PHY_CITY,JV,AV_SD&f=json&outSR=4326"
)
log(f"  GET {arcgis_url[:150]}...")
status, body = web_get(arcgis_url, timeout=20)
log(f"  -> HTTP {status}, body len={len(body)}")
if status == 200:
    try:
        data = json.loads(body)
        features = data.get("features", [])
        log(f"  Found {len(features)} features")
        for f in features[:5]:
            attrs = f.get("attributes", {})
            log(f"  PARCEL_ID={attrs.get('PARCEL_ID')} DOR_UC={attrs.get('DOR_UC')} ADDR={attrs.get('PHY_ADDR1')} CITY={attrs.get('PHY_CITY')}")
    except Exception as e:
        log(f"  Parse error: {e}")
        log(f"  Body: {body[:300]}")
else:
    log(f"  Failed: {body[:100]}")

# ── 5. Hamilton Tax Collector probe ─────────────────────────────────────────
log("\n=== Hamilton Tax Collector probe ===")
tc_url = "https://www.hamiltoncountytaxcollector.com/Property/search"
try:
    import urllib.parse
    post_data = urllib.parse.urlencode({
        "ownername": "", "streetnumber": "1658", "streetname": "3RD",
        "propertynumber": "", "taxbillnumber": "", "RollTypes": "", "Years": "2025",
    }).encode()
    req = urllib.request.Request(
        tc_url,
        data=post_data,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        status = r.status
        body = r.read().decode("utf-8", errors="replace")
    log(f"  POST {tc_url} -> HTTP {status}, body len={len(body)}")
    if status == 200:
        try:
            outer = json.loads(body)
            inner_str = outer.get("result", "{}")
            inner = json.loads(inner_str) if inner_str else {}
            rows = inner.get("FLTax", {}).get("ResultsList", [])
            if isinstance(rows, dict):
                rows = [rows]
            log(f"  Results: {len(rows)} row(s)")
            for row in rows[:3]:
                log(f"  -> {row}")
        except Exception as e:
            log(f"  Parse error: {e}")
            log(f"  Body preview: {body[:300]}")
    else:
        log(f"  Body: {body[:200]}")
except Exception as e:
    log(f"  TC probe failed: {e}")

# ── 6. Hamilton myfloridacounty.com official records probe ───────────────────
log("\n=== Hamilton myfloridacounty.com ORI probe ===")
# myfloridacounty.com/orisearch/24 — official records index, Hamilton county=24
# This was documented as JS/session-driven, but let's get the raw HTML
mfc_url = "https://www.myfloridacounty.com/ori/search/type/result.do?cId=24&doSearch=true&cType=official"
log(f"  GET {mfc_url}")
status, body = web_get(mfc_url, timeout=15)
log(f"  -> HTTP {status}, body len={len(body)}")
if status == 200:
    log(f"  Body preview: {body[:400]}")
else:
    log(f"  Failed: {body[:100]}")

log("\n=== PROBE COMPLETE ===")
