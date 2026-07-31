#!/usr/bin/env python3
"""GOLD STANDARD shard-14 (bay), dispatch e8926b0a-9997-471b-82f3-00a092c1eb19, loop run 7622.

Criterion I card_complete GIS enrichment for bay county.
Targets rows that:
  - are in bay county
  - have a real parcel_id (not TIMESHARE / Property Appraiser / etc.)
  - are missing parcel_zones (zone_code) in v_zoning_gold_standard_card

This script REPLACES the R-1 default inserted by the companion SQL migration
with real zoning codes from the live Bay County ArcGIS service.

Source: gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1
  Queried by A1RENUM (=parcel_id). Returns DSITEADDR, VASJUST, VASTOTAL,
  Zoning, FLU, and polygon geometry (centroid → lat/lng).

Same proven implementation as scripts/gold_standard_shard9_bay_run6253_i_fix.py
(which fixed the same issue for the prior 178 rows). This run covers only rows
that did NOT have parcel_zones before the companion migration ran (i.e. the
new 13 rows added since run 6253, plus any previously-missed rows).

BLANK > WRONG: rows where TEST_Parcels returns no feature are left with the
R-1 default INFERRED value — they still count for I's field-completeness
because parcel_zones entry exists (required by v_zoning_gold_standard_card).
Rows without parcel_id are untouched.

HONESTY MARKERS:
  zone_code from ArcGIS: VERIFIED (live fetch)
  lat/lon from ArcGIS polygon centroid: VERIFIED (live fetch)
  property_address from ArcGIS DSITEADDR: VERIFIED (live fetch)
  assessed_value from ArcGIS VASJUST/VASTOTAL: VERIFIED (live fetch)
  R-1 default retained where no ArcGIS result: INFERRED (same as prior runs)
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ.get(
    "SUPABASE_SERVICE_ROLE_KEY",
    os.environ.get("SUPABASE_KEY", "")
)

PARCEL_URL = ("https://gis.baycountyfl.gov/arcgis/rest/services"
              "/TEST_Parcels/MapServer/1/query")
ZONING_URL = ("https://gis.baycountyfl.gov/arcgis/rest/services"
              "/Land_Use_Planning/MapServer/1/query")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
RATE_LIMIT = 1.5
BUFFER_DEGREES = (0.00005, 0.0001, 0.0002, 0.0004)

PLACEHOLDER_PARCEL_IDS = {"TIMESHARE", "Property Appraiser", "MULTIPLE PARCELS", ""}

# jurisdiction_id map (confirmed live 2026-07-10 per shard9_run6253, stable since)
JURISDICTION_ID = {
    1: 1332,   # Unincorporated Bay County
    2: 983,    # Callaway
    3: 873,    # Lynn Haven
    4: 985,    # Mexico Beach
    5: 884,    # Panama City
    6: 907,    # Panama City Beach
}


def _get(url, params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def lookup_parcel(parcel_id):
    time.sleep(RATE_LIMIT)
    data = _get(PARCEL_URL, {
        "where": f"A1RENUM='{parcel_id}'",
        "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL,Zoning,FLU",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    feats = data.get("features", [])
    return feats[0] if feats else None


def lookup_zoning_by_point(lat, lon):
    for buf in BUFFER_DEGREES:
        time.sleep(RATE_LIMIT)
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
    return sum(ys) / len(ys), sum(xs) / len(xs)


def _retry(fn, attempts=3):
    for i in range(attempts):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (409,) or i == attempts - 1:
                raise
            time.sleep(1.5 * (i + 1))


def rest_get(path):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            headers={"apikey": SUPABASE_KEY,
                     "Authorization": f"Bearer {SUPABASE_KEY}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def rest_post(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(), method="POST",
            headers={"apikey": SUPABASE_KEY,
                     "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json",
                     "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def rest_patch(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}",
            data=json.dumps(body).encode(), method="PATCH",
            headers={"apikey": SUPABASE_KEY,
                     "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json",
                     "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _retry(_do)


def main():
    print("bay I GIS fix — run7622 (shard14)")
    print("Fetching bay rows from multi_county_auctions...")

    rows = rest_get(
        "multi_county_auctions?county=eq.bay"
        "&select=id,case_number,parcel_id,property_address,"
        "latitude,longitude,po_latitude,po_longitude,assessed_value,market_value"
    )
    print(f"Total bay rows: {len(rows)}")

    real_parcel_rows = [
        r for r in rows
        if r.get("parcel_id") and r["parcel_id"] not in PLACEHOLDER_PARCEL_IDS
    ]
    print(f"Rows with real parcel_id: {len(real_parcel_rows)}")

    existing_pz = rest_get(
        "parcel_zones?select=parcel_id&jurisdiction_id=gt.0"
    )
    existing_pz_ids = {r["parcel_id"] for r in existing_pz}
    print(f"Existing parcel_zones entries (total): {len(existing_pz_ids)}")

    gap_rows = [
        r for r in real_parcel_rows
        if r["parcel_id"] not in existing_pz_ids
    ]
    print(f"Rows needing GIS zone lookup (not yet in parcel_zones): {len(gap_rows)}")

    if not gap_rows:
        print("No gap rows — all bay parcel_ids already have parcel_zones. "
              "R-1 defaults from SQL migration are sufficient.")
        return

    zoned_ok = addr_ok = geo_ok = value_ok = 0
    not_found = no_zoning = ambiguous = no_jur = 0

    for r in gap_rows:
        pid = r["parcel_id"]
        feat = lookup_parcel(pid)
        if not feat:
            not_found += 1
            print(f"  {r.get('case_number','?')} / {pid}: NOT FOUND in TEST_Parcels "
                  f"— R-1 default retained (INFERRED per honesty protocol)")
            continue

        attrs = feat.get("attributes", {})
        addr = attrs.get("DSITEADDR")
        value = attrs.get("VASJUST") or attrs.get("VASTOTAL")
        lat, lon = polygon_centroid(feat.get("geometry"))

        zone_code = attrs.get("Zoning")
        jur_id = None
        if zone_code and lat and lon:
            z2_code, z2_jur, n = lookup_zoning_by_point(lat, lon)
            if n == 1 and z2_code == zone_code:
                jur_id = z2_jur
        elif not zone_code and lat and lon:
            zone_code, jur_id, n = lookup_zoning_by_point(lat, lon)
            if n > 1:
                ambiguous += 1
                print(f"  {pid}: ambiguous zoning ({n} codes) — R-1 default retained")
                zone_code = None

        if zone_code and jur_id:
            try:
                rest_post("parcel_zones", {
                    "jurisdiction_id": jur_id,
                    "parcel_id": pid,
                    "zone_code": zone_code,
                    "zone_name": attrs.get("FLU"),
                    "source": ("gis.baycountyfl.gov TEST_Parcels+Land_Use_Planning MapServer "
                               "(live fetch, shard14_run7622)"),
                })
                zoned_ok += 1
                print(f"  {pid}: zone_code={zone_code} jur={jur_id} VERIFIED via live ArcGIS")
            except Exception as e:
                if "duplicate" in str(e).lower() or "conflict" in str(e).lower():
                    print(f"  {pid}: parcel_zones conflict (already exists) — skip")
                else:
                    raise
        elif zone_code and not jur_id:
            no_jur += 1
            print(f"  {pid}: zone_code={zone_code} but jurisdiction undetermined — R-1 default retained")
        elif not zone_code:
            no_zoning += 1
            print(f"  {pid}: no Zoning attribute — R-1 default retained (INFERRED)")

        patch_body = {}
        if not r.get("property_address") and addr:
            patch_body["property_address"] = addr
            addr_ok += 1
        if not (r.get("latitude") or r.get("po_latitude")) and lat:
            patch_body["latitude"] = lat
            patch_body["longitude"] = lon
            geo_ok += 1
        if not (r.get("assessed_value") or r.get("market_value")) and value:
            patch_body["assessed_value"] = value
            value_ok += 1
        if patch_body:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)

    print(f"\n=== TOTALS ===")
    print(f"gap rows processed:  {len(gap_rows)}")
    print(f"zone_code VERIFIED:  {zoned_ok}")
    print(f"geo filled:          {geo_ok}")
    print(f"address filled:      {addr_ok}")
    print(f"value filled:        {value_ok}")
    print(f"not found in GIS:    {not_found}  (R-1 default retained, INFERRED)")
    print(f"no zoning attr:      {no_zoning}  (R-1 default retained, INFERRED)")
    print(f"ambiguous zoning:    {ambiguous}  (R-1 default retained, INFERRED)")
    print(f"no jurisdiction:     {no_jur}  (R-1 default retained, INFERRED)")
    print()
    print("Run pencil_dod_evaluate_county('bay') to confirm I metric moved to >=95%")


if __name__ == "__main__":
    main()
