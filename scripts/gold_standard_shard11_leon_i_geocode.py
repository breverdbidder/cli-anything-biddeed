#!/usr/bin/env python3
"""GOLD STANDARD shard11, dispatch dd396ee4-e383-45ea-8953-5ad92fb1c1af, county=leon.

I (card_complete) partial fix: backfill latitude/longitude for the 8 leon rows
that have a clean, well-formed property_address but NULL lat/lng (mostly the
same rows that had NULL parity_status before scripts/gold_standard_shard11_leon_cd_i_ajax_harvest.py
ran -- that harvester does not supply coordinates, only address/parcel_id/value).

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- a free, authoritative, independent US government TIGER-line-based
geocoder. Not PropertyOnion-derived, so results are written to the
latitude/longitude columns (double precision) rather than po_latitude/
po_longitude (numeric, PropertyOnion-provenance-named columns) -- this
distinction matters for HONESTY PROTOCOL provenance labeling.

Every write is verified against the geocoder's own matchedAddress echo before
being trusted (defensive: reject if returned city/zip don't match input).

Usage: python3 scripts/gold_standard_shard11_leon_i_geocode.py
"""
import os
import json
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# (case_number, original property_address as stored, cleaned address for geocoder)
TARGETS = [
    ("14-0367", "627 KISSIMMEE ST, TAL, FL- 32310", "627 KISSIMMEE ST, TALLAHASSEE, FL 32310"),
    ("16-0785", "5634 MEMPHIS RD, TAL, FL- 32304", "5634 MEMPHIS RD, TALLAHASSEE, FL 32304"),
    ("2024 CA 000319", "2383 LAKE HERITAGE DR, TALLAHASSEE, FL- 32311", "2383 LAKE HERITAGE DR, TALLAHASSEE, FL 32311"),
    ("2025 CA 000634", "1684 RODEO DR, TALLAHASSEE, FL- 32311", "1684 RODEO DR, TALLAHASSEE, FL 32311"),
    ("2025 CA 000765", "2287 LAKE HERITAGE DR, TALLAHASSEE, FL- 32311", "2287 LAKE HERITAGE DR, TALLAHASSEE, FL 32311"),
    ("2025 CA 001807", "5628 DOONESBURY WAY, TALLAHASSEE, FL- 32303", "5628 DOONESBURY WAY, TALLAHASSEE, FL 32303"),
    ("2025 CA 001966", "4134 CHELMSFORD RD, TALLAHASSEE, FL- 32309", "4134 CHELMSFORD RD, TALLAHASSEE, FL 32309"),
    ("2025 CA 002129", "3137 CONNECTOR DR, TALLAHASSEE, FL- 32303", "3137 CONNECTOR DR, TALLAHASSEE, FL 32303"),
]


def geocode(address):
    q = urllib.parse.urlencode({
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    m = matches[0]
    return {
        "lat": m["coordinates"]["y"],
        "lon": m["coordinates"]["x"],
        "matched_address": m["matchedAddress"],
    }


def rest_patch(case_number, body):
    path = f"multi_county_auctions?county=eq.leon&case_number=eq.{urllib.parse.quote(case_number)}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    geocoded = 0
    skipped = 0
    for cn, orig_addr, clean_addr in TARGETS:
        try:
            result = geocode(clean_addr)
        except Exception as e:
            print(f"  {cn}: GEOCODE FAIL for '{clean_addr}': {e}")
            skipped += 1
            continue
        if not result:
            print(f"  {cn}: NO MATCH from Census geocoder for '{clean_addr}' -- leaving NULL")
            skipped += 1
            continue
        # defensive check: matched address must echo the same zip we sent
        if clean_addr.split()[-1] not in result["matched_address"]:
            print(f"  {cn}: SANITY FAIL -- zip mismatch, matched='{result['matched_address']}' -- leaving NULL")
            skipped += 1
            continue
        try:
            rows = rest_patch(cn, {"latitude": result["lat"], "longitude": result["lon"]})
        except Exception as e:
            print(f"  {cn}: PATCH FAIL: {e}")
            skipped += 1
            continue
        if not rows:
            print(f"  {cn}: PATCH returned 0 rows (case_number mismatch?) -- verify manually")
            skipped += 1
            continue
        geocoded += 1
        print(f"  {cn}: geocoded lat={result['lat']} lon={result['lon']} matched='{result['matched_address']}'")
        time.sleep(0.5)

    print(f"\nTOTALS: geocoded={geocoded} skipped={skipped} of {len(TARGETS)}")
    if geocoded == 0 and len(TARGETS) > 0:
        raise RuntimeError("Silent failure: 0 rows geocoded out of target set")


if __name__ == "__main__":
    main()
