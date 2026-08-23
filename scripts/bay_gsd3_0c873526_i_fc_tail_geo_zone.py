#!/usr/bin/env python3
"""Gold Standard shard-3, dispatch 0c873526-996a-4f5d-9123-99836d1d585f, county=bay, letter I.

Part 2 of the FC-tail fix: after bay_gsd3_0c873526_i_fc_tail_ajax_backfill.py wrote
real parcel_id/property_address/assessed_value for 7 bay foreclosure rows from the
live RealForeclose AJAX calendar, this script:
  1. geocodes each real property_address via the free US Census geocoder
     (geocoding.geo.census.gov, same proven method as scripts/shard14_bay_geocode_
     backfill.py) -- writes lat/lon ONLY on an exact single-match response.
  2. does a live gis.baycountyfl.gov Land_Use_Planning point-in-polygon zoning
     lookup at the geocoded centroid (same proven method as scripts/gold_standard_
     shard9_bay_run6253_i_fix_pass2_zonepoint.py) and inserts a parcel_zones row.

One parcel (25001056CA, PKR sub-zoning label "See FLU(PKR)") maps to a
SUB_ZONING code not in the previously-known JURISDICTION_ID table
{1:1332 Unincorporated, 2:983 Callaway, 3:873 Lynn Haven, 4:985 Mexico Beach,
5:884 Panama City, 6:907 Panama City Beach}. Corroborated live: jurisdictions
table has an existing row id=1588 name='Parker', and 'PKR' is an unambiguous
abbreviation of Parker matching the ArcGIS Label field convention seen for every
other jurisdiction in this county (CAL=Callaway, BC=Bay County unincorporated,
SPR=Springfield -- all previously verified). Treated as real corroboration, not
a guess, consistent with the Springfield/SUB_ZONING=8 precedent from the
2026-08-15 shard-4 fix.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
CENSUS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
ZONING_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/Land_Use_Planning/MapServer/1/query"
BUFFERS = (0.00005, 0.0001, 0.0002, 0.0004)
JURISDICTION_ID = {1: 1332, 2: 983, 3: 873, 4: 985, 5: 884, 6: 907}

# (mca_id, case_number, parcel_id, address_for_geocode)
ROWS = [
    ("533efc1e-46e5-41c5-ba7f-830043572346", "25001240CA", "06177-000-000",
     "6123 CHERRY ST, PANAMA CITY, FL 32404"),
    ("008b8f71-fcd9-4f76-8190-c2c70d8f7c00", "24001056CA", "07585-262-020",
     "3919 CEDAR BLUFF RD, SOUTHPORT, FL 32409"),
    ("a7d27aa5-dc40-463b-8bdc-69048f594d78", "26000160CA", "31232-000-000",
     "4600 MAGNOLIA BEACH RD, PANAMA CITY BEACH, FL 32408"),
    ("6bc3cdf6-7ecb-4290-b154-aaaae85260a8", "25001319CA", "06701-176-000",
     "1045 TIDEWATER LN, PANAMA CITY, FL 32404"),
    ("ce85abd7-17d2-4366-a94a-37b829ee3aa1", "25001056CA", "26275-000-000",
     "29 ALMA AVE, PANAMA CITY, FL 32404"),
    ("aff7ac61-70fc-4efb-a8ca-c25ccbf92ca9", "26000281CA", "03834-085-000",
     "8801 TOWER RD, PANAMA CITY, FL 32404"),
    ("f77411d8-0fde-4bff-8d6d-64f41b99ab9d", "26000084CA", "31402-222-000",
     "104 GOLF DR, PANAMA CITY BEACH, FL 32408"),
]

# Corroborated live: SUB_ZONING for 'See FLU(PKR)' -> jurisdictions.id 1588 (Parker)
JURISDICTION_ID_EXTRA_LABEL_MAP = {"PKR": 1588}


def geocode(address):
    params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    url = f"{CENSUS_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "biddeed-gold-standard/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    matches = data.get("result", {}).get("addressMatches", [])
    if len(matches) != 1:
        return None, f"{len(matches)}_matches"
    m = matches[0]
    coords = m.get("coordinates", {})
    lat, lon = coords.get("y"), coords.get("x")
    if lat is None or lon is None:
        return None, "no_coordinates"
    return (lat, lon), "exact_unique"


def lookup_zoning_by_point(lat, lon):
    for buf in BUFFERS:
        time.sleep(1.0)
        env = f"{lon - buf},{lat - buf},{lon + buf},{lat + buf}"
        params = {
            "geometry": env, "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects", "outFields": "ZONING,SUB_ZONING,Label",
            "returnGeometry": "false", "f": "json",
        }
        req = urllib.request.Request(f"{ZONING_URL}?{urllib.parse.urlencode(params)}", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        feats = data.get("features", [])
        if not feats:
            continue
        codes = {f["attributes"].get("ZONING") for f in feats}
        subs = {f["attributes"].get("SUB_ZONING") for f in feats}
        label = next(iter({f["attributes"].get("Label") for f in feats}))
        if len(codes) != 1:
            return None, None, len(codes), label
        zone_code = next(iter(codes))
        jur_id = JURISDICTION_ID.get(next(iter(subs))) if len(subs) == 1 else None
        if jur_id is None and label:
            # extract parenthesized abbreviation, e.g. "See FLU(PKR)" -> "PKR"
            if "(" in label and label.endswith(")"):
                abbrev = label[label.index("(") + 1:-1]
                jur_id = JURISDICTION_ID_EXTRA_LABEL_MAP.get(abbrev)
        return zone_code, jur_id, 1, label
    return None, None, 0, None


def _with_retry(fn, attempts=4):
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
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                      headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
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


def rest_post(path, body):
    def _do():
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Content-Type": "application/json", "Prefer": "return=representation"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    return _with_retry(_do)


def main():
    geocoded = 0
    zoned = 0
    for mca_id, cn, pid, addr in ROWS:
        coords, status = geocode(addr)
        if not coords:
            print(f"  {cn}: geocode FAILED ({status}) -- left NULL")
            continue
        lat, lon = coords
        result = rest_patch(f"multi_county_auctions?id=eq.{mca_id}", {"latitude": lat, "longitude": lon})
        if not result:
            print(f"  {cn}: PATCH lat/lon returned 0 rows -- FAIL LOUD")
            continue
        geocoded += 1
        print(f"  {cn}: geocoded lat={lat} lon={lon}")

        zone_code, jur_id, n, label = lookup_zoning_by_point(lat, lon)
        if n != 1 or not zone_code or not jur_id:
            print(f"    {cn} zoning: SKIP n={n} zone_code={zone_code} jur_id={jur_id} label={label} -- left alone (BLANK>WRONG)")
            continue
        existing = rest_get(f"parcel_zones?jurisdiction_id=eq.{jur_id}&parcel_id=eq.{urllib.parse.quote(pid)}&select=id")
        if existing:
            print(f"    {cn} zoning: parcel_zones row already exists, skip insert")
            continue
        rest_post("parcel_zones", {
            "jurisdiction_id": jur_id, "parcel_id": pid, "zone_code": zone_code,
            "zone_name": label,
            "source": "gis.baycountyfl.gov Land_Use_Planning MapServer point lookup (live fetch, "
                       "gold-standard-shard3 dispatch 0c873526, bay I foreclosure tail; centroid from "
                       "Census geocoder onelineaddress exact match)",
        })
        zoned += 1
        print(f"    {cn} zoning: zoned {zone_code} (jur={jur_id}, label={label})")

    print(f"\nTOTAL geocoded={geocoded} of {len(ROWS)}, zoned={zoned} of {len(ROWS)}")


if __name__ == "__main__":
    main()
