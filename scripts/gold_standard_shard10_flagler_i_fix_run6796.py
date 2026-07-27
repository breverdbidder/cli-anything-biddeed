#!/usr/bin/env python3
"""
gold_standard_shard10_flagler_i_fix_run6796.py — flagler-only (GOLD STANDARD
shard-10, loop run 6796).

Fixes the 7 specific flagler rows failing letter I (card_complete) at 94.7%
(143/151). Scope: flagler ONLY. Idempotent — safe to re-run.

Sub-fixes:
  1. case "2025 CC 000553" (id=78713ea7-59d2-440a-858a-f66e0150bf34): parcel_id
     is a scraper-bug placeholder ("Property Appraiser"), property_address is
     NULL. Real parcel/address lookup attempted via WebSearch, RealForeclose
     source_url (flagler.realforeclose.com, AID=1505145 -- returns HTTP 403,
     bot-blocked) and Firecrawl (HTTP 402, out of credits). Flagler Clerk's
     case search portal (Benchmark platform) is not curl-queryable anonymously.
     Result: UNTESTED / genuinely unfindable this session. NOT patched --
     no fabricated parcel_id or address written. Logged loudly below.

  2. Three parcels with no parcel_zones row -- real zone codes sourced live
     from ArcGIS REST FeatureServer queries (point-in-polygon on stored
     lat/lng), VERIFIED this session:
       - 27-11-31-5904-00000-0360 (25 Pine Harbor Dr, Palm Coast) -> inside
         Palm Coast city limits (PalmCoastFL_CityLimits FeatureServer hit) ->
         PalmCoastFL_Zoning FeatureServer/0, LAYER field = "MPD" (Master
         Planned Development District). Zone MPD already exists in
         zoning_districts for jurisdiction_id=966 (Palm Coast), id=7622.
       - 2711314892000000050 (152 N Lakewalk Dr, Palm Coast mailing address)
         -> OUTSIDE Palm Coast city limits (PalmCoastFL_CityLimits query
         returned 0 features) -> real jurisdiction is Unincorporated Flagler
         County (id=1184). Flagler County's own "Unincorporated_Zoning"
         FeatureServer (flaglercountyfl-fcmaps.opendata.arcgis.com open data
         catalog) returns ZONECODE="PUD", ZONENAME="PLANNED UNIT
         DEVELOPMENT", CITYNAME="UNINCORPORATED". PUD is a new code for
         jurisdiction_id=1184 (not in the existing FC-* set) -- inserted.
       - 3012295550001000012 (280 Archie Ln, Bunnell mailing address) ->
         same Unincorporated_Zoning FeatureServer query -> ZONECODE="AC",
         ZONENAME="AGRICULTURAL", CITYNAME="UNINCORPORATED". New code for
         jurisdiction_id=1184 -- inserted.
     Source ArcGIS endpoints:
       https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_Zoning/FeatureServer/0
       https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_CityLimits/FeatureServer/0
       https://services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0
     No density/FAR/parking numbers are written -- category/name only, per
     guardrail #3.

  3. Three rows with real parcel_id + address but NULL lat/lng -- geocoded via
     US Census Bureau Geocoder (Public_AR_Current benchmark), same pattern as
     scripts/gold_standard_shard7_flagler_i_geocode.py. Defensive check: the
     matched address zip must echo the zip we sent.

Usage: python3 scripts/gold_standard_shard10_flagler_i_fix_run6796.py
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
BASE = f"{SUPABASE_URL}/rest/v1"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

COUNTY = "flagler"
RETRY_ATTEMPTS = 3

# --- Sub-fix 2: parcel_zones inserts (VERIFIED via live ArcGIS REST this session) ---
PARCEL_ZONE_TARGETS = [
    {
        "parcel_id": "27-11-31-5904-00000-0360",
        "case_number": "2025 CA 000767",
        "jurisdiction_id": 966,  # Palm Coast -- confirmed inside city limits
        "zone_code": "MPD",
        "zone_name": None,  # already exists in zoning_districts, no new insert needed
        "source": "PalmCoastFL_Zoning FeatureServer (services1.arcgis.com/tpnsCwhQRDqwL3mq) LAYER field, point-in-polygon @ 29.525101246251,-81.16774183704, verified inside PalmCoastFL_CityLimits",
    },
    {
        "parcel_id": "2711314892000000050",
        "case_number": "26-058 TDC",
        "jurisdiction_id": 1184,  # Unincorporated Flagler -- confirmed OUTSIDE Palm Coast city limits
        "zone_code": "PUD",
        "zone_name": "PLANNED UNIT DEVELOPMENT",
        "source": "Flagler County Unincorporated_Zoning FeatureServer (services3.arcgis.com/hSKL9bYjhP4rHxSD) ZONECODE/ZONENAME field, point-in-polygon @ 29.516047018088,-81.158601807373, CITYNAME=UNINCORPORATED (outside PalmCoastFL_CityLimits)",
    },
    {
        "parcel_id": "3012295550001000012",
        "case_number": "26-063 TDC",
        "jurisdiction_id": 1184,  # Unincorporated Flagler
        "zone_code": "AC",
        "zone_name": "AGRICULTURAL",
        "source": "Flagler County Unincorporated_Zoning FeatureServer (services3.arcgis.com/hSKL9bYjhP4rHxSD) ZONECODE/ZONENAME field, point-in-polygon @ 29.425564073363,-81.412909318144, CITYNAME=UNINCORPORATED",
    },
]

# --- Sub-fix 3: geocode targets (Census Bureau Geocoder) ---
GEOCODE_TARGETS = [
    ("2024 CA 000290", "6255 CHERRY LN, BUNNELL, FL 32110"),
    ("2025 CA 000602", "42 DEL PALMA DR, PALM COAST, FL 32137"),
    ("2025 CA 000445", "32 PRATTWOOD LN, PALM COAST, FL 32164"),
]

# --- Sub-fix 1: unresolved case (documented, NOT patched) ---
UNRESOLVED_CASE = {
    "case_number": "2025 CC 000553",
    "id": "78713ea7-59d2-440a-858a-f66e0150bf34",
    "reason": (
        "parcel_id/address genuinely unfindable this session: RealForeclose "
        "source_url (flagler.realforeclose.com AID=1505145) returns HTTP 403 "
        "bot-block; Firecrawl scrape returns HTTP 402 (out of credits); "
        "WebSearch returns no indexed case-specific hits; Flagler Clerk's "
        "case search portal (Benchmark platform) has no anonymous curl-"
        "queryable endpoint found. UNTESTED -- not patched, no fabricated "
        "parcel_id/address written."
    ),
}


def rest_get(path: str, params: str = "") -> list:
    url = f"{BASE}/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  GET ERROR {path}: {e.code} {e.read().decode()[:300]}")
        return []


def rest_patch(path: str, filter_qs: str, body: dict) -> tuple:
    url = f"{BASE}/{path}?{filter_qs}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), method="PATCH",
        headers={**HEADERS, "Prefer": "return=representation"},
    )
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = f"{e.code} {e.read().decode()[:300]}"
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            time.sleep(1.5 * (attempt + 1))
    return 599, last_err


def rest_post(path: str, body) -> tuple:
    req = urllib.request.Request(
        f"{BASE}/{path}", data=json.dumps(body).encode(), method="POST",
        headers={**HEADERS, "Prefer": "return=representation,resolution=ignore-duplicates"},
    )
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            last_err = f"{e.code} {e.read().decode()[:300]}"
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_err = str(e)
            time.sleep(1.5 * (attempt + 1))
    return 599, last_err


def evaluate_county(county: str) -> dict:
    status, resp = rest_post("rpc/pencil_dod_evaluate_county", {"p_county": county})
    if status not in (200, 201):
        print(f"  EVAL ERROR: {status} {resp}")
        return {}
    return resp


def geocode(address: str):
    q = urllib.parse.urlencode({
        "address": address, "benchmark": "Public_AR_Current", "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?{q}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read())
    matches = data.get("result", {}).get("addressMatches", [])
    if not matches:
        return None
    m = matches[0]
    return {"lat": m["coordinates"]["y"], "lon": m["coordinates"]["x"], "matched_address": m["matchedAddress"]}


def ensure_zoning_district(jurisdiction_id: int, code: str, name: str, source: str) -> bool:
    """Insert zoning_districts row if code doesn't already exist for jurisdiction. Idempotent."""
    existing = rest_get(
        "zoning_districts",
        f"jurisdiction_id=eq.{jurisdiction_id}&code=eq.{urllib.parse.quote(code)}&select=id",
    )
    if existing:
        print(f"    zoning_districts {code} already exists for jurisdiction {jurisdiction_id} (id={existing[0]['id']})")
        return True
    body = {
        "jurisdiction_id": jurisdiction_id,
        "code": code,
        "name": name,
        "category": "Uncategorized",
    }
    status, resp = rest_post("zoning_districts", body)
    if status in (200, 201):
        print(f"    INSERTED zoning_districts {code} for jurisdiction {jurisdiction_id}: {resp}")
        return True
    print(f"    ERROR inserting zoning_districts {code}: {status} {resp}")
    return False


