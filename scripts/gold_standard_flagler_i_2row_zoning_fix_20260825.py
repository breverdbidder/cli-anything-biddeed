#!/usr/bin/env python3
"""
gold_standard_flagler_i_2row_zoning_fix_20260825.py — flagler-only.

Forked from scripts/gold_standard_shard10_flagler_i_fix_run6796.py and
scripts/gold_standard_flagler_i_8gap_geo_zoning_fix.py (same county, same
letter, same ArcGIS-verified point-in-polygon zoning-lookup pattern).

Fixes letter I (card_complete) FAIL at 94.5% (155/164). Task brief flagged 4
rows with real parcel_id + real lat/lng but NULL zoning_code:
  2e7aef04-be0d-43c7-93cf-3d74ffedd3f6 (20-10-31-3050-00080-0050)
  58ef3cf4-2522-46c6-8bf6-30c88417633e (07-11-31-7025-00160-0170)
  7c6013d5-1130-4c29-a93b-8217c4a1cf33 (20-10-31-0300-00150-0000)
  c1b495e8-a142-4f7c-aaad-7372948dfe2b (07-11-31-7013-00040-0340)

Live ArcGIS re-check this session (0-tolerance point-in-polygon, then 30m/10m
buffer retry ONLY when every polygon returned agrees on the same code):
  - c1b495e8: inside PalmCoastFL_CityLimits, 0-tolerance hit on
    PalmCoastFL_Zoning -> SFR-2 (unambiguous). WRITTEN.
  - 2e7aef04: 0-tolerance miss both layers; 10m buffer on
    Unincorporated_Zoning FeatureServer -> 3 unanimous R-1 polygons. WRITTEN.
    (R-1 did not exist yet in zoning_districts for jurisdiction_id=1184 --
    inserted, category/name only, no fabricated standards.)
  - 58ef3cf4: 30m buffer -> MIXED (SFR-2 + SFR-3). Genuine boundary
    ambiguity, matches the 20260816 migration's documented residual. LEFT
    UNZONED (BLANK > WRONG).
  - 7c6013d5: 30m buffer on Unincorporated_Zoning -> MIXED (R-1 + R/C).
    Genuine ambiguity. LEFT UNZONED.

Idempotent -- safe to re-run (checks parcel_zones for an existing row before
insert, checks zoning_districts for an existing code before insert).

Usage: python3 scripts/gold_standard_flagler_i_2row_zoning_fix_20260825.py
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

PALMCOAST_ZONING = "https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_Zoning/FeatureServer/0/query"
PALMCOAST_CITYLIMITS = "https://services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_CityLimits/FeatureServer/0/query"
UNINCORPORATED_ZONING = "https://services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0/query"

# Confirmed live this session -- see migration file for full derivation notes.
PARCEL_ZONE_TARGETS = [
    {
        "parcel_id": "07-11-31-7013-00040-0340",
        "jurisdiction_id": 966,  # Palm Coast
        "zone_code": "SFR-2",
        "zone_name": "Single-Family Residential District",
        "new_district": False,  # already exists (zoning_districts id=7614)
        "source": "PalmCoastFL_Zoning FeatureServer (services1.arcgis.com/tpnsCwhQRDqwL3mq/arcgis/rest/services/PalmCoastFL_Zoning/FeatureServer/0) LAYER field, point-in-polygon @ 29.561273,-81.241686, confirmed inside PalmCoastFL_CityLimits, 0-tolerance exact hit, verified live 2026-08-25",
    },
    {
        "parcel_id": "20-10-31-3050-00080-0050",
        "jurisdiction_id": 1184,  # Unincorporated Flagler
        "zone_code": "R-1",
        "zone_name": "RURAL RESIDENTIAL",
        "new_district": True,
        "source": "Flagler County Unincorporated_Zoning FeatureServer (services3.arcgis.com/hSKL9bYjhP4rHxSD/arcgis/rest/services/Unincorporated_Zoning/FeatureServer/0) ZONECODE/ZONENAME field, point-in-polygon @ 29.617258375565,-81.193565937186, 0-tolerance miss but 10m buffer returned 3 unanimous R-1/CITYNAME=UNINCORPORATED polygons, verified live 2026-08-25",
    },
]

# Re-confirmed ambiguous this session -- explicitly NOT written.
AMBIGUOUS_RESIDUALS = [
    {"parcel_id": "07-11-31-7025-00160-0170", "reason": "30m buffer MIXED (2x SFR-2, 4x SFR-3) on PalmCoastFL_Zoning -- boundary straddle"},
    {"parcel_id": "20-10-31-0300-00150-0000", "reason": "30m buffer MIXED (3x R-1, 1x R/C) on Unincorporated_Zoning -- boundary straddle"},
]


def rest_get(path: str, params: str = "") -> list:
    url = f"{BASE}/{path}{'?' + params if params else ''}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  GET ERROR {path}: {e.code} {e.read().decode()[:300]}")
        return []


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


def arcgis_query(url: str, lon: float, lat: float, distance_m: int = 0) -> list:
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "f": "json",
    }
    if distance_m:
        params["distance"] = str(distance_m)
        params["units"] = "esriSRUnit_Meter"
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{q}", timeout=20) as r:
        data = json.loads(r.read())
    return data.get("features", [])


def ensure_zoning_district(jurisdiction_id: int, code: str, name: str) -> bool:
    existing = rest_get(
        "zoning_districts",
        f"jurisdiction_id=eq.{jurisdiction_id}&code=eq.{urllib.parse.quote(code)}&select=id",
    )
    if existing:
        print(f"    zoning_districts {code} already exists for jurisdiction {jurisdiction_id} (id={existing[0]['id']})")
        return True
    body = {"jurisdiction_id": jurisdiction_id, "code": code, "name": name, "category": "Residential"}
    status, resp = rest_post("zoning_districts", body)
    if status in (200, 201):
        print(f"    INSERTED zoning_districts {code} for jurisdiction {jurisdiction_id}: {resp}")
        return True
    print(f"    ERROR inserting zoning_districts {code}: {status} {resp}")
    return False


def fix_parcel_zones():
    print("\n=== parcel_zones inserts ===")
    inserted = 0
    for t in PARCEL_ZONE_TARGETS:
        pid = t["parcel_id"]
        existing = rest_get(
            "parcel_zones",
            f"parcel_id=eq.{urllib.parse.quote(pid)}&jurisdiction_id=eq.{t['jurisdiction_id']}&select=id",
        )
        if existing:
            print(f"  {pid}: parcel_zones row already exists (id={existing[0]['id']}) -- skip")
            continue
        if t["new_district"]:
            ensure_zoning_district(t["jurisdiction_id"], t["zone_code"], t["zone_name"])
        body = {
            "parcel_id": pid,
            "jurisdiction_id": t["jurisdiction_id"],
            "zone_code": t["zone_code"],
            "zone_name": t["zone_name"],
            "source": t["source"],
        }
        status, resp = rest_post("parcel_zones", body)
        if status in (200, 201):
            print(f"  {pid}: INSERTED zone_code={t['zone_code']} jurisdiction_id={t['jurisdiction_id']}")
            inserted += 1
        else:
            print(f"  {pid}: INSERT FAILED {status} {resp}")
    return inserted


def report_residuals():
    print("\n=== Ambiguous residuals -- re-confirmed, NOT written (BLANK > WRONG) ===")
    for r in AMBIGUOUS_RESIDUALS:
        print(f"  {r['parcel_id']}: {r['reason']}")


def verify_targets():
    print("\n=== Verification: re-GET all 4 target parcel_ids ===")
    for t in PARCEL_ZONE_TARGETS + [{"parcel_id": r["parcel_id"], "jurisdiction_id": None} for r in AMBIGUOUS_RESIDUALS]:
        pid = t["parcel_id"]
        pz = rest_get("parcel_zones", f"parcel_id=eq.{urllib.parse.quote(pid)}&select=zone_code,jurisdiction_id,source")
        print(f"  {pid}: parcel_zones={pz}")


def main():
    print("=== gold_standard_flagler_i_2row_zoning_fix_20260825 ===")

    before = evaluate_county(COUNTY)
    print(f"BEFORE: {json.dumps(before.get('I', {}))}")

    zones_inserted = fix_parcel_zones()
    report_residuals()

    print(f"\nTOTALS: parcel_zones inserted={zones_inserted}/2, ambiguous_residuals=2 (left unzoned)")

    verify_targets()

    after = evaluate_county(COUNTY)
    print(f"\nAFTER: {json.dumps(after.get('I', {}))}")
    print(f"\nFULL AFTER (all letters): {json.dumps(after)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
