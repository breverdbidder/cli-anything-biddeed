#!/usr/bin/env python3
"""Gold Standard escambia I fix, dispatch 1a7d03e0-6c1f-4240-822d-185fd0fe77dd, 2026-07-24.

Root cause (VERIFIED live query against pencil_dod_evaluate_county('escambia') and
its underlying `c` CTE, 2026-07-24): I=90.1% (328/364). Of the 36 gap rows, 33 have
a real property_address and real assessed/market value but NULL latitude/longitude
(both `latitude` and `po_latitude` are NULL). The remaining 3 rows have no usable
parcel_id/address at all (parcel_id IN ('MULTIPLE PARCELS','Property Appraiser') or
NULL) and are genuinely blocked -- see report.

Fix: same lever as prior Duval/Bay/Martin/Leon I-fixes (scripts/shard4_martin_geocode_backfill.py,
scripts/gold_standard_shard11_leon_i_geocode.py) -- the free, public, no-key US Census
Bureau geocoder (geocoding.geo.census.gov), real government address-point data, never
invented. Targets are pulled LIVE from the DB (not hardcoded), addresses parsed from
the two observed escambia property_address formats:
  - "2024 TD" rows:      "<STREET> <ZIP5>"                      (city implied Pensacola)
  - "2025/2026 CA" rows: "<STREET>, <CITY>, FL- <ZIP5>"

Writes ONLY latitude/longitude, and ONLY on a returned Census address match with
tigerLine/exact-ish confidence (accepts any returned match -- Census only returns
matches it is confident in). No-match -> left NULL, never guessed/fabricated.
Idempotent: query always re-selects rows still missing latitude, so re-running only
processes remaining gaps.

Usage: python3 scripts/shard_escambia_i_geocode_backfill_20260724.py [--dry-run]
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def fetch_targets_full():
    """Live-pull escambia rows with a real address but no lat/lon (idempotent gap query).

    Excludes data_source=propertyonion server-side (PostgREST 'not.eq') to match the
    evaluator's base row set semantics for the common case; the small residual of
    tier1_authoritative=true PO-sourced rows (if any) is re-included via a second,
    narrow query rather than pulling the full untier'd PO set (which alone exceeds
    PostgREST's 1000-row default page size for escambia and would silently truncate
    results without an explicit Range header).
    """
    base_params = {
        "select": "id,case_number,property_address,data_source,tier1_authoritative,po_latitude",
        "county": "eq.escambia",
        "property_address": "not.is.null",
        "latitude": "is.null",
    }

    params_non_po = dict(base_params, **{"data_source": "not.eq.propertyonion"})
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?{urllib.parse.urlencode(params_non_po)}",
        headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        rows_non_po = json.loads(r.read())

    # data_source IS NULL rows are excluded by not.eq.propertyonion in Postgres's
    # three-valued logic (NULL <> 'propertyonion' is NULL, not true) -- fetch them
    # explicitly too.
    params_null_ds = dict(base_params, **{"data_source": "is.null"})
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?{urllib.parse.urlencode(params_null_ds)}",
        headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        rows_null_ds = json.loads(r.read())

    params_po_tier1 = dict(base_params, **{
        "data_source": "eq.propertyonion", "tier1_authoritative": "eq.true"})
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?{urllib.parse.urlencode(params_po_tier1)}",
        headers=REST_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        rows_po_tier1 = json.loads(r.read())

    seen = set()
    out = []
    for row in rows_non_po + rows_null_ds + rows_po_tier1:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        if row.get("po_latitude") is not None:
            continue  # already has geo via po_latitude fallback, not a real gap
        out.append(row)
    return out


def parse_address(addr):
    """Returns (street, city, zipc) or None if unparseable."""
    addr = addr.strip()
    if "," in addr:
        parts = [p.strip() for p in addr.split(",")]
        street = parts[0]
        city = parts[1] if len(parts) > 1 else "Pensacola"
        zipm = re.search(r"(\d{5})", parts[-1])
        zipc = zipm.group(1) if zipm else ""
    else:
        m = re.match(r"^(.*\S)\s+(\d{5})$", addr)
        if not m:
            return None
        street = m.group(1)
        zipc = m.group(2)
        city = "Pensacola"
    if not street or not zipc:
        return None
    return street, city, zipc


def _geocode_once(street, city, zipc):
    params = urllib.parse.urlencode({
        "street": street, "city": city, "state": "FL", "zip": zipc,
        "benchmark": "Public_AR_Current", "format": "json",
    })
    req = urllib.request.Request(f"{CENSUS_URL}?{params}")
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return coords["y"], coords["x"]


# Known TIGER/Line street-name normalizations discovered this session (2026-07-24):
# some scraped street names concatenate words the Census TIGER/Line road name keeps
# space-separated (e.g. "JOJO RD" scraped vs official "JO JO RD"). Confirmed via a
# real Census addressMatches hit with a plausible address range (1000-1098 containing
# 1030) before being added here -- this is a normalization fallback, not a guess.
_STREET_FALLBACKS = {
    "1030 JOJO RD": "1030 JO JO RD",
}


def geocode(street, city, zipc):
    match = _geocode_once(street, city, zipc)
    if match:
        return match
    fallback = _STREET_FALLBACKS.get(street)
    if fallback:
        return _geocode_once(fallback, city, zipc)
    return None


def rest_patch(row_id, lat, lon):
    body = json.dumps({"latitude": lat, "longitude": lon}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{row_id}",
        data=body, method="PATCH",
        headers={**REST_HEADERS, "Prefer": "return=minimal"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def main():
    dry_run = "--dry-run" in sys.argv
    targets = fetch_targets_full()
    print(f"Live gap targets fetched: {len(targets)}")
    if not targets:
        print("No gap rows found -- nothing to do.")
        return

    fixed = 0
    unparseable = 0
    no_match = 0
    errors = 0

    for row in targets:
        addr = row["property_address"]
        parsed = parse_address(addr)
        if not parsed:
            print(f"{row['case_number']}: '{addr}' -> UNPARSEABLE (skipped)")
            unparseable += 1
            continue
        street, city, zipc = parsed
        try:
            match = geocode(street, city, zipc)
        except Exception as e:
            print(f"{row['case_number']}: {street} -> GEOCODE ERROR {e}")
            errors += 1
            time.sleep(1)
            continue
        if not match:
            print(f"{row['case_number']}: {street}, {city} {zipc} -> NO MATCH (left NULL)")
            no_match += 1
            time.sleep(0.3)
            continue
        lat, lon = match
        print(f"{row['case_number']}: {street}, {city} {zipc} -> {lat},{lon}")
        if not dry_run:
            status = rest_patch(row["id"], lat, lon)
            print(f"  PATCHED (HTTP {status})")
        fixed += 1
        time.sleep(0.3)  # be polite to the free Census endpoint

    print(f"\nTOTAL targets: {len(targets)}")
    print(f"  Geocoded+patched: {fixed}")
    print(f"  No Census match: {no_match}")
    print(f"  Unparseable address: {unparseable}")
    print(f"  Errors: {errors}")

    if len(targets) > 0 and fixed == 0:
        print("\n*** WARNING: parsed >0 candidate rows but wrote 0 fixes. "
              "Investigate before assuming this letter is blocked. ***", file=sys.stderr)


if __name__ == "__main__":
    main()
