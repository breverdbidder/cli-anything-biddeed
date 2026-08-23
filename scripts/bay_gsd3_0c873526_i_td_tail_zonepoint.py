#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 0c873526-996a-4f5d-9123-99836d1d585f, county=bay, letter I.

Extends the proven gis.baycountyfl.gov Land_Use_Planning point-in-polygon zoning
lookup (scripts/gold_standard_shard9_bay_run6253_i_fix_pass2_zonepoint.py) to the
NEW tail of 13 bay tax_deed rows added since the 2026-08-15 shard-4 fix
(supabase/migrations/20260815_shard4_bay_c_i_10of10.sql). auctions_total grew
230 -> 246; these 13 rows already have real address/geo/value/parcel_id (all
sourced from the live RealTaxDeed AJAX harvest run this session) but have never
been linked to a zoning district, so they fail I's stricter parcel_zones
requirement even though they pass E.

Same JURISDICTION_ID map as pass2, corroborated live via jurisdictions table.
BLANK > WRONG: only writes a parcel_zones row when the point query returns a
single unambiguous ZONING code; anything else is left alone and reported.
"""
import json
import os
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ZONING_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query"
RATE = 1.5
BUFFERS = (0.00005, 0.0001, 0.0002, 0.0004)
JURISDICTION_ID = {1: 1332, 2: 983, 3: 873, 4: 985, 5: 884, 6: 907}

# (mca_id, parcel_id, lat, lon, case_number) -- pulled live from multi_county_auctions
# this session (RealTaxDeed AJAX harvest already populated address/geo/value/parcel_id
# for all 13; only zoning linkage is missing).
ROWS = [
    ("260f8b74-b853-4dee-92c7-fa3242224708", "22491-000-000", 30.156456, -85.630306, "2026-3618TD"),
    ("dbefcbb4-c9e8-4902-8304-0ef219c32b3f", "07400-200-000", 30.114827, -85.495472, "2026-1718TD"),
    ("87cddd34-d59f-4e89-917a-e0768c65a8b7", "22434-000-000", 30.153622, -85.625483, "2026-3610TD"),
    ("78cfd102-c25c-4a77-8cc5-6a22efd9511c", "24144-000-000", 30.151218, -85.62341, "2026-3856TD"),
    ("4bb1f808-896b-4a4b-86f7-dc0886eaed07", "07502-013-000", 30.408463, -85.686703, "2026-1834TD"),
    ("fe3d0a42-0eeb-46e3-9602-afafbb4de7db", "32446-100-000", 30.331658, -85.855788, "2026-4918TD"),
    ("6ad804ef-7ac7-4305-9ebc-3cf2aace35ba", "01865-000-000", 30.468279, -85.426904, "2026-0332TD"),
    ("8716fd1f-b9f8-43bf-87f8-5e8fa6e898a6", "30197-635-000", 30.173377, -85.781173, "2026-4589TD"),
    ("06f28ed5-92a0-4102-b75d-9291ec18a681", "05263-122-309", 30.311025, -85.516071, "2026-0917TD"),
    ("06f79883-d07f-4a2e-9795-edf83d85db7c", "07760-150-000", 30.3046, -85.601652, "2026-1958TD"),
    ("63052184-1ffd-4b10-bbbc-fdf904d8f73e", "23913-000-000", 30.146148, -85.611943, "2026-3821TD"),
    ("4d6f1da0-50b1-43d3-b58e-9b27642c75a3", "01118-004-000", 30.491375, -85.458878, "2026-0200TD"),
    ("1e28de6f-29ba-4eb1-a8f4-affab067728d", "17437-000-000", 30.169362, -85.649315, "2026-3267TD"),
]


def _get(url, params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def lookup_zoning_by_point(lat, lon):
    for buf in BUFFERS:
        time.sleep(RATE)
        env = f"{lon - buf},{lat - buf},{lon + buf},{lat + buf}"
        data = _get(ZONING_URL, {
            "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false", "f": "json",
        })
        feats = data.get("features", [])
        if not feats:
            continue
        codes = {f["attributes"].get("ZONING") for f in feats}
        subs = {f["attributes"].get("SUB_ZONING") for f in feats}
        if len(codes) != 1:
            return None, None, len(codes), next(iter({f['attributes'].get('Label') for f in feats}))
        zone_code = next(iter(codes))
        jur_id = JURISDICTION_ID.get(next(iter(subs))) if len(subs) == 1 else None
        return zone_code, jur_id, 1, next(iter({f['attributes'].get('Label') for f in feats}))
    return None, None, 0, None


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    zoned = 0
    for mca_id, pid, lat, lon, cn in ROWS:
        zone_code, jur_id, n, label = lookup_zoning_by_point(lat, lon)
        if n != 1 or not zone_code or not jur_id:
            print(f"  {cn} {pid}: SKIP n={n} zone_code={zone_code} jur_id={jur_id} label={label} -- left alone (BLANK>WRONG)")
            continue
        existing = rest_get(f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if existing:
            print(f"  {cn} {pid}: parcel_zones row already exists, skip insert")
            continue
        rest_post("parcel_zones", {
            "jurisdiction_id": jur_id, "parcel_id": pid, "zone_code": zone_code,
            "zone_name": label,
            "source": "gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, "
                       "gold-standard-shard3 dispatch 0c873526, bay I tax_deed tail)",
        })
        zoned += 1
        print(f"  {cn} {pid}: zoned {zone_code} (jur={jur_id})")
    print(f"\nTOTAL zoned={zoned} of {len(ROWS)}")


if __name__ == "__main__":
    main()
