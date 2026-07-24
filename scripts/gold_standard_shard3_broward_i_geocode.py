#!/usr/bin/env python3
"""GOLD STANDARD shard-3, dispatch 0f64d3fa-6878-48ac-b4d6-cb070032beab, county=broward.

I (card_complete) partial fix: backfill latitude/longitude for broward rows
that have a clean property_address (and now, post value-enrichment, real
assessed_value/market_value) but NULL lat/lng.

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- free, authoritative, independent US government TIGER-line-based
geocoder. Same proven pattern as scripts/gold_standard_shard11_leon_i_geocode.py.
Not PropertyOnion-derived, so results are written to latitude/longitude
(double precision), not po_latitude/po_longitude.

Every write is verified against the geocoder's own matchedAddress echo before
being trusted (defensive: reject if returned zip doesn't match input where a
zip was supplied). Rows without city/zip in the stored address (the TD-*
tax-deed rows here) are geocoded on the raw string only, and the match is
additionally sanity-checked to land within Broward County's lat/lon bounding
box (25.90-26.40 N, -80.50 to -80.05 W) before being trusted -- Census can
return an out-of-county false match for a bare street address with no city.

Usage: python3 scripts/gold_standard_shard3_broward_i_geocode.py
"""
import os
import json
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Broward County approximate bounding box (used only as a sanity check for
# the 3 bare-street-address TD-* rows below that have no city/zip to echo-verify).
BROWARD_LAT_MIN, BROWARD_LAT_MAX = 25.90, 26.40
BROWARD_LON_MIN, BROWARD_LON_MAX = -80.50, -80.05

# (case_number, stored property_address, geocoder query, has_zip)
TARGETS = [
    ("CACE-23-021250", "13382 LAKEPOINTE CIR, COOPER CITY, 33330", "13382 LAKEPOINTE CIR, COOPER CITY, FL 33330", True),
    ("CACE-24-001145", "1801 S OCEAN DR 301, HOLLYWOOD, 33019", "1801 S OCEAN DR, HOLLYWOOD, FL 33019", True),
    ("CACE-24-011211", "3028 S OAKLAND FOREST DR 3205, OAKLAND PARK, 33309", "3028 S OAKLAND FOREST DR, OAKLAND PARK, FL 33309", True),
    ("CACE-24-016458", "1720 HARRISON ST, HOLLYWOOD, 33020", "1720 HARRISON ST, HOLLYWOOD, FL 33020", True),
    ("CACE-25-005443", "8489 NW 43 CT, CORAL SPRINGS, 33065", "8489 NW 43 CT, CORAL SPRINGS, FL 33065", True),
    ("CACE-25-009477", "150 NE 15 AVE UNIT 344, FORT LAUDERDALE, 33301", "150 NE 15 AVE, FORT LAUDERDALE, FL 33301", True),
    ("CACE-25-010544", "9070 LIME BAY BLVD, TAMARAC, 33321", "9070 LIME BAY BLVD, TAMARAC, FL 33321", True),
    ("CACE-25-011263", "6143 SW 40 ST, MIRAMAR, 33025", "6143 SW 40 ST, MIRAMAR, FL 33025", True),
    ("CACE-25-011467", "2900 NW 48 TER, LAUDERDALE LAKES, 33313", "2900 NW 48 TER, LAUDERDALE LAKES, FL 33313", True),
    ("CACE-25-012253", "6010 S FALLS CIRCLE DR, LAUDERHILL, 33319", "6010 S FALLS CIRCLE DR, LAUDERHILL, FL 33319", True),
    ("CACE-25-013171", "505 N FT LAUDERDALE BCH BLVD 7, FORT LAUDERDALE, 33304", "505 N FORT LAUDERDALE BEACH BLVD, FORT LAUDERDALE, FL 33304", True),
    ("CACE-25-016380", "5059 NW 42 ST, LAUDERDALE LAKES, 33319", "5059 NW 42 ST, LAUDERDALE LAKES, FL 33319", True),
    ("CACE-25-017818", "4250 NW 55 DR, COCONUT CREEK, 33073", "4250 NW 55 DR, COCONUT CREEK, FL 33073", True),
    ("CACE-25-018558", "3370 NW 21 CT, COCONUT CREEK, 33066", "3370 NW 21 CT, COCONUT CREEK, FL 33066", True),
    ("CACE-26-000767", "10861 NW 35 PL, SUNRISE, 33351", "10861 NW 35 PL, SUNRISE, FL 33351", True),
    ("COCE-25-047596", "460 LAKEVIEW DR 3, WESTON, 33326", "460 LAKEVIEW DR, WESTON, FL 33326", True),
    ("COCE-25-080423", "3591 INVERRARY BLVD W, LAUDERHILL, 33319", "3591 INVERRARY BLVD, LAUDERHILL, FL 33319", True),
    ("COWE-25-067830", "9801 NW 58 CT, PARKLAND, 33076", "9801 NW 58 CT, PARKLAND, FL 33076", True),
    ("COWE-26-021926", "4253 SW 124 TER, MIRAMAR, 33027", "4253 SW 124 TER, MIRAMAR, FL 33027", True),
    ("TD-53676", "1201 SW 52 AVE", "1201 SW 52 AVE, BROWARD COUNTY, FL", False),
    ("TD-53694", "4771 NW 10 CT", "4771 NW 10 CT, BROWARD COUNTY, FL", False),
    ("TD-53726", "5864 NW 22 ST", "5864 NW 22 ST, BROWARD COUNTY, FL", False),
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
    path = f"multi_county_auctions?county=eq.broward&case_number=eq.{urllib.parse.quote(case_number)}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    geocoded = 0
    skipped = 0
    for cn, orig_addr, clean_addr, has_zip in TARGETS:
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

        if has_zip:
            zip_code = clean_addr.strip().split()[-1]
            if zip_code not in result["matched_address"]:
                print(f"  {cn}: SANITY FAIL -- zip mismatch, matched='{result['matched_address']}' -- leaving NULL")
                skipped += 1
                continue
        else:
            lat, lon = result["lat"], result["lon"]
            if not (BROWARD_LAT_MIN <= lat <= BROWARD_LAT_MAX and BROWARD_LON_MIN <= lon <= BROWARD_LON_MAX):
                print(f"  {cn}: SANITY FAIL -- lat/lon {lat},{lon} outside Broward bbox, matched='{result['matched_address']}' -- leaving NULL")
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
