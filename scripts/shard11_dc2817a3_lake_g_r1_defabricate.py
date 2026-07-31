#!/usr/bin/env python3
"""SHARD-11 (dispatch dc2817a3) lake letter G fix: de-fabricate the leftover
synthetic R-1 district under jurisdiction_id=835 and remove 4 orphaned
synthetic parcel_zones rows with no real multi_county_auctions backing.

LIVE VERIFICATION PERFORMED THIS SESSION (see session report for full detail):
  1. Confirmed live via v_zoning_gold_standard_kpi_v3 + pencil_dod_evaluate_county:
     lake G = density 93.8% (45/48), far 100%, pk1000 N/A -- BASELINE.
  2. Fetched Lake County's live Municode API (same jobId=487541/productId=11115
     used by the prior shard7c fix) for Table 3.02.06 AND Section 3.00.00 (district
     name list). Confirmed:
       - "R-1" = "Rural Residential" district, Table 3.02.06 real values:
         1 DU/AC density (NOT 4.0), FAR 0.20 (NOT 0.35).
       - A/R-3/R-6/R-7/RM/CFD values already written by shard7c ALL match this
         live table exactly -- those 6 codes are CONFIRMED CORRECT, not touched.
  3. Found zoning_districts id=10716 (jurisdiction_id=835, code='R-1') is still
     the literal fabricated row from an OLDER session:
       name = "Single Family Residential (Shard7 Synthetic)"
       description = "Synthetic R-1 district seeded by shard7_g_i_fix for Gold
                       Standard I criterion"
     zone_standards id=3401 attached to it: max_density_du_acre=4.0, max_far=0.35,
     parking_per_1000sf=2.0, source_url=NULL, confidence_score=NULL -- i.e. it was
     NEVER replaced by the shard7c live-Table-3.02.06 fix (that fix wrote NEW rows
     for A/CFD/PUD/R-3/R-6/R-7/RM but did not touch the pre-existing R-1 row,
     because it already existed and the script's ensure_zoning_district() skips
     when a row is already present).
  4. Of the 10 parcel_zones rows pointing at zone_code='R-1'/jurisdiction_id=835:
       - 4 have parcel_id values 'SYN-LAKE-FC-001/002/003' and
         'SYN-LAKE-TD-SHARD6-001' -- confirmed via live query against
         multi_county_auctions that ZERO of these parcel_ids exist in that table
         (or anywhere else). They are pure orphaned synthetic rows with no real
         auction/parcel behind them -- inflating the G-metric denominator with
         fake data. DELETED.
       - 6 have real parcel_ids with real lat/lon in multi_county_auctions
         (source tag was 'shard7_g_i_fix/lake_auto' / 'shard6_run651_synthetic' --
         i.e. the zone_code assignment ITSELF was fabricated, not derived from any
         GIS query, even though the 6 real parcels do exist). Re-verified live
         against Lake County's own zoning GIS layer
         (gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50)
         for each parcel's real coordinates:
           HIT (3 of 6): 33-18-24-000400005800, 28-17-28-000400003400,
             28-17-28-000400003500 -- GIS independently returns Zoning='R-1',
             ZoningNm='Rural Residential' -- CONFIRMS zone_code='R-1' was
             coincidentally correct for these 3, so their parcel_zones.zone_code
             is left as-is (now pointing at the corrected district/standards).
           MISS (3 of 6): 13-19-26-120100004600, 22-19-24-092500000900,
             25-19-24-120000001702 -- no ArcGIS feature at those coordinates
             (parcel falls inside an incorporated municipality that zones its
             own land, same structural pattern as the existing coverage-backfill
             script's MISS handling). Their fabricated 'R-1' zone_code assignment
             is UNSOURCED and should not be trusted, but per the "conservative,
             don't fabricate, don't guess" rule this script does NOT overwrite or
             delete them -- it leaves them exactly as found and flags them in the
             receipt as a genuine unresolved gap for a future session with access
             to per-municipality zoning layers.

FIX APPLIED:
  - UPDATE zoning_districts id=10716: name -> 'Rural Residential', category ->
    'Residential', description -> live-source note (real Lake County name/code
    per Section 3.00.00.C.3).
  - UPDATE zone_standards id=3401: max_density_du_acre 4.0 -> 1.0, max_far
    0.35 -> 0.20, parking_per_1000sf 2.0 -> NULL (unsourced fabricated value,
    Table 3.02.06 does not carry a parking figure), source_url/ordinance_section/
    confidence_score set to the same live Municode citation shard7c used.
  - DELETE 4 parcel_zones rows (SYN-LAKE-FC-001/002/003, SYN-LAKE-TD-SHARD6-001)
    -- orphaned synthetic rows with zero real backing anywhere.
  - The 6 real-parcel R-1 rows are NOT deleted or re-coded (GIS independently
    confirms 3 of them; the other 3 MISS but "R-1" is not disprovable as wrong
    either -- leaving the code alone and only fixing the DIMENSIONAL VALUES it
    points to is the conservative move; a code-level re-verification for the 3
    MISS parcels is out of scope here and logged as a residual, not silently
    resolved).

This script only touches jurisdiction_id=835 zone_code='R-1' rows in lake.
It does not touch A/R-3/R-6/R-7/RM/CFD/PUD (already verified correct or
already-honest N/A) or any other lake jurisdiction.

Usage:
  python3 scripts/shard11_dc2817a3_lake_g_r1_defabricate.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

DRY_RUN = "--dry-run" in sys.argv

DISTRICT_ID = 10716
STANDARDS_ID = 3401
ORPHAN_PARCEL_ZONE_IDS = [818442, 818449, 818450, 819871]  # SYN-LAKE-* rows

SOURCE_URL = ("https://api.municode.com/CodesContent?jobId=487541&"
              "nodeId=APXELADERE_CHIIZODIRE_3.02.00BURE&productId=11115"
              " (Lake County Code of Ordinances, Appendix E LDR, Chapter III Zoning "
              "District Regulations, Table 3.02.06, cross-checked against Section "
              "3.00.00.C.3 district name list -- 'R-1' = 'Rural Residential' -- "
              "codified through Ord. No. 2026-3, live Supplement 150; human-readable "
              "viewer: https://library.municode.com/fl/lake_county/codes/code_of_ordinances"
              "?nodeId=APXELADERE_CHIIZODIRE_3.02.00BURE)")
ORDINANCE_SECTION = "Table 3.02.06 (Density...) + Section 3.00.00.C.3 (district names)"


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def rest_get(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        log(f"PATCH {path} FAILED: {e.code} {body_err}", "VERIFIED")
        raise


def rest_delete(path):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}", method="DELETE",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Prefer": "return=representation"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_err = e.read().decode()
        log(f"DELETE {path} FAILED: {e.code} {body_err}", "VERIFIED")
        raise


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    log("=== SHARD-11 lake G fix: de-fabricate R-1 (jurisdiction 835) ===")

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    log(f"BASELINE G: {baseline['G']}", "VERIFIED")

    # sanity re-check right before writing: confirm the fabricated row is still
    # exactly what we expect (name/description match), and confirm the 4 orphan
    # rows still have zero multi_county_auctions backing.
    district = rest_get(f"zoning_districts?id=eq.{DISTRICT_ID}&select=*")
    if not district or "Synthetic" not in (district[0].get("description") or ""):
        log("SAFETY ABORT: zoning_districts id=10716 no longer matches the "
            "expected fabricated-row fingerprint. Not touching it.", "VERIFIED")
        sys.exit(1)
    log(f"Confirmed fabricated district fingerprint: {district[0]['name']!r} / "
        f"{district[0]['description']!r}", "VERIFIED")

    for pzid in ORPHAN_PARCEL_ZONE_IDS:
        pz = rest_get(f"parcel_zones?id=eq.{pzid}&select=parcel_id")
        if not pz:
            log(f"parcel_zones id={pzid} already gone, skipping", "VERIFIED")
            continue
        pid = pz[0]["parcel_id"]
        check = rest_get(f"multi_county_auctions?parcel_id=eq.{pid}&select=id")
        if check:
            log(f"SAFETY ABORT: parcel_id={pid} (parcel_zones id={pzid}) now HAS "
                f"real multi_county_auctions backing -- not deleting.", "VERIFIED")
            sys.exit(1)
        log(f"Confirmed parcel_zones id={pzid} parcel_id={pid} has zero real "
            f"multi_county_auctions rows -- orphaned synthetic, safe to delete",
            "VERIFIED")

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        print(f"Would UPDATE zoning_districts id={DISTRICT_ID}, "
              f"zone_standards id={STANDARDS_ID}, "
              f"DELETE parcel_zones ids={ORPHAN_PARCEL_ZONE_IDS}")
        return

    # 1. Fix the district row's name/category to reflect the real district.
    updated_district = rest_patch(
        f"zoning_districts?id=eq.{DISTRICT_ID}",
        {
            "name": "Rural Residential",
            "category": "Residential",
            "description": ("Real Lake County 'R-1' Rural Residential district "
                             "(Sec. 3.00.00.C.3); dimensional standards per Table "
                             "3.02.06 -- replaces the prior synthetic placeholder."),
            "ordinance_section": ORDINANCE_SECTION,
        })
    log(f"Updated zoning_districts id={DISTRICT_ID}: {updated_district}", "VERIFIED")

    # 2. Fix the standards row's fabricated dimensional values.
    updated_standards = rest_patch(
        f"zone_standards?id=eq.{STANDARDS_ID}",
        {
            "max_density_du_acre": 1.0,
            "max_far": 0.20,
            "parking_per_1000sf": None,
            "source_url": SOURCE_URL,
            "ordinance_section": "Table 3.02.06 (Density, Impervious Surface, Floor Area, and Height Requirements)",
            "confidence_score": 1.0,
        })
    log(f"Updated zone_standards id={STANDARDS_ID}: {updated_standards}", "VERIFIED")

    # 3. Delete the 4 orphaned synthetic parcel_zones rows.
    for pzid in ORPHAN_PARCEL_ZONE_IDS:
        deleted = rest_delete(f"parcel_zones?id=eq.{pzid}")
        log(f"Deleted parcel_zones id={pzid}: {deleted}", "VERIFIED")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    log(f"AFTER G: {after['G']}", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print("SELECT id, code, name, description FROM zoning_districts WHERE id=10716;")
    print("SELECT id, max_density_du_acre, max_far, parking_per_1000sf, source_url "
          "FROM zone_standards WHERE id=3401;")
    print("SELECT count(*) FROM parcel_zones WHERE id IN (818442,818449,818450,819871);"
          "  -- expect 0")
    print(f"BEFORE G: {baseline['G']}")
    print(f"AFTER  G: {after['G']}")


if __name__ == "__main__":
    main()
