#!/usr/bin/env python3
"""
sarasota_i_property_cards.py

Enrich sarasota MCA rows with real property card data from:
- Sarasota County Property Appraiser (SCPAO): https://www.sc-pa.com/
- SCPAO parcel search API: https://www.sc-pa.com/propertysearch/

Card completeness (criterion I) requires:
  - address IS NOT NULL
  - latitude IS NOT NULL
  - assessed_value IS NOT NULL
  - parcel_id is linked in parcel_zones (zone_code present)

This script handles the first three fields:
- address/geo: from MCA existing data or SCPAO geocode lookup
- assessed_value: from SCPAO parcel data

honesty_marker: VERIFIED for SCPAO-sourced values. UNTESTED for endpoints
that haven't been confirmed alive this session.

dispatch_id: shard6-sarasota-i-property-cards-20260720
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

DISPATCH_ID = "shard6-sarasota-i-property-cards-20260720"
COUNTY_SLUG = "sarasota"

SCPAO_BASE = "https://www.sc-pa.com"
SCPAO_SEARCH_URL = f"{SCPAO_BASE}/propertysearch/"

SARASOTA_CENTROID_LAT = 27.2080
SARASOTA_CENTROID_LON = -82.4559


def sb_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_patch(table, match_params, payload):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    if match_params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in match_params.items())
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="PATCH",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  PATCH {table} HTTP {e.code}: {e.read()[:200].decode()}")
        return e.code


def fetch_http(url, headers=None):
    req_headers = {"User-Agent": UA, "Accept": "application/json, text/html"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def fetch_scpao_parcel(parcel_id):
    """
    Try to fetch parcel data from SCPAO.
    Returns dict with {assessed_value, latitude, longitude, address} or None.
    SCPAO uses a standard FL property appraiser format.
    """
    clean_pid = re.sub(r"[^0-9]", "", parcel_id)
    if len(clean_pid) < 10:
        return None

    search_url = f"{SCPAO_SEARCH_URL}?parcel={urllib.parse.quote(clean_pid)}"
    status, body = fetch_http(search_url)
    if not status or status != 200:
        return None

    result = {}

    assessed_m = re.search(r'Just(?:ified)?\s+Value.*?\$([\d,]+)', body, re.IGNORECASE)
    if not assessed_m:
        assessed_m = re.search(r'Assessed\s+Value.*?\$([\d,]+)', body, re.IGNORECASE)
    if assessed_m:
        try:
            result["assessed_value"] = float(assessed_m.group(1).replace(",", ""))
        except ValueError:
            pass

    lat_m = re.search(r'"latitude"\s*:\s*([\d.]+)', body)
    lon_m = re.search(r'"longitude"\s*:\s*(-[\d.]+)', body)
    if lat_m and lon_m:
        try:
            result["latitude"] = float(lat_m.group(1))
            result["longitude"] = float(lon_m.group(1))
        except ValueError:
            pass

    addr_m = re.search(r'Site\s+Address.*?<td[^>]*>(.*?)</td>', body, re.IGNORECASE | re.DOTALL)
    if addr_m:
        addr = re.sub(r"<[^>]+>", " ", addr_m.group(1)).strip()
        addr = re.sub(r"\s+", " ", addr)
        if addr:
            result["property_address"] = addr

    return result if result else None


def fetch_mca_rows_needing_enrichment():
    """Fetch sarasota MCA rows missing assessed_value or lat/lon."""
    rows = []
    offset = 0
    page_size = 500
    while True:
        params = {
            "county": "eq.sarasota",
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value",
            "limit": str(page_size),
            "offset": str(offset),
        }
        batch = sb_get("multi_county_auctions", params)
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    needing_assessed = [r for r in rows if not r.get("assessed_value")]
    needing_geo = [r for r in rows if not r.get("latitude") or not r.get("longitude")]
    needing_any = list({r["case_number"]: r for r in needing_assessed + needing_geo}.values())

    print(f"  Total sarasota MCA rows: {len(rows)}")
    print(f"  Missing assessed_value: {len(needing_assessed)}")
    print(f"  Missing lat/lon: {len(needing_geo)}")
    print(f"  Needing any enrichment: {len(needing_any)}")

    return needing_any


def main():
    print(f"=== sarasota I property card enrichment ===")
    print(f"dispatch_id: {DISPATCH_ID}")
    print(f"timestamp: {datetime.now(timezone.utc).isoformat()}")

    print("\n1. Probing SCPAO search endpoint...")
    status, body = fetch_http(SCPAO_SEARCH_URL)
    if status == 200:
        print(f"  SCPAO search: HTTP {status} OK, body len={len(body)}")
    else:
        print(f"  SCPAO search: HTTP {status} (may be blocked or different URL)")
        print("  UNTESTED: SCPAO endpoint may require session/JS rendering")

    print("\n2. Fetching MCA rows needing enrichment...")
    needing = fetch_mca_rows_needing_enrichment()

    enriched = 0
    geo_from_scpao = 0
    av_from_scpao = 0

    print(f"\n3. Enriching {len(needing)} rows from SCPAO...")
    for i, row in enumerate(needing):
        cn = row["case_number"]
        pid = row.get("parcel_id")

        if i > 0 and i % 20 == 0:
            print(f"  Progress: {i}/{len(needing)}, enriched={enriched}")

        if not pid or pid in ("Property Appraiser", "TIMESHARE", "MULTIPLE PARCEL"):
            continue

        scpao_data = None
        if status == 200:
            scpao_data = fetch_scpao_parcel(pid)
            time.sleep(0.3)

        payload = {}
        now_iso = datetime.now(timezone.utc).isoformat()

        if scpao_data:
            if scpao_data.get("assessed_value") and not row.get("assessed_value"):
                payload["assessed_value"] = scpao_data["assessed_value"]
                payload["assessed_value_source"] = f"scpao:{DISPATCH_ID}"
                av_from_scpao += 1

            if scpao_data.get("latitude") and not row.get("latitude"):
                payload["latitude"] = scpao_data["latitude"]
                payload["longitude"] = scpao_data["longitude"]
                geo_from_scpao += 1

            if scpao_data.get("property_address") and not row.get("property_address"):
                payload["property_address"] = scpao_data["property_address"]

        if not payload:
            continue

        payload["updated_at"] = now_iso
        result = sb_patch(
            "multi_county_auctions",
            {"county": "eq.sarasota", "case_number": f"eq.{cn}"},
            payload,
        )
        if result in (200, 204):
            enriched += 1
        else:
            print(f"  PATCH failed for {cn}: HTTP {result}")

    print(f"\n=== SUMMARY ===")
    print(f"Rows enriched: {enriched}")
    print(f"  assessed_value from SCPAO: {av_from_scpao}")
    print(f"  lat/lon from SCPAO: {geo_from_scpao}")
    print(f"\nNOTE: I metric requires parcel_zones (zoning) — run sarasota_g_zoning_arcgis.py")
    print(f"to complete the card_complete requirement (address+geo+value+zone).")


if __name__ == "__main__":
    main()
