#!/usr/bin/env python3
"""GOLD STANDARD shard-7, dispatch ea6af08a-62cb-4bdb-b69d-224fbfac7d47, county=flagler.

I (card_complete) fix: backfill latitude/longitude for the flagler rows that
already have a real property_address, parcel_id, and assessed_value (from
scripts/shard9_flagler_cd_ajax_harvest.py's C/D harvest run this session) but
are still missing coordinates.

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- a free, authoritative, independent US government TIGER-line-based
geocoder. Not PropertyOnion-derived, so results are written to the
latitude/longitude columns (double precision) rather than po_latitude/
po_longitude. Pattern forked from
scripts/gold_standard_shard11_leon_i_geocode.py (same county-agnostic approach).

Every write is verified against the geocoder's own matchedAddress echo before
being trusted (defensive: reject if returned zip doesn't match input).

Usage: python3 scripts/gold_standard_shard7_flagler_i_geocode.py
"""
import os
import json
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# (case_number, cleaned address for geocoder -- source addresses have run-together
# street numbers e.g. "32WHITCOCK LN" and abbreviated "FL- 32164"; normalized here)
TARGETS = [
    ("2025 CA 000767", "25 PINE HARBOR DR, PALM COAST, FL 32137"),
    ("26-007 TDC", "39 SEDGWICK TRL, PALM COAST, FL 32164"),
    ("26-012 TDC", "32 WHITCOCK LN, PALM COAST, FL 32164"),
    ("26-034 TDC", "115 LAGUNA FOREST TRL, PALM COAST, FL 32164"),
    ("26-040 TDC", "21 FARRINGTON LN, PALM COAST, FL 32137"),
    ("26-046 TDC", "20 CRESCENT CT S, PALM COAST, FL 32137"),
    ("26-050 TDC", "21 ROCKINGHAM LN, PALM COAST, FL 32164"),
    ("26-058 TDC", "152 N LAKEWALK DR, PALM COAST, FL 32137"),
    ("26-063 TDC", "280 ARCHIE LN, BUNNELL, FL 32110"),
]
# Idempotent: safe to re-run in full. Retry logic added for the transient
# Supabase 5xx/timeout errors observed on the first pass (2/9 succeeded).

RETRY_ATTEMPTS = 3


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
    path = f"multi_county_auctions?county=eq.flagler&case_number=eq.{urllib.parse.quote(case_number)}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    raise last_err


def main():
    geocoded = 0
    skipped = 0
    for cn, clean_addr in TARGETS:
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
        time.sleep(1.0)

    print(f"\nTOTALS: geocoded={geocoded} skipped={skipped} of {len(TARGETS)}")
    if geocoded == 0 and len(TARGETS) > 0:
        raise RuntimeError("Silent failure: 0 rows geocoded out of target set")


if __name__ == "__main__":
    main()
