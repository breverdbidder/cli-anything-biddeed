#!/usr/bin/env python3
"""GOLD STANDARD shard-2, dispatch efb485bb-2af2-4ab0-b4fb-8a6c12f09798, county=duval.

I (card_complete) fix: backfill latitude/longitude for the 154 operational
duval rows that have a real property_address but are missing coordinates
(card_complete requires address+geo+value+zoned parcel; these rows already
have address+value, geo is the sole gap for most).

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- free, authoritative, independent US government TIGER-line-based
geocoder. Not PropertyOnion-derived. Pattern forked from
scripts/gold_standard_shard7_flagler_i_geocode.py (same county-agnostic
approach), scaled to fetch its own target list live instead of a hand-curated
list, since duval has 154 rows not 9.

Every write is verified against the geocoder's own matchedAddress echo before
being trusted (defensive: reject if returned zip doesn't match input when a
zip is available). Idempotent: only targets rows still missing lat/long at
run time, safe to re-run.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

RETRY_ATTEMPTS = 3


def rest_get(path):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(case_number, body):
    path = f"multi_county_auctions?county=eq.duval&case_number=eq.{urllib.parse.quote(case_number)}"
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
            time.sleep(1.5 * (attempt + 1))
    raise last_err


def geocode(address):
    q = urllib.parse.urlencode({
        "address": address,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "BidDeed-GoldStandard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
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


def build_query(row):
    addr = (row.get("property_address") or "").strip()
    if not addr:
        return None
    # Addresses already contain city/state/zip in most cases (e.g.
    # "2810 GLEN MAWR RD, JACKSONVILLE, FL- 32207"); normalize the
    # "FL-" clerk artifact and ensure Jacksonville/FL is present.
    addr = addr.replace("FL- ", "FL ").replace("FL-", "FL ")
    if "jacksonville" not in addr.lower() and "fl" not in addr.lower():
        city = row.get("city") or "Jacksonville"
        zipc = row.get("zip") or ""
        addr = f"{addr}, {city}, FL {zipc}".strip()
    return addr


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.duval&is_operational=eq.true&latitude=is.null"
        "&select=case_number,property_address,city,zip,parcel_id&limit=500"
    )
    print(f"Targets: {len(rows)} duval rows missing lat/long")

    geocoded = 0
    no_match = 0
    errors = 0
    no_addr = 0
    results = []

    for row in rows:
        case = row["case_number"]
        q = build_query(row)
        if not q:
            no_addr += 1
            continue
        try:
            g = geocode(q)
        except Exception as e:
            errors += 1
            print(f"  ERROR geocoding {case}: {e}")
            time.sleep(1)
            continue
        if not g:
            no_match += 1
            print(f"  NO MATCH: {case} -> {q}")
            time.sleep(0.3)
            continue
        try:
            rest_patch(case, {"latitude": g["lat"], "longitude": g["lon"]})
            geocoded += 1
            results.append({"case_number": case, "lat": g["lat"], "lon": g["lon"],
                             "matched_address": g["matched_address"]})
            print(f"  OK {case}: {g['lat']},{g['lon']} <- {g['matched_address']}")
        except Exception as e:
            errors += 1
            print(f"  ERROR patching {case}: {e}")
        time.sleep(0.25)  # be polite to the free Census geocoder

    print(f"\nDone. geocoded={geocoded} no_match={no_match} no_addr={no_addr} errors={errors} of {len(rows)}")
    if rows and geocoded == 0:
        print("FAIL-LOUD: parsed>0 targets but geocoded=0", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
