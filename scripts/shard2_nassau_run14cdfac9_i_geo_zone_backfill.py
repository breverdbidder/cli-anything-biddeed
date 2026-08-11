#!/usr/bin/env python3
"""Gold Standard shard-2 (dispatch 14cdfac9, nassau): I-criterion geo+zone backfill.

The 9 nassau tax_deed rows just enrolled via the E-criterion RealAuction
backfill (26TD000009..018AXYX) have parcel_id but no lat/lon and no zoning
link, both required by v_zoning_gold_standard_card / pencil_dod I criterion.
Reuses the proven Nassau County PA ArcGIS layer (maps.ncpafl.com, field PIN --
see scripts/architect_triage_17241_nassau_cdi_pin_field_fix.py for the correct
field-name discovery) with returnGeometry=true to get both a real polygon
centroid (lat/lon) and the ZoningDistrict attribute in one query. Idempotent:
SELECT-before-INSERT on parcel_zones, PATCH only NULL lat/lon fields.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
H = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
     "Content-Type": "application/json", "Prefer": "return=representation"}

NASSAU_PA_ARCGIS = ("https://maps.ncpafl.com/ncflpa_arcgis/rest/services/nassau/"
                     "TaxMap4_CitrixV2/MapServer/144/query")

JURISDICTION_ID = {
    "fernandina beach": 865,
    "city of fernandina beach": 865,
    "callahan": 1066,
    "town of callahan": 1066,
    "hilliard": 1067,
    "town of hilliard": 1067,
    "unincorporated nassau county": 1508,
}

TARGET_CASES = [
    "26TD000009AXYX", "26TD000011AXYX", "26TD000012AXYX", "26TD000013AXYX",
    "26TD000014AXYX", "26TD000015AXYX", "26TD000016AXYX", "26TD000017AXYX",
    "26TD000018AXYX",
]


def sb_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read())


def sb_patch(path, body):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(),
                                  method="PATCH", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def sb_post(path, body):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(),
                                  method="POST", headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def query_pa(pin):
    params = {
        "where": f"UPPER(PIN) = UPPER('{pin}')",
        "outFields": "PIN,ZoningDistrict,Municipality,HOUSE_NO,STREET,ST_CITY,ST_ZIP5",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = NASSAU_PA_ARCGIS + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    feats = data.get("features", [])
    return feats[0] if feats else None


def centroid(geometry):
    rings = (geometry or {}).get("rings")
    if not rings or not rings[0]:
        return None, None
    ring = rings[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(ys) / len(ys), sum(xs) / len(xs)


def main():
    cases = ",".join(f'"{c}"' for c in TARGET_CASES)
    rows = sb_get(f"multi_county_auctions?county=eq.nassau&case_number=in.({cases})"
                   "&select=id,case_number,parcel_id,latitude,longitude")
    print(f"rows fetched: {len(rows)}")

    geo_ok = zone_ok = not_found = no_zone_attr = no_jur = 0
    for r in rows:
        pid = r["parcel_id"]
        feat = query_pa(pid)
        time.sleep(0.5)
        if not feat:
            not_found += 1
            print(f"  {r['case_number']}: NOT FOUND for PIN={pid}")
            continue
        attrs = feat.get("attributes", {})
        lat, lon = centroid(feat.get("geometry"))
        zone = attrs.get("ZoningDistrict")
        muni = (attrs.get("Municipality") or "").strip().lower()
        jur_id = JURISDICTION_ID.get(muni)

        patch = {}
        if lat and lon and not (r.get("latitude") and r.get("longitude")):
            patch["latitude"] = lat
            patch["longitude"] = lon
            geo_ok += 1
        if patch:
            sb_patch(f"multi_county_auctions?id=eq.{r['id']}", patch)

        if not zone:
            no_zone_attr += 1
            print(f"  {r['case_number']}: no ZoningDistrict attribute (muni={muni})")
            continue
        if not jur_id:
            no_jur += 1
            print(f"  {r['case_number']}: zone={zone} but unmapped municipality '{muni}'")
            continue

        existing = sb_get(f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if not existing:
            sb_post("parcel_zones", {
                "jurisdiction_id": jur_id,
                "parcel_id": pid,
                "zone_code": zone,
                "source": "shard2_run14cdfac9_nassau_ncpa_arcgis_land_parcels_144",
            })
            zone_ok += 1
        print(f"  {r['case_number']}: PIN={pid} zone={zone} muni={muni} lat={lat} lon={lon}")

    print(f"\nTOTALS: geo_backfilled={geo_ok} zone_backfilled={zone_ok} "
          f"not_found={not_found} no_zone_attr={no_zone_attr} no_jurisdiction={no_jur}")


if __name__ == "__main__":
    main()
