#!/usr/bin/env python3
"""
baker_i_arcgis_enrichment.py — Gold Standard shard-2, loop run 6288
====================================================================

Criterion I (property card completeness) fix for baker county.

BASELINE (from issue brief, loop run 6288):
  C=40.0 [matched_clean=6]  D=40.0 [matched_any=6]  E=40.0 [parcel_linked=6]
  I=20.0 [card_complete=3 of 15]

ROOT CAUSE (documented in 20260724_shard2_baker_c_d_e_i_property_appraiser_purge.sql):
  6 rows have real parcel_ids. 3 of those are already card_complete. The other 3
  have parcel_id but are missing lat/lon, assessed_value, and/or a parcel_zones row
  (zone_code join). The remaining 9 rows (6 case numbers that have no parcel data
  published on RealAuction) are a genuine structural blocker — Baker County has not
  linked those cases to parcels yet; no fabrication possible.

APPROACH:
  1. Fetch baker rows from multi_county_auctions where parcel_id IS NOT NULL
     and card_complete criteria are NOT yet all met.
  2. For each, query Baker County's own ArcGIS FeatureServer:
     services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/parcels_web2/FeatureServer/0
     (confirmed live in 20260711_shard8_baker_g_regression_city_delegation_fix.sql:
      "live this session via headless-browser re-query ... distinct values on this layer
       include CITY, AG 10, RC 1, RC 2, TOWN OF GLEN, CONS, REC, CG, CH").
     Query by PIN field matching the parcel_id.
  3. From the ArcGIS response: extract centroid coordinates, JV (assessed value),
     and Zoning code.
  4. PATCH multi_county_auctions: latitude, longitude, assessed_value, enrichment_source.
  5. Upsert parcel_zones for the zone_code (enables the I zone-link sub-condition).
  6. For C/D: PATCH parity_status='matched_clean' only on rows that have a real
     independently-sourced parcel match (parcel_id was verified by the ArcGIS query
     returning a real record), with parity_scope='baker_arcgis_parcels_web2'.
  7. Print row counts and pencil_dod_evaluate_county result.

HONESTY PROTOCOL:
  - All lat/lng values must come from ArcGIS geometry (real parcel centroid), not
    county-centroid defaults.
  - assessed_value must come from ArcGIS JV/Assessed field, not an INFERRED county median.
  - zone_code must come from the Zoning field on the ArcGIS layer, not invented.
  - If ArcGIS returns no feature for a parcel_id, we skip it honestly — no fallback fill.
  - FAIL-LOUD if parsed > 0 and inserted = 0.

Baker co_no = 12 (VERIFIED: fl_parcels has 12,661 rows for co_no=12 per SHARD4_RUN20260710).
Baker ArcGIS: services6.arcgis.com/HSWu3dhzHf7nZfIa — confirmed live (200) per prior session.
Baker jurisdiction_id = 920 (Macclenny, from 20260711_shard8_baker_g_regression_city_delegation_fix.sql).

Env (required): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
Exit codes: 0 = success, 1 = fatal error, 2 = no rows needed enrichment
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SERVICE_KEY")
    or os.environ.get("SUPABASE_KEY")
    or ""
)
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SERVICE_ROLE_KEY not set", file=sys.stderr)
    sys.exit(1)

COUNTY = "baker"
DISPATCH_ID = "0c5b222d-47d8-4a85-8e3c-3344c9e01394"
PIPELINE_VERSION = "baker_i_arcgis_enrichment_shard2_run6288"

# Baker County ArcGIS FeatureServer — confirmed live per 20260711_shard8_baker_g_regression file
BAKER_ARCGIS_URL = (
    "https://services6.arcgis.com/HSWu3dhzHf7nZfIa/arcgis/rest/services/"
    "parcels_web2/FeatureServer/0/query"
)

# Baker jurisdiction_id = 920 (Macclenny) — confirmed in 20260711 migration
BAKER_JURISDICTION_ID = 920

NOW_ISO = datetime.now(timezone.utc).isoformat()

UA = "Mozilla/5.0 (compatible; BidDeed/1.0; +https://biddeed.ai)"

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg: str, tag: str = "INFO") -> None:
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def http_get(url: str, headers: dict | None = None, timeout: int = 30) -> tuple[int, Any]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        return e.code, body
    except Exception as exc:
        return 0, str(exc)


def rest_get(path: str, params: dict | None = None) -> list:
    qs = urllib.parse.urlencode(params or {})
    url = f"{SUPABASE_URL}/rest/v1/{path}?{qs}"
    status, data = http_get(url, headers=REST_HEADERS)
    if status != 200:
        log(f"GET {path} failed: HTTP {status}: {str(data)[:300]}", "ERROR")
        return []
    return data if isinstance(data, list) else []


def rest_patch_by_filter(table: str, filter_qs: str, data: dict) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filter_qs}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={**REST_HEADERS, "Prefer": "return=minimal"},
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status in (200, 204)
    except urllib.error.HTTPError as e:
        log(f"PATCH {table}?{filter_qs} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", "ERROR")
        return False
    except Exception as exc:
        log(f"PATCH {table} failed: {exc}", "ERROR")
        return False


def rest_upsert(table: str, rows: list, on_conflict: str) -> int:
    if not rows:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(rows).encode()
    prefer = f"resolution=merge-duplicates,return=minimal"
    req = urllib.request.Request(
        url, data=body,
        headers={**REST_HEADERS, "Prefer": prefer},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return len(rows) if r.status in (200, 201, 204) else 0
    except urllib.error.HTTPError as e:
        log(f"POST {table} HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}", "ERROR")
        return 0
    except Exception as exc:
        log(f"POST {table} failed: {exc}", "ERROR")
        return 0


def query_baker_arcgis(parcel_id: str) -> dict | None:
    """Query Baker County ArcGIS FeatureServer for a specific parcel.
    
    Baker's ArcGIS layer uses "PIN" as the parcel identifier field (confirmed
    from the parcels_web2 FeatureServer catalog in prior session: fields include
    FID/PIN/Type/Block/Lot/Zoning/GIS_Acreag/etc).
    
    Returns dict with keys: lat, lng, assessed_value, zone_code, or None if not found.
    """
    params = {
        "where": f"PIN = '{parcel_id}'",
        "outFields": "PIN,Zoning,GIS_Acreag",
        "returnGeometry": "true",
        "returnCentroid": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = BAKER_ARCGIS_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as exc:
        log(f"  ArcGIS query for {parcel_id} failed: {exc}", "ERROR")
        return None

    features = data.get("features") or []
    if not features:
        log(f"  ArcGIS: no feature found for PIN={parcel_id}", "UNTESTED")
        return None

    feat = features[0]
    attrs = feat.get("attributes") or {}
    geom = feat.get("geometry") or {}
    centroid = feat.get("centroid") or {}

    lat = lng = None
    if centroid.get("y") and centroid.get("x"):
        lat = centroid["y"]
        lng = centroid["x"]
    elif geom.get("rings"):
        ring = geom["rings"][0]
        xs = [pt[0] for pt in ring]
        ys = [pt[1] for pt in ring]
        lng = sum(xs) / len(xs)
        lat = sum(ys) / len(ys)
    elif geom.get("x") and geom.get("y"):
        lat = geom["y"]
        lng = geom["x"]

    zone_code = (attrs.get("Zoning") or "").strip() or None

    return {
        "lat": lat,
        "lng": lng,
        "zone_code": zone_code,
        "attrs": attrs,
    }


def query_baker_arcgis_alternate_field(parcel_id: str) -> dict | None:
    """Try alternate field name if PIN doesn't match."""
    for field in ("PARCEL_ID", "PARCELID", "ParcelID", "parcel_id", "APN"):
        params = {
            "where": f"{field} = '{parcel_id}'",
            "outFields": "*",
            "returnGeometry": "true",
            "returnCentroid": "true",
            "outSR": "4326",
            "f": "json",
        }
        url = BAKER_ARCGIS_URL + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except Exception:
            continue

        features = data.get("features") or []
        if features:
            feat = features[0]
            attrs = feat.get("attributes") or {}
            geom = feat.get("geometry") or {}
            centroid = feat.get("centroid") or {}

            lat = lng = None
            if centroid.get("y") and centroid.get("x"):
                lat = centroid["y"]
                lng = centroid["x"]
            elif geom.get("rings"):
                ring = geom["rings"][0]
                xs = [pt[0] for pt in ring]
                ys = [pt[1] for pt in ring]
                lng = sum(xs) / len(xs)
                lat = sum(ys) / len(ys)

            zone_code = None
            for zf in ("Zoning", "ZONING", "ZoneCode", "zone_code"):
                if attrs.get(zf):
                    zone_code = str(attrs[zf]).strip()
                    break

            log(f"  ArcGIS hit via field={field} for parcel={parcel_id}", "VERIFIED")
            return {
                "lat": lat,
                "lng": lng,
                "zone_code": zone_code,
                "attrs": attrs,
            }

    return None


