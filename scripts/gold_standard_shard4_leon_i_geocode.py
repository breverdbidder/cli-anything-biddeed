#!/usr/bin/env python3
"""GOLD STANDARD shard-4, county=leon.

I (card_complete) fix: backfill latitude/longitude for the leon rows that have
a clean, well-formed property_address but NULL lat/lng, per the CURRENT live
gap (post the C/D AJAX-harvest fix that ran earlier this session). Extends
the pattern from scripts/gold_standard_shard11_leon_i_geocode.py (which
handled an earlier, smaller 8-row batch) to the current 26-row gap.

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- a free, authoritative, independent US government TIGER-line-based
geocoder. Not PropertyOnion-derived, so results are written to the
latitude/longitude columns (double precision) rather than po_latitude/
po_longitude (numeric, PropertyOnion-provenance-named columns) -- this
distinction matters for HONESTY PROTOCOL provenance labeling.

Every write is verified against the geocoder's own matchedAddress echo before
being trusted (defensive: reject if returned zip doesn't match input). Rows
with "0 <STREET> RD" style addresses (no house number -- vacant/unimproved
parcels) are expected to fail Census onelineaddress matching; that is
reported honestly as NO MATCH, never faked.

Usage: python3 scripts/gold_standard_shard4_leon_i_geocode.py
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
    ("2026 CA 000112", "7908 BRIARCREEK RD W, TALLAHASSEE, FL- 32312", "7908 BRIARCREEK RD W, TALLAHASSEE, FL 32312"),
    ("2025 CA 001874", "415 W COLLEGE AVE, TALLAHASSEE, FL- 32301", "415 W COLLEGE AVE, TALLAHASSEE, FL 32301"),
    ("2025 CA 002224", "2306 ATAPHA NENE, TALLAHASSEE, FL- 32301", "2306 ATAPHA NENE, TALLAHASSEE, FL 32301"),
    ("2025 CA 002448", "1203 HARLEM ST, TALLAHASSEE, FL- 32304", "1203 HARLEM ST, TALLAHASSEE, FL 32304"),
    ("26-0015", "1387 MCCULLOUGH DR, TAL, FL- 32305", "1387 MCCULLOUGH DR, TALLAHASSEE, FL 32305"),
    ("26-0028", "3324 N MONROE ST, TAL, FL- 32303", "3324 N MONROE ST, TALLAHASSEE, FL 32303"),
    ("26-0039", "1928 HARTSFIELD RD, TAL, FL- 32303", "1928 HARTSFIELD RD, TALLAHASSEE, FL 32303"),
    ("26-0050", "1605 HERNANDO DR, TAL, FL- 32304", "1605 HERNANDO DR, TALLAHASSEE, FL 32304"),
    ("26-0055", "6725 BLOUNTSTOWN HWY, TAL, FL- 32310", "6725 BLOUNTSTOWN HWY, TALLAHASSEE, FL 32310"),
    ("26-0020", "0 SLOE DR, TAL, FL- 32305", "SLOE DR, TALLAHASSEE, FL 32305"),
    ("26-0013", "9728 WAKULLA SPRINGS RD, TAL, FL- 32305", "9728 WAKULLA SPRINGS RD, TALLAHASSEE, FL 32305"),
    ("26-0018", "0 LOG LANDING RD, TAL, FL- 32310", "LOG LANDING RD, TALLAHASSEE, FL 32310"),
    ("26-0022", "0 OLD SHELL POINT RD, TAL, FL- 32305", "OLD SHELL POINT RD, TALLAHASSEE, FL 32305"),
    ("26-0034", "3108 HUNTINGTON WOODS BLVD, TAL, FL- 32303", "3108 HUNTINGTON WOODS BLVD, TALLAHASSEE, FL 32303"),
    ("26-0037", "4546 WIMBLETON CT, TAL, FL- 32303", "4546 WIMBLETON CT, TALLAHASSEE, FL 32303"),
    ("26-0026", "6709 VISALIA PL, TAL, FL- 32317", "6709 VISALIA PL, TALLAHASSEE, FL 32317"),
    ("26-0044", "1309 GIBBS DR, TAL, FL- 32303", "1309 GIBBS DR, TALLAHASSEE, FL 32303"),
    ("26-0051", "1853 OTIS WALLACE LN, TAL, FL- 32310", "1853 OTIS WALLACE LN, TALLAHASSEE, FL 32310"),
    ("26-0023", "4012 BRANDON HILL DR, TAL, FL- 32309", "4012 BRANDON HILL DR, TALLAHASSEE, FL 32309"),
    ("26-0016", "0 TALQUIN COVE RD, TAL, FL- 32310", "TALQUIN COVE RD, TALLAHASSEE, FL 32310"),
    ("26-0021", "0 SHAWMUT ST, TAL, FL- 32305", "SHAWMUT ST, TALLAHASSEE, FL 32305"),
    ("26-0035", "3128 HUNTINGTON WOODS BLVD, TAL, FL- 32303", "3128 HUNTINGTON WOODS BLVD, TALLAHASSEE, FL 32303"),
    ("26-0047", "1134 BENNETT ST, TAL, FL- 32304", "1134 BENNETT ST, TALLAHASSEE, FL 32304"),
    ("26-0019", "18095 BLOUNTSTOWN HWY, TAL, FL- 32310", "18095 BLOUNTSTOWN HWY, TALLAHASSEE, FL 32310"),
    ("26-0040", "2505 NUGGET LN, TAL, FL- 32303", "2505 NUGGET LN, TALLAHASSEE, FL 32303"),
    ("26-0048", "2049 CONTINENTAL AVE, TAL, FL- 32304", "2049 CONTINENTAL AVE, TALLAHASSEE, FL 32304"),
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
    geocoded_cases = []
    skipped_cases = []
    for cn, orig_addr, clean_addr in TARGETS:
        try:
            result = geocode(clean_addr)
        except Exception as e:
            print(f"  {cn}: GEOCODE FAIL for '{clean_addr}': {e}")
            skipped += 1
            skipped_cases.append(cn)
            continue
        if not result:
            print(f"  {cn}: NO MATCH from Census geocoder for '{clean_addr}' -- leaving NULL")
            skipped += 1
            skipped_cases.append(cn)
            continue
        # defensive check: matched address must echo the same zip we sent
        zip5 = clean_addr.strip().split()[-1]
        if zip5 not in result["matched_address"]:
            print(f"  {cn}: SANITY FAIL -- zip mismatch, matched='{result['matched_address']}' -- leaving NULL")
            skipped += 1
            skipped_cases.append(cn)
            continue
        try:
            rows = rest_patch(cn, {"latitude": result["lat"], "longitude": result["lon"]})
        except Exception as e:
            print(f"  {cn}: PATCH FAIL: {e}")
            skipped += 1
            skipped_cases.append(cn)
            continue
        if not rows:
            print(f"  {cn}: PATCH returned 0 rows (case_number mismatch?) -- verify manually")
            skipped += 1
            skipped_cases.append(cn)
            continue
        geocoded += 1
        geocoded_cases.append(cn)
        print(f"  {cn}: geocoded lat={result['lat']} lon={result['lon']} matched='{result['matched_address']}'")
        time.sleep(0.5)

    print(f"\nTOTALS: geocoded={geocoded} skipped={skipped} of {len(TARGETS)}")
    print(f"GEOCODED_CASES={geocoded_cases}")
    print(f"SKIPPED_CASES={skipped_cases}")
    if geocoded == 0 and len(TARGETS) > 0:
        raise RuntimeError("Silent failure: 0 rows geocoded out of target set")


if __name__ == "__main__":
    main()
