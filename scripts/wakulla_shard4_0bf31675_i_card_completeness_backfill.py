#!/usr/bin/env python3
"""
Gold Standard shard-4 (dispatch 0bf31675): wakulla letter I (property card
completeness) backfill.

BASELINE (verified live via pencil_dod_evaluate_county('wakulla') at session
start, immediately after the sibling wakulla-E task in the same workflow run):
  I: {"pass": false, "detail": "card_complete=41 of 52", "metric": 78.8}
  auctions_total: 52.

Ground-truth gap (11 rows), re-verified fresh via REST before any writes:
  - 4 rows (2026-TXD-124/125/126/127): missing parcel_id/address/geo/value
    entirely. CONFIRMED still true after the sibling wakulla-E task ran (E
    task's own evidence + a fresh WebFetch of wakullaclerk.org/official_records/
    tax_deed_sales.php this session both show these 4 as "Redeemed" plain-text
    rows with NO PDF link, NO cert number, NO parcel/address published
    anywhere on the clerk site). GENUINE STRUCTURAL GAP -- no cert number or
    address exists to search against qPublic/wakullatax.com/FL GIO. Left
    UNRESOLVED, not fabricated.

  - 4 rows (26-CA-19, 26-CA-31, 25-CA-9, 25-CA-145): already had
    parcel_id/address/geo, missing assessed_value/market_value only.
    RESOLVED via FL GIO Statewide Cadastral ArcGIS FeatureServer
    (services9.arcgis.com/Gh9awoU677aKree0/.../Florida_Statewide_Cadastral/
    FeatureServer/0), field JV (Just Value), matched by spatial
    point-in-polygon query at each row's stored lat/lon AND cross-checked by
    exact dashless PARCEL_ID string match + PHY_ADDR1 address match (3 of 4)
    or exact PARCEL_ID + PHY_ADDR1 + OWN_ADDR1 match (25-CA-145). JV was
    confirmed as the correct field by cross-referencing the one PARITY_OK row
    already on file for this county (25-CA-105: DB assessed_value=market_value
    =287905.00, FL GIO JV=AV_SD=AV_NSD=287905 exact match).
      26-CA-19  (00-00-073-335-10187-025): JV=250045
      26-CA-31  (13-4S-02W-000-01923-000): JV=151262
      25-CA-9   (00-00-075-262-10242-B02): JV=152344
      25-CA-145 (06-3S-01W-243-04301-039): JV=277716

  - 3 rows (25-CA-105, 2026-TXD-122, 2026-TXD-097): had full card fields
    (address/geo/value/parcel_id) but parcel_id did NOT resolve in
    v_zoning_gold_standard_card with a non-null zone_code. The prior session
    (dispatch 95d2d8fc, 2026-08-28) reconfirmed these as a ceiling using the
    OLDER "ZoningWakulla" ArcGIS layer (services1.arcgis.com/lDFzr3JyGEn5Eymu/
    .../ZoningWakulla/FeatureServer/0, a springshed-clipped partial-extent
    layer): 2 of 3 only hit a pre-subdivision PARENT parcel (correctly
    withheld per BLANK > WRONG), 1 had zero coverage at all.

    THIS SESSION found a DIFFERENT, newer, county-published, full-extent
    zoning district map that did not surface in the 08-28 session's search:
    "Zoning_Master Pro" at services9.arcgis.com/vAltLjtfYIJc7pDt/arcgis/rest/
    services/Zoning_Map/FeatureServer/30 (CUR_ZONING/ZONE_TYPE/Informatio
    fields, Informatio cites real Wakulla LDC section numbers e.g. "Sec.
    5-25, LDC"). This is the county's official zoning DISTRICT boundary map
    (legislative zoning, large polygons spanning many parcels by design --
    NOT a parcel/cadastral layer), confirmed via its own service metadata
    (name="Zoning_Master Pro", uniqueValue renderer keyed by CUR_ZONING) and
    cross-referenced against the Wakulla County GIS Hub's own "Zoning Map"
    page (gis-portal-update-wakullaplanning.hub.arcgis.com/pages/zoning).
    Point-in-polygon query at each row's exact stored lat/lon (not a parent-
    parcel spatial guess -- a direct hit on the actual zoning district
    polygon covering that ground point) resolved all 3:
      25-CA-105    (00-00-055-429-19932-034): CUR_ZONING=PUD
      2026-TXD-122 (30-2S-01W-000-04171-004): CUR_ZONING=AG
      2026-TXD-097 (23-5S-02W-128-02816-078): CUR_ZONING=RSU1

  BONUS (found while re-verifying the 4 assessed_value-only rows also needed
  zone_code -- the ground-truth doc's original split was INCOMPLETE, per this
  task's explicit instruction to "re-verify all of this fresh, do not trust
  it blindly"): the same 4 CA rows patched for assessed_value above ALSO had
  zero v_zoning_gold_standard_card zone_code coverage. Re-queried the same
  Zoning_Master Pro layer at their exact lat/lon:
      26-CA-19  (00-00-073-335-10187-025): CUR_ZONING=PUD
      26-CA-31  (13-4S-02W-000-01923-000): CUR_ZONING=RR1
      25-CA-145 (06-3S-01W-243-04301-039): CUR_ZONING=PUD
      25-CA-9   (00-00-075-262-10242-B02): NO HIT (point falls in an
        unmapped seam/gap between polygons -- a 300m buffer query around the
        same point returns 8 distinct neighboring zone codes (RSU2/RR1/RR2/
        C2/AG/CO/C4), so the exact governing district cannot be determined
        without guessing. Left UNRESOLVED, not fabricated -- a genuine,
        newly-confirmed structural gap distinct from and additional to the
        original 3 ceiling rows.

G-REGRESSION CAUGHT AND FIXED (same session, before claiming any result):
  Inserting parcel_zones rows for the new codes (PUD x2, AG, RSU1 x2, RR1)
  transiently broke letter G (95.0 pass -> FAIL far=0.0/pk1000=0.0) because
  RSU1 had no corresponding public.zoning_districts row for jurisdiction_id
  =1402 (Unincorporated Wakulla) at all. v_zoning_district_applicability /
  v_zoning_gold_standard_kpi_v3 treats a code with NO zoning_districts match
  as "default applicable=true" (documented fleet-wide failure pattern, see
  supabase/migrations/20260724x_gold_standard_shard3_wakulla_g_regression_fix.sql
  for the identical precedent on RR5/C2/PUD). Fixed by inserting a
  zoning_districts row for RSU1 (far_regulated=false, pk1000_regulated=false,
  citing the same LDC Sec. 5-28 reference the Zoning_Master Pro layer's own
  Informatio field provided), matching the existing R1/RMH1/RR1/RSU2 sibling
  rows' documented far/pk1000-not-applicable pattern for this county's
  residential districts. Post-fix: G restored to PASS (95.0, far=/pk1000=
  blank, byte-identical formula behavior to the pre-session baseline).

RESULT (live, verified via pencil_dod_evaluate_county('wakulla') immediately
after all writes):
  I: {"pass": false, "detail": "card_complete=47 of 52", "metric": 90.4}
      <- IMPROVED (78.8 -> 90.4, 41/52 -> 47/52) but still FAIL (threshold
      >=95%, needs >=50/52). Per this task's own math note, even the full
      8-row non-ceiling fix (all 4 CA value rows + 3 ceiling-zoning rows)
      caps at 49/52=94.2%, still below threshold -- this session additionally
      found a live zoning source for the 4 CA rows too, reaching 47/52 (only
      TXD-124/125/126/127's total-absence-of-identifying-data and 25-CA-9's
      zoning seam-gap remain unresolved of the original 11).
  No regression on A/B/C/D/E/F/G/H/J (all confirmed identical before/after
  except the G transient regression above, caught and fixed in the same
  session before final report).

This script is a RECORD of the session's live REST/RPC actions (all actual
writes were performed directly via PostgREST during the session, not by
running this script standalone). Re-running main() replays the same
idempotent writes for audit/reproducibility.
"""
import os
import sys
import json
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