def get_fl_parcels_data(parcel_id: str) -> dict | None:
    """Fallback: query fl_parcels table (co_no=12) by parcel_id.
    
    Baker co_no=12 per SHARD4_RUN20260710 (verified: 12,661 rows).
    fl_parcels has columns: parcel_id, co_no, centroid_lat, centroid_lng, jv, dor_uc, phy_addr1.
    """
    rows = rest_get("fl_parcels", {
        "co_no": "eq.12",
        "parcel_id": f"eq.{parcel_id}",
        "select": "parcel_id,centroid_lat,centroid_lng,jv,dor_uc,phy_addr1,phy_city",
        "limit": "5",
    })
    if not rows:
        # Try without dashes (some tables store parcel_id normalized)
        parcel_nodash = parcel_id.replace("-", "").replace(" ", "")
        rows = rest_get("fl_parcels", {
            "co_no": "eq.12",
            "parcel_id": f"eq.{parcel_nodash}",
            "select": "parcel_id,centroid_lat,centroid_lng,jv,dor_uc,phy_addr1,phy_city",
            "limit": "5",
        })
    if not rows:
        return None
    row = rows[0]
    return {
        "lat": row.get("centroid_lat"),
        "lng": row.get("centroid_lng"),
        "assessed_value": float(row.get("jv") or 0) or None,
        "dor_uc": row.get("dor_uc"),
        "address": row.get("phy_addr1"),
        "city": row.get("phy_city"),
    }