def fix_parcel_zones():
    print("\n=== Sub-fix 2: parcel_zones inserts ===")
    inserted = 0
    for t in PARCEL_ZONE_TARGETS:
        pid = t["parcel_id"]
        existing = rest_get("parcel_zones", f"parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if existing:
            print(f"  {pid}: parcel_zones row already exists (id={existing[0]['id']}) -- skip")
            continue
        if t["zone_name"]:
            ensure_zoning_district(t["jurisdiction_id"], t["zone_code"], t["zone_name"], t["source"])
        body = {
            "parcel_id": pid,
            "jurisdiction_id": t["jurisdiction_id"],
            "zone_code": t["zone_code"],
            "zone_name": t["zone_name"],
            "source": t["source"],
        }
        status, resp = rest_post("parcel_zones", body)
        if status in (200, 201):
            print(f"  {pid} ({t['case_number']}): INSERTED zone_code={t['zone_code']} jurisdiction_id={t['jurisdiction_id']}")
            inserted += 1
        else:
            print(f"  {pid} ({t['case_number']}): INSERT FAILED {status} {resp}")
    return inserted


def fix_geocodes():
    print("\n=== Sub-fix 3: geocode NULL lat/lng ===")
    geocoded = 0
    for cn, addr in GEOCODE_TARGETS:
        rows = rest_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}&select=id,latitude,longitude",
        )
        if not rows:
            print(f"  {cn}: NOT FOUND in multi_county_auctions -- skip")
            continue
        row = rows[0]
        if row.get("latitude") is not None and row.get("longitude") is not None:
            print(f"  {cn}: already has lat/lng ({row['latitude']},{row['longitude']}) -- skip")
            continue
        try:
            result = geocode(addr)
        except Exception as e:
            print(f"  {cn}: GEOCODE FAIL for '{addr}': {e}")
            continue
        if not result:
            print(f"  {cn}: NO MATCH from Census geocoder for '{addr}' -- leaving NULL")
            continue
        expected_zip = addr.strip().split()[-1]
        if expected_zip not in result["matched_address"]:
            print(f"  {cn}: SANITY FAIL -- zip mismatch, matched='{result['matched_address']}' -- leaving NULL")
            continue
        status, resp = rest_patch(
            "multi_county_auctions",
            f"id=eq.{row['id']}",
            {"latitude": result["lat"], "longitude": result["lon"]},
        )
        if status in (200, 201) and resp:
            print(f"  {cn}: geocoded lat={result['lat']} lon={result['lon']} matched='{result['matched_address']}'")
            geocoded += 1
        else:
            print(f"  {cn}: PATCH FAILED {status} {resp}")
        time.sleep(1.0)
    return geocoded


