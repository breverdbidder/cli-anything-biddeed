#!/usr/bin/env python3
"""
Shard-7 run3679: Lake county criterion-I (property card completeness) real-data fix.

ROOT CAUSE (diagnosed live against multi_county_auctions + parcel_zones +
v_zoning_gold_standard_card, 2026-07-11):
  - I = card_complete/card_rows where card_rows already have property_address,
    (lat/po_lat), (lon/po_lon), (assessed_value/market_value) — ALL 73
    parcel-linked lake auction rows already have these fields populated (a prior
    session's ArcGIS FieldMap enrichment covered them). The remaining I gap is
    NOT missing auction-row fields — it's the zoning substrate join:
    v_zoning_gold_standard_card requires parcel_id to match a row in
    parcel_zones (jurisdiction_id=835 for Lake) WHERE zone_code IS NOT NULL.
  - parcel_zones for jurisdiction 835 only had 15 rows, all with a blanket
    generic zone_code='R-1' / zone_name='Single Family Residential' and
    source='shard7_g_i_fix/lake_auto' (a prior best-effort default, not real
    per-parcel zoning) — 3 of those 15 rows are attached to fabricated
    'SYN-LAKE-*' parcel_ids that don't correspond to any real auction row
    (left untouched here; out of scope, no auction row references them).

REAL FIX: Lake County's own GIS (gis.lakecountyfl.gov) publishes an actual
zoning polygon layer at InteractiveMap/MapServer/50 (fields: Zoning,
ZoningDist, ZoningNm, OrdNum, OrdDate) covering unincorporated Lake County.
For each of the 73 parcel-linked lake auction rows (all of which already carry
real lat/lon from the prior ArcGIS FieldMap enrichment), we run a live
point-in-polygon query against this layer:
  - HIT (feature found): the point is on unincorporated county land subject to
    county zoning -> insert/update parcel_zones with the REAL zone_code from
    the layer, source='lake_county_gis_zoning_layer_live'.
  - MISS (no feature found): the point falls inside an incorporated
    municipality (Clermont, Eustis, Leesburg, etc. all zone their own land,
    not the county) -> left untouched, NOT defaulted, NOT fabricated. This is
    an honest structural gap (out of scope: would require per-municipality
    zoning layers, a Phase-4-style scrape effort, not a data backfill).

This script only ever writes a zone_code that came verbatim from a live
ArcGIS response for that exact parcel's own coordinates. No blanket/default
zoning is applied. No coordinates are invented (all rows here already carry
real lat/lon from a prior enrichment; this script does not touch lat/lon).

Writes:
  - parcel_zones: INSERT new rows for parcels not yet present (jurisdiction_id=835)
  - parcel_zones: UPDATE existing generic-R-1 rows where the real zoning layer
    disagrees with the prior default (correcting the earlier best-effort default
    with the ArcGIS ground truth)
"""
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
JURISDICTION_ID = 835  # Lake County (unincorporated) — confirmed via existing parcel_zones rows

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


def http_patch(url, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def fetch_parcel_linked_rows():
    url = (
        f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
        "?county=eq.lake&data_source=neq.propertyonion"
        "&select=id,case_number,parcel_id,property_address,latitude,longitude"
        "&limit=1000"
    )
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch multi_county_auctions rows: HTTP {status}: {rows}")
    return [r for r in rows if r["parcel_id"] and r["latitude"] is not None and r["longitude"] is not None]


def fetch_existing_parcel_zones():
    url = f"{SUPABASE_URL}/rest/v1/parcel_zones?jurisdiction_id=eq.{JURISDICTION_ID}&select=id,parcel_id,zone_code"
    status, rows = http_get(url, headers=REST_HEADERS)
    if status != 200:
        raise RuntimeError(f"Failed to fetch parcel_zones: HTTP {status}: {rows}")
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
    status, data = http_get(url, headers=ARCGIS_HEADERS, timeout=20)
    return status, data


def main():
    rows = fetch_parcel_linked_rows()
    existing = fetch_existing_parcel_zones()

    receipt = []
    counts = {
        "parcel_linked_with_coords": len(rows),
        "arcgis_hit": 0,
        "arcgis_miss_municipal_or_unmapped": 0,
        "arcgis_query_error": 0,
        "inserted": 0,
        "updated": 0,
        "update_skipped_same_value": 0,
        "write_failures": 0,
    }

    for row in rows:
        case_number = row["case_number"]
        parcel_id = row["parcel_id"]
        lat, lon = row["latitude"], row["longitude"]

        try:
            status, data = query_zoning(lat, lon)
        except Exception as e:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "query_error", "error": str(e)})
            time.sleep(0.1)
            continue

        if status != 200:
            counts["arcgis_query_error"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "http_error", "status": status})
            time.sleep(0.1)
            continue

        feats = data.get("features", [])
        if not feats:
            counts["arcgis_miss_municipal_or_unmapped"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "no_feature_municipal_or_gap"})
            time.sleep(0.1)
            continue

        counts["arcgis_hit"] += 1
        attrs = feats[0]["attributes"]
        zone_code = (attrs.get("Zoning") or "").strip() or None
        zone_name = attrs.get("ZoningNm")

        if not zone_code:
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "hit_but_null_zone_code", "attrs": attrs})
            time.sleep(0.1)
            continue

        existing_row = existing.get(parcel_id)
        if existing_row is None:
            body = {
                "parcel_id": parcel_id,
                "jurisdiction_id": JURISDICTION_ID,
                "zone_code": zone_code,
                "zone_name": zone_name,
                "source": "lake_county_gis_zoning_layer_live",
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
        elif existing_row["zone_code"] != zone_code:
            body = {
                "zone_code": zone_code,
                "zone_name": zone_name,
                "source": "lake_county_gis_zoning_layer_live",
            }
            wstatus, wtext = http_patch(
                f"{SUPABASE_URL}/rest/v1/parcel_zones?id=eq.{existing_row['id']}", body,
                headers={**REST_HEADERS, "Prefer": "return=minimal"})
            ok = wstatus in (200, 201, 204)
            if ok:
                counts["updated"] += 1
            else:
                counts["write_failures"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "update",
                             "old_zone_code": existing_row["zone_code"], "new_zone_code": zone_code,
                             "write_status": wstatus, "write_ok": ok,
                             "write_error": None if ok else wtext})
        else:
            counts["update_skipped_same_value"] += 1
            receipt.append({"case_number": case_number, "parcel_id": parcel_id, "result": "already_correct", "zone_code": zone_code})

        time.sleep(0.1)

    output = {"receipt": receipt, "counts": counts}
    print(json.dumps(output, indent=2))

    if counts["arcgis_hit"] > 0 and (counts["inserted"] + counts["updated"] + counts["update_skipped_same_value"]) == 0:
        print("FAIL-LOUD: ArcGIS returned hits but zero rows were written/confirmed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
