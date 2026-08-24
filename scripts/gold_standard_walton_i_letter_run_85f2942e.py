#!/usr/bin/env python3
"""
Gold Standard walton I fix — dispatch 85f2942e, 2026-08-24.

Target: walton I (property card completeness).
  Live before: card_complete=134 of 153 (87.6%) — need >=146/153 (95%).

Fresh live diagnosis (this session, via v_auction_property_card + multi_county_auctions
joined by id, county='walton'): 19 gap rows total.

Bucket by missing field (address / geo / value / zoning_code), non-excluded rows only
(none of the 19 are redeemed/cancelled — all sale_type in {foreclosure, tax_deed} with
parity_status=matched_clean, still upcoming/pending):

  Bucket A — 11 rows WITH a real parcel_id (EnerGov FeatureServer PARCELNO match):
    2026-0125TD  19-1N-17-04000-001-0110   missing addr/geo/value/zone
    2026-0092TD  15-3N-20-28070-044-0010   missing zone only (addr/geo/value already present)
    2026-0127TD  36-3N-20-28140-000-014A   missing addr/geo/value/zone
    2026-0119TD  25-3N-19-19070-001-5200   missing addr/geo/value/zone
    2026-0121TD  25-3N-19-19070-000-8140   missing addr/geo/value/zone
    2026-0088TD  10-2N-19-18000-001-0040   missing value/zone (addr/geo present)
    2026-0097TD  22-2S-20-33120-092-0220   missing geo/zone (addr/value present)
    2026-0126TD  15-3N-20-28070-034-0310   missing addr/geo/value/zone
    2026-0093TD  18-3N-20-28056-012-0070   missing value/zone (addr/geo present)
    2026-0122TD  15-3N-17-06000-004-0010   missing addr/geo/value/zone
    2026-0090TD  29-2S-21-42502-00B-0403   missing zone only (addr/geo/value present)

    All 11 VERIFIED live against Walton EnerGov ArcGIS FeatureServer (Layer 4 Parcels,
    Layer 19 Zoning), same endpoint proven in shard9_walton_cd_i_backfill.py and
    gold_standard_shard3_walton_i_run9906_c5a8b2c7.py:
      https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer
    All 11 zone classes resolved (General Agriculture x2, Rural Residential x3,
    Municipal x3, Conservation Residential 1 unit per 2.5 acres x1, Coastal Center x1)
    and all already exist as zoning_districts rows under jurisdiction 1333/842 from
    prior sessions — no new zoning_districts inserts required, only parcel_zones.

  Bucket B — 8 rows with NO usable parcel_id (root cause: calendar_sweep ingestion
    could not resolve a real parcel from the auction calendar page; realforeclose_aids
    join returns scrape-artifact placeholder strings, not real parcel IDs):
    25CA000608   parcel_id in realforeclose_aids = 'Property Appraiser' (placeholder)
    19CA000472   parcel_id in realforeclose_aids = 'Property Appraiser' (placeholder)
    25CA000142   parcel_id in realforeclose_aids = 'MULTIPLE PARCELS' (placeholder)
    26CA000030   parcel_id in realforeclose_aids = 'Property Appraiser' (placeholder)
    25CA000348   parcel_id in realforeclose_aids = 'Property Appraiser' (placeholder)
    25CA000531A  parcel_id in mca = 'TIMESHARE' literal (not a real parcel)
    26CA000062   parcel_id in realforeclose_aids = 'MULTIPLE PARCELS' (placeholder)
    25CA000044   parcel_id in realforeclose_aids = 'MULTIPLE PARCELS' (placeholder)

    Re-verified this session (VERIFIED, fresh probes, not reused from memory):
      - walton.realforeclose.com auction detail pages: HTTP 403 (bot-blocked), confirmed
        again this session for all 6 distinct case numbers.
      - qpublic.schneidercorp.com (Walton PA parcel search UI): HTTP 403 (bot-blocked).
      - waltonpa.com: HTTP 302 -> HTTP 403 on redirect target (bot-blocked).
      - civitekflorida.com/ocrs/county/66 (Walton OCRS civil case index): HTTP 200 but
        is a JSF/PrimeFaces postback form (ViewState-based), no GET-queryable case-number
        endpoint reachable via static curl.
      - orsearch.clerkofcourts.co.walton.fl.us (LandmarkWeb Official Records Search):
        HTTP 200 but is a JS-driven SPA (LandmarkWeb), and even if reachable indexes
        recorded instruments (deeds/liens), not parcel_id per civil case number.
      - taxsmart.clerkofcourts.co.walton.fl.us: HTTP 200, reachable, but is a tax-deed
        sale/deposit portal, not a parcel-by-case-number lookup; none of these 6 case
        numbers are tax_deed sale_type (all foreclosure) so not applicable here.
    BLOCKED this session — left untouched, no fabricated parcel_id/address/geo/value.
    Per BLANK > WRONG: leaving null is correct; do not fabricate.
    'MULTIPLE PARCELS' cases (25CA000142, 26CA000062, 25CA000044) are structurally
    ambiguous even with a working scrape route (multi-parcel foreclosure judgments
    have no single canonical parcel_id) — same root-cause class documented for
    26CA000030/25CA000608 in gold_standard_shard3_walton_i_run9906_c5a8b2c7.py.

First pass result (11 rows: geo+value+zoning_code): 134 -> 139/153 (only 5 rows fully
flipped to card_complete — the other 6 had geo/value/zone fixed but property_address
was still NULL, discovered via a fresh v_auction_property_card query after the patch).

SECOND PASS (address backfill, this session, same dispatch): of the 6 rows still
missing property_address after pass 1, queried two independent real GIS sources:
  - EnerGov Layer 9 "EnerGov Address Parcel" (PARCELNO-joined site address):
      25-3N-19-19070-000-8140 -> "379 US HIGHWAY 90 E, DEFUNIAK SPRINGS FL 32433" (real)
      15-3N-17-06000-004-0010 -> "1949 STATE HIGHWAY 81, PONCE DE LEON FL 32455" (real)
      (other 4 parcels: FullAddr=None in Layer 9 — genuinely no address point joined)
  - FL DOR Statewide Cadastral (Florida_Statewide_Cadastral FeatureServer, CO_NO=76,
    PARCEL_ID = EnerGov GIS_FIG format) PHY_ADDR1 field, cross-checked against the 4
    parcels with no Layer-9 address:
      36-3N-20-28140-000-014A  (GIS_FIG 363N2028140000014A) -> PHY_ADDR1="JOHN BOLAND RD" (real, road-frontage, no house number — normal for vacant lots)
      25-3N-19-19070-001-5200  (GIS_FIG 253N19190700015200) -> PHY_ADDR1="N  DAVIS LN" (real)
      15-3N-20-28070-034-0310  (GIS_FIG 153N20280700340310) -> PHY_ADDR1="E  DOGWOOD AVE" (real)
      19-1N-17-04000-001-0110  (GIS_FIG 191N17040000010110) -> PHY_ADDR1=" " (blank —
        confirmed genuinely no situs address in FL DOR's own statewide database, same
        conclusion as EnerGov. Cross-verified via a spatial point-in-polygon query
        against EnerGov Layer 1 "Address Points" for the parcel's full polygon: zero
        address points intersect. Three independent authoritative sources (county
        EnerGov join, county EnerGov spatial address layer, FL DOR statewide cadastral)
        agree — genuinely blocked, not a scraper gap. USE_DESC='VACANT', BLDG_VALUE=0.
        BLANK > WRONG: left untouched, no fabricated address.)

Result after both passes: 134 -> 144/153 (94.1%) — 9 rows remain: the 1 genuinely
address-less vacant parcel above + the 8 no-parcel-id Bucket B rows (all still
structurally blocked this session; RealAuction/realforeclose.com 403s persist even
with a browser User-Agent — splash/login page only; Walton OCRS civitek is a JSF
postback form; orsearch.clerkofcourts.co.walton.fl.us LandmarkWeb has no discoverable
GET/REST search API (404 on api/search probe) and is a JS SPA; the one available
recorded-document PDF for 25CA000608 (OR book 3403 page 21, fetched live this session)
is a scanned image with zero extractable text, so even that lead yields no parcel_id).

Expected final: 144/153 = 94.1% — short of the 146/153 (95.4%) needed. This session
cannot mechanically reach >=95% without a source for at least 1 of the remaining 9
blocked rows; documented honestly below rather than claiming a pass that live data
does not support.

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

DISPATCH_ID = "85f2942e"
ENERG0V_BASE = "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/EnerGov/FeatureServer"
ENERG0V_PARCELS = f"{ENERG0V_BASE}/4/query"
ENERG0V_ZONING = f"{ENERG0V_BASE}/19/query"

FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
WALTON_CO_NO = 76

# Rows still missing property_address after the geo/value/zone pass. Sourced from
# EnerGov Layer 9 (EnerGov Address Parcel) FullAddr / ShortAddress, or FL DOR
# Statewide Cadastral PHY_ADDR1 where Layer 9 had no address point join. All VERIFIED
# live this session — see module docstring "SECOND PASS" for full source-by-row detail.
ADDRESS_BACKFILL = {
    "074f998d-c78c-4555-adcc-091709748a0d": "379 US HIGHWAY 90 E, DEFUNIAK SPRINGS, FL- 32433",  # 2026-0121TD, EnerGov Layer 9
    "790f8347-927f-4fef-97ec-99b85d37c6ac": "1949 STATE HIGHWAY 81, PONCE DE LEON, FL- 32455",  # 2026-0122TD, EnerGov Layer 9
    "af07cb4f-23bc-4ba6-ba43-99f10a3977cc": "JOHN BOLAND RD, DEFUNIAK SPRINGS, FL- 32435",  # 2026-0127TD, FL DOR PHY_ADDR1
    "c0f53de1-af09-45a2-9e0f-f8d1bc5e93b1": "N DAVIS LN, DEFUNIAK SPRINGS, FL- 32433",  # 2026-0119TD, FL DOR PHY_ADDR1
    "d85f3040-7380-40e6-8ede-8d96fe34587e": "E DOGWOOD AVE, DEFUNIAK SPRINGS, FL- 32433",  # 2026-0126TD, FL DOR PHY_ADDR1
}

# a6f01601 (2026-0125TD, parcel 19-1N-17-04000-001-0110) intentionally excluded from
# ADDRESS_BACKFILL: confirmed genuinely address-less across 3 independent sources
# (EnerGov Layer 9 join, EnerGov Layer 1 spatial point-in-polygon, FL DOR PHY_ADDR1
# blank) — vacant land, USE_DESC='VACANT', BLDG_VALUE=0. Left untouched.
BLOCKED_NO_ADDRESS = {
    "a6f01601-af1d-4055-8752-b4eabe2fcb86": "2026-0125TD",
}

# id -> parcel_id for the 11 addressable gap rows
GAP_ROWS = {
    "a6f01601-af1d-4055-8752-b4eabe2fcb86": "19-1N-17-04000-001-0110",  # 2026-0125TD
    "fd198d49-86b6-471e-8054-058fc1111b01": "15-3N-20-28070-044-0010",  # 2026-0092TD
    "af07cb4f-23bc-4ba6-ba43-99f10a3977cc": "36-3N-20-28140-000-014A",  # 2026-0127TD
    "c0f53de1-af09-45a2-9e0f-f8d1bc5e93b1": "25-3N-19-19070-001-5200",  # 2026-0119TD
    "074f998d-c78c-4555-adcc-091709748a0d": "25-3N-19-19070-000-8140",  # 2026-0121TD
    "4247c9b1-d2b1-4423-9602-b6498d57278d": "10-2N-19-18000-001-0040",  # 2026-0088TD
    "b1aff0f2-bf19-4769-b6c9-ff1b46573f4c": "22-2S-20-33120-092-0220",  # 2026-0097TD
    "d85f3040-7380-40e6-8ede-8d96fe34587e": "15-3N-20-28070-034-0310",  # 2026-0126TD
    "2d3f8033-a167-4683-b926-10a705754ab5": "18-3N-20-28056-012-0070",  # 2026-0093TD
    "790f8347-927f-4fef-97ec-99b85d37c6ac": "15-3N-17-06000-004-0010",  # 2026-0122TD
    "104cdadc-068e-4520-afc2-126888c62a55": "29-2S-21-42502-00B-0403",  # 2026-0090TD
}

BLOCKED_IDS = {
    "1d2916fb-ef5d-45b8-bfc0-a0d28e9e903f": "25CA000608",
    "1f0e3585-4de8-4bd2-9d1c-1c3d06206d2c": "19CA000472",
    "23fdecae-c972-4515-877f-d794f6b40142": "25CA000142",
    "6d379ee8-5ccc-4d14-ae17-e4171956def4": "26CA000030",
    "854d828c-6cb5-4d0f-b8d9-e863d0d3711b": "25CA000348",
    "952908fb-27d5-4288-b091-61e634fc2bb1": "25CA000531A",
    "c28155d7-c19a-4417-91d4-bf159f0092df": "26CA000062",
    "fe5b2212-abea-470e-be84-4deef7254ec0": "25CA000044",
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
        headers={"User-Agent": "BidDeed-GoldStandard-Walton-I/1.0; contact:ariel@everestcapitalusa.com"},
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
            "description": f"walton_enerGov_arcgis_gs_{DISPATCH_ID}",
        },
        prefer="resolution=merge-duplicates,return=minimal",
    )


def get_existing_parcel_zone(parcel_id: str) -> bool:
    existing = sb_get("parcel_zones", {"select": "id", "parcel_id": f"eq.{parcel_id}", "limit": "1"})
    return bool(existing)


def get_current_row(row_id: str) -> dict:
    rows = sb_get(
        "multi_county_auctions",
        {
            "select": "id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value",
            "id": f"eq.{row_id}",
        },
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
    fixed_rows: list[dict] = []
    already_zoned_parcels: set[str] = set()

    for row_id, parcel_id in GAP_ROWS.items():
        row = get_current_row(row_id)
        if not row:
            print(f"  SKIP {row_id}: row not found live (may have been fixed already)")
            continue
        case_number = row.get("case_number")
        print(f"\nProcessing id={row_id} case={case_number} parcel={parcel_id}")
        fields_fixed: list[str] = []

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
            fields_fixed.append("geo")
        if not row.get("assessed_value") and not row.get("market_value"):
            if parcel_info.get("assessed_value") is not None:
                mca_patch["assessed_value"] = parcel_info["assessed_value"]
            if parcel_info.get("market_value") is not None:
                mca_patch["market_value"] = parcel_info["market_value"]
            mca_patch["assessed_value_source"] = f"walton_enerGov_arcgis_gs_{DISPATCH_ID}"
            fields_fixed.append("value")

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
                        "source": f"walton_enerGov_arcgis/gold_standard_{DISPATCH_ID}_{date.today().isoformat()}",
                        "effective_date": "2018-12-11",
                    },
                    prefer="resolution=ignore-duplicates,return=minimal",
                )
                already_zoned_parcels.add(parcel_id)
                zoned_new += 1
                fields_fixed.append("zoning_code")
                print(f"  parcel_zones INSERTED: {parcel_id} -> jur={jur_id} zone={zone_class}")
            else:
                fields_fixed.append("zoning_code(already-linked)")
                print(f"  parcel_zones already present for {parcel_id} (skip insert)")
        else:
            print(f"  WARNING: no zone class resolved for {parcel_id} — card_complete will still fail for this row")

        if fields_fixed:
            fixed_rows.append({"case_number": case_number, "fields_fixed": fields_fixed})

    # SECOND PASS: address backfill for rows whose geo/value/zone got fixed above but
    # still lack property_address (EnerGov Layer 4 has no situs address field; requires
    # EnerGov Layer 9 join or FL DOR Statewide Cadastral PHY_ADDR1 fallback).
    print("\n=== SECOND PASS: address backfill ===")
    address_filled = 0
    for row_id, address in ADDRESS_BACKFILL.items():
        row = get_current_row(row_id)
        if not row:
            print(f"  SKIP {row_id}: row not found live")
            continue
        if row.get("property_address"):
            print(f"  SKIP {row.get('case_number')}: property_address already present")
            continue
        sb_patch(
            "multi_county_auctions",
            f"id=eq.{row_id}",
            {"property_address": address, "updated_at": "now()"},
        )
        address_filled += 1
        print(f"  PATCHED property_address for {row.get('case_number')}: {address!r}")
        for fr in fixed_rows:
            if fr["case_number"] == row.get("case_number"):
                fr["fields_fixed"].append("address")

    print("\n=== BLOCKED (left untouched, no fabrication) ===")
    for row_id, cn in BLOCKED_IDS.items():
        print(f"  {cn} (id={row_id}): no real parcel_id available from any reachable source this session")
    for row_id, cn in BLOCKED_NO_ADDRESS.items():
        print(f"  {cn} (id={row_id}): parcel_id known but genuinely no situs address in any of 3 independent sources (vacant land)")

    print(f"\nrows_touched={rows_touched} geo_filled={geo_filled} value_filled={value_filled} zoned_new={zoned_new} address_filled={address_filled}")

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
    print(f"fixed_rows: {json.dumps(fixed_rows, indent=2)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
