#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 6ef79515-debe-4deb-b162-442a677def37, county=bay, letter I.

Extends the proven gis.baycountyfl.gov Land_Use_Planning point-in-polygon zoning
lookup (scripts/bay_gsd3_0c873526_i_td_tail_zonepoint.py) to the 20 bay tax_deed
rows for the 2026-10-20 sale. These rows just had parity_status/property_address/
assessed_value backfilled this session via scripts/shard9_run6046_bay_cd_future_
harvest.py (fixed C 91.2%->98.5%, D 92.7%->100%); parcel_id/lat/lon were already
populated from an earlier FL GIO ingestion. Only zoning linkage (parcel_zones) is
missing, which is why they still fail I's stricter card-completeness requirement
even though they now pass E.

Same JURISDICTION_ID map as the proven prior runs, corroborated live via the
jurisdictions table. BLANK > WRONG: only writes a parcel_zones row when the point
query returns a single unambiguous ZONING code; anything else is left alone and
reported.
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

# (mca_id, parcel_id, lat, lon, case_number) -- live from multi_county_auctions
# this session (2026-10-20 tax_deed RealTaxDeed AJAX harvest already populated
# address/geo/value/parcel_id; only zoning linkage is missing).
ROWS = [
    ("44d400cf-db69-482d-bcc2-60a190926599", "00068-000-000", 30.51904, -85.407764, "2026-0015TD"),
    ("78f0afaa-db8f-4d51-b54b-5b5eaff09e68", "00183-000-000", 30.5178, -85.4071, "2026-0037TD"),
    ("bfd4b01c-88ab-4d03-bfc1-98c45fbe1fc3", "0024-000-000", 30.510251, -85.414031, "2026-0045TD"),
    ("3fe151b4-cfc5-4b2c-b66e-60ed304006de", "00350-010-000", 30.51047, -85.434999, "2026-0080TD"),
    ("b4575161-4e73-4a67-8808-186cc76944ed", "00771-000-000", 30.490641, -85.401085, "2026-0142TD"),
    ("8b461eac-501e-4b68-83b5-b5a203017415", "00778-000-000", 30.488767, -85.401159, "2026-0144TD"),
    ("8f426eef-69fe-4226-badd-7d6f4cecf40f", "00991-000-000", 30.491469, -85.43656, "2026-0176TD"),
    ("d3002d48-55f3-4f4d-971c-925f39505582", "03099-000-000", 30.549219, -85.402268, "2026-0553TD"),
    ("072f58c0-380e-4792-a28e-a436a3819d3b", "05264-010-028", 30.315352, -85.527542, "2026-0921TD"),
    ("42035082-bf30-4770-b2c0-387d6293b2c3", "05288-506-000", 30.310645, -85.548244, "2026-0993TD"),
    ("06e52ad9-638a-4b7b-9426-c8adfb75e5c2", "05288-602-000", 30.311406, -85.548877, "2026-0997TD"),
    ("a8f6bae5-a869-4d41-a854-6d331d6b160a", "05288-650-000", 30.311731, -85.547705, "2026-1006TD"),
    ("9089a122-05f3-4078-b392-1bef01544977", "06130-000-000", 30.148934, -85.578869, "2026-1357TD"),
    ("8723291d-bef9-4d7c-ba03-c59892f4a0ed", "06701-254-000", 30.129047, -85.535439, "2026-1499TD"),
    ("2b4da6e9-8bcf-423c-8700-00582742c5ab", "06940-700-000", 30.131375, -85.579282, "2026-1548TD"),
    ("a770dc71-6798-479d-a45e-efaac810368c", "07264-000-000", 30.119056, -85.575252, "2026-1609TD"),
    ("36d10f4c-b544-4238-a64e-875a1d5f6842", "07284-010-000", 30.127352, -85.5677, "2026-1612TD"),
    ("f9027d68-c8a3-48d0-9845-a30774239175", "07464-013-165", 30.411564, -85.686153, "2026-1806TD"),
    ("91743b48-a13a-40b6-8183-06ccab16be95", "16809-040-000", 30.17269, -85.646593, "2026-3153TD"),
    ("f318958f-b6e9-4156-881b-67a8ba417782", "30561-040-000", 30.141463, -85.755187, "2026-4540TD"),
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
                       "gold-standard-shard3 dispatch 6ef79515, bay I 2026-10-20 tax_deed tail)",
        })
        zoned += 1
        print(f"  {cn} {pid}: zoned {zone_code} (jur={jur_id})")
    print(f"\nTOTAL zoned={zoned} of {len(ROWS)}")


if __name__ == "__main__":
    main()
