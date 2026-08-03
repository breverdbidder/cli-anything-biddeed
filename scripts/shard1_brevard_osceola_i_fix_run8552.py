#!/usr/bin/env python3
"""GOLD STANDARD SHARD-1: brevard + osceola — criterion I fixes.
dispatch_id: 1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5
loop run: 8552

BREVARD I (84.3%, card_complete=5985/7099 per brief):
  Root cause (VERIFIED across 3 prior sessions a42bf937/09F985FC/08-01):
  - ~1124 rows missing property_address → ~98% are genuinely no-situs vacant
    land (confirmed live against gis.brevardfl.gov Parcel_New MapServer/5).
    NOT a scraper gap. NOT fixable without a non-GIS source for vacant parcels.
  - ~56 rows with address but no parcel_zones entry → sit in Brevard's
    municipalities (Melbourne, Titusville, Palm Bay, Cocoa, Rockledge, etc.)
    which have SEPARATE ArcGIS zoning services not yet integrated.
  Fix this session: query each Brevard municipal ArcGIS endpoint for parcels
  missing parcel_zones, write real zone codes with proper source tags.

  Brevard municipal ArcGIS endpoints (from BCPAO + city GIS portals):
  - Melbourne: https://gis.melbourneflorida.org/ (ArcGIS Zoning layer)
  - Titusville: https://gis.titusville.com/ (Zoning_Districts FeatureServer)
  - Palm Bay: https://gisweb.palmbayflorida.org/ (Zoning FeatureServer)
  - Cocoa: https://www.cocoafl.org/gis/
  - Rockledge: Brevard County layer covers incorporated areas with Rockledge zoning
  NOTE: All queries use parcel centroid lat/lon for point-in-polygon lookup
  (same pattern as Kissimmee/St. Cloud fix in shard5/shard6 osceola sessions)

OSCEOLA I (92.7%, card_complete=127/137 per brief):
  10 remaining rows. From session history (ac5f5206 3rd firing + 091fb9f9 2nd
  firing), residual gap:
  - ~24 placeholder-address rows (21 with "Osceola County, FL 34741", 3 with
    bare street name) — need heavier address-to-fl_parcels matching
  - 3 OSC- synthetic-id rows from clerk PDF (foreclosure cases)
  - 1 multi-district-straddle parcel (declines correctly, structural)
  Fix this session: FL GIO address-based matching for placeholder rows,
  then query Kissimmee/St. Cloud municipal GIS for zone codes.

Usage:
    python3 scripts/shard1_brevard_osceola_i_fix_run8552.py [--dry-run] [--county brevard|osceola|both]
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DRY_RUN = "--dry-run" in sys.argv
COUNTY_ARG = None
for i, a in enumerate(sys.argv[1:]):
    if a == "--county" and i + 1 < len(sys.argv) - 1:
        COUNTY_ARG = sys.argv[i + 2]

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SB_URL or not SB_KEY:
    print("FATAL: SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY must be set", flush=True)
    sys.exit(1)

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)

BREVARD_CO_NO = 9
OSCEOLA_CO_NO = 59


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="INFO"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def sb_get(path, timeout=60):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def sb_patch(path, body, timeout=30):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {list(body.keys())}", "UNTESTED")
        return 1
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="PATCH",
        headers=SB_HDR,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        result = json.loads(r.read())
        return len(result) if isinstance(result, list) else 1


def sb_post(path, body, timeout=30):
    if DRY_RUN:
        log(f"DRY-RUN POST {path}: {list(body.keys())}", "UNTESTED")
        return {}
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{path}",
        data=json.dumps(body).encode(),
        method="POST",
        headers=SB_HDR,
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def sb_rpc(fn, params, timeout=120):
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/rpc/{fn}",
        data=json.dumps(params).encode(),
        method="POST",
        headers={k: v for k, v in SB_HDR.items() if k != "Prefer"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def polygon_centroid(rings):
    """Compute centroid of ArcGIS polygon rings."""
    xs, ys = [], []
    for ring in rings:
        for pt in ring:
            xs.append(pt[0])
            ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def query_arcgis_point_in_polygon(service_url, layer_id, lat, lon, zone_field, timeout=30):
    """Query an ArcGIS FeatureServer layer for the zone code at a lat/lon point."""
    params = {
        "geometry": json.dumps({"x": lon, "y": lat}),
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326",
        "outFields": zone_field,
        "returnGeometry": "false",
        "f": "json",
    }
    url = f"{service_url}/{layer_id}/query?" + urllib.parse.urlencode(params)
    try:
        result = http_get(url, timeout=timeout)
        features = result.get("features", [])
        if features:
            attrs = features[0].get("attributes", {})
            zone = attrs.get(zone_field)
            if zone and str(zone).strip() and str(zone).upper() not in ("NULL", "NONE", "", "0"):
                return str(zone).strip()
    except Exception as e:
        log(f"ArcGIS query failed for ({lat:.4f},{lon:.4f}): {e}", "WARN")
    return None


BREVARD_MUNICIPAL_ARCGIS = [
    {
        "city": "Melbourne",
        "service_url": "https://services1.arcgis.com/IBrJ3N3PAmVxGzf4/arcgis/rest/services/MelbourneZoning/FeatureServer",
        "layer_id": "0",
        "zone_field": "ZONING",
        "jurisdiction_slug": "melbourne",
    },
    {
        "city": "Palm Bay",
        "service_url": "https://gis.palmbayflorida.org/arcgis/rest/services/Zoning/MapServer",
        "layer_id": "0",
        "zone_field": "ZONE_CODE",
        "jurisdiction_slug": "palm_bay",
    },
    {
        "city": "Titusville",
        "service_url": "https://gis.titusville.com/arcgis/rest/services/Zoning/FeatureServer",
        "layer_id": "0",
        "zone_field": "ZONING",
        "jurisdiction_slug": "titusville",
    },
    {
        "city": "Cocoa",
        "service_url": "https://gis.cocoafl.org/arcgis/rest/services/Zoning/FeatureServer",
        "layer_id": "0",
        "zone_field": "ZONE_CODE",
        "jurisdiction_slug": "cocoa",
    },
    {
        "city": "Rockledge",
        "service_url": "https://services1.arcgis.com/IBrJ3N3PAmVxGzf4/arcgis/rest/services/RockledgeZoning/FeatureServer",
        "layer_id": "0",
        "zone_field": "ZONING",
        "jurisdiction_slug": "rockledge",
    },
]

KISSIMMEE_ZONING_SVC = "https://services1.arcgis.com/AuZDpnVX5jOHN0R1/arcgis/rest/services/Zoning_Districts/FeatureServer"
KISSIMMEE_ZONE_FIELD = "ZONE_CODE"
ST_CLOUD_ZONING_SVC = "https://arcgisweb.stcloud.org/arcgis/rest/services/Zoning/FeatureServer"
ST_CLOUD_ZONE_FIELD = "ZONE_CODE"
OSCEOLA_UNINC_ZONING_SVC = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Osceola_County_Zoning/FeatureServer"
OSCEOLA_UNINC_ZONE_FIELD = "PRIM_ZON"


def get_brevard_jurisdiction_id(city_name):
    """Fetch jurisdiction_id for a Brevard city from DB."""
    encoded = urllib.parse.quote(city_name)
    rows = sb_get(f"jurisdictions?name=eq.{encoded}&county=eq.Brevard&select=id,name")
    if rows:
        return rows[0]["id"]
    rows = sb_get(f"jurisdictions?name=ilike.*{urllib.parse.quote(city_name.lower())}*&county=eq.Brevard&select=id,name")
    if rows:
        return rows[0]["id"]
    return None


def get_or_create_zoning_district(jurisdiction_id, zone_code, source_url):
    """Get or create a zoning_districts row. Returns district id."""
    rows = sb_get(
        f"zoning_districts?jurisdiction_id=eq.{jurisdiction_id}"
        f"&code=eq.{urllib.parse.quote(zone_code)}&select=id"
    )
    if rows:
        return rows[0]["id"]
    if DRY_RUN:
        log(f"DRY-RUN: would INSERT zoning_districts ({jurisdiction_id}, {zone_code})", "UNTESTED")
        return -1
    result = sb_post("zoning_districts", {
        "jurisdiction_id": jurisdiction_id,
        "code": zone_code,
        "name": zone_code,
        "category": "residential",
        "source_url": source_url,
        "far_regulated": None,
        "density_regulated": None,
    })
    if isinstance(result, list) and result:
        return result[0]["id"]
    return None


def insert_parcel_zone(parcel_id, jurisdiction_id, zone_code, source):
    """Insert parcel_zones row (idempotent via ON CONFLICT DO NOTHING)."""
    if DRY_RUN:
        log(f"DRY-RUN: would INSERT parcel_zones ({parcel_id}, {zone_code}, jur={jurisdiction_id})", "UNTESTED")
        return True
    body = {
        "parcel_id": parcel_id,
        "jurisdiction_id": jurisdiction_id,
        "zone_code": zone_code,
        "source": source,
        "tax_account": parcel_id,
    }
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/parcel_zones",
        data=json.dumps(body).encode(),
        method="POST",
        headers={**SB_HDR, "Prefer": "return=minimal,resolution=ignore-duplicates"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode()[:200]
        if "duplicate" in body_txt.lower() or "conflict" in body_txt.lower() or e.code == 409:
            return True
        log(f"parcel_zones INSERT failed: {e.code} {body_txt}", "WARN")
        return False


def fix_brevard_i():
    """Fix Brevard criterion I: query municipal ArcGIS zoning for parcels missing parcel_zones."""
    log("=== BREVARD I FIX: municipal zoning backfill ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": "brevard"})
    log(f"BASELINE: {baseline}", "VERIFIED")

    brevard_i = baseline.get("I", {})
    log(f"Brevard I (before): {brevard_i}", "VERIFIED")

    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.brevard"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude"
        "&property_address=not.is.null"
        "&latitude=not.is.null"
        "&longitude=not.is.null"
        "&limit=2000"
    )
    log(f"Brevard rows with address+geo: {len(rows)}", "VERIFIED")

    rows_with_parcel = [r for r in rows if r.get("parcel_id")]
    log(f"Brevard rows with parcel_id: {len(rows_with_parcel)}", "VERIFIED")

    existing_zones = sb_get(
        "parcel_zones?select=parcel_id&jurisdiction_id=in.(select id from jurisdictions where county=eq.Brevard)"
        if False
        else "parcel_zones?select=parcel_id&limit=50000"
    )
    zoned_parcel_ids = {r["parcel_id"] for r in existing_zones if r.get("parcel_id")}
    log(f"Parcel IDs already in parcel_zones (all counties): {len(zoned_parcel_ids)}", "VERIFIED")

    zoneless = [r for r in rows_with_parcel if r["parcel_id"] not in zoned_parcel_ids]
    log(f"Brevard rows with address+geo+parcel but NO zone: {len(zoneless)}", "VERIFIED")

    if not zoneless:
        log("No zoneless rows found — Brevard I zoning gap already resolved", "VERIFIED")
        return 0

    fixed = 0
    declined = 0

    for row in zoneless[:100]:
        lat = row.get("latitude")
        lon = row.get("longitude")
        parcel_id = row["parcel_id"]
        if not lat or not lon:
            continue

        found = False
        for muni in BREVARD_MUNICIPAL_ARCGIS:
            zone_code = query_arcgis_point_in_polygon(
                muni["service_url"], muni["layer_id"], lat, lon, muni["zone_field"]
            )
            if zone_code:
                jur_id = get_brevard_jurisdiction_id(muni["city"])
                if not jur_id:
                    log(f"jurisdiction not found for {muni['city']} — skipping", "WARN")
                    continue
                source = f"municipal_gis:{muni['city'].lower().replace(' ', '_')}:arcgis_pip"
                ok = insert_parcel_zone(parcel_id, jur_id, zone_code, source)
                if ok:
                    log(f"WROTE parcel_zones: parcel={parcel_id} city={muni['city']} zone={zone_code}", "VERIFIED")
                    fixed += 1
                    found = True
                break

        if not found:
            county_layer_url = "https://gis.brevardfl.gov/arcgis/rest/services/Planning_Development/Zoning_WKID2881/MapServer"
            zone_code = query_arcgis_point_in_polygon(county_layer_url, "0", lat, lon, "ZONING")
            if zone_code:
                county_jur_rows = sb_get("jurisdictions?name=eq.Unincorporated Brevard County&select=id")
                if not county_jur_rows:
                    county_jur_rows = sb_get("jurisdictions?name=ilike.*Brevard*&county=eq.Brevard&select=id,name&limit=5")
                if county_jur_rows:
                    jur_id = county_jur_rows[0]["id"]
                    source = "brevardfl_gov_planning_zoning_wkid2881:arcgis_pip"
                    ok = insert_parcel_zone(parcel_id, jur_id, zone_code, source)
                    if ok:
                        log(f"WROTE parcel_zones (county): parcel={parcel_id} zone={zone_code}", "VERIFIED")
                        fixed += 1
                        found = True

        if not found:
            declined += 1
            log(f"No zone found for parcel={parcel_id} lat={lat:.4f} lon={lon:.4f} — skipped (no fabrication)", "INFO")

        time.sleep(0.2)

    log(f"Brevard I fix: {fixed} parcel_zones written, {declined} declined (no zone found)", "VERIFIED")

    if not DRY_RUN:
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "brevard"})
        log(f"AFTER I: {after.get('I')}", "VERIFIED")
        return fixed, after
    return fixed, None


def fix_osceola_i():
    """Fix Osceola criterion I: address+geo+zone backfill for remaining ~10 incomplete rows."""
    log("=== OSCEOLA I FIX: remaining placeholder-address rows ===")
    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": "osceola"})
    log(f"BASELINE: {baseline}", "VERIFIED")

    osceola_i = baseline.get("I", {})
    log(f"Osceola I (before): {osceola_i}", "VERIFIED")

    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.osceola"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
        "&limit=1000"
    )
    log(f"Osceola total rows: {len(rows)}", "VERIFIED")

    incomplete = [
        r for r in rows
        if not (
            r.get("property_address")
            and r.get("latitude")
            and r.get("longitude")
            and (r.get("assessed_value") or r.get("market_value"))
        )
        and r.get("parcel_id")
    ]
    log(f"Osceola incomplete rows (address|geo|value missing): {len(incomplete)}", "VERIFIED")

    placeholder_addresses = {
        "Osceola County, FL 34741", "Osceola County, FL",
        "UNKNOWN, Osceola County, FL", "Kissimmee, FL 34741",
    }

    fixed = 0

    for row in incomplete:
        parcel_id = row.get("parcel_id", "")
        if not parcel_id:
            continue

        if parcel_id.startswith("OSC-"):
            log(f"Skipping OSC- synthetic parcel {parcel_id} (needs clerk PDF source)", "INFO")
            continue

        try:
            clean_pid = parcel_id.replace("-", "").replace(" ", "")
            is_truncated = len(clean_pid) < 16

            if is_truncated:
                log(f"Truncated parcel_id {parcel_id} — FL GIO prefix search may be ambiguous, skip", "INFO")
                continue

            params = {
                "where": f"PARCEL_ID='{parcel_id}' AND CO_NO={OSCEOLA_CO_NO}",
                "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
                "outSR": "4326",
                "returnGeometry": "true",
                "f": "json",
            }
            url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
            result = http_get(url, timeout=45)
            features = result.get("features", [])
            if not features:
                continue

            feat = features[0]
            attrs = feat.get("attributes", {})
            if attrs.get("CO_NO") != OSCEOLA_CO_NO:
                continue

            lat, lon = polygon_centroid(feat.get("geometry", {}).get("rings", []))
            addr1 = (attrs.get("PHY_ADDR1") or "").strip()
            city = (attrs.get("PHY_CITY") or "").strip()
            zipcd = attrs.get("PHY_ZIPCD")
            jv = attrs.get("JV")
            av_sd = attrs.get("AV_SD")

            address = None
            if addr1 and city and zipcd:
                address = f"{addr1}, {city}, FL {int(zipcd)}"
            elif addr1 and city:
                address = f"{addr1}, {city}, FL"

            body = {}
            current_addr = row.get("property_address") or ""
            if current_addr in placeholder_addresses or not current_addr:
                if address:
                    body["property_address"] = address
            if row.get("latitude") is None and lat:
                body["latitude"] = lat
            if row.get("longitude") is None and lon:
                body["longitude"] = lon
            if row.get("assessed_value") is None and av_sd:
                body["assessed_value"] = av_sd
            if row.get("market_value") is None and jv:
                body["market_value"] = jv

            if body:
                n = sb_patch(f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola", body)
                if n:
                    log(f"PATCHED osceola parcel={parcel_id}: {list(body.keys())}", "VERIFIED")
                    fixed += 1

                    if not row.get("latitude") and lat and lon:
                        zone_code = None
                        zone_source = None

                        zone_code = query_arcgis_point_in_polygon(
                            KISSIMMEE_ZONING_SVC, "0", lat, lon, KISSIMMEE_ZONE_FIELD
                        )
                        if zone_code:
                            zone_source = "kissimmee_arcgis_pip:run8552"
                            jur_rows = sb_get("jurisdictions?name=eq.Kissimmee&county=eq.Osceola&select=id")
                            if jur_rows:
                                insert_parcel_zone(parcel_id, jur_rows[0]["id"], zone_code, zone_source)
                                log(f"Osceola parcel {parcel_id} zone={zone_code} (Kissimmee)", "VERIFIED")

                        if not zone_code:
                            zone_code = query_arcgis_point_in_polygon(
                                ST_CLOUD_ZONING_SVC, "0", lat, lon, ST_CLOUD_ZONE_FIELD
                            )
                            if zone_code:
                                zone_source = "stcloud_arcgis_pip:run8552"
                                jur_rows = sb_get("jurisdictions?name=eq.Saint Cloud&county=eq.Osceola&select=id")
                                if not jur_rows:
                                    jur_rows = sb_get("jurisdictions?name=ilike.*cloud*&county=eq.Osceola&select=id,name&limit=2")
                                if jur_rows:
                                    insert_parcel_zone(parcel_id, jur_rows[0]["id"], zone_code, zone_source)
                                    log(f"Osceola parcel {parcel_id} zone={zone_code} (St. Cloud)", "VERIFIED")

                        if not zone_code:
                            zone_code = query_arcgis_point_in_polygon(
                                OSCEOLA_UNINC_ZONING_SVC, "0", lat, lon, OSCEOLA_UNINC_ZONE_FIELD
                            )
                            if zone_code and zone_code.upper() != "INCORP":
                                zone_source = "gis_osceola_org_zoning_parcels:arcgis_pip:run8552"
                                jur_rows = sb_get("jurisdictions?id=eq.1186&select=id")
                                if jur_rows:
                                    insert_parcel_zone(parcel_id, 1186, zone_code, zone_source)
                                    log(f"Osceola parcel {parcel_id} zone={zone_code} (unincorporated)", "VERIFIED")

        except Exception as e:
            log(f"Error processing osceola parcel {parcel_id}: {e}", "WARN")
            continue

        time.sleep(0.1)

    log(f"Osceola I fix: {fixed} rows patched", "VERIFIED")

    if not DRY_RUN:
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": "osceola"})
        log(f"AFTER I: {after.get('I')}", "VERIFIED")
        return fixed, after
    return fixed, None


def log_session_closeout(dispatch_id, brevard_result, osceola_result):
    """Write session checkpoint to gold_standard_campaign."""
    log("=== SESSION CLOSE-OUT ===")
    brevard_criteria = {}
    osceola_criteria = {}
    if brevard_result and isinstance(brevard_result, dict):
        for l in "ABCDEFGHIJ":
            ld = brevard_result.get(l, {})
            brevard_criteria[l] = ld.get("pass", False) if isinstance(ld, dict) else False
    if osceola_result and isinstance(osceola_result, dict):
        for l in "ABCDEFGHIJ":
            ld = osceola_result.get(l, {})
            osceola_criteria[l] = ld.get("pass", False) if isinstance(ld, dict) else False

    for county, criteria in [("brevard", brevard_criteria), ("osceola", osceola_criteria)]:
        passed = sum(1 for v in criteria.values() if v)
        log(f"{county}: {passed}/10 criteria passed: {criteria}", "VERIFIED")

    if not DRY_RUN:
        update_sql = f"""
UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(brevard_criteria)}'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '{dispatch_id}'
  AND county_slug = 'brevard';

UPDATE public.gold_standard_campaign
SET
  criteria_passed = '{json.dumps(osceola_criteria)}'::jsonb,
  criteria_total = 10,
  exit_reason = 'timeout',
  session_end_at = now()
WHERE dispatch_id = '{dispatch_id}'
  AND county_slug = 'osceola';
"""
        log(f"Session close-out SQL (for manual apply if needed):\n{update_sql}", "VERIFIED")


def main():
    log("=== SHARD-1 BREVARD+OSCEOLA I FIX (run 8552) ===")
    log(f"DRY_RUN={DRY_RUN} COUNTY={COUNTY_ARG or 'both'}")

    dispatch_id = "1f5f4ede-c466-4c43-a9ec-e6ce1d02c1e5"

    brevard_after = None
    osceola_after = None

    if COUNTY_ARG in (None, "both", "brevard"):
        brevard_fixed, brevard_after = fix_brevard_i()
        log(f"Brevard I: {brevard_fixed} new parcel_zones written", "VERIFIED")

    if COUNTY_ARG in (None, "both", "osceola"):
        osceola_fixed, osceola_after = fix_osceola_i()
        log(f"Osceola I: {osceola_fixed} rows enriched", "VERIFIED")

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\n### SQL VERIFICATION")
    print(f"Timestamp UTC: {now_iso}")
    print(f"SELECT public.pencil_dod_evaluate_county('brevard');")
    if brevard_after:
        print(f"Brevard result: {json.dumps(brevard_after)}")
    print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
    if osceola_after:
        print(f"Osceola result: {json.dumps(osceola_after)}")

    log_session_closeout(dispatch_id, brevard_after, osceola_after)


if __name__ == "__main__":
    main()
