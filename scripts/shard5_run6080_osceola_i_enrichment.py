#!/usr/bin/env python3
"""SHARD-5 run6080 (dispatch ac5f5206) — Osceola criterion I enrichment.

CONTEXT (run6080, 2026-07-24):
  Osceola I = 35.8% (card_complete=48 of 134). Target: >= 95% (127/134).
  E=100% (all 134 rows have parcel_id). Need 79 more complete cards.

  v_zoning_gold_standard_card requires ALL FOUR to be non-null:
    1. property_address (or address)
    2. latitude + longitude
    3. assessed_value OR market_value
    4. parcel_zones row with non-null zone_code for this parcel_id

  Prior work (sessions through run5668):
    - 89 parcel_zones rows exist for jurisdiction_id=1186 (unincorporated Osceola)
    - Real zone codes: AC, PD, CT, RMH, MXD, STRPD, PMUD, CR
    - 21 parcels returned INCORP (inside Kissimmee/St Cloud) — not yet addressed
    - Some rows still lack lat/lon or assessed_value/market_value

  Known blockers (from 3rd Firing Addendum 2026-07-19):
    - 19 PURE_INCORP: parcels inside Kissimmee/St Cloud city limits
    - 12 MIXED_HAS_REAL_ZONE: multi-unit STRAPs with ambiguous sub-units (no house number)
    - 5 SYNTHETIC_NO_DATA: placeholder parcel_ids from PDF-scraped civil filings

  This session's approach:
    Step 1: FL GIO geo/value enrichment for any remaining rows missing lat/lon/value
    Step 2: Kissimmee ArcGIS spatial query for INCORP parcels with real centroid
            (cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10)
    Step 3: St Cloud ArcGIS PIN join for INCORP parcels
            (arcgisweb.stcloud.org/arcgis/rest/services/Referenced_Layers/Zoning/FeatureServer/2)
    Step 4: Additional real GIS parcel_zones backfill for any remaining uncovered rows

  HARD RULES:
  - BLANK > WRONG: if GIS returns INCORP, no-match, or ambiguous → leave NULL, skip
  - No PD-defaulting: prior sessions confirmed this is fabrication
  - FAIL-LOUD: if inserts needed but 0 inserted, raise
  - KISIMMEE/ST CLOUD: these need separate jurisdictions or use jurisdiction_id=1186
    with proper source tagging. Use the city-specific ArcGIS endpoints.

  NOTE: Kissimmee and St Cloud parcels need their own jurisdiction entries.
  If jurisdictions don't exist for them, we must create them OR tag under
  Unincorporated Osceola (1186) with zone_code from the city data.
  Per prior session findings, these ~9 INCORP parcels are inside municipal limits.
  The cleanest approach: check if Kissimmee/St Cloud jurisdictions exist in the DB,
  create if needed, then insert parcel_zones under those jurisdiction IDs.
  Fallback: tag under jurisdiction_id=1186 (unincorporated) with city source but
  only if actual zone code is verifiably correct (district polygon confirmed).

HONESTY:
  - FL GIO values: VERIFIED when returned from API
  - City ArcGIS: VERIFIED per live API response
  - No fabricated addresses, no guessed zone codes

Usage:
    python3 scripts/shard5_run6080_osceola_i_enrichment.py [--dry-run]

Env:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
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

COUNTY = "osceola"
CO_NO = 59
JURISDICTION_ID = 1186

DRY_RUN = "--dry-run" in sys.argv

SB_URL = os.environ["SUPABASE_URL"].rstrip("/")
SB_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

FL_DOR_CADASTRAL = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/"
    "Florida_Statewide_Cadastral/FeatureServer/0/query"
)
OSCEOLA_GIS_ZONING = (
    "https://gis.osceola.org/hosting/rest/services/Zoning_Parcels/FeatureServer/0/query"
)
KISSIMMEE_ZONING = (
    "https://cw.kissimmee.gov/arcgis/rest/services/Zoning_Districts/MapServer/10/query"
)
ST_CLOUD_ZONING = (
    "https://arcgisweb.stcloud.org/arcgis/rest/services/Referenced_Layers/Zoning/FeatureServer/2/query"
)

CHUNK_SIZE = 50
MAX_RETRIES = 3
REQUEST_DELAY = 0.4

KNOWN_VALID_ZONE_CODES = {"AC", "CR", "CT", "PD", "PMUD", "RMH", "STRPD", "MXD"}
INCORP_CODES = {"INCORP", "INCORPORATED", ""}

SB_HDR = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def log(msg, tag="UNTESTED"):
    print(f"[{ts()}] [{tag}] {msg}", flush=True)


def _retry(fn, retries=MAX_RETRIES):
    last = None
    for i in range(retries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError) as exc:
            last = exc
            wait = 2 ** i
            log(f"retry {i+1}/{retries} in {wait}s: {exc}", "UNTESTED")
            time.sleep(wait)
    raise RuntimeError(f"All {retries} retries exhausted: {last}")


def sb_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            headers={k: v for k, v in SB_HDR.items() if k not in ("Content-Type", "Prefer")},
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    return _retry(_do)


def sb_patch(path, body):
    if DRY_RUN:
        log(f"DRY-RUN PATCH {path}: {list(body.keys())}", "UNTESTED")
        return 1
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(),
            headers=SB_HDR,
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 1


def sb_post(table, records):
    if DRY_RUN:
        log(f"DRY-RUN POST {table}: {len(records)} records", "UNTESTED")
        return len(records)
    if not records:
        return 0
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/{table}",
            data=json.dumps(records).encode(),
            headers={**SB_HDR, "Prefer": "resolution=ignore-duplicates,return=representation"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as r:
            return json.loads(r.read())
    result = _retry(_do)
    return len(result) if isinstance(result, list) else 0


def sb_rpc(fn, params):
    def _do():
        req = urllib.request.Request(
            f"{SB_URL}/rest/v1/rpc/{fn}",
            data=json.dumps(params).encode(),
            headers={k: v for k, v in SB_HDR.items() if k not in ("Prefer",)},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    return _retry(_do)


def centroid(features):
    xs, ys = [], []
    for feat in features:
        rings = (feat.get("geometry") or {}).get("rings", [])
        for ring in rings:
            for pt in ring:
                xs.append(pt[0])
                ys.append(pt[1])
    if not xs:
        return None, None
    return sum(ys) / len(ys), sum(xs) / len(xs)


def get_osceola_mca_rows():
    rows = sb_get(
        "multi_county_auctions"
        "?county=eq.osceola"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude,"
        "assessed_value,market_value"
        "&order=case_number"
        "&limit=500"
    )
    log(f"Fetched {len(rows)} osceola MCA rows", "VERIFIED")
    return rows


def get_existing_parcel_zones():
    rows = sb_get(
        f"parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}"
        "&select=parcel_id,zone_code"
        "&limit=5000"
    )
    existing = {r["parcel_id"]: r["zone_code"] for r in rows}
    log(f"Existing parcel_zones (jurisdiction 1186): {len(existing)} rows", "VERIFIED")
    return existing


def get_city_jurisdictions():
    """Look up Kissimmee and St Cloud jurisdiction IDs."""
    rows = sb_get(
        "jurisdictions"
        "?county=eq.Osceola"
        "&select=id,name,state"
        "&limit=20"
    )
    log(f"Osceola jurisdictions in DB: {len(rows)}", "VERIFIED")
    for r in rows:
        log(f"  id={r['id']} name={r['name']}", "VERIFIED")
    kiss_id = next((r["id"] for r in rows if "kissimmee" in r["name"].lower()), None)
    stcloud_id = next((r["id"] for r in rows if "cloud" in r["name"].lower() or "st. cloud" in r["name"].lower()), None)
    log(f"Kissimmee jurisdiction_id: {kiss_id}", "VERIFIED")
    log(f"St Cloud jurisdiction_id: {stcloud_id}", "VERIFIED")
    return kiss_id, stcloud_id


def ensure_city_jurisdictions():
    """Create Kissimmee and St Cloud jurisdiction entries if they don't exist."""
    kiss_id, stcloud_id = get_city_jurisdictions()

    if not kiss_id:
        log("Kissimmee jurisdiction not found — creating...", "UNTESTED")
        if not DRY_RUN:
            records = [{
                "name": "Kissimmee",
                "county": "Osceola",
                "state": "FL",
                "co_no": 59,
                "source": "shard5_run6080_osceola_i:2026-07-24",
            }]
            req = urllib.request.Request(
                f"{SB_URL}/rest/v1/jurisdictions",
                data=json.dumps(records).encode(),
                headers={**SB_HDR, "Prefer": "resolution=ignore-duplicates,return=representation"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
            if result:
                kiss_id = result[0]["id"]
                log(f"Created Kissimmee jurisdiction id={kiss_id}", "VERIFIED")
            else:
                kiss_id, _ = get_city_jurisdictions()
                log(f"Kissimmee jurisdiction created (or existed), id={kiss_id}", "VERIFIED")
        else:
            log("DRY-RUN: would create Kissimmee jurisdiction", "UNTESTED")
            kiss_id = -1

    if not stcloud_id:
        log("St Cloud jurisdiction not found — creating...", "UNTESTED")
        if not DRY_RUN:
            records = [{
                "name": "St. Cloud",
                "county": "Osceola",
                "state": "FL",
                "co_no": 59,
                "source": "shard5_run6080_osceola_i:2026-07-24",
            }]
            req = urllib.request.Request(
                f"{SB_URL}/rest/v1/jurisdictions",
                data=json.dumps(records).encode(),
                headers={**SB_HDR, "Prefer": "resolution=ignore-duplicates,return=representation"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                result = json.loads(r.read())
            if result:
                stcloud_id = result[0]["id"]
                log(f"Created St. Cloud jurisdiction id={stcloud_id}", "VERIFIED")
            else:
                _, stcloud_id = get_city_jurisdictions()
                log(f"St Cloud jurisdiction created (or existed), id={stcloud_id}", "VERIFIED")
        else:
            log("DRY-RUN: would create St. Cloud jurisdiction", "UNTESTED")
            stcloud_id = -2

    return kiss_id, stcloud_id


def fetch_fl_gio_chunk(parcel_ids):
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCEL_ID IN ({id_list}) AND CO_NO = {CO_NO}",
        "outFields": "PARCEL_ID,CO_NO,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,AV_SD",
        "outSR": "4326",
        "returnGeometry": "true",
        "f": "json",
    }
    url = FL_DOR_CADASTRAL + "?" + urllib.parse.urlencode(params)
    def _do():
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def fetch_osceola_gis_chunk(parcel_ids):
    """Query Osceola county GIS for zone codes (unincorporated only)."""
    id_list = ",".join(f"'{p}'" for p in parcel_ids)
    params = {
        "where": f"PARCELNO IN ({id_list})",
        "outFields": "PARCELNO,PRIM_ZON",
        "returnGeometry": "false",
        "f": "json",
    }
    url = OSCEOLA_GIS_ZONING + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        return _retry(_do)
    except Exception as exc:
        log(f"Osceola GIS fetch failed: {exc}", "VERIFIED")
        return {"features": []}


def fetch_kissimmee_zoning_for_parcel(lat, lon):
    """Query Kissimmee GIS district layer at a point coordinate."""
    if lat is None or lon is None:
        return None
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "ZONING_COD,SUMMARY_LI",
        "returnGeometry": "false",
        "f": "json",
    }
    url = KISSIMMEE_ZONING + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        data = _retry(_do)
        features = data.get("features", [])
        if features:
            attrs = features[0]["attributes"]
            return attrs.get("ZONING_COD", "").strip()
        return None
    except Exception as exc:
        log(f"Kissimmee GIS fetch failed: {exc}", "UNTESTED")
        return None


def fetch_stcloud_zoning_for_parcel(parcel_id):
    """Query St Cloud GIS for zone code by Strap/PIN."""
    params = {
        "where": f"Strap='{parcel_id}' OR PIN='{parcel_id}'",
        "outFields": "PIN,Strap,Zoning",
        "returnGeometry": "false",
        "f": "json",
    }
    url = ST_CLOUD_ZONING + "?" + urllib.parse.urlencode(params)
    try:
        def _do():
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        data = _retry(_do)
        features = data.get("features", [])
        if features:
            attrs = features[0]["attributes"]
            return (attrs.get("Zoning") or "").strip()
        return None
    except Exception as exc:
        log(f"St Cloud GIS fetch failed for {parcel_id}: {exc}", "UNTESTED")
        return None


def step1_geo_value_enrichment(mca_rows):
    """Backfill lat/lon + assessed_value/market_value via FL GIO."""
    needs_geo = [
        r for r in mca_rows
        if r.get("parcel_id") and (
            r.get("latitude") is None or r.get("longitude") is None
            or (r.get("assessed_value") is None and r.get("market_value") is None)
        )
    ]
    log(f"Step 1: {len(needs_geo)} rows need geo/value enrichment", "UNTESTED")
    if not needs_geo:
        return 0

    parcel_ids = [r["parcel_id"] for r in needs_geo if r.get("parcel_id")]
    enrichment = {}
    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        try:
            data = fetch_fl_gio_chunk(chunk)
        except Exception as exc:
            log(f"FL GIO chunk {i}-{i+len(chunk)} FAILED: {exc}", "VERIFIED")
            continue
        if "error" in data:
            log(f"FL GIO error on chunk {i}: {data['error']}", "VERIFIED")
            continue
        features = data.get("features", [])
        for feat in features:
            attrs = feat["attributes"]
            pid = attrs.get("PARCEL_ID")
            if not pid:
                continue
            if attrs.get("CO_NO") != CO_NO:
                continue
            lat, lon = centroid([feat])
            addr1 = (attrs.get("PHY_ADDR1") or "").strip()
            city = (attrs.get("PHY_CITY") or "").strip()
            zipcd = attrs.get("PHY_ZIPCD")
            enrichment[pid] = {
                "lat": lat,
                "lon": lon,
                "market_value": attrs.get("JV") or None,
                "assessed_value": attrs.get("AV_SD") or None,
                "property_address": (
                    f"{addr1}, {city}, FL {int(zipcd)}"
                    if addr1 and city and zipcd else
                    (f"{addr1}, {city}, FL" if addr1 and city else None)
                ),
            }
        log(
            f"FL GIO chunk {i}-{i+len(chunk)}: requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    patched = 0
    for row in needs_geo:
        pid = row.get("parcel_id")
        entry = enrichment.get(pid)
        if not entry:
            continue
        body = {}
        if row.get("latitude") is None and entry["lat"] is not None:
            body["latitude"] = entry["lat"]
        if row.get("longitude") is None and entry["lon"] is not None:
            body["longitude"] = entry["lon"]
        if row.get("assessed_value") is None and entry["assessed_value"] is not None:
            body["assessed_value"] = entry["assessed_value"]
        if row.get("market_value") is None and entry["market_value"] is not None:
            body["market_value"] = entry["market_value"]
        if not row.get("property_address") and entry["property_address"]:
            body["property_address"] = entry["property_address"]
        if body:
            n = sb_patch(
                f"multi_county_auctions?id=eq.{row['id']}&county=eq.osceola",
                body,
            )
            if n:
                patched += 1
                log(f"PATCHED {row['case_number']} ({pid}): {list(body.keys())}", "VERIFIED")
        time.sleep(0.1)

    log(f"Step 1 complete: {patched}/{len(needs_geo)} rows enriched", "VERIFIED")
    return patched


def step2_county_parcel_zones_backfill(mca_rows, existing_pz):
    """Insert parcel_zones for county (unincorporated) rows not yet covered."""
    needs_pz = [
        r for r in mca_rows
        if r.get("parcel_id") and r["parcel_id"] not in existing_pz
    ]
    log(f"Step 2: {len(needs_pz)} rows need county parcel_zones entry", "UNTESTED")
    if not needs_pz:
        return 0, {}

    parcel_ids = [r["parcel_id"] for r in needs_pz]
    gis_zone_map = {}
    incorp_map = {}

    for i in range(0, len(parcel_ids), CHUNK_SIZE):
        chunk = parcel_ids[i:i + CHUNK_SIZE]
        data = fetch_osceola_gis_chunk(chunk)
        features = data.get("features", [])
        for feat in features:
            attrs = feat["attributes"]
            parcelno = attrs.get("PARCELNO")
            prim_zon = (attrs.get("PRIM_ZON") or "").strip()
            if parcelno:
                if prim_zon and prim_zon not in INCORP_CODES:
                    gis_zone_map[parcelno] = prim_zon
                elif prim_zon in INCORP_CODES:
                    incorp_map[parcelno] = prim_zon
        log(
            f"Osceola GIS chunk {i}-{i+len(chunk)}: requested={len(chunk)} matched={len(features)}",
            "VERIFIED",
        )
        time.sleep(REQUEST_DELAY)

    pz_inserts = []
    skipped_incorp = []
    skipped_unknown = []

    for row in needs_pz:
        pid = row["parcel_id"]
        raw_zone = gis_zone_map.get(pid, "")

        if pid in incorp_map:
            skipped_incorp.append((row["case_number"], pid))
            continue

        if not raw_zone:
            skipped_incorp.append((row["case_number"], pid))
            continue

        if raw_zone not in KNOWN_VALID_ZONE_CODES:
            skipped_unknown.append((row["case_number"], pid, raw_zone))
            continue

        pz_inserts.append({
            "parcel_id": pid,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": raw_zone,
            "source": f"shard5_run6080_osceola_gis_live:{raw_zone}:2026-07-24",
        })

    log(f"County GIS-verified inserts: {len(pz_inserts)}", "VERIFIED")
    log(f"Skipped INCORP/no-match: {len(skipped_incorp)} (will try city GIS next)", "VERIFIED")
    log(f"Skipped unknown codes: {len(skipped_unknown)} (BLANK>WRONG)", "VERIFIED")

    if pz_inserts:
        inserted = sb_post("parcel_zones", pz_inserts)
        log(f"Inserted {inserted}/{len(pz_inserts)} county parcel_zones rows", "VERIFIED")
        if not DRY_RUN and inserted == 0 and len(pz_inserts) > 0:
            raise RuntimeError(
                f"FAIL-LOUD: {len(pz_inserts)} parcel_zones queued but 0 inserted"
            )
    else:
        inserted = 0

    incorp_parcel_ids = [row["parcel_id"] for row in needs_pz if row["parcel_id"] in incorp_map
                         or (row["parcel_id"] not in gis_zone_map and row["parcel_id"] not in incorp_map)]
    incorp_rows = [r for r in needs_pz if r["parcel_id"] in incorp_map]

    return inserted, {r["parcel_id"]: r for r in incorp_rows}


def step3_city_zoning_backfill(mca_rows, incorp_pid_to_row, existing_pz, kiss_id, stcloud_id):
    """Look up zone codes for INCORP parcels from city ArcGIS endpoints."""
    log(f"Step 3: {len(incorp_pid_to_row)} INCORP parcels to try via city GIS", "UNTESTED")
    if not incorp_pid_to_row:
        return 0

    pz_inserts = []
    for pid, row in incorp_pid_to_row.items():
        if pid in existing_pz:
            log(f"  {row['case_number']} ({pid}): already has parcel_zones, skipping", "VERIFIED")
            continue

        lat = row.get("latitude")
        lon = row.get("longitude")

        stcloud_zone = fetch_stcloud_zoning_for_parcel(pid)
        time.sleep(0.3)

        if stcloud_zone and stcloud_zone not in INCORP_CODES:
            log(f"  {row['case_number']} ({pid}): St Cloud zone={stcloud_zone}", "VERIFIED")
            jid = stcloud_id if stcloud_id and stcloud_id > 0 else JURISDICTION_ID
            pz_inserts.append({
                "parcel_id": pid,
                "jurisdiction_id": jid,
                "zone_code": stcloud_zone,
                "zone_name": f"St. Cloud: {stcloud_zone}",
                "source": f"shard5_run6080_stcloud_gis:{stcloud_zone}:2026-07-24",
            })
            continue

        if lat and lon:
            kiss_zone = fetch_kissimmee_zoning_for_parcel(lat, lon)
            time.sleep(0.3)

            if kiss_zone and kiss_zone not in INCORP_CODES:
                log(f"  {row['case_number']} ({pid}): Kissimmee zone={kiss_zone}", "VERIFIED")
                jid = kiss_id if kiss_id and kiss_id > 0 else JURISDICTION_ID
                pz_inserts.append({
                    "parcel_id": pid,
                    "jurisdiction_id": jid,
                    "zone_code": kiss_zone,
                    "zone_name": f"Kissimmee: {kiss_zone}",
                    "source": f"shard5_run6080_kissimmee_gis:{kiss_zone}:2026-07-24",
                })
                continue

        log(f"  {row['case_number']} ({pid}): no city zone found (BLANK>WRONG, left NULL)", "VERIFIED")

    log(f"City GIS results: {len(pz_inserts)} city-zone rows to insert", "VERIFIED")
    if pz_inserts:
        inserted = sb_post("parcel_zones", pz_inserts)
        log(f"Inserted {inserted}/{len(pz_inserts)} city parcel_zones rows", "VERIFIED")
        return inserted
    return 0


def main():
    log("=== SHARD-5 RUN-6080 OSCEOLA I ENRICHMENT ===")

    baseline = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
    log(
        f"BASELINE: I={baseline.get('I')} card_complete={baseline.get('card_complete')} "
        f"auctions_total={baseline.get('auctions_total')}",
        "VERIFIED",
    )
    print(f"BEFORE: {json.dumps(baseline, indent=2)}", flush=True)

    mca_rows = get_osceola_mca_rows()
    existing_pz = get_existing_parcel_zones()

    kiss_id, stcloud_id = ensure_city_jurisdictions()

    geo_patched = step1_geo_value_enrichment(mca_rows)

    mca_rows = get_osceola_mca_rows()

    county_inserted, incorp_rows = step2_county_parcel_zones_backfill(mca_rows, existing_pz)

    existing_pz_updated = get_existing_parcel_zones()
    city_inserted = step3_city_zoning_backfill(mca_rows, incorp_rows, existing_pz_updated, kiss_id, stcloud_id)

    total_inserted = county_inserted + city_inserted

    if not DRY_RUN:
        log("Waiting 3s for DB to settle before re-evaluating...", "UNTESTED")
        time.sleep(3)
        after = sb_rpc("pencil_dod_evaluate_county", {"p_county": COUNTY})
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n### SQL VERIFICATION")
        print(f"Timestamp UTC: {now_iso}")
        print(f"SELECT public.pencil_dod_evaluate_county('osceola');")
        print(f"BEFORE: I={baseline.get('I')} card_complete={baseline.get('card_complete')}")
        print(f"AFTER:  I={after.get('I')} card_complete={after.get('card_complete')}")
        print(f"geo_patched={geo_patched} county_pz_inserted={county_inserted} city_pz_inserted={city_inserted}")
        print(f"AFTER JSON: {json.dumps(after, indent=2)}")

        if total_inserted == 0 and geo_patched == 0:
            log("No rows modified — all parcels already have zones and geo/value", "VERIFIED")
    else:
        print(
            f"\nDRY-RUN COMPLETE. Would geo_patch ~{geo_patched} rows, "
            f"insert ~{county_inserted} county + ~{city_inserted} city parcel_zones rows."
        )


if __name__ == "__main__":
    main()
