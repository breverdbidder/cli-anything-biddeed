#!/usr/bin/env python3
"""GOLD STANDARD shard-9 (bay), dispatch 0c4df455-e5d2-4d65-9237-0d35132b0e53, loop run 6253
audit-refresh follow-up.

Adversarial ULTRALOOP verification of letter E found 53 bay rows sharing two
fabricated fallback centroids (30.1766,-85.6801 x12 incl. 2 'TIMESHARE'/
'Property Appraiser' placeholders; 30.1588,-85.6602 x41 with 41 DISTINCT real
Bay parcel numbers) -- a single hardcoded coordinate reused across genuinely
different parcels, not real per-parcel geocoding. Root cause of how the
fallback got written is not identified; this script repairs it going forward
using the proven live gis.baycountyfl.gov TEST_Parcels pattern (see
scripts/gold_standard_shard9_bay_run6253_i_fix.py), the difference being this
one UNCONDITIONALLY overwrites lat/lon for the specific flagged rows (the
prior script only fills NULLs, so it never touched these already-fabricated
values) and clears the 2 known-garbage parcel_id placeholder strings.

BLANK > WRONG: rows TEST_Parcels has no answer for keep their existing
(fabricated) value untouched but are reported, never silently left claiming
success.
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
PARCEL_URL = "https://gis.baycountyfl.gov/arcgis/rest/services/TEST_Parcels/MapServer/1/query"
RATE_LIMIT_SECONDS = 1.5

GARBAGE_PARCEL_IDS = {"TIMESHARE", "Property Appraiser"}
GHOST_CENTROIDS = {(30.1766, -85.6801), (30.1588, -85.6602)}


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
    flagged = [r for r in rows if (r.get("latitude"), r.get("longitude")) in GHOST_CENTROIDS]
    print(f"flagged rows (ghost centroid): {len(flagged)}")

    cleared_garbage = 0
    regeocoded = 0
    not_found = 0

    for r in flagged:
        pid = r.get("parcel_id")

        if pid in GARBAGE_PARCEL_IDS:
            rest_patch(f"multi_county_auctions?id=eq.{r['id']}", {"parcel_id": None})
            cleared_garbage += 1
            print(f"  {r['case_number']}: parcel_id={pid!r} -- garbage placeholder, cleared to NULL "
                  f"(not a real parcel identifier, per established fleet pattern)")
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
        print(f"  {r['case_number']} / {pid}: re-geocoded to ({lat:.6f},{lon:.6f}) via live "
              f"TEST_Parcels lookup")

    print(f"\nTOTALS: flagged={len(flagged)} cleared_garbage_parcel_id={cleared_garbage} "
          f"regeocoded={regeocoded} not_found_left_in_place={not_found}")


if __name__ == "__main__":
    main()
