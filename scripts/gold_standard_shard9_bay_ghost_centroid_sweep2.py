#!/usr/bin/env python3
"""GOLD STANDARD shard-9 (bay), dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53, loop run 6253
audit-refresh follow-up, sweep 2.

The first pass (gold_standard_shard9_bay_ghost_centroid_regeocode.py) fixed the
two centroids the adversarial refuter happened to sample. A full clustering
scan of all 178 bay rows (any coordinate pair shared by >=3 rows -- real
distinct parcels essentially never coincide exactly) found 6 clusters / 30
rows total, only 2 clusters / 4 rows of which were already cleaned (those 4
already have parcel_id=NULL from sweep 1; their leftover fabricated lat/lon is
cleared here too). The remaining 4 clusters / 26 rows have real parcel_ids
that were never touched. This script re-geocodes all of them via the same
live gis.baycountyfl.gov TEST_Parcels lookup, BLANK>WRONG on any not found.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
PARCEL_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1/query"
RATE_LIMIT_SECONDS = 1.5
CLUSTER_MIN_SIZE = 3


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
        "outFields": "A1RENUM,DSITEADDR,VASJUST,VASTOTAL",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    })
    feats = data.get("features", [])
    return feats[0] if feats else None


def polygon_centroid(geometry):
    rings = (geometry or {}).get("rings")
    if not rings or not rings[0]:
        return None, None
    ring = rings[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(ys) / len(ys), sum(xs) / len(xs)


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
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                     "Range-Unit": "items", "Range": "0-999"})
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
        "multi_county_auctions?county=eq.bay&select=id,case_number,parcel_id,latitude,longitude,"
        "property_address,assessed_value,market_value")
    print(f"total bay rows fetched: {len(rows)}")

    clusters = defaultdict(list)
    for r in rows:
        if r.get("latitude") is not None and r.get("longitude") is not None:
            clusters[(r["latitude"], r["longitude"])].append(r)
    suspicious = [v for v in clusters.values() if len(v) >= CLUSTER_MIN_SIZE]
    flagged = [r for cluster in suspicious for r in cluster]
    print(f"suspicious clusters: {len(suspicious)}, flagged rows: {len(flagged)}")

    null_cleared = 0
    regeocoded = 0
    not_found = 0

    for r in flagged:
        pid = r.get("parcel_id")

        if not pid:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", {"latitude": None, "longitude": None})
            null_cleared += 1
            print(f"  {r['case_number']}: parcel_id is NULL (already cleared as garbage) -- "
                  f"clearing leftover fabricated lat/lon too")
            continue

        feat = lookup_parcel(pid)
        if not feat:
            not_found += 1
            print(f"  {r['case_number']} / {pid}: NOT FOUND in TEST_Parcels -- ghost centroid left "
                  f"in place, flagged (BLANK>WRONG: cannot fabricate a replacement)")
            continue

        attrs = feat.get("attributes", {})
        lat, lon = polygon_centroid(feat.get("geometry"))
        if lat is None or lon is None:
            not_found += 1
            print(f"  {r['case_number']} / {pid}: feature found but no geometry -- left in place")
            continue

        patch_body = {"latitude": lat, "longitude": lon}
        addr = attrs.get("DSITEADDR")
        value = attrs.get("VASJUST") or attrs.get("VASTOTAL")
        if not r.get("property_address") and addr:
            patch_body["property_address"] = addr
        if not (r.get("assessed_value") or r.get("market_value")) and value:
            patch_body["assessed_value"] = value

        rest_patch(f"multi_county_auctions?id=eq.{r['id']}", patch_body)
        regeocoded += 1
        print(f"  {r['case_number']} / {pid}: re-geocoded to ({lat:.6f},{lon:.6f})")

    print(f"\nTOTALS: flagged={len(flagged)} null_lat_lon_cleared={null_cleared} "
          f"regeocoded={regeocoded} not_found_left_in_place={not_found}")


if __name__ == "__main__":
    main()