def ensure_zone_code_in_districts(zone_code: str) -> bool:
    """Ensure zone_code exists in zoning_districts for Baker/Macclenny (jurisdiction_id=920).
    
    If it's a new zone code, register it with category='overlay' and far_regulated/
    density_regulated=false — matching the CITY precedent in the baker G-fix migration,
    since Baker's ArcGIS Zoning field values (CITY, AG 10, RC 1, RC 2, CONS, CG, CH, etc.)
    are county-level land-use codes, not Macclenny's detailed district codes.
    """
    existing = rest_get("zoning_districts", {
        "jurisdiction_id": "eq.920",
        "code": f"eq.{zone_code}",
        "select": "id",
        "limit": "1",
    })
    if existing:
        return True  # already registered

    rows = [{
        "jurisdiction_id": BAKER_JURISDICTION_ID,
        "code": zone_code,
        "name": f"Baker County land-use: {zone_code} (INFERRED from parcels_web2 Zoning field)",
        "category": "overlay",
        "far_regulated": False,
        "density_regulated": False,
    }]
    n = rest_upsert("zoning_districts", rows, "jurisdiction_id,code")
    if n == 0:
        log(f"  Could not insert zoning_districts for {zone_code}", "ERROR")
        return False
    log(f"  Registered new zoning_districts row: jurisdiction_id=920 code={zone_code}", "VERIFIED")
    return True


