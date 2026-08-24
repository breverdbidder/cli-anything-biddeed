#!/usr/bin/env python3
"""
Lake county letter-I "zone_link" gap fix (shard-3, dispatch 8da53925, session 2026-08-24).

Orchestrator's precomputed I-gap list contained 8 rows tagged missing=["zone_link"]:
parcel_id is known but has NO parcel_zones row for jurisdiction_id=835 (Lake County
unincorporated -- same jurisdiction used by every prior lake zoning-backfill script,
e.g. scripts/shard_lake_g_parcel_zones_coverage_backfill.py).

Confirmed live (2026-08-24) via REST: all 8 parcel_ids have zero parcel_zones rows
(any jurisdiction), and all 8 multi_county_auctions rows have real, non-null lat/lon
already on file (from a prior ArcGIS enrichment pass).

Method: identical to the proven shard_lake_g_parcel_zones_coverage_backfill.py pattern
-- live point-in-polygon query against Lake County's own zoning GIS layer
(gis.lakecountyfl.gov/lakegis/rest/services/InteractiveMap/MapServer/50, fields:
Zoning, ZoningDist, ZoningNm, OrdNum, OrdDate) for each row's real lat/lon.
  - HIT: insert parcel_zones with the REAL zone_code from the live ArcGIS response,
    source='lake_county_gis_zoning_layer_live_i_zonelink_8gap_fix'.
  - MISS (no feature -- point falls inside an incorporated municipality with its own
    zoning, e.g. Clermont/Eustis/Leesburg/Mount Dora/Tavares/Minneola/etc, which this
    countywide unincorporated layer does not cover): left untouched, NOT defaulted,
    NOT fabricated -- documented as a genuine structural gap (out of scope, needs a
    per-municipality zoning layer this session did not build).

No coordinates invented. No zone_code guessed. Every write traces to a live ArcGIS
response for that exact parcel's own on-file coordinates.

Usage:
  python3 scripts/lake_i_zone_link_8row_gap_fix.py [--dry-run]
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
SOURCE_TAG = "lake_county_gis_zoning_layer_live_i_zonelink_8gap_fix"

DRY_RUN = "--dry-run" in sys.argv

REST_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
ARCGIS_HEADERS = {"User-Agent": "curl/8.5.0"}  # Cloudflare in front of gis.lakecountyfl.gov blocks default UA

# The 8 rows from the orchestrator's precomputed I-gap list (missing=["zone_link"]).
GAP_ROWS = [
    {"id": "54cda541-67d4-4700-aef9-003f071453cc", "case_number": "2024CA000927", "parcel_id": "052225010000001900"},
    {"id": "a4cfe863-c651-494b-a2f4-f6cf3e0afe29", "case_number": "2025CA002147", "parcel_id": "051927000400000700"},
    {"id": "906269ea-ab0d-4f7d-901c-0752b5fdb092", "case_number": "2025CA002791", "parcel_id": "251927050002301300"},
    {"id": "8337e62d-52c4-4686-ab29-61b0a792091c", "case_number": "2024CA001936", "parcel_id": "262426240000002800"},
    {"id": "7818aa8a-8836-45ce-8127-e9712e5a216a", "case_number": "2026CA000434", "parcel_id": "221924085000000100"},
    {"id": "bf34e389-6478-47cf-9769-297444d40ef0", "case_number": "2025CA001816", "parcel_id": "291925160000001000"},
    {"id": "39ab5969-b775-4ab4-b7ca-e20ff851327f", "case_number": "2025CA002565", "parcel_id": "011926060000202200"},
    {"id": "4861ac0d-1ba4-4466-bcb8-2c84f6ffeeb3", "case_number": "2024CA002034", "parcel_id": "242426001100018200"},
]


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


def fetch_coords():
    ids = ",".join(r["parcel_id"] for r in GAP_ROWS)
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        f"?county=eq.lake&parcel_id=in.({ids})"
        "&select=id,case_number,parcel_id,latitude,longitude"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch coords: HTTP {status}: {rows}")
    return {r["parcel_id"]: r for r in rows}


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
    coords = fetch_coords()
    baseline = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] BASELINE I: {baseline['I']}", flush=True)
    print(f"[VERIFIED] BASELINE E: {baseline['E']}", flush=True)

    receipt = []
    counts = {"gap_rows": len(GAP_ROWS), "arcgis_hit": 0, "arcgis_miss_municipal_or_unmapped": 0,
              "arcgis_query_error": 0, "inserted": 0, "write_failures": 0, "no_coords": 0}

    for row in GAP_ROWS:
        parcel_id = row["parcel_id"]
        case_number = row["case_number"]
        mca = coords.get(parcel_id)
        if not mca or mca["latitude"] is None or mca["longitude"] is None:
            counts["no_coords"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "no_coords_on_file"})
            continue

        lat, lon = mca["latitude"], mca["longitude"]
        try:
            status, data = query_zoning(lat, lon)
        except Exception as e:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "query_error", "error": str(e)})
            time.sleep(0.2)
            continue

        if status != 200:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "http_error", "status": status})
            time.sleep(0.2)
            continue

        feats = data.get("features", [])
        if not feats:
            counts["arcgis_miss_municipal_or_unmapped"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id,
                             "result": "no_feature_municipal_or_gap", "lat": lat, "lon": lon})
            time.sleep(0.2)
            continue

        counts["arcgis_hit"] += 1
        attrs = feats[0]["attributes"]
        zone_code = (attrs.get("Zoning") or "").strip() or None
        zone_name = attrs.get("ZoningNm")

        if not zone_code:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "hit_but_null_zone_code", "attrs": attrs})
            time.sleep(0.2)
            continue

        if DRY_RUN:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "dry_run_would_insert",
                             "zone_code": zone_code, "zone_name": zone_name})
            time.sleep(0.2)
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
                         "zone_code": zone_code, "zone_name": zone_name, "write_status": wstatus,
                         "write_ok": ok, "write_error": None if ok else wtext})
        time.sleep(0.2)

    print(json.dumps({"receipt": receipt, "counts": counts}, indent=2))

    if counts["arcgis_hit"] > 0 and counts["inserted"] == 0 and not DRY_RUN:
        print("FAIL-LOUD: ArcGIS returned hits but zero rows were written.", file=sys.stderr)
        sys.exit(1)

    if DRY_RUN:
        print("\n### DRY-RUN COMPLETE -- no writes performed")
        return

    after = rpc("pencil_dod_evaluate_county", {"p_county": "lake"})
    print(f"[VERIFIED] AFTER I: {after['I']}", flush=True)
    print(f"[VERIFIED] AFTER E: {after['E']}", flush=True)
    print(f"BEFORE I: {baseline['I']}")
    print(f"AFTER  I: {after['I']}")
    print(f"BEFORE E: {baseline['E']}")
    print(f"AFTER  E: {after['E']}")


if __name__ == "__main__":
    main()