ASSESSED_VALUE_FIXES = [
    # (case_number, value) -- FL GIO Statewide Cadastral JV field
    ("26-CA-19", 250045),
    ("26-CA-31", 151262),
    ("25-CA-9", 152344),
    ("25-CA-145", 277716),
]

PARCEL_ZONES_INSERTS = [
    # (parcel_id, jurisdiction_id, zone_code, zone_name)
    ("00-00-055-429-19932-034", 1402, "PUD", "Planned Unit Development"),
    ("30-2S-01W-000-04171-004", 1402, "AG", "AG Agricultural District"),
    ("23-5S-02W-128-02816-078", 1402, "RSU1", "Semi-Urban Residential District"),
    ("00-00-073-335-10187-025", 1402, "PUD", "Planned Unit Development"),
    ("13-4S-02W-000-01923-000", 1402, "RR1", "Semi-Rural Residential District"),
    ("06-3S-01W-243-04301-039", 1402, "PUD", "Planned Unit Development"),
]

PARCEL_ZONES_SOURCE = (
    "Wakulla_County_Zoning_Master_Pro_ArcGIS_"
    "services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30_"
    "wakulla_shard4_0bf31675_i"
)

RSU1_ZONING_DISTRICT = {
    "jurisdiction_id": 1402,
    "code": "RSU1",
    "name": (
        "RSU1 Semi-Urban Residential District -- VERIFIED zone_code from "
        "Wakulla County official Zoning_Master_Pro ArcGIS layer "
        "(services9.arcgis.com/vAltLjtfYIJc7pDt/Zoning_Map/FeatureServer/30, "
        "CUR_ZONING field, Informatio field cites Wakulla LDC Sec. 5-28), "
        "same documentation-gap class as this jurisdiction's existing "
        "R1/RMH1/RR1/RSU2 rows (dimensional standards not sourced this session)"
    ),
    "category": "residential",
    "ordinance_section": "Sec. 5-28",
    "far_regulated": False,
    "pk1000_regulated": False,
}