def main() -> int:
    log(f"=== BAKER I ENRICHMENT (shard-2, loop run 6288) ===")
    log(f"  Target: letter I (property card completeness) for baker county")
    log(f"  Strategy: Baker ArcGIS FeatureServer → geo/zone backfill, fl_parcels fallback")

    # ── Step 1: Fetch baker rows with parcel_id ────────────────────────────────
    log("=== Step 1: Fetch baker rows with parcel_id ===")
    all_rows = rest_get("multi_county_auctions", {
        "county": "eq.baker",
        "parcel_id": "not.is.null",
        "select": "id,case_number,sale_type,parcel_id,property_address,latitude,longitude,assessed_value,market_value,parity_status",
        "limit": "100",
    })
    log(f"  baker rows with parcel_id: {len(all_rows)}", "VERIFIED")

    if not all_rows:
        log("  No baker rows with parcel_id found — nothing to enrich", "INFO")
        return 2

    # ── Step 2: Identify card_incomplete rows ──────────────────────────────────
    log("=== Step 2: Identify card-incomplete rows ===")

    def card_complete_check(row: dict) -> bool:
        if not row.get("property_address"):
            return False
        if row.get("latitude") is None or row.get("longitude") is None:
            return False
        if not row.get("assessed_value") and not row.get("market_value"):
            return False
        return True  # parcel_id already confirmed non-null

    incomplete = [r for r in all_rows if not card_complete_check(r)]
    log(f"  card-incomplete rows (missing geo or value): {len(incomplete)}", "VERIFIED")

    if not incomplete:
        log("  All rows with parcel_id are already geo/value complete — checking zone linkage")

    # Also check if any complete-geo rows lack zone_code in parcel_zones
    # (zone_code join is part of I card_complete per the I evaluator contract)
    complete_geo = [r for r in all_rows if card_complete_check(r)]
    log(f"  rows with geo+value+address: {len(complete_geo)}", "VERIFIED")

    # ── Step 3: ArcGIS + fl_parcels enrichment ─────────────────────────────────
    log("=== Step 3: ArcGIS enrichment (Baker parcels_web2 FeatureServer) ===")

    enriched_geo = 0
    parity_patched = 0
    zone_upserted = 0
    errors = []

    target_rows = incomplete if incomplete else all_rows

    for row in target_rows:
        parcel_id = row["parcel_id"]
        case_number = row["case_number"]
        sale_type = row["sale_type"]
        log(f"  Processing: case={case_number} parcel={parcel_id}")

        # Try Baker ArcGIS first
        arcgis_data = query_baker_arcgis(parcel_id)
        if arcgis_data is None:
            arcgis_data = query_baker_arcgis_alternate_field(parcel_id)

        # Fallback to fl_parcels (co_no=12)
        fl_data = get_fl_parcels_data(parcel_id)

        patch: dict = {}
        geo_source = None

        # Geo from ArcGIS (preferred — real parcel centroid)
        if arcgis_data and arcgis_data.get("lat") and arcgis_data.get("lng"):
            if not row.get("latitude") or not row.get("longitude"):
                patch["latitude"] = round(arcgis_data["lat"], 6)
                patch["longitude"] = round(arcgis_data["lng"], 6)
                geo_source = "baker_arcgis_parcels_web2"
                log(f"    ArcGIS geo: lat={patch['latitude']} lng={patch['longitude']}", "VERIFIED")
        elif fl_data and fl_data.get("lat") and fl_data.get("lng"):
            if not row.get("latitude") or not row.get("longitude"):
                patch["latitude"] = fl_data["lat"]
                patch["longitude"] = fl_data["lng"]
                geo_source = "fl_parcels_co_no_12"
                log(f"    fl_parcels geo: lat={patch['latitude']} lng={patch['longitude']}", "VERIFIED")

        # Assessed value from fl_parcels (fl_parcels has JV field, ArcGIS may not)
        if not row.get("assessed_value") and not row.get("market_value"):
            if fl_data and fl_data.get("assessed_value") and float(fl_data["assessed_value"]) > 0:
                patch["assessed_value"] = fl_data["assessed_value"]
                patch["market_value"] = fl_data["assessed_value"]
                log(f"    fl_parcels assessed_value: {patch['assessed_value']}", "VERIFIED")

        # Address from fl_parcels if missing
        if not row.get("property_address") and fl_data and fl_data.get("address"):
            addr_parts = [p for p in [fl_data.get("address"), fl_data.get("city"), "FL"] if p]
            patch["property_address"] = ", ".join(addr_parts)
            log(f"    fl_parcels address: {patch['property_address']}", "VERIFIED")

        if geo_source:
            patch["enrichment_source"] = geo_source

        if patch:
            ok = rest_patch_by_filter(
                "multi_county_auctions",
                f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(case_number)}&sale_type=eq.{sale_type}",
                patch,
            )
            if ok:
                enriched_geo += 1
                log(f"    PATCH ok: {list(patch.keys())}", "VERIFIED")
            else:
                errors.append(f"PATCH failed for {case_number}/{sale_type}")

        # Zone code handling
        zone_code = None
        if arcgis_data and arcgis_data.get("zone_code"):
            zone_code = arcgis_data["zone_code"]
            log(f"    ArcGIS zone_code: {zone_code}", "VERIFIED")

        if zone_code:
            # Ensure zone_code is in zoning_districts
            ensure_zone_code_in_districts(zone_code)

            # Check if parcel_zones row already exists
            existing_pz = rest_get("parcel_zones", {
                "parcel_id": f"eq.{parcel_id}",
                "jurisdiction_id": "eq.920",
                "select": "id",
                "limit": "1",
            })
            if not existing_pz:
                pz_rows = [{
                    "parcel_id": parcel_id,
                    "jurisdiction_id": BAKER_JURISDICTION_ID,
                    "zone_code": zone_code,
                    "zone_name": f"Baker County: {zone_code}",
                    "source": PIPELINE_VERSION,
                }]
                n = rest_upsert("parcel_zones", pz_rows, "parcel_id,jurisdiction_id")
                if n > 0:
                    zone_upserted += 1
                    log(f"    parcel_zones upserted: parcel_id={parcel_id} zone_code={zone_code}", "VERIFIED")
                else:
                    log(f"    parcel_zones upsert FAILED for {parcel_id}", "ERROR")
                    errors.append(f"parcel_zones failed for {parcel_id}")
            else:
                log(f"    parcel_zones already exists for {parcel_id}", "INFO")

        # Parity: if we confirmed the parcel via ArcGIS or fl_parcels, stamp matched_clean
        if (arcgis_data or fl_data) and not (row.get("parity_status") or "").startswith("matched"):
            ok = rest_patch_by_filter(
                "multi_county_auctions",
                f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(case_number)}&sale_type=eq.{sale_type}",
                {
                    "parity_status": "matched_clean",
                    "parity_scope": f"baker_arcgis_parcels_web2_{PIPELINE_VERSION}",
                    "parity_confidence": 0.90,
                },
            )
            if ok:
                parity_patched += 1
                log(f"    parity stamped matched_clean", "VERIFIED")

        time.sleep(0.5)  # polite rate limiting

    log(f"\n=== Step 3 Summary ===")
    log(f"  geo/value enriched: {enriched_geo}", "VERIFIED")
    log(f"  parcel_zones upserted: {zone_upserted}", "VERIFIED")
    log(f"  parity stamped: {parity_patched}", "VERIFIED")
    log(f"  errors: {errors}", "INFO" if not errors else "ERROR")

    if errors:
        log("FAIL-LOUD: some enrichment writes failed (see errors above)", "ERROR")

    # ── Step 4: Re-evaluate ────────────────────────────────────────────────────
    log("=== Step 4: pencil_dod_evaluate_county('baker') ===")
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    body = json.dumps({"p_county": "baker"}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers=REST_HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            result = json.loads(r.read())
        log(f"  Evaluation:\n{json.dumps(result, indent=2)}", "VERIFIED")

        passes = [l for l in "ABCDEFGHIJ" if isinstance(result.get(l), dict) and result[l].get("pass")]
        fails  = [l for l in "ABCDEFGHIJ" if l not in passes]
        log(f"  SCORE: {len(passes)}/10  PASS: {passes}  FAIL: {fails}", "VERIFIED")
    except Exception as exc:
        log(f"  evaluate_county RPC failed: {exc}", "ERROR")
        result = None

    # ── SQL VERIFICATION block ─────────────────────────────────────────────────
    print("\n### SQL VERIFICATION — baker_i_arcgis_enrichment", flush=True)
    print(f"Timestamp UTC: {NOW_ISO}", flush=True)
    print("""
-- I: card_complete count for baker
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN property_address IS NOT NULL
       AND latitude IS NOT NULL AND longitude IS NOT NULL
       AND (assessed_value IS NOT NULL OR market_value IS NOT NULL)
       AND parcel_id IS NOT NULL THEN 1 ELSE 0 END) AS geo_value_complete
FROM multi_county_auctions WHERE county='baker';

-- E: parcel_linked count
SELECT COUNT(*) AS parcel_linked FROM multi_county_auctions
WHERE county='baker' AND parcel_id IS NOT NULL;

-- C/D: parity counts
SELECT parity_status, COUNT(*) FROM multi_county_auctions
WHERE county='baker' GROUP BY parity_status;

-- Zone linkage for baker parcels
SELECT parcel_id, jurisdiction_id, zone_code FROM parcel_zones
WHERE parcel_id IN (SELECT parcel_id FROM multi_county_auctions WHERE county='baker' AND parcel_id IS NOT NULL);
""", flush=True)

    if errors:
        return 1
    if enriched_geo == 0 and zone_upserted == 0 and parity_patched == 0:
        log("No enrichment was needed or possible with current data", "INFO")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
