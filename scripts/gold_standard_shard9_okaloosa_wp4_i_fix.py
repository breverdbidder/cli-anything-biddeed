#!/usr/bin/env python3
"""
Okaloosa Gold Standard WP4: letter I (property card completeness) fix
=======================================================================
Dispatch f8de10ec-e7af-4ac2-9af7-6b7dd80c3809, work-package 4 of 5.

Baseline (LIVE-VERIFIED, pencil_dod_evaluate_county before this run):
  I: card_complete=38 of 57 (66.7%), needs >=55/57 (>=95%) to PASS.

I's exact SQL requires, per row: property_address IS NOT NULL AND
geo(lat+lon) IS NOT NULL AND COALESCE(assessed_value,market_value) IS NOT NULL
AND parcel_id resolves to a zone_code in v_zoning_gold_standard_card.

Gap diagnosis (fresh, this session, after fix1's fabrication purge + fix3's
parcel linkage work):
  - 2 rows (2024-CA-000470, 2024-TDD-000089): documented stale placeholder
    seed rows with NO parcel_id at all. NOT recoverable. Left untouched.
  - 15 rows (B4A-1299795..B4A-1299809, tax_deed): real APN-format parcel_id
    already present (e.g. '351S24274800000040'), but NO lat/lon and NO
    assessed/market value (fix1 purged their prior fabricated values).
  - 2 rows (2025-CA-002956-C, 2025CA000832F, foreclosure): already had
    address+geo+value, only missing a parcel_zones zone-code match.

THE LEVER (TD lane, value+geo in one shot):
  Okaloosa's ArcGIS PIN field uses DASHED format
  (##-#N/S-##-####-####-####), but our stored tax_deed parcel_id is the
  UNDASHED 18-char APN (e.g. '351S24274800000040'). Verified live that
  splitting into 2/2/2/4/4/4-char groups and re-joining with dashes produces
  an exact PIN match:
    '351S24274800000040' -> '35-1S-24-2748-0000-0040' -> 1 GIS feature.
  Confirmed for all 15 B4A-1299795..809 rows (1 feature each, live query
  against Land-Ownership/Parcels_with_Addressing/MapServer/121).
  TOTALAPPR/ASSEDVAL give real market/assessed value; polygon ring centroid
  gives real lat/lon. One query per row closes both gaps.

Zoning substrate (after geo+value real):
  City resolved via point-in-polygon against
  Admin-Boundaries/Admin_Boundaries/MapServer/99 (ICLPY_CITY_CODE).
  Zone resolved via the matching per-city GIS layer, or for UNINCORPORATED
  via Planning-Development/Zoning/MapServer.

  IMPORTANT LIVE FINDING: the county zoning layer has MOVED since the prior
  reference script (shard4_run5668) was written. Layer 28 is now "Coastal
  Construction Control Line" (unrelated). Live probe of
  Planning-Development/Zoning/MapServer?f=json found "County Zoning" (with
  the expected ZNGPY_ZONE field) at layer 25. This script uses layer 25.

  Mary Esther (city_code MARY ESTHER) has NO known zoning GIS source: probed
  LocalGovernment/Mary_Esther_EnerGov/MapServer -- only Site Address, Parcels,
  Subdivisions, Platted-Lots, flood/boundary layers, no zoning field anywhere.
  Also confirmed the county's own unincorporated zoning layer (25) returns 0
  features at Mary Esther's coordinates (it's inside the incorporated city
  limits, outside the county's unincorporated zoning coverage). Row
  B4A-1299799 is therefore LEFT UNRESOLVED -- do not guess a zone_code.

Result (LIVE-VERIFIED, pencil_dod_evaluate_county after this run):
  I: card_complete=54 of 57 (94.7%) -- up from 38/57 (66.7%), still 1 short
  of the 55/57 (>=95%) PASS threshold.

Residual (3 rows, all confirmed unrecoverable or unresolved with real data):
  - 2024-CA-000470, 2024-TDD-000089: stale placeholder seed rows, no
    parcel_id, not touched (documented, out of scope).
  - B4A-1299799 (Mary Esther): real address/geo/value present, but no live
    GIS zoning source exists for this municipality. Left unresolved rather
    than guessing a zone_code.

Env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
County scope: okaloosa ONLY. This script is single-county; it does not loop
over or touch any other county's rows.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DRY_RUN = "--dry-run" in sys.argv
COUNTY = "okaloosa"

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

GIS_BASE = "https://okgis.myokaloosa.com/arcgis/rest/services/Land-Ownership/Parcels_with_Addressing/MapServer/121/query"
CITY_LIMITS_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Admin-Boundaries/Admin_Boundaries/MapServer/99/query"
# NOTE: layer index moved from 28 (prior script) -> 25 (live, this session).
# 28 is now "Coastal Construction Control Line". 25 is "County Zoning" with
# the expected ZNGPY_ZONE field.
COUNTY_ZONING_URL = "https://okgis.myokaloosa.com/arcgis/rest/services/Planning-Development/Zoning/MapServer/25/query"
COUNTY_ZONING_SOURCE_TAG = "okaloosa_gis:planning-development/zoning:25"

CITY_ZONING_SOURCES = {
    "CRESTVIEW": {
        "jurisdiction_name": "Crestview",
        "url": "https://services9.arcgis.com/zvdDL6ILvlkPNTg8/arcgis/rest/services/Zoning_and_FLU/FeatureServer/0/query",
        "zone_field": "ZONE",
        "source_tag": "crestview_gis:zoning_and_flu_featureserver:0",
    },
    "FORT WALTON BEACH": {
        "jurisdiction_name": "Fort Walton Beach",
        "url": "https://gis.fwb.org/arcgis/rest/services/Maps/Zoning/MapServer/0/query",
        "zone_field": "Zoning",
        "source_tag": "fwb_gis:maps/zoning:0",
    },
    "NICEVILLE": {
        "jurisdiction_name": "Niceville",
        "url": "https://gis.nicevillefl.gov/server/rest/services/Zoning/MapServer/0/query",
        "zone_field": "Zoning_2015",
        "source_tag": "niceville_gis:zoning:0",
    },
    "DESTIN": {
        "jurisdiction_name": "Destin",
        "url": "https://okgis.myokaloosa.com/arcgis/rest/services/LocalGovernment/Destin_EnerGov/MapServer/6/query",
        "zone_field": "Zone_ABBR",
        "source_tag": "okaloosa_gis:localgovernment/destin_energov:6",
    },
    # MARY ESTHER intentionally absent: no known zoning GIS source (probed
    # live, 2026-07-24 -- see docstring above).
}

UNINCORPORATED_JURISDICTION_NAME = "Unincorporated Okaloosa County"


def ts():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}


def sb_get(path, limit=500):
    url = f"{SB_URL}/rest/v1/{path}{'&' if '?' in path else '?'}limit={limit}"
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(path, params, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}?{params}: {list(body.keys())}", "UNTESTED")
        return True
    url = f"{SB_URL}/rest/v1/{path}?{params}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data,
                                  headers={**_headers(), "Prefer": "return=representation"},
                                  method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            return len(result) > 0 if isinstance(result, list) else True
    except urllib.error.HTTPError as e:
        log(f"PATCH {path} failed: {e.code} {e.read().decode()[:200]}", "VERIFIED")
        return False


def sb_post(table, records):
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(records)} records", "UNTESTED")
        return len(records)
    if not records:
        return 0
    data = json.dumps(records).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/{table}",
        data=data,
        headers={**_headers(), "Prefer": "resolution=ignore-duplicates,return=representation"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            result = json.loads(r.read())
            return len(result) if isinstance(result, list) else 0
    except urllib.error.HTTPError as e:
        log(f"POST {table} failed: {e.code} {e.read().decode()[:200]}", "VERIFIED")
        return 0


def _point_query(url, lon, lat, out_fields):
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": out_fields,
        "returnGeometry": "false",
        "f": "json",
    }
    req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS error at {url}: {data['error']}")
    return data.get("features", [])


def _pin_query(where, out_fields="PIN,SITE_ADDR,TOTALAPPR,ASSEDVAL"):
    params = {"where": where, "outFields": out_fields, "outSR": "4326", "f": "json", "returnGeometry": "true"}
    req = urllib.request.Request(GIS_BASE + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    if "error" in data:
        raise RuntimeError(f"GIS query error: {data['error']} (where={where})")
    return data.get("features", [])


def _centroid(feature):
    geom = feature.get("geometry")
    if not geom or "rings" not in geom or not geom["rings"]:
        return None
    ring = geom["rings"][0]
    if not ring:
        return None
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _to_dashed_pin(apn18):
    """Okaloosa TD parcel_id (18-char undashed APN) -> GIS PIN dashed format.
    VERIFIED live 2026-07-24: '351S24274800000040' -> '35-1S-24-2748-0000-0040'
    matches exactly 1 feature; confirmed across all 15 gap rows this session.
    """
    if len(apn18) != 18:
        return None
    return f"{apn18[0:2]}-{apn18[2:4]}-{apn18[4:6]}-{apn18[6:10]}-{apn18[10:14]}-{apn18[14:18]}"


def resolve_city_code(lat, lon):
    try:
        feats = _point_query(CITY_LIMITS_URL, lon, lat, "ICLPY_CITY_CODE")
    except Exception as exc:
        log(f"city_limits query error: {exc}", "VERIFIED")
        return None
    if len(feats) != 1:
        return None
    return feats[0]["attributes"]["ICLPY_CITY_CODE"]


def resolve_zone(city_code, lat, lon):
    if city_code == "UNINCORPORATED":
        try:
            feats = _point_query(COUNTY_ZONING_URL, lon, lat, "ZNGPY_ZONE")
        except Exception as exc:
            return None, f"county_zoning_error:{exc}"
        if len(feats) == 0:
            return None, "county_zoning_layer_0_results"
        zones = {f["attributes"].get("ZNGPY_ZONE") for f in feats}
        if len(zones) != 1:
            return None, f"county_zoning_layer_{len(feats)}_results_disagreeing"
        zone = next(iter(zones))
        if not zone:
            return None, "county_zoning_layer_null_zone_field"
        note = "" if len(feats) == 1 else f" ({len(feats)}_duplicate_features_agreeing)"
        return zone, COUNTY_ZONING_SOURCE_TAG + note
    cfg = CITY_ZONING_SOURCES.get(city_code)
    if not cfg:
        return None, f"no_known_zoning_source_for_city_code_{city_code!r}"
    try:
        feats = _point_query(cfg["url"], lon, lat, cfg["zone_field"])
    except Exception as exc:
        return None, f"{cfg['jurisdiction_name']}_zoning_error:{exc}"
    if len(feats) != 1:
        return None, f"{cfg['jurisdiction_name']}_zoning_layer_{len(feats)}_results"
    zone = feats[0]["attributes"].get(cfg["zone_field"])
    if not zone:
        return None, f"{cfg['jurisdiction_name']}_zoning_layer_null_zone_field"
    return zone, cfg["source_tag"]


def fetch_rows():
    rows = sb_get(
        "multi_county_auctions?county=eq.okaloosa"
        "&select=case_number,sale_type,property_address,parcel_id,"
        "assessed_value,market_value,latitude,longitude"
    )
    log(f"Fetched {len(rows)} okaloosa rows", "VERIFIED")
    return rows


def fetch_jurisdictions():
    rows = sb_get("jurisdictions?county=eq.Okaloosa&select=id,name")
    return {row["name"]: row["id"] for row in rows}


def fetch_existing_parcel_zone_ids(parcel_ids):
    if not parcel_ids:
        return set()
    quoted = ",".join(f'"{p}"' for p in parcel_ids)
    rows = sb_get(f"parcel_zones?parcel_id=in.({quoted})&select=parcel_id")
    return {r["parcel_id"] for r in rows}


def run_td_gis_enrichment(rows):
    """TD lane: for rows with an undashed 18-char APN and missing geo/value,
    convert to dashed PIN format and query GIS for value + centroid."""
    targets = [
        r for r in rows
        if r["sale_type"] == "tax_deed" and r.get("parcel_id")
        and (r.get("latitude") is None or r.get("longitude") is None or
             (r.get("assessed_value") is None and r.get("market_value") is None))
    ]
    matched, unmatched, skipped = [], [], []
    for r in targets:
        cn = r["case_number"]
        apn = r["parcel_id"]
        dashed = _to_dashed_pin(apn)
        if not dashed:
            skipped.append((cn, f"apn_not_18_chars_undashed:{apn!r}"))
            continue
        try:
            feats = _pin_query(f"PIN = '{dashed}'")
        except Exception as exc:
            unmatched.append((cn, f"gis_query_error:{exc}"))
            continue
        if len(feats) != 1:
            unmatched.append((cn, f"{len(feats)}_results_for_pin_{dashed!r}"))
            continue
        attrs = feats[0]["attributes"]
        cen = _centroid(feats[0])
        fields = {}
        if attrs.get("ASSEDVAL") is not None and r.get("assessed_value") is None:
            fields["assessed_value"] = attrs["ASSEDVAL"]
        if attrs.get("TOTALAPPR") is not None and r.get("market_value") is None:
            fields["market_value"] = attrs["TOTALAPPR"]
        if cen and (r.get("latitude") is None or r.get("longitude") is None):
            fields["latitude"], fields["longitude"] = cen
        if not fields:
            skipped.append((cn, "already_complete"))
            continue
        matched.append((cn, fields))
        log(f"RESOLVED {cn} apn={apn} pin={dashed} fields={list(fields.keys())}", "VERIFIED")

    log(f"TD GIS enrichment: {len(matched)} matches, {len(unmatched)} unmatched, {len(skipped)} skipped", "UNTESTED")
    for cn, reason in unmatched:
        log(f"  UNMATCHED {cn}: {reason}", "VERIFIED")

    success = 0
    for cn, fields in matched:
        ok = sb_patch("multi_county_auctions", f"county=eq.{COUNTY}&case_number=eq.{urllib.parse.quote(cn)}", fields)
        if ok:
            success += 1
        time.sleep(0.1)
    log(f"TD GIS enrichment: {success}/{len(matched)} patched", "VERIFIED")
    return success


def run_zoning_substrate(rows, jurisdictions):
    """Insert parcel_zones for any okaloosa row with parcel_id+lat+lon not
    already covered."""
    rows_with_geo = [r for r in rows if r.get("parcel_id") and r.get("latitude") and r.get("longitude")]
    existing = fetch_existing_parcel_zone_ids([r["parcel_id"] for r in rows_with_geo])

    if UNINCORPORATED_JURISDICTION_NAME not in jurisdictions:
        raise RuntimeError(
            f"'{UNINCORPORATED_JURISDICTION_NAME}' jurisdiction row not found -- "
            "expected from supabase/migrations/20260719_shard3_okaloosa_i_unincorporated_jurisdiction.sql"
        )

    city_to_juris_name = {
        "CRESTVIEW": "Crestview",
        "FORT WALTON BEACH": "Fort Walton Beach",
        "NICEVILLE": "Niceville",
        "DESTIN": "Destin",
        "UNINCORPORATED": UNINCORPORATED_JURISDICTION_NAME,
    }

    to_insert, unresolved, already_covered = [], [], []
    for r in rows_with_geo:
        pid = r["parcel_id"]
        if pid in existing:
            already_covered.append((r["case_number"], pid))
            continue
        lat, lon = r["latitude"], r["longitude"]
        city_code = resolve_city_code(lat, lon)
        if city_code is None:
            unresolved.append((r["case_number"], pid, "city_limits_layer_ambiguous_or_zero_results"))
            continue
        jur_name = city_to_juris_name.get(city_code)
        if not jur_name or jur_name not in jurisdictions:
            unresolved.append((r["case_number"], pid, f"no_jurisdiction_for_city_code_{city_code!r}"))
            continue
        zone_code, source_or_reason = resolve_zone(city_code, lat, lon)
        if zone_code is None:
            unresolved.append((r["case_number"], pid, source_or_reason))
            continue
        to_insert.append({
            "parcel_id": pid,
            "jurisdiction_id": jurisdictions[jur_name],
            "zone_code": zone_code,
            "source": source_or_reason + ":shard9_okaloosa_wp4",
        })
        log(f"RESOLVED {r['case_number']} parcel_id={pid} city={city_code} zone={zone_code}", "VERIFIED")
        time.sleep(0.1)

    log(f"Zoning substrate: {len(already_covered)} already covered, {len(to_insert)} to insert, {len(unresolved)} unresolved", "UNTESTED")
    for cn, pid, reason in unresolved:
        log(f"  UNRESOLVED {cn} ({pid}): {reason}", "VERIFIED")

    if not to_insert:
        return 0
    inserted = sb_post("parcel_zones", to_insert)
    log(f"Zoning substrate: inserted {inserted} parcel_zones rows", "VERIFIED")
    return inserted


def main():
    log(f"=== Okaloosa WP4 (letter I) fix, county={COUNTY} dry_run={DRY_RUN} ===", "UNTESTED")
    rows = fetch_rows()
    jurisdictions = fetch_jurisdictions()
    run_td_gis_enrichment(rows)
    rows = fetch_rows()  # re-fetch post-patch for zoning substrate step
    run_zoning_substrate(rows, jurisdictions)
    log("Done. Verify via pencil_dod_evaluate_county RPC.", "UNTESTED")


if __name__ == "__main__":
    main()
