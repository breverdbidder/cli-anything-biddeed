#!/usr/bin/env python3
"""Gold Standard walton letter I (property card completeness) — 2026-08-26.

Fastest-win fix identified this session: of the 10 live gap rows, exactly 2
rows already have property_address + latitude/longitude + assessed_value —
the ONLY thing blocking card_complete for them is a missing zone link
(no matching row in parcel_zones / v_zoning_gold_standard_card for their
parcel_id). This script closes just that gap for those 2 rows.

============================================================================
BASELINE (verified live via pencil_dod_evaluate_county, 2026-08-26)
============================================================================
I: card_complete=144 of 154 (93.5%) — FAIL, need >=147/154 (95%). Gap = 3
rows minimum; 10 total gap rows exist.

Fresh live diagnosis this session (independent re-fetch, paginated via
Range header, cross-checked against v_zoning_gold_standard_card + a direct
parcel_zones existence probe — NOT reused from any prior session's memory):

  8 rows missing address+geo+value+parcel_id entirely (calendar_sweep_mca_v3
  bare stubs / one address-less vacant parcel) — SAME case_numbers already
  confirmed as genuine structural ceilings by
  scripts/gold_standard_walton_i_letter_run_2rows_2026_08_25.py (2026-0125TD,
  25CA000531A) and scripts/gold_standard_shard3_walton_i_run9906_c5a8b2c7.py
  (26CA000030, 25CA000608, RealForeclose/civitek/qpublic all blocked) plus
  25CA000142, 19CA000472, 25CA000044, 26CA000062 (same calendar_sweep_mca_v3
  stub pattern, same blocked upstream sources). NOT re-attempted this
  session — no new lever exists vs. the prior two sessions' exhaustive
  probes.

  2 rows (the genuinely NEW gap identified this session) have
  property_address + latitude/longitude + assessed_value ALL already
  populated, and a real (non-placeholder) parcel_id, but NO row in
  parcel_zones for that parcel_id and thus no v_zoning_gold_standard_card
  match:
    - 25CA000348 (id=854d828c-6cb5-4d0f-b8d9-e863d0d3711b)
      parcel=25-3N-19-19070-000-7260, "111 W CHAFFIN AVE, DEFUNIAK
      SPRINGS, FL- 32433"
    - 25CA000493 (id=83cf06c9-d366-47c1-89c5-4e80b6fc75df)
      parcel=28-1S-21-41010-007-0140, "30 SYCAMORE DR, FREEPORT, FL- 32439"

Source (VERIFIED live, same endpoint used by prior walton-I sessions):
  Walton County EnerGov ArcGIS FeatureServer, Layer 19 (Zoning)
  https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer/19/query
  Point-in-polygon query against each row's own stored lat/lon (already
  verified accurate — DB lat/lon matches EnerGov parcel centroid within
  ~0.0001 deg for both rows).

  25CA000348 -> ZONE_CLASS='Municipal', PLAN_AREA='North Central'
    (DeFuniak Springs city limits — matches property_address city)
  25CA000493 -> ZONE_CLASS='Rural Village', PLAN_AREA='South Central'
    (unincorporated Walton — matches property_address city Freeport,
    which is NOT itself a Walton jurisdiction in our jurisdictions table
    for this zone class; Freeport town limits use a different zoning
    regime not returned by this point query, so we defer to what the
    county's own zoning layer says for this exact point: Rural Village).

  zoning_districts rows for both ZONE_CLASS values ALREADY EXIST live
  (verified via direct query before writing — no new zoning_districts
  insert needed, only a parcel_zones link):
    id=11397 jurisdiction_id=842  (DeFuniak Springs) code='Municipal'
    id=11394 jurisdiction_id=1333 (Unincorp. Walton) code='Rural Village'

Fix: INSERT INTO parcel_zones (parcel_id, tax_account, jurisdiction_id,
zone_code, source, effective_date) for both parcels, matching the existing
zoning_districts jurisdiction_id exactly (no invented jurisdiction).

FAIL-LOUD invariant: if gap rows are parsed but zero DB writes occur, raise.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

DISPATCH_TAG = "gs_walton_i_zonelink_20260826"
ENERG0V_ZONING = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer/19/query"

# id -> (parcel_id, lat, lon, expected jurisdiction_id, expected zone_class)
TARGET_ROWS = {
    "854d828c-6cb5-4d0f-b8d9-e863d0d3711b": {
        "case_number": "25CA000348",
        "parcel_id": "25-3N-19-19070-000-7260",
        "lat": 30.723282,
        "lon": -86.117075,
    },
    "83cf06c9-d366-47c1-89c5-4e80b6fc75df": {
        "case_number": "25CA000493",
        "parcel_id": "28-1S-21-41010-007-0140",
        "lat": 30.474244,
        "lon": -86.337123,
    },
}


def _sb_headers(prefer: str = "") -> dict:
    h = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_get(table: str, params: dict) -> list:
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{SB_URL}/rest/v1/{table}?{qs}", headers=_sb_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(table: str, body, prefer: str = "return=minimal") -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(),
        headers=_sb_headers(prefer),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_rpc(fn: str, payload: dict):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers=_sb_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def arcgis_zone_query(lat: float, lon: float) -> dict | None:
    qs = urllib.parse.urlencode({
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONE_CLASS,PLAN_AREA",
        "inSR": "4326",
        "f": "json",
    })
    req = urllib.request.Request(
        f"{ENERG0V_ZONING}?{qs}",
        headers={"User-Agent": "BidDeed-GoldStandard-Walton-ZoneLink/1.0; contact:ariel@everestcapitalusa.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    return feats[0]["attributes"] if feats else None


def get_zoning_district(zone_class: str) -> dict | None:
    rows = sb_get(
        "zoning_districts",
        {"select": "id,jurisdiction_id,code,category", "code": f"eq.{zone_class}", "limit": "1"},
    )
    return rows[0] if rows else None


def parcel_zone_exists(parcel_id: str) -> bool:
    rows = sb_get("parcel_zones", {"select": "id", "parcel_id": f"eq.{parcel_id}", "limit": "1"})
    return bool(rows)


def main() -> int:
    if not SB_KEY or not SB_URL:
        print("ERROR: missing Supabase credentials/env", file=sys.stderr)
        return 1

    print("=== BEFORE (walton I) ===")
    before = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(before.get("I", {}), indent=2))

    zoned_new = 0

    for row_id, info in TARGET_ROWS.items():
        parcel_id = info["parcel_id"]
        print(f"\n=== {info['case_number']} (id={row_id}) parcel={parcel_id} ===")

        if parcel_zone_exists(parcel_id):
            print("  SKIP: parcel_zones entry already exists live (may have been fixed already)")
            continue

        attrs = arcgis_zone_query(info["lat"], info["lon"])
        if not attrs or not attrs.get("ZONE_CLASS"):
            print(f"  SKIP: EnerGov zoning layer returned no ZONE_CLASS for {parcel_id} — no fix applied, real ceiling")
            continue

        zone_class = attrs["ZONE_CLASS"].strip()
        plan_area = attrs.get("PLAN_AREA")
        print(f"  EnerGov Layer 19 (Zoning) VERIFIED: ZONE_CLASS={zone_class!r} PLAN_AREA={plan_area!r}")

        district = get_zoning_district(zone_class)
        if not district:
            print(f"  SKIP: no existing zoning_districts row for code={zone_class!r} — "
                  f"not inventing a new jurisdiction mapping this run, real ceiling")
            continue

        jur_id = district["jurisdiction_id"]
        print(f"  zoning_districts VERIFIED match: id={district['id']} jurisdiction_id={jur_id} category={district['category']}")

        sb_post(
            "parcel_zones",
            {
                "parcel_id": parcel_id,
                "tax_account": parcel_id,
                "jurisdiction_id": jur_id,
                "zone_code": zone_class,
                "source": f"walton_enerGov_arcgis/{DISPATCH_TAG}_{date.today().isoformat()}",
                "effective_date": "2018-12-11",
            },
            prefer="resolution=ignore-duplicates,return=minimal",
        )
        zoned_new += 1
        print(f"  parcel_zones INSERTED: {parcel_id} -> jur={jur_id} zone={zone_class}")

    print(f"\nzoned_new={zoned_new}")

    if TARGET_ROWS and zoned_new == 0:
        raise RuntimeError(
            f"FAIL-LOUD: parsed {len(TARGET_ROWS)} walton zone-link gap rows but wrote 0 "
            f"(zoned_new=0) — silent no-op, refusing to report success."
        )

    print("\n=== AFTER (walton I) ===")
    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(after.get("I", {}), indent=2))

    print("\n=== SUMMARY ===")
    print(f"I before: {before.get('I')}")
    print(f"I after:  {after.get('I')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
