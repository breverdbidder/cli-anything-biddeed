#!/usr/bin/env python3
"""
SHARD-8, run 6288: Sumter County metric-I residual fix attempt.

BACKGROUND: sumter is at 9/10 (only I fails, 90.9%, card_complete=10 of 11).
The one incomplete card is case 2025-CA-000255 (Wildwood Phase One LLC / 
TL Gulf Coast Holdings LLC), which has NO parcel_id (E also fails for this case at 90.9%).
Multiple prior sessions (4+) confirmed all standard sources are blocked:
  - qpublic.schneidercorp.com: Cloudflare 403
  - hamiltonpa.com: N/A (wrong county)
  - Sumter GIS (app.sumterpa.com): no parcels/ownership layer
  - FL GIO OWN_NAME filter: HTTP 400 (platform limitation)
  - myfloridacounty.com OCRS: Cloudflare Turnstile

NEW ANGLES TO TRY THIS SESSION:
1. Sumter County's ArcGIS Geocoder (VERIFIED live by shard14 session) -- try
   reverse-geocoding "Wildwood" subdivision legal description.
   URL: https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/Sumter_Geocoder/GeocodeServer
   Approach: addressToLocations with "Phase One" or "Wildwood" in singleLine.
   
2. FL GIO Statewide Cadastral FeatureServer -- try CO_NO=60 (Sumter) with a 
   smaller page size and retry logic, looking for PARCEL_ID containing a text
   hint that matches "Wildwood" or the case. The statewide layer DOES have real
   sumter parcels (shard9 verified 10 sumter parcels via CO_NO=70 cross-match
   by OWN_NAME against R14X015/G03A014 etc.).
   
3. Sumter County's own development services ArcGIS (the FLU layer that shard14 
   refire found: DevelopmentServices/Development_Services/MapServer/5).
   Try querying MapServer/5 (Future Land Use) for features where the 
   owner/address contains "Wildwood Phase One" -- might have an attribute filter.

4. Florida Department of State Sunbiz -- look for "Wildwood Phase One LLC" registered
   agent address which might give us the parcel location.
   URL: search.sunbiz.org/Inquiry/CorporationSearch/ByName

dispatch_id: 3e3d7776-a97e-4894-bacf-d416d23ea407 (shard-8, run 6288)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTY = "sumter"
SB_URL = (os.environ.get("SUPABASE_URL") or "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or ""
CASE_NUMBER = "2025-CA-000255"
BASE = f"{SB_URL}/rest/v1"
HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}
FLGIO_URL = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
SUMTER_GEOCODER = "https://gis.sumtercountyfl.gov/sumtergis/rest/services/Operations/Sumter_Geocoder/GeocodeServer/findAddressCandidates"
SUMTER_FLU = "https://services.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Development_Services/MapServer/5/query"


def ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def http_get(url: str, params: dict, timeout: int = 25) -> dict:
    full_url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}
    except Exception as e:
        return {"error": str(e)}


def evaluate_county() -> dict:
    url = f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"county_slug_arg": COUNTY}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"  evaluate_county error: {e}")
        return {}


def sb_patch(case_number: str, payload: dict) -> bool:
    url = f"{BASE}/multi_county_auctions?case_number=eq.{case_number}&county=eq.{COUNTY}"
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=dict(HEADERS), method="PATCH")
    req.remove_header("Prefer")
    req.add_header("Prefer", "return=minimal")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            log(f"  PATCH {case_number}: HTTP {r.status}")
            return r.status in (200, 204)
    except urllib.error.HTTPError as e:
        log(f"  PATCH {case_number} error: HTTP {e.code} {e.read().decode()[:200]}")
        return False


def main() -> None:
    if not SB_KEY:
        log("ERROR: SUPABASE_KEY not set")
        sys.exit(1)

    log("=== SHARD-8 run-6288: Sumter I fix — Wildwood Phase One LLC parcel probe ===")

    # Baseline
    log("--- BASELINE pencil_dod_evaluate_county('sumter') ---")
    baseline = evaluate_county()
    log(json.dumps(baseline, indent=2))

    # 1) Sumter County ArcGIS Geocoder: try to locate "Wildwood Phase One"
    log("--- Attempt 1: Sumter ArcGIS Geocoder ---")
    for query in ["Wildwood Phase One, Wildwood, FL", "Wildwood Phase One LLC, FL 34785"]:
        log(f"  Geocoder query: {query!r}")
        result = http_get(SUMTER_GEOCODER, {
            "SingleLine": query,
            "f": "json",
            "outFields": "Addr_type,Score",
            "outSR": "4326",
            "maxLocations": "5",
        })
        candidates = result.get("candidates", [])
        log(f"  -> {len(candidates)} candidates")
        for c in candidates[:3]:
            log(f"    score={c.get('score')} addr={c.get('address')} loc={c.get('location')}")
        if candidates and candidates[0].get("score", 0) >= 80:
            log("  HIGH-CONFIDENCE geocode found - investigating further")
            best = candidates[0]
            loc = best.get("location", {})
            lon, lat = loc.get("x"), loc.get("y")
            if lat and lon:
                log(f"  Candidate location: lat={lat}, lon={lon}")

    # 2) FL GIO Statewide Cadastral: try OWN_NAME partial match via WHERE clause
    # (Previous sessions confirmed OWN_NAME filter returns HTTP 400 on this layer,
    # but try a very small CO_NO=60 page to discover the PARCEL_ID format for Sumter)
    log("--- Attempt 2: FL GIO Statewide Cadastral (CO_NO=60, small page) ---")
    result = http_get(FLGIO_URL, {
        "where": "CO_NO=60",
        "outFields": "PARCEL_ID,OWN_NAME,PHY_ADDR1,PHY_CITY,JV,AV_SD",
        "returnGeometry": "false",
        "resultRecordCount": "5",
        "resultOffset": "0",
        "f": "json",
        "outSR": "4326",
    }, timeout=30)
    features = result.get("features", [])
    log(f"  CO_NO=60 sample: {len(features)} features")
    for f in features[:5]:
        attrs = f.get("attributes", {})
        log(f"    PARCEL_ID={attrs.get('PARCEL_ID')} OWN_NAME={attrs.get('OWN_NAME')} PHY_ADDR1={attrs.get('PHY_ADDR1')}")
    if result.get("error"):
        log(f"  FL GIO error: {result.get('error')}")

    # 3) Try OWN_NAME filter anyway (known to fail, but the format may have changed)
    log("--- Attempt 3: FL GIO OWN_NAME filter for Wildwood Phase One ---")
    for owner_query in ["WILDWOOD PHASE ONE%", "TL GULF COAST%"]:
        result = http_get(FLGIO_URL, {
            "where": f"CO_NO=60 AND OWN_NAME LIKE '{owner_query}'",
            "outFields": "PARCEL_ID,OWN_NAME,PHY_ADDR1,JV,AV_SD",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        }, timeout=25)
        features = result.get("features", [])
        if features:
            log(f"  OWN_NAME LIKE '{owner_query}': {len(features)} features FOUND!")
            for feat in features[:3]:
                attrs = feat.get("attributes", {})
                geom = feat.get("geometry", {})
                log(f"    PARCEL_ID={attrs.get('PARCEL_ID')} OWN_NAME={attrs.get('OWN_NAME')} "
                    f"PHY_ADDR1={attrs.get('PHY_ADDR1')} JV={attrs.get('JV')}")
                if geom:
                    log(f"    geometry={json.dumps(geom)[:200]}")
        else:
            log(f"  OWN_NAME LIKE '{owner_query}': {result.get('error', 'no results')}")

    # 4) Sunbiz search for Wildwood Phase One LLC
    log("--- Attempt 4: Sunbiz entity lookup for Wildwood Phase One LLC ---")
    sunbiz_url = "https://search.sunbiz.org/Inquiry/CorporationSearch/ByName"
    full_url = sunbiz_url + "?" + urllib.parse.urlencode({
        "inquiryType": "EntityName",
        "inquiryDirectionType": "ForwardList",
        "searchNameOrder": "WILDWOOD PHASE ONE",
        "aggregateId": "",
        "searchTerm": "wildwood phase one",
        "listNameOrder": "WILDWOOD PHASE ONE",
    })
    req = urllib.request.Request(full_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode(errors="replace")
            if "WILDWOOD PHASE ONE" in html.upper():
                log("  Sunbiz: 'WILDWOOD PHASE ONE' found in page")
                # Extract registered agent address lines
                import re
                # Look for address patterns near the entity name
                idx = html.upper().find("WILDWOOD PHASE ONE")
                snippet = html[max(0, idx-200):idx+1000]
                log(f"  Sunbiz snippet: {snippet[:600]!r}")
            else:
                log("  Sunbiz: entity not found")
    except Exception as e:
        log(f"  Sunbiz error: {e}")

    # 5) Final evaluation
    log("--- AFTER pencil_dod_evaluate_county('sumter') ---")
    after = evaluate_county()
    log(json.dumps(after, indent=2))

    before_i = baseline.get("I", {})
    after_i = after.get("I", {})
    log(f"I: {before_i} -> {after_i}")
    before_e = baseline.get("E", {})
    after_e = after.get("E", {})
    log(f"E: {before_e} -> {after_e}")


if __name__ == "__main__":
    main()
