#!/usr/bin/env python3
"""
Lake county letter-G coverage backfill (continuation of shard7_run3679_lake_i_real_zoning_backfill.py
and shard7c_lake_g_zoning_standards_fix.py, same session, after a separate agent's Lake letter-E
parcel-linkage fix increased the number of parcel-linked lake auction rows).

DIAGNOSIS (live, 2026-07-24):
  v_zoning_gold_standard_kpi_v3 showed lake G = density 73.8%, far 100.0%, pk1000 NULL
  (0 applicable, 43 N/A) -- and pencil_dod_evaluate_county's G computation takes
  LEAST(density_pct, far_pct, pk1000_pct); pk1000_pct is NULL when pk1000_applicable_parcels=0,
  and NULL propagates through LEAST() so the whole G metric reads as failing/null-contaminated
  even though far is 100%. That NULL-LEAST() behavior is a pre-existing evaluator trait, not
  something this script patches or works around (see closing report note below).

  Separately and independently: the prior letter-E agent in this session linked MORE lake
  auction rows to real parcel_id values than existed when the last G/I zoning work ran. Live
  query against parcel_zones (jurisdiction_id=835, Lake County) for jurisdiction 835:

    SELECT COUNT(*) FROM multi_county_auctions m
    LEFT JOIN parcel_zones pz ON pz.parcel_id = m.parcel_id AND pz.jurisdiction_id = 835
    WHERE m.county='lake' AND m.data_source != 'propertyonion'
      AND m.parcel_id IS NOT NULL AND pz.zone_code IS NULL;
    -> 41 rows (40 distinct parcel_id; one parcel_id shared by 2 case numbers)

  All 41 of these have real lat/lon already (from a prior ArcGIS FieldMap enrichment) --
  this is a genuine COVERAGE gap (missing parcel_zones rows entirely), not a standards gap.
  ROOT CAUSE = (2) from the task brief: parcel_zones coverage is incomplete for Lake and
  needs backfilling from the real Lake County GIS zoning layer, now that E linked more parcels.

REAL FIX: identical method to shard7_run3679_lake_i_real_zoning_backfill.py -- live
point-in-polygon query against Lake County's own zoning GIS layer
(gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50, fields: Zoning,
ZoningDist, ZoningNm, OrdNum, OrdDate) for each of the 41 newly-gapped rows' real lat/lon.
  - HIT: insert parcel_zones with the REAL zone_code from the layer,
    source='lake_county_gis_zoning_layer_live_g_coverage_backfill'.
  - MISS (no feature -- point falls inside an incorporated municipality that zones its own
    land, e.g. Clermont/Eustis/Leesburg/Mount Dora/Tavares/etc.): left untouched, NOT
    defaulted, NOT fabricated -- an honest structural gap requiring per-municipality zoning
    layers (out of scope for this fix).

This script only ever writes a zone_code that came verbatim from a live ArcGIS response for
that exact parcel's own coordinates. No blanket/default zoning is applied. No coordinates
are invented -- all read from existing multi_county_auctions.latitude/longitude.

Usage:
  python3 scripts/shard_lake_g_parcel_zones_coverage_backfill.py [--dry-run]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

ZONING_URL = "https://gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50/query"
JURISDICTION_ID = 835  # Lake County (unincorporated) -- confirmed via existing parcel_zones rows
SOURCE_TAG = "lake_county_gis_zoning_layer_live_g_coverage_backfill"

DRY_RUN = "--dry-run" in sys.argv

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}  # Cloudflare in front of gis.lakecountyfl.gov blocks default UA


def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode())


def http_post(url, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def rpc(fn, params):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(params).encode(), method="POST",
        headers={**REST_HEADERS})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch_gap_rows():
    """multi_county_auctions rows for lake with a real parcel_id + coords but NO parcel_zones row."""
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.lake&data_source=neq.propertyonion"
        "&select=id,case_number,parcel_id,latitude,longitude"
        "&limit=1000"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch multi_county_auctions rows: HTTP {status}: {rows}")
    rows = [r for r in rows if r["parcel_id"] and r["latitude"] is not None and r["longitude"] is not None]

    pz_url = f"{SUPABASE_URL}/rest/v1/parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}&select=parcel_id"
    status, pz_rows = http_get(pz_url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch parcel_zones: HTTP {status}: {pz_rows}")
    have_pz = {r["parcel_id"] for r in pz_rows}

    seen = set()
    gap = []
    for r in rows:
        if r["parcel_id"] in have_pz or r["parcel_id"] in seen:
            continue
        seen.add(r["parcel_id"])
        gap.append(r)
    return gap


def query_zoning(lat, lon):
    params = {
        "geometry": json.dumps({"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "Zoning,ZoningDist,ZoningNm,OrdNum,OrdDate",
        "returnGeometry": "false",
        "f": "json",
    }
    url = ZONING_URL + "?" + urllib.parse.urlencode(params)
    return http_get(url, headers=ARCGIS_HEADERS, timeout=20)


def main():
    gap_rows = fetch_gap_rows()
    print(f"[INFO] {len(gap_rows)} distinct lake parcel_ids with real coords but NO parcel_zones row",
          flush=True)

    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] BASELINE G: {baseline['G']}", flush=True)
    print(f"[VERIFIED] BASELINE I: {baseline['I']}", flush=True)

    receipt = []
    counts = {
        "gap_rows": len(gap_rows),
        "arcgis_hit": 0,
        "arcgis_miss_municipal_or_unmapped": 0,
        "arcgis_query_error": 0,
        "inserted": 0,
        "write_failures": 0,
    }

    for row in gap_rows:
        case_number = row["case_number"]
        parcel_id = row["parcel_id"]
        lat, lon = row["latitude"], row["longitude"]

        try:
            status, data = query_zoning(lat, lon)
        except Exception as e:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "query_error", "error": str(e)})
            time.sleep(0.1)
            continue

        if status != 200:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "http_error", "status": status})
            time.sleep(0.1)
            continue

        feats = data.get("features", [])
        if not feats:
            counts["arcgis_miss_municipal_or_unmapped"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "no_feature_municipal_or_gap"})
            time.sleep(0.1)
            continue

        counts["arcgis_hit"] += 1
        attrs = feats[0]["attributes"]
        zone_code = (attrs.get("Zoning") or "").strip() or None
        zone_name = attrs.get("ZoningNm")

        if not zone_code:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "hit_but_null_zone_code", "attrs": attrs})
            time.sleep(0.1)
            continue

        if DRY_RUN:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "dry_run_would_insert", "zone_code": zone_code})
            time.sleep(0.1)
            continue

        body = {
            "parcel_id": parcel_id,
            "jurisdiction_id": JURISDICTION_ID,
            "zone_code": zone_code,
            "zone_name": zone_name,
            "source": SOURCE_TAG,
        }
        wstatus, wtext = http_post(f"{SUPABASE_URL}/rest/v1/parcel_zones", body,
                                    headers={**REST_HEADERS, "Prefer": "return=minimal"})
        ok = wstatus in (200, 201, 204)
        if ok:
            counts["inserted"] += 1
        else:
            counts["write_failures"] += 1
        receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "insert",
                         "zone_code": zone_code, "write_status": wstatus, "write_ok": ok,
                         "write_error": None if ok else wtext})

        time.sleep(0.1)

    print(json.dumps({"receipt": receipt, "counts": counts}, indent=2))

    if counts["arcgis_hit"] > 0 and counts["inserted"] == 0 and not DRY_RUN:
        print("FAIL-LOUD: ArcGIS returned hits but zero rows were written.", file=sys.stderr)
        sys.exit(1)

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] AFTER G: {after['G']}", flush=True)
    print(f"[VERIFIED] AFTER I: {after['I']}", flush=True)
    print(f"BEFORE G: {baseline['G']}")
    print(f"AFTER  G: {after['G']}")
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")


if __name__ == "__main__":
    main()
