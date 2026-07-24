#!/usr/bin/env python3
"""Bay I-fix pass 2: for rows with existing lat/lon but no zone_code (parcel_zones),
do a point-in-polygon zoning lookup via the Bay County Land_Use_Planning layer.
Reuses the exact endpoint/logic proven in scripts/gold_standard_shard9_bay_run6253_i_fix.py.
BLANK > WRONG: only writes when a single unambiguous zoning code is found.
"""
import json, os, sys, time, urllib.parse, urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ZONING_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query"
RATE = 1.5
BUFFERS = (0.00005, 0.0001, 0.0002, 0.0004)
JURISDICTION_ID = {1: 1332, 2: 983, 3: 873, 4: 985, 5: 884, 6: 907}

ROWS = [
    ("06d9a5f7-e932-4957-ac95-51c707c216ab", "30374-000-000", 30.1647798, -85.785722),
    ("0990beb9-94f6-49b7-a399-c82195091712", "23854-020-000", 30.1588, -85.6602),
    ("0c97eb70-4f7e-4eea-9678-833f25a32f1c", "30184-590-000", 30.1759943, -85.7752538),
    ("1bc094c8-09ee-483d-8521-acb7b0defc2a", "23796-000-000", 30.1523513391104, -85.6194392536308),
    ("3c7335a4-5d35-43d1-a039-5e779eef31a7", "23824-000-000", 30.1513976966131, -85.6174824507468),
    ("431533e1-1fcf-44b4-bc35-988fba2ecb96", "38335-396-311", 30.2317894, -85.9005799),
    ("4cc0fd6a-f17f-4ec9-acc0-7c9e4c27e588", "15026-010-000", 30.167345563802, -85.5959967803767),
    ("538bcb5d-8cb2-417a-b435-f893f7744487", "40001-100-107", 30.1843199, -85.7842197),
    ("5e703436-4b66-4b96-9bf9-4ec17fbd5384", "34511-509-000", 30.2032137, -85.85469),
    ("7ec71211-2c9a-41bc-b595-2c4ec521a153", "34801-302-000", 30.1900315, -85.8215797),
    ("94dc4d1e-891a-431e-b492-3682fab9b45e", "30484-238-000", 30.16109, -85.7815494),
    ("b5ba939a-db50-45a3-be7b-09a2c0628d3c", "21315-000-000", 30.1468401, -85.6426141),
    ("bb661cb0-6f9d-4891-b0fc-e65df340b049", "24180-001-000", 30.1465236429688, -85.6210157502043),
    ("e86f4541-2e8c-4110-b29f-cb6771671e5c", "10589-000-000", 30.2357319, -85.6407612),
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
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def main():
    zoned = 0
    for mca_id, pid, lat, lon in ROWS:
        zone_code, jur_id, n, label = lookup_zoning_by_point(lat, lon)
        if n != 1 or not zone_code or not jur_id:
            print(f"  {pid}: SKIP n={n} zone_code={zone_code} jur_id={jur_id} label={label} -- left alone (BLANK>WRONG)")
            continue
        existing = rest_get(f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if existing:
            print(f"  {pid}: parcel_zones row already exists, skip insert")
            continue
        rest_post("parcel_zones", {
            "jurisdiction_id": jur_id, "parcel_id": pid, "zone_code": zone_code,
            "zone_name": label,
            "source": "gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, shard9_run6253 pass2)",
        })
        zoned += 1
        print(f"  {pid}: zoned {zone_code} (jur={jur_id})")
    print(f"\nTOTAL zoned={zoned} of {len(ROWS)}")

if __name__ == "__main__":
    main()
