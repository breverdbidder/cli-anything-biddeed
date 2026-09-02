#!/usr/bin/env python3
"""Gold Standard walton letter I (property card completeness) — 2026-09-02.

Template: scripts/gold_standard_shard3_walton_i_zonelink_2rows_2026_08_26.py
(same EnerGov ArcGIS FeatureServer, same parcel_zones INSERT pattern).

============================================================================
BASELINE (verified live via pencil_dod_evaluate_county, 2026-09-02)
============================================================================
I: card_complete=150 of 158 (94.9%) — FAIL, need >=151/158 (95%). Gap = 1 row.

Fresh live diagnosis this session (independent re-fetch of all 158 walton
rows via multi_county_auctions REST, cross-checked field-by-field against
the evaluator's known predicate: property_address, COALESCE(latitude,
po_latitude), COALESCE(longitude,po_longitude), COALESCE(assessed_value,
market_value), AND a parcel_zones/v_zoning_gold_standard_card match):

  8 rows fail the base-field predicate entirely (address/geo/value/parcel_id
  missing or placeholder): 19CA000472, 25CA000044, 25CA000142, 25CA000531A,
  26CA000030, 26CA000062, 2026-0125TD, 25CA000404.

  Of those 8, 7 are the SAME case_numbers already exhaustively confirmed as
  genuine structural ceilings by prior sessions:
    - scripts/gold_standard_walton_i_letter_run_2rows_2026_08_25.py:
      2026-0125TD (address-less vacant ag parcel, 3 independent
      county/state sources agree), 25CA000531A (timeshare-interest
      foreclosure, no discrete parcel_id exists in any FL CAMA/GIS system
      by domain characteristic; RealForeclose 403 + civitek JSF postback +
      LandmarkWeb SPA all re-confirmed blocked).
    - scripts/gold_standard_shard3_walton_i_run9906_c5a8b2c7.py /
      scripts/gold_standard_walton_i_letter_run_85f2942e.py:
      19CA000472, 25CA000044, 25CA000142, 26CA000030, 26CA000062 — all
      data_source=calendar_sweep_mca_v3 bare stubs, RealForeclose
      case-detail route structurally blocked (curl + headless Playwright
      both confirmed splash-page-only, no case JSON).
  NOT re-attempted this session — no new lever exists vs. those exhaustive
  prior probes. (25CA000608, previously in this ceiling bucket, has since
  been resolved by a separate session — confirmed live this session: it now
  has full base fields + zone link.)

  1 row is a GENUINELY NEW gap (row created 2026-09-02, same day as this
  session, by calendar_sweep_mca_v3 — did not exist in any prior session's
  denominator):
    - 25CA000404 (id=cd860516-8e1f-4087-b511-6be3cb7cbff4)
      parcel=30-2S-19-24010-000-0050, "45 CROSSING LN, SANTA ROSA BEACH,
      FL- 32459". property_address + assessed_value (250791) + parcel_id
      ALL already populated. ONLY latitude/longitude were null, AND no
      parcel_zones row existed for this parcel_id.

Source (VERIFIED live, same endpoints used by prior walton-I sessions):
  Walton County EnerGov ArcGIS FeatureServer
  https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer/

  Step 1 — Layer 4 (Parcels), queried by PARCELNO='30-2S-19-24010-000-0050'
  with returnCentroid=true, outSR=4326:
    centroid lon=-86.18628809658732 lat=30.38285195048736
    (cross-checked against a manual polygon-ring average from the same
    query with returnGeometry=true instead: -86.18627882356171,
    30.38286280123922 — agrees to ~0.00001 deg, confirms centroid is real
    and not a service default/fallback)
    OWNER_NAME='VALENTINE WILLIAM RUSH III &', USE_DESC='TOWNHOUSE'
    (consistent with a residential foreclosure at a "LN" address)

  Step 2 — Layer 19 (Zoning), point-in-polygon at that centroid:
    ZONE_CLASS='Town Center One', PLAN_AREA='South'
    (Santa Rosa Beach / South Walton area — matches property_address city)

  Step 3 — jurisdiction resolution: Santa Rosa Beach is NOT a separate
  incorporated municipality in our jurisdictions table (only DeFuniak
  Springs id=842, Freeport id=861, Paxton id=1146, and Unincorporated
  Walton County id=1333 exist for county='Walton') — this parcel falls
  under jurisdiction_id=1333, same as the other unincorporated-Walton
  zone_code rows already in zoning_districts (Rural Village, Rural Low
  Density, etc., all jurisdiction_id=1333).

  No zoning_districts row existed yet for code='Town Center One' (checked
  live before writing). Unlike the 2026-08-26 zonelink script (which
  skipped when no zoning_districts match existed, to avoid inventing a
  jurisdiction mapping), THIS zone_code's jurisdiction is not ambiguous —
  Layer 19's own geometry resolved directly against Layer 4's own
  centroid for THIS parcel, both from the same authoritative EnerGov
  source, both in unincorporated Walton. Inserted a new zoning_districts
  row (id=14374) with jurisdiction_id=1333 to record this newly-observed
  zone class, category='mixed' (Walton's Town Center districts are
  mixed-use per the county LDC), then linked parcel_zones to it.

  Verified empirically (dry-run insert + delete of a throwaway
  parcel_zones row) that v_zoning_gold_standard_card resolves directly off
  parcel_zones.parcel_id + jurisdiction_id + zone_code — it does NOT
  require a zoning_districts FK match for existence (zoning_districts is
  only used upstream to source the correct jurisdiction_id when
  cross-referencing an already-known zone_code). Confirmed by checking the
  two rows fixed by the 2026-08-26 zonelink script: both appear in the
  view with gold_core_complete=false (standards fields null) but are still
  countable for Criterion I, which only requires the row to exist.

FAIL-LOUD invariant: if the gap row is parsed but zero DB writes occur,
raise.
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

DISPATCH_TAG = "gs_walton_i_25CA000404_20260902"
ENERG0V_PARCELS = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer/4/query"
ENERG0V_ZONING = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer/19/query"

TARGET_ROW_ID = "cd860516-8e1f-4087-b511-6be3cb7cbff4"
TARGET_CASE = "25CA000404"
TARGET_PARCEL = "30-2S-19-24010-000-0050"
UNINCORP_WALTON_JURISDICTION_ID = 1333


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


def sb_patch(table: str, filt: str, body: dict) -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filt}",
        data=json.dumps(body).encode(),
        headers=_sb_headers("return=representation"),
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_post(table: str, body, prefer: str = "return=representation") -> bytes:
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


def arcgis_parcel_centroid(parcelno: str) -> tuple[float, float] | None:
    qs = urllib.parse.urlencode({
        "where": f"PARCELNO='{parcelno}'",
        "outFields": "PARCELNO",
        "returnCentroid": "true",
        "returnGeometry": "false",
        "outSR": "4326",
        "f": "json",
    })
    req = urllib.request.Request(
        f"{ENERG0V_PARCELS}?{qs}",
        headers={"User-Agent": "BidDeed-GoldStandard-Walton-GeoZone/1.0; contact:ariel@everestcapitalusa.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    if not feats or "centroid" not in feats[0]:
        return None
    c = feats[0]["centroid"]
    return c["y"], c["x"]  # lat, lon


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
        headers={"User-Agent": "BidDeed-GoldStandard-Walton-GeoZone/1.0; contact:ariel@everestcapitalusa.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    return feats[0]["attributes"] if feats else None


def get_or_create_zoning_district(zone_class: str, jurisdiction_id: int) -> dict:
    rows = sb_get(
        "zoning_districts",
        {"select": "id,jurisdiction_id,code,category", "code": f"eq.{zone_class}", "jurisdiction_id": f"eq.{jurisdiction_id}", "limit": "1"},
    )
    if rows:
        return rows[0]
    created = json.loads(sb_post(
        "zoning_districts",
        {
            "jurisdiction_id": jurisdiction_id,
            "code": zone_class,
            "name": zone_class,
            "category": "mixed",
            "ordinance_section": f"walton_enerGov_zoning_layer19_verified_{date.today().isoformat()}",
        },
    ))
    return created[0]


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

    writes = 0

    print(f"\n=== {TARGET_CASE} (id={TARGET_ROW_ID}) parcel={TARGET_PARCEL} ===")

    centroid = arcgis_parcel_centroid(TARGET_PARCEL)
    if not centroid:
        print(f"  SKIP: EnerGov Parcels layer returned no centroid for {TARGET_PARCEL} — real ceiling")
    else:
        lat, lon = centroid
        print(f"  EnerGov Layer 4 (Parcels) VERIFIED centroid: lat={lat} lon={lon}")

        sb_patch(
            "multi_county_auctions",
            f"id=eq.{TARGET_ROW_ID}",
            {"latitude": lat, "longitude": lon, "geo_source": "walton_enerGov_arcgis_parcels_layer4_centroid"},
        )
        writes += 1
        print(f"  multi_county_auctions PATCHED: latitude={lat} longitude={lon}")

        if parcel_zone_exists(TARGET_PARCEL):
            print("  SKIP zone link: parcel_zones entry already exists live")
        else:
            attrs = arcgis_zone_query(lat, lon)
            if not attrs or not attrs.get("ZONE_CLASS"):
                print(f"  SKIP zone link: EnerGov zoning layer returned no ZONE_CLASS — real ceiling")
            else:
                zone_class = attrs["ZONE_CLASS"].strip()
                plan_area = attrs.get("PLAN_AREA")
                print(f"  EnerGov Layer 19 (Zoning) VERIFIED: ZONE_CLASS={zone_class!r} PLAN_AREA={plan_area!r}")

                district = get_or_create_zoning_district(zone_class, UNINCORP_WALTON_JURISDICTION_ID)
                print(f"  zoning_districts VERIFIED: id={district['id']} jurisdiction_id={district['jurisdiction_id']}")

                sb_post(
                    "parcel_zones",
                    {
                        "parcel_id": TARGET_PARCEL,
                        "tax_account": TARGET_PARCEL,
                        "jurisdiction_id": district["jurisdiction_id"],
                        "zone_code": zone_class,
                        "source": f"walton_enerGov_arcgis/{DISPATCH_TAG}",
                        "effective_date": "2018-12-11",
                    },
                    prefer="resolution=ignore-duplicates,return=minimal",
                )
                writes += 1
                print(f"  parcel_zones INSERTED: {TARGET_PARCEL} -> jur={district['jurisdiction_id']} zone={zone_class}")

    print(f"\nwrites={writes}")

    if writes == 0:
        raise RuntimeError(
            "FAIL-LOUD: parsed 1 walton card-complete gap row but wrote 0 — "
            "silent no-op, refusing to report success."
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
