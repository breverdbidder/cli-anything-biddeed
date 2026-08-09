#!/usr/bin/env python3
"""
Gold Standard shard-3 walton I fix — dispatch c5a8b2c7, run9906, 2026-08-09.

Target: walton I (property card completeness).
  Live before: card_complete=104 of 116 (89.7%) — need >=111/116 (95%).

Fresh live diagnosis (this session, re-verified against pencil_dod_evaluate_county
SQL definition via pg_get_functiondef, not the stale snapshot in the dispatch prompt):
  12 gap `id` rows (note: several case_numbers appear twice as distinct auction
  rows — 2026-0101TD, 2026-0103TD, 2026-0105TD, 2026-0104TD, 2026-0086TD each
  have 2 rows in multi_county_auctions with different `id`, both must independently
  satisfy card_complete):
    - 26CA000030 (id=6d379ee8): no parcel_id, address, geo, value at all.
    - 25CA000608 (id=1d2916fb): no parcel_id, address, geo, value at all.
    - 2026-0095TD (id=fdada653) parcel=16-3N-20-28060-025-0770: missing geo+value+zone
    - 2026-0101TD (id=230c077c) parcel=20-4N-20-29000-001-0020: missing geo+zone
    - 2026-0101TD (id=40bab43e) parcel=20-4N-20-29000-001-0020: missing geo+value+zone
    - 2026-0085TD (id=908801e1) parcel=14-1S-19-23000-014-0000: missing geo+zone
    - 2026-0103TD (id=36bd0953) parcel=20-4N-20-29000-053-0270: missing geo+zone
    - 2026-0103TD (id=cfe3709a) parcel=20-4N-20-29000-053-0270: missing geo+value+zone
    - 2026-0086TD (id=37d4a0e4) parcel=25-3N-19-19110-000-0210: missing zone only
    - 2026-0086TD (id=e22e30c2) parcel=25-3N-19-19110-000-0210: missing zone only
    - 2026-0105TD (id=10cf492b) parcel=20-4N-20-29000-053-0290: missing geo+value
      (zone link already present live)
    - 2026-0104TD (id=68648ed3) parcel=20-4N-20-29000-053-0350: missing geo+value
      (zone link already present live)

Root cause: rows ingested by calendar_sweep_mca_v3 without a follow-up EnerGov
ArcGIS enrichment pass (same class of gap as the prior shard9_walton_cd_i_backfill.py
session, recurring because new auction rows keep landing weekly).

Source (VERIFIED live, reused unmodified endpoint from shard9_walton_cd_i_backfill.py):
  Walton County EnerGov ArcGIS FeatureServer
  https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer
  Layer 4  = Parcels  (PARCELNO, OWNER_NAME, APPRAISED_VALUE, JUST_VALUE, polygon geometry)
  Layer 19 = Zoning   (ZONE_CLASS, point-in-polygon against parcel centroid)

26CA000030 / 25CA000608 (blank stub rows, no parcel_id):
  realforeclose_aids has both case_numbers (VERIFIED via live query) but
  parcel_id='Property Appraiser' is a scrape-artifact placeholder string, not a
  real parcel ID, and property_address/assessed_value are NULL there too — this
  table has NO usable enrichment data for these 2 cases despite matching by
  case_number. qpublic.schneidercorp.com and waltonpa.com both return
  403 (bot-blocked). walton.realforeclose.com auction detail pages
  (AID=1512839, AID=1508959) require an authenticated session (splash/login
  page only, no case data in the static HTML). civitek OCRS
  (civitekflorida.com/ocrs/county/66) is a JSF postback form requiring
  interactive search+submit, not reachable via static scrape.
  BLOCKED this session — left untouched, no fabricated address/parcel/geo/value.
  Per BLANK > WRONG: leaving null is correct; do not fabricate.

FAIL-LOUD invariant: if gap rows are parsed but zero DB writes occur, raise.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from typing import Any

SB_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SB_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)

DISPATCH_ID = "c5a8b2c7"
ENERG0V_BASE = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer"
ENERG0V_PARCELS = f"{ENERG0V_BASE}/4/query"
ENERG0V_ZONING = f"{ENERG0V_BASE}/19/query"

# id -> parcel_id for the 10 addressable gap rows (26CA000030 / 25CA000608 excluded — blocked)
GAP_ROWS = {
    "fdada653-9eb0-4342-8034-c463669bf8bf": "16-3N-20-28060-025-0770",  # 2026-0095TD
    "230c077c-d576-4dea-a2ed-a221ac4e3671": "20-4N-20-29000-001-0020",  # 2026-0101TD
    "40bab43e-b0c4-4122-98d0-16e748e19553": "20-4N-20-29000-001-0020",  # 2026-0101TD (dup id)
    "908801e1-a699-498d-bc78-d361e7da44a5": "14-1S-19-23000-014-0000",  # 2026-0085TD
    "36bd0953-3bcc-4917-97ea-0706c61215a5": "20-4N-20-29000-053-0270",  # 2026-0103TD
    "cfe3709a-2dbe-4a52-a84b-d0a2bd8dc3bb": "20-4N-20-29000-053-0270",  # 2026-0103TD (dup id)
    "37d4a0e4-b2ef-454a-9f11-18c9e7ef38ea": "25-3N-19-19110-000-0210",  # 2026-0086TD
    "e22e30c2-f87c-483b-a874-8119289858be": "25-3N-19-19110-000-0210",  # 2026-0086TD (dup id)
    "10cf492b-762e-4e9b-b5c3-9282a01174d2": "20-4N-20-29000-053-0290",  # 2026-0105TD
    "68648ed3-12dc-4460-8688-5797431c3ff7": "20-4N-20-29000-053-0350",  # 2026-0104TD
}

BLOCKED_IDS = {
    "6d379ee8-5ccc-4d14-ae17-e4171956def4": "26CA000030",
    "1d2916fb-ef5d-45b8-bfc0-a0d28e9e903f": "25CA000608",
}

WALTON_JURS = {
    1333: "Unincorporated Walton County",
    842: "DeFuniak Springs",
    861: "Freeport",
    1146: "Paxton",
}

CATEGORY_MAP = {
    "Rural Low Density": "residential",
    "Rural Residential": "residential",
    "Rural Village": "mixed",
    "General Agriculture": "agricultural",
    "Residential Preservation": "residential",
    "Conservation": "conservation",
    "Coastal Center": "mixed",
    "Village Mixed Use": "mixed",
    "Municipal": "deferred",
    "Commercial": "commercial",
    "Industrial": "industrial",
    "Planned Unit Development": "mixed",
    "PUD": "mixed",
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


def sb_patch(table: str, filter_qs: str, body: dict) -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}?{filter_qs}",
        data=json.dumps(body).encode(),
        headers=_sb_headers("return=minimal"),
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_post(table: str, body: Any, prefer: str = "return=minimal") -> bytes:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=json.dumps(body).encode(),
        headers=_sb_headers(prefer),
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def sb_rpc(fn: str, payload: dict) -> Any:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(payload).encode(),
        headers=_sb_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def arcgis_query(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{qs}",
        headers={"User-Agent": "BidDeed-GoldStandard-Shard3-Walton/1.0; contact:ariel@everestcapitalusa.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_arcgis_parcel(parcel_id: str) -> dict | None:
    result = arcgis_query(
        ENERG0V_PARCELS,
        {
            "where": f"PARCELNO='{parcel_id}'",
            "outFields": "PARCELNO,OWNER_NAME,APPRAISED_VALUE,JUST_VALUE",
            "returnGeometry": "true",
            "geometryType": "esriGeometryPolygon",
            "outSR": "4326",
            "f": "json",
        },
    )
    features = result.get("features", [])
    if not features:
        return None
    feat = features[0]
    geo = feat.get("geometry", {})
    rings = geo.get("rings", [])
    if not rings:
        return None
    flat = [pt for ring in rings for pt in ring]
    centroid_lon = sum(p[0] for p in flat) / len(flat)
    centroid_lat = sum(p[1] for p in flat) / len(flat)
    attrs = feat.get("attributes", {})

    def _to_num(v):
        try:
            return float(v) if v not in (None, "", "0") else None
        except (TypeError, ValueError):
            return None

    return {
        "centroid_lat": centroid_lat,
        "centroid_lon": centroid_lon,
        "assessed_value": _to_num(attrs.get("APPRAISED_VALUE")),
        "market_value": _to_num(attrs.get("JUST_VALUE")),
    }


def fetch_arcgis_zone(lat: float, lon: float) -> str | None:
    result = arcgis_query(
        ENERG0V_ZONING,
        {
            "geometry": f"{lon},{lat}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONE_CLASS",
            "inSR": "4326",
            "f": "json",
        },
    )
    features = result.get("features", [])
    if not features:
        return None
    return (features[0].get("attributes", {}).get("ZONE_CLASS") or "").strip() or None


def resolve_jurisdiction(zone_class: str | None) -> int:
    if zone_class == "Municipal":
        return 842
    return 1333


def get_existing_zoning_district(jur_id: int, zone_code: str) -> bool:
    existing = sb_get(
        "zoning_districts",
        {"select": "id", "jurisdiction_id": f"eq.{jur_id}", "code": f"eq.{zone_code}", "limit": "1"},
    )
    return bool(existing)


def ensure_zoning_district(jur_id: int, zone_code: str) -> None:
    if get_existing_zoning_district(jur_id, zone_code):
        return
    category = CATEGORY_MAP.get(zone_code, "residential")
    sb_post(
        "zoning_districts",
        {
            "jurisdiction_id": jur_id,
            "code": zone_code,
            "name": zone_code,
            "category": category,
            "ordinance_section": "2018-29",
            "description": f"walton_enerGov_arcgis_gs_shard3_{DISPATCH_ID}",
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def get_existing_parcel_zone(parcel_id: str) -> bool:
    existing = sb_get("parcel_zones", {"select": "id", "parcel_id": f"eq.{parcel_id}", "limit": "1"})
    return bool(existing)


def get_current_row(row_id: str) -> dict:
    rows = sb_get(
        "multi_county_auctions",
        {"select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value", "id": f"eq.{row_id}"},
    )
    return rows[0] if rows else {}


def main() -> int:
    if not SB_KEY or not SB_URL:
        print("ERROR: missing Supabase credentials/env", file=sys.stderr)
        return 1

    print("=== BEFORE ===")
    before = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(before.get("I", {}), indent=2))

    parcel_cache: dict[str, dict | None] = {}
    zone_cache: dict[str, str | None] = {}

    geo_filled = 0
    value_filled = 0
    zoned_new = 0
    rows_touched = 0
    already_zoned_parcels: set[str] = set()

    for row_id, parcel_id in GAP_ROWS.items():
        row = get_current_row(row_id)
        if not row:
            print(f"  SKIP {row_id}: row not found live (may have been fixed already)")
            continue
        print(f"\nProcessing id={row_id} case={row.get('case_number')} parcel={parcel_id}")

        if parcel_id not in parcel_cache:
            time.sleep(0.25)
            parcel_cache[parcel_id] = fetch_arcgis_parcel(parcel_id)
        parcel_info = parcel_cache[parcel_id]
        if not parcel_info:
            print(f"  SKIP: EnerGov returned no parcel feature for {parcel_id}")
            continue

        lat = parcel_info["centroid_lat"]
        lon = parcel_info["centroid_lon"]

        mca_patch: dict = {"updated_at": "now()"}
        if not row.get("latitude") or not row.get("longitude"):
            mca_patch["latitude"] = lat
            mca_patch["longitude"] = lon
        if not row.get("assessed_value") and not row.get("market_value"):
            if parcel_info.get("assessed_value") is not None:
                mca_patch["assessed_value"] = parcel_info["assessed_value"]
            if parcel_info.get("market_value") is not None:
                mca_patch["market_value"] = parcel_info["market_value"]
            mca_patch["assessed_value_source"] = f"walton_enerGov_arcgis_gs_shard3_{DISPATCH_ID}"

        if len(mca_patch) > 1:
            sb_patch("multi_county_auctions", f"id=eq.{row_id}", mca_patch)
            rows_touched += 1
            if "latitude" in mca_patch:
                geo_filled += 1
            if "assessed_value" in mca_patch or "market_value" in mca_patch:
                value_filled += 1
            print(f"  PATCHED mca: {list(mca_patch.keys())}")

        # zone link
        if parcel_id not in zone_cache:
            time.sleep(0.25)
            zone_cache[parcel_id] = fetch_arcgis_zone(lat, lon)
        zone_class = zone_cache[parcel_id]
        print(f"  zone={zone_class!r}")

        if zone_class:
            if not get_existing_parcel_zone(parcel_id) and parcel_id not in already_zoned_parcels:
                jur_id = resolve_jurisdiction(zone_class)
                ensure_zoning_district(jur_id, zone_class)
                sb_post(
                    "parcel_zones",
                    {
                        "parcel_id": parcel_id,
                        "tax_account": parcel_id,
                        "jurisdiction_id": jur_id,
                        "zone_code": zone_class,
                        "source": f"walton_enerGov_arcgis/gold_standard_shard3_{DISPATCH_ID}_{date.today().isoformat()}",
                        "effective_date": "2018-12-11",
                    },
                    prefer="resolution=ignore-duplicates,return=minimal",
                )
                already_zoned_parcels.add(parcel_id)
                zoned_new += 1
                print(f"  parcel_zones INSERTED: {parcel_id} -> jur={jur_id} zone={zone_class}")
            else:
                print(f"  parcel_zones already present for {parcel_id} (skip insert)")
        else:
            print(f"  WARNING: no zone class resolved for {parcel_id} — card_complete will still fail for this row")

    print(f"\n=== BLOCKED (left untouched, no fabrication) ===")
    for row_id, cn in BLOCKED_IDS.items():
        print(f"  {cn} (id={row_id}): no parcel_id/address available from any reachable source this session")

    print(f"\nrows_touched={rows_touched} geo_filled={geo_filled} value_filled={value_filled} zoned_new={zoned_new}")

    if GAP_ROWS and rows_touched == 0 and zoned_new == 0:
        raise RuntimeError(
            f"FAIL-LOUD: parsed {len(GAP_ROWS)} walton card-gap rows but wrote 0 "
            f"(rows_touched=0, zoned_new=0) — silent no-op, refusing to report success."
        )

    print("\n=== AFTER ===")
    after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "walton"})
    print(json.dumps(after.get("I", {}), indent=2))

    print("\n=== SUMMARY ===")
    print(f"I before: {before.get('I')}")
    print(f"I after:  {after.get('I')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
