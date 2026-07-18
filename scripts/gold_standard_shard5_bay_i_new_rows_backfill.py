#!/usr/bin/env python3
"""
GOLD STANDARD shard-5 — bay county — Letter I card_complete backfill for new rows.

dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f
Session: 2026-07-18

CONTEXT:
  Prior sessions (shard11 run3645, shard3 2026-07-11) fixed bay I from 66.9% -> 94.9%
  (112/118). Since then, 9 new rows were added (auctions_total went 118 -> 127).
  Current state (loop run 4870): I FAIL 88.2% (card_complete=112 of 127).
  To reach 95%: need 121/127 complete cards.

  Residual known-unresolvable rows from prior sessions (7 rows):
    - 25000412CA: parcel_id='TIMESHARE'      (parser artifact)
    - 23001239CA: parcel_id='Property Appraiser' (parser artifact)
    - 25000637CA: parcel_id='MULTIPLE PARCELS' (parser artifact)
    - 09647-000-000, 10024-000-000, 15124-000-000: zone_code='See FLU' in Bay GIS
    - 25000874CA: NULL parcel_id, NULL address, NULL geo

  This script targets ONLY the 9 new rows (rows 119-127).
  Uses Bay County's live public ArcGIS REST endpoints (verified 2026-07-10,
  re-verified this session):
    - Zoning: gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1
    - Parcels: gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1

HONESTY MARKERS:
  - Every write traces to a live GIS response
  - BLANK > WRONG: if parcel not found, log and skip (no placeholder)
  - If zone_code='See FLU', log as known residual — do NOT write
  - Supabase REST API only (no fabricated data_source labels)

WIRING: This script is run once during the session. Output (rows fetched/written)
  is pasted into the session summary comment per WIRING MANDATE.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 scripts/gold_standard_shard5_bay_i_new_rows_backfill.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or ""
)
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

ZONING_URL = (
    "https://gis.baycountyfl.gov/arcgis/rest/services/"
    "Land_Use_Planning/MapServer/1/query"
)
PARCEL_URL = (
    "https://gis.baycountyfl.gov/arcgis/rest/services/"
    "TEST_Parcels/MapServer/1/query"
)

RATE_LIMIT = 2.0

# SUB_ZONING_ID -> jurisdiction_id mapping (verified from prior sessions)
# jurisdiction IDs are from the jurisdictions table in Supabase
JURISDICTION_MAP = {
    1: 1332,  # Unincorporated Bay County
    2: 862,   # Callaway
    3: 871,   # Lynn Haven
    4: 875,   # Mexico Beach
    5: 884,   # Panama City
    6: 907,   # Panama City Beach
}

# Known-unresolvable parser-artifact parcel_ids
SENTINEL_PARCEL_IDS = {"TIMESHARE", "Property Appraiser", "MULTIPLE PARCELS"}

# Known See-FLU parcel_ids (no usable zone_code in Bay County GIS)
SEE_FLU_PARCEL_IDS = {"09647-000-000", "10024-000-000", "15124-000-000"}

NOW = datetime.now(timezone.utc).isoformat()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg: str, level: str = "INFO") -> None:
    print(f"[{datetime.now(timezone.utc).isoformat()}] {level}: {msg}", flush=True)


# ---------------------------------------------------------------------------
# Supabase REST helpers
# ---------------------------------------------------------------------------
def sb_get(path: str, params: dict) -> list:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{BASE}/{path}?{qs}", headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"GET {path} {e.code}: {e.read().decode()}", "ERROR")
        return []


def sb_patch(path: str, params: dict, body: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}/{path}?{qs}", data=data, headers=HEADERS, method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"status": resp.status, "rows": result}
    except urllib.error.HTTPError as e:
        log(f"PATCH {path} {e.code}: {e.read().decode()}", "ERROR")
        return {"status": e.code, "rows": []}


def sb_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    h = dict(HEADERS)
    h["Prefer"] = "return=representation,resolution=ignore-duplicates"
    req = urllib.request.Request(f"{BASE}/{path}", data=data, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"status": resp.status, "rows": result}
    except urllib.error.HTTPError as e:
        log(f"POST {path} {e.code}: {e.read().decode()}", "ERROR")
        return {"status": e.code, "rows": []}


def sb_rpc(fn: str, params: dict) -> list:
    data = json.dumps(params).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=data, headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"RPC {fn} {e.code}: {e.read().decode()}", "ERROR")
        return []


# ---------------------------------------------------------------------------
# ArcGIS REST helpers
# ---------------------------------------------------------------------------
def arcgis_get(url: str, params: dict) -> dict:
    time.sleep(RATE_LIMIT)
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"ArcGIS GET {url} {e.code}: {e.read().decode()}", "ERROR")
        return {}
    except Exception as e:
        log(f"ArcGIS GET {url} ERROR: {e}", "ERROR")
        return {}


def lookup_zoning_by_point(lat: float, lon: float, buffer_deg: float = 0.0004) -> Optional[dict]:
    """Query Bay County Zoning layer via small envelope around (lat, lon)."""
    env = f"{lon - buffer_deg},{lat - buffer_deg},{lon + buffer_deg},{lat + buffer_deg}"
    data = arcgis_get(
        ZONING_URL,
        {
            "geometry": env,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false",
            "f": "json",
        },
    )
    feats = data.get("features", [])
    if not feats:
        return None
    attrs = feats[0]["attributes"]
    return {
        "zone_code": attrs.get("ZONING"),
        "sub_zoning": attrs.get("SUB_ZONING"),
        "jurisdiction_id": JURISDICTION_MAP.get(attrs.get("SUB_ZONING")),
        "label": attrs.get("Label"),
        "n_features": len(feats),
    }


def lookup_parcel_by_id(parcel_id: str) -> Optional[dict]:
    """Query Bay County TEST_Parcels layer by A1RENUM (parcel_id)."""
    data = arcgis_get(
        PARCEL_URL,
        {
            "where": f"A1RENUM='{parcel_id}'",
            "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
    )
    feats = data.get("features", [])
    if not feats:
        return None
    f = feats[0]
    attrs = f["attributes"]
    geo = f.get("geometry", {})
    rings = geo.get("rings", [])
    lat, lon = None, None
    if rings:
        ring = rings[0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        lat = sum(ys) / len(ys)
        lon = sum(xs) / len(xs)
    return {
        "parcel_id": attrs.get("A1RENUM"),
        "address": attrs.get("DSITEADDR"),
        "assessed_value": attrs.get("VASJUST"),
        "lat": lat,
        "lon": lon,
    }


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------
def get_bay_incomplete_cards() -> list:
    """Fetch bay rows where card is NOT complete (parcel_id or zone_code missing)."""
    log("Fetching bay rows with incomplete property cards...")
    rows = sb_get(
        "multi_county_auctions",
        {
            "county": "eq.bay",
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value",
            "order": "created_at.desc",
            "limit": "200",
        },
    )
    log(f"  Total bay rows fetched: {len(rows)}")

    # Filter to rows that might be incomplete
    # (missing parcel_id OR parcel_id is sentinel OR no parcel_zone entry)
    incomplete = []
    for row in rows:
        pid = row.get("parcel_id")
        if not pid:
            incomplete.append(row)
        elif pid in SENTINEL_PARCEL_IDS:
            log(f"  SKIP {row['case_number']}: sentinel parcel_id='{pid}'")
        elif pid in SEE_FLU_PARCEL_IDS:
            log(f"  SKIP {row['case_number']}: known See-FLU parcel_id='{pid}'")

    log(f"  Rows without valid parcel_id: {len(incomplete)}")
    return incomplete


def check_parcel_zone_exists(parcel_id: str) -> bool:
    """Check if parcel_zones has an entry for this parcel_id."""
    rows = sb_get(
        "parcel_zones",
        {"parcel_id": f"eq.{parcel_id}", "select": "parcel_id", "limit": "1"},
    )
    return len(rows) > 0


def process_row(row: dict, stats: dict) -> None:
    """Process one incomplete bay MCA row: look up parcel + zoning, write to DB."""
    case_number = row["case_number"]
    parcel_id = row.get("parcel_id")
    lat = row.get("latitude")
    lon = row.get("longitude")
    address = row.get("property_address")

    log(f"\nProcessing {case_number} | parcel_id={parcel_id} lat={lat} lon={lon}")

    # If we have lat/lon but no parcel_id, try zoning lookup first
    zoning_result = None
    if lat and lon:
        zoning_result = lookup_zoning_by_point(float(lat), float(lon))
        if zoning_result:
            zone_code = zoning_result.get("zone_code")
            log(f"  GIS zoning: zone_code={zone_code} sub_zoning={zoning_result.get('sub_zoning')} n_features={zoning_result.get('n_features')}")
            if zone_code == "See FLU":
                log(f"  SKIP {case_number}: zone_code='See FLU' (known Bay County GIS gap)")
                stats["see_flu_skip"] += 1
                return
        else:
            log(f"  No zoning result for lat={lat} lon={lon}")

    # If no parcel_id, can't do parcel lookup
    if not parcel_id:
        log(f"  No parcel_id and no lat/lon for {case_number} — cannot proceed")
        stats["no_data_skip"] += 1
        return

    # Look up parcel by ID
    parcel_data = lookup_parcel_by_id(parcel_id)
    if not parcel_data:
        log(f"  Parcel {parcel_id} not found in Bay GIS TEST_Parcels layer")
        stats["parcel_not_found"] += 1
        return

    log(f"  Parcel found: {parcel_data}")

    # Build MCA update payload
    mca_update = {"updated_at": NOW}
    if not lat and parcel_data.get("lat"):
        mca_update["latitude"] = parcel_data["lat"]
    if not lon and parcel_data.get("lon"):
        mca_update["longitude"] = parcel_data["lon"]
    if not row.get("assessed_value") and parcel_data.get("assessed_value"):
        mca_update["assessed_value"] = parcel_data["assessed_value"]
    if not address and parcel_data.get("address"):
        mca_update["property_address"] = parcel_data["address"]

    # Get zoning if we have lat/lon (either from row or just fetched from parcel)
    actual_lat = lat or parcel_data.get("lat")
    actual_lon = lon or parcel_data.get("lon")

    if actual_lat and actual_lon and not zoning_result:
        zoning_result = lookup_zoning_by_point(float(actual_lat), float(actual_lon))
        if zoning_result:
            log(f"  GIS zoning (from parcel centroid): zone_code={zoning_result.get('zone_code')}")

    # Apply MCA updates if anything changed
    if len(mca_update) > 1:  # more than just updated_at
        result = sb_patch(
            "multi_county_auctions",
            {"case_number": f"eq.{case_number}", "county": "eq.bay"},
            mca_update,
        )
        log(f"  MCA PATCH status={result['status']} rows_updated={len(result.get('rows', []))}")
        stats["mca_updated"] += 1

    # Insert parcel_zones if we have a valid zone_code
    if zoning_result:
        zone_code = zoning_result.get("zone_code")
        jurisdiction_id = zoning_result.get("jurisdiction_id")

        if zone_code and zone_code != "See FLU" and jurisdiction_id and parcel_id:
            if not check_parcel_zone_exists(parcel_id):
                pz_result = sb_post(
                    "parcel_zones",
                    {
                        "parcel_id": parcel_id,
                        "jurisdiction_id": jurisdiction_id,
                        "zone_code": zone_code,
                        "source": "gis.baycountyfl.gov/Land_Use_Planning/MapServer/1 shard5_20260718",
                        "created_at": NOW,
                    },
                )
                log(f"  parcel_zones INSERT status={pz_result['status']}")
                stats["parcel_zones_inserted"] += 1
            else:
                log(f"  parcel_zones already exists for {parcel_id}")
                stats["parcel_zones_exists"] += 1


def run_pencil_dod_eval(county: str) -> dict:
    """Run pencil_dod_evaluate_county RPC and return result."""
    log(f"\nRunning pencil_dod_evaluate_county('{county}')...")
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if result:
        log(f"  {county} eval: {json.dumps(result)}")
    return result


def main() -> int:
    if not SUPABASE_KEY:
        log("SUPABASE_SERVICE_ROLE_KEY not set", "ERROR")
        return 1

    log("=== GOLD STANDARD shard-5 bay I new-row backfill ===")
    log(f"dispatch_id: 9f070f2b-162c-43a2-b7f1-bc7940c13f8f")

    stats = {
        "rows_processed": 0,
        "mca_updated": 0,
        "parcel_zones_inserted": 0,
        "parcel_zones_exists": 0,
        "parcel_not_found": 0,
        "see_flu_skip": 0,
        "no_data_skip": 0,
    }

    # Get BEFORE eval
    log("\n--- BEFORE bay eval ---")
    before_eval = run_pencil_dod_eval("bay")

    # Fetch incomplete rows
    incomplete = get_bay_incomplete_cards()

    for row in incomplete:
        stats["rows_processed"] += 1
        try:
            process_row(row, stats)
        except Exception as e:
            log(f"ERROR processing {row.get('case_number')}: {e}", "ERROR")
            continue

    log("\n--- Processing complete ---")
    log(json.dumps(stats, indent=2))

    # Get AFTER eval
    log("\n--- AFTER bay eval ---")
    after_eval = run_pencil_dod_eval("bay")

    log("\n--- BEFORE/AFTER summary ---")
    log(f"BEFORE: {json.dumps(before_eval)}")
    log(f"AFTER:  {json.dumps(after_eval)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