def _request(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def patch_assessed_values():
    for case_number, value in ASSESSED_VALUE_FIXES:
        path = f"multi_county_auctions?county=eq.wakulla&case_number=eq.{case_number}"
        result = _request("PATCH", path, {"assessed_value": value, "market_value": value})
        print(f"PATCH {case_number} -> {value}: {len(result)} row(s) updated")


def insert_parcel_zones():
    for parcel_id, jurisdiction_id, zone_code, zone_name in PARCEL_ZONES_INSERTS:
        existing = _request("GET", f"parcel_zones?parcel_id=eq.{parcel_id}")
        if existing:
            print(f"SKIP {parcel_id}: already has parcel_zones row(s)")
            continue
        body = [{
            "parcel_id": parcel_id,
            "jurisdiction_id": jurisdiction_id,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": PARCEL_ZONES_SOURCE,
        }]
        result = _request("POST", "parcel_zones", body)
        print(f"INSERT parcel_zones {parcel_id} -> {zone_code}: {len(result)} row(s)")


def insert_rsu1_zoning_district():
    existing = _request(
        "GET", "zoning_districts?jurisdiction_id=eq.1402&code=eq.RSU1"
    )
    if existing:
        print("SKIP RSU1 zoning_districts: already exists")
        return
    result = _request("POST", "zoning_districts", RSU1_ZONING_DISTRICT)
    print(f"INSERT zoning_districts RSU1: {len(result)} row(s)")


def main():
    patch_assessed_values()
    insert_parcel_zones()
    insert_rsu1_zoning_district()
    print("Done. Run pencil_dod_evaluate_county('wakulla') to verify.")


if __name__ == "__main__":
    main()
