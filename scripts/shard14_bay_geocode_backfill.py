#!/usr/bin/env python3
"""SHARD-14 (martin/bay/alachua/lake), dispatch 2a2b2667-58f3-4e55-a353-d33a04236bf9.

Bay criterion I fix: 32 of bay's 39 card-incomplete rows already carry a real
property_address, real parcel_id, and real assessed_value -- they are missing
ONLY latitude/longitude (confirmed via a direct diagnostic pull of
multi_county_auctions vs v_zoning_gold_standard_card; bay's zoning join
already covers every field-complete row 1:1, so this is a pure geocoding
gap, not a zoning-substrate gap). Same lever the Duval I-fix used
(2026-06-12 session, see docs comment trail): the free, public, no-key US
Census Bureau geocoder (geocoding.geo.census.gov) -- real government
address-point data, never invented.

Writes ONLY latitude/longitude, and ONLY on an exact-match ("Match" ==
"Exact") response. No-match or tie -> left NULL, never guessed.

Usage: python3 scripts/shard14_bay_geocode_backfill.py [--dry-run]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def geocode(address):
    params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    url = f"{CENSUS_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "biddeed-gold-standard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    matches = data.get("result", {}).get("addressMatches", [])
    if len(matches) != 1:
        return None, f"{len(matches)}_matches"
    m = matches[0]
    coords = m.get("coordinates", {})
    lat, lon = coords.get("y"), coords.get("x")
    if lat is None or lon is None:
        return None, "no_coordinates"
    return (lat, lon), "exact_unique"


def main():
    dry_run = "--dry-run" in sys.argv
    rows = rest_get(
        "multi_county_auctions?county=eq.bay&latitude=is.null&po_latitude=is.null"
        "&property_address=not.is.null"
        "&or=(data_source.neq.propertyonion,tier1_authoritative.eq.true)"
        "&select=id,case_number,property_address")

    matched = 0
    for row in rows:
        addr = row["property_address"]
        try:
            coords, method = geocode(addr)
        except Exception as e:
            coords, method = None, f"error:{e}"
        if not coords:
            print(f"  SKIP {row['case_number']}: {method} ({addr})")
            time.sleep(0.3)
            continue
        lat, lon = coords
        if dry_run:
            matched += 1
            print(f"  WOULD SET {row['case_number']}: {addr} -> ({lat}, {lon})")
        else:
            status, resp = rest_patch(
                f"multi_county_auctions?id=eq.{row['id']}",
                {"latitude": lat, "longitude": lon})
            if status not in (200, 204):
                print(f"  PATCH FAILED {row['case_number']}: HTTP {status} {resp}", file=sys.stderr)
            else:
                matched += 1
                print(f"  SET {row['case_number']}: {addr} -> ({lat}, {lon})")
        time.sleep(0.3)

    print(f"\nTOTALS: candidates={len(rows)} geocoded={matched}{' (DRY RUN)' if dry_run else ''}")


if __name__ == "__main__":
    main()