def report_unresolved():
    print("\n=== Sub-fix 1: unresolved case (LOUD, not silently swallowed) ===")
    print(f"  case_number={UNRESOLVED_CASE['case_number']} id={UNRESOLVED_CASE['id']}")
    print(f"  REASON: {UNRESOLVED_CASE['reason']}")
    print("  ACTION: NOT patched. No fabricated parcel_id/address written. Tag: UNTESTED.")


def verify_targets():
    print("\n=== Verification: re-GET all 7 target rows ===")
    case_numbers = [
        "2025 CC 000553", "2025 CA 000767", "26-058 TDC", "26-063 TDC",
        "2024 CA 000290", "2025 CA 000602", "2025 CA 000445",
    ]
    results = {}
    for cn in case_numbers:
        rows = rest_get(
            "multi_county_auctions",
            f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value",
        )
        if not rows:
            print(f"  {cn}: NOT FOUND")
            continue
        row = rows[0]
        pz = rest_get("parcel_zones", f"parcel_id=eq.{urllib.parse.quote(row['parcel_id'] or '')}&select=zone_code,jurisdiction_id") if row.get("parcel_id") else []
        print(f"  {cn}: {json.dumps(row)}")
        print(f"    parcel_zones: {pz}")
        results[cn] = {"row": row, "parcel_zones": pz}
    return results


def main():
    print(f"=== gold_standard_shard10_flagler_i_fix_run6796 ===")

    before = evaluate_county(COUNTY)
    print(f"BEFORE: {json.dumps(before.get('I', {}))}")

    report_unresolved()
    zones_inserted = fix_parcel_zones()
    geocoded = fix_geocodes()

    print(f"\nTOTALS: parcel_zones inserted={zones_inserted}/3, geocoded={geocoded}/3, unresolved=1 (case 2025 CC 000553)")

    verify_targets()

    after = evaluate_county(COUNTY)
    print(f"\nAFTER: {json.dumps(after.get('I', {}))}")
    print(f"\nFULL AFTER (all letters): {json.dumps(after)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
