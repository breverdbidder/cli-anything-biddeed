#!/usr/bin/env python3
"""GOLD STANDARD shard-6, dispatch 3bb96d0d-0de5-4f6f-b933-2a95d7168f3d, county=broward.

I (card_complete) fix: backfill latitude/longitude for broward rows that have
a clean property_address but NULL lat/lng. Dynamically pulls the current miss
list from multi_county_auctions (not hardcoded) -- generalizes the proven
pattern from scripts/gold_standard_shard3_broward_i_geocode.py.

Source: US Census Bureau Geocoder (geocoding.geo.census.gov), Public_AR_Current
benchmark -- free, authoritative, independent US government TIGER-line-based
geocoder. Writes to latitude/longitude (double precision), not po_latitude/
po_longitude, since this is not PropertyOnion-derived.

Every write is verified against the geocoder's own matchedAddress echo before
being trusted: rows with a zip in the stored address are rejected unless the
zip appears in the matched address; the 3 bare-street TD-* rows (no city/zip)
are instead sanity-checked to land inside Broward County's lat/lon bounding
box (25.90-26.40 N, -80.50 to -80.05 W).

Usage: python3 scripts/gold_standard_shard6_broward_i_geocode_run7519.py
"""
import os
import json
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BROWARD_LAT_MIN, BROWARD_LAT_MAX = 25.90, 26.40
BROWARD_LON_MIN, BROWARD_LON_MAX = -80.50, -80.05

HEADERS_SB = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS_SB)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_patch(case_number, body):
    path = f"multi_county_auctions?county=eq.broward&case_number=eq.{urllib.parse.quote(case_number)}"
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS_SB, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def clean_query(addr):
    """Normalize a stored address into a Census-friendly one-line query."""
    a = addr.strip()
    # strip unit/apt suffixes after the zip-bearing comma segments where present;
    # Census tolerates unit numbers poorly, so drop trailing unit tokens like
    # "UNIT 344" / "# 112H" / "304-H" / "218" appended after the street line.
    parts = [p.strip() for p in a.split(",")]
    if len(parts) >= 3:
        # "STREET [UNIT], CITY, ZIP" -> keep street's first token block, city, FL zip
        street = parts[0]
        city = parts[1]
        zip_code = parts[-1].strip()
        return f"{street}, {city}, FL {zip_code}", zip_code
    if len(parts) == 1:
        # bare street, e.g. TD-* rows
        return f"{a}, BROWARD COUNTY, FL", None
    return a, None


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


def main():
    rows = sb_get(
        "multi_county_auctions?select=case_number,property_address,data_source,tier1_authoritative"
        "&county=eq.broward&latitude=is.null&po_latitude=is.null&property_address=not.is.null"
        "&or=(data_source.neq.propertyonion,data_source.is.null,tier1_authoritative.eq.true)"
    )
    print(f"Fetched {len(rows)} broward rows in scope missing lat/lon with a stored address.")

    geocoded = 0
    skipped = 0
    for row in rows:
        cn = row["case_number"]
        orig_addr = row["property_address"]
        query_addr, zip_code = clean_query(orig_addr)

        try:
            result = geocode(query_addr)
        except Exception as e:
            print(f"  {cn}: GEOCODE FAIL for '{query_addr}': {e}")
            skipped += 1
            continue
        if not result:
            print(f"  {cn}: NO MATCH from Census geocoder for '{query_addr}' -- leaving NULL")
            skipped += 1
            continue

        if zip_code:
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
            patched = rest_patch(cn, {"latitude": result["lat"], "longitude": result["lon"]})
        except Exception as e:
            print(f"  {cn}: PATCH FAIL: {e}")
            skipped += 1
            continue
        if not patched:
            print(f"  {cn}: PATCH returned 0 rows (case_number mismatch?) -- verify manually")
            skipped += 1
            continue
        geocoded += 1
        print(f"  {cn}: geocoded lat={result['lat']} lon={result['lon']} matched='{result['matched_address']}'")
        time.sleep(0.4)

    print(f"\nTOTALS: geocoded={geocoded} skipped={skipped} of {len(rows)}")
    if geocoded == 0 and len(rows) > 0:
        raise RuntimeError("Silent failure: 0 rows geocoded out of target set")


if __name__ == "__main__":
    main()
