#!/usr/bin/env python3
"""GOLD STANDARD shard-9 (bay), dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53, loop run 6253.

Criterion I (card_complete) backfill for bay. All 57 incomplete rows are
missing zone_code (v_zoning_gold_standard_card has no parcel_zones row for
their parcel_id); 42 of those are also missing lat/lng, 5 missing address,
1 missing value.

Reuses the proven Bay County ArcGIS pattern from
scripts/gold_standard_bay_zoning_backfill.py: TEST_Parcels/MapServer/1,
queried by A1RENUM (=parcel_id), returns DSITEADDR/VASJUST/VASTOTAL/Zoning/
FLU plus polygon geometry (centroid -> lat/lng). Public, unauthenticated,
live Bay County government endpoint. No fabricated data -- every value
written here traces to a specific GIS feature; rows the service has no
answer for are left alone (BLANK > WRONG), not guessed.

Writes:
  - parcel_zones (jurisdiction_id, parcel_id, zone_code, zone_name, source)
    for rows where TEST_Parcels returns a non-null Zoning attribute.
  - multi_county_auctions.latitude/longitude (from polygon centroid),
    .property_address (from DSITEADDR) and .assessed_value (from VASJUST/
    VASTOTAL) only where currently NULL.

Idempotent: SELECT-before-INSERT on parcel_zones keyed by (jurisdiction_id,
parcel_id); PATCH only fields that are currently NULL on multi_county_auctions.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PARCEL_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1/query"
ZONING_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query"
RATE_LIMIT_SECONDS = 1.5
BUFFER_DEGREES_TRY = (0.00005, 0.0001, 0.0002, 0.0004)  # narrowest first

# SUB_ZONING attribute -> jurisdictions.id (bay county live table, confirmed 2026-07-10/2026-07-24)
JURISDICTION_ID = {
    1: 1332,  # Unincorporated Bay County
    2: 983,   # Callaway
    3: 873,   # Lynn Haven
    4: 985,   # Mexico Beach
    5: 884,   # Panama City
    6: 907,   # Panama City Beach
}


def _get(url, params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def lookup_parcel(parcel_id):
    time.sleep(RATE_LIMIT_SECONDS)
    where = f"A1RENUM='{parcel_id}'"
    data = _get(PARCEL_URL, {
        "where": where,
        "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL,Zoning,FLU",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    feats = data.get("features", [])
    if not feats:
        return None
    return feats[0]


def lookup_zoning_by_point(lat, lon):
    """Point-in-polygon zoning lookup with buffer-narrowing (proven pattern from
    scripts/gold_standard_bay_zoning_backfill.py). Returns (zone_code, jurisdiction_id,
    n_distinct_codes) for the first buffer size that yields >=1 feature; if the
    features at that buffer disagree on ZONING, returns n_distinct_codes>1 so the
    caller can skip rather than guess."""
    for buf in BUFFER_DEGREES_TRY:
        time.sleep(RATE_LIMIT_SECONDS)
        env = f"{lon - buf},{lat - buf},{lon + buf},{lat + buf}"
        data = _get(ZONING_URL, {
            "geometry": env,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false",
            "f": "json",
        })
        feats = data.get("features", [])
        if not feats:
            continue
        codes = {f["attributes"].get("ZONING") for f in feats}
        subs = {f["attributes"].get("SUB_ZONING") for f in feats}
        if len(codes) != 1:
            # ambiguous at the first buffer that returned anything -- a bigger
            # buffer only pulls in more neighboring polygons, never less
            # ambiguity, so stop here and let the caller skip (BLANK > WRONG).
            return None, None, len(codes)
        zone_code = next(iter(codes))
        jur_id = JURISDICTION_ID.get(next(iter(subs))) if len(subs) == 1 else None
        return zone_code, jur_id, 1
    return None, None, 0


def polygon_centroid(geometry):
    rings = (geometry or {}).get("rings")
    if not rings or not rings[0]:
        return None, None
    ring = rings[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(ys) / len(ys), sum(xs) / len(xs)  # (lat, lon)


def _with_retry(fn, attempts=3):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code == 409 or i == attempts - 1:
                raise
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_post(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def rest_patch(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def main():
    rows = rest_get(
        "multi_county_auctions?county=eq.bay"
        "&or=(data_source.neq.propertyonion,data_source.is.null)"
        "&select=id,parcel_id,property_address,latitude,longitude,po_latitude,po_longitude,assessed_value,market_value")

    def is_complete(r):
        has_geo = (r.get("latitude") or r.get("po_latitude")) and (r.get("longitude") or r.get("po_longitude"))
        return bool(r.get("property_address")) and bool(has_geo) and bool(r.get("assessed_value") or r.get("market_value"))

    gap_rows = [r for r in rows if r.get("parcel_id") and not is_complete(r)]
    print(f"gap rows with real parcel_id: {len(gap_rows)}")

    zoned_ok, geo_ok, addr_ok, value_ok = 0, 0, 0, 0
    not_found, no_zoning_attr, ambiguous_zoning, no_jurisdiction = 0, 0, 0, 0

    for r in gap_rows:
        pid = r["parcel_id"]
        feat = lookup_parcel(pid)
        if not feat:
            not_found += 1
            print(f"  {pid}: NOT FOUND in TEST_Parcels -- left alone")
            continue
        attrs = feat.get("attributes", {})
        addr = attrs.get("DSITEADDR")
        value = attrs.get("VASJUST") or attrs.get("VASTOTAL")
        lat, lon = polygon_centroid(feat.get("geometry"))

        zone_code = attrs.get("Zoning")
        jur_id = None
        if zone_code:
            # TEST_Parcels carries a Zoning value directly but not jurisdiction;
            # cross-check against the Zoning layer point lookup for jurisdiction
            # + a second independent read of the code.
            if lat and lon:
                z2_code, z2_jur, n = lookup_zoning_by_point(lat, lon)
                if n == 1 and z2_code == zone_code:
                    jur_id = z2_jur
        elif lat and lon:
            zone_code, jur_id, n = lookup_zoning_by_point(lat, lon)
            if n > 1:
                ambiguous_zoning += 1
                print(f"  {pid}: ambiguous zoning point-lookup ({n} distinct codes) -- left alone")
                zone_code = None

        if zone_code and jur_id:
            existing = rest_get(
                f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
            if not existing:
                rest_post("parcel_zones", {
                    "jurisdiction_id": jur_id,
                    "parcel_id": pid,
                    "zone_code": zone_code,
                    "zone_name": attrs.get("FLU"),
                    "source": "gis.baycountyfl.gov TEST_Parcels+Land_Use_Planning MapServer (live fetch, shard9_run6253)",
                })
                zoned_ok += 1
        elif zone_code and not jur_id:
            no_jurisdiction += 1
            print(f"  {pid}: zone_code={zone_code} but jurisdiction undetermined -- left alone")
        elif not zone_code:
            no_zoning_attr += 1
            print(f"  {pid}: no Zoning attribute from either layer (FLU={attrs.get('FLU')}) -- left alone")

        patch_body = {}
        if not r.get("property_address") and addr:
            patch_body["property_address"] = addr
            addr_ok += 1
        if not (r.get("latitude") or r.get("po_latitude")) and lat and lon:
            patch_body["latitude"] = lat
            patch_body["longitude"] = lon
            geo_ok += 1
        if not (r.get("assessed_value") or r.get("market_value")) and value:
            patch_body["assessed_value"] = value
            value_ok += 1
        if patch_body:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)

    print(f"\nTOTALS: zone_backfilled={zoned_ok} geo_backfilled={geo_ok} "
          f"addr_backfilled={addr_ok} value_backfilled={value_ok} "
          f"not_found={not_found} no_zoning_attr={no_zoning_attr} "
          f"ambiguous_zoning={ambiguous_zoning} no_jurisdiction={no_jurisdiction}")


if __name__ == "__main__":
    main()
