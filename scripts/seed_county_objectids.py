#!/usr/bin/env python3
"""
seed_county_objectids.py
For each pending FL county with last_parcel_id=0/None, find the first OBJECTID
in the FL Statewide Cadastral FeatureServer and seed last_parcel_id accordingly.

Problem: ArcGIS returns 400 when a query must scan >~2M records before finding
county data (e.g. CO_NO=60 AND OBJECTID>0 scans 7.1M records → 400 error).
Fix: find the correct starting OBJECTID for each county and pre-seed it.
"""
import os, json, time, urllib.request, urllib.parse, sys

BASE = (
    "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest"
    "/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
)
SB  = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
assert KEY, "SUPABASE_SERVICE_KEY required"

HEADERS = {
    "apikey":        KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type":  "application/json",
}

# Probe points (OBJECTID values): try each until we get features for this CO_NO
# Ordered from low to high so we find the min OBJECTID efficiently
PROBES = [
    0, 100_000, 200_000, 300_000, 500_000, 700_000,
    1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000,
    3_500_000, 4_000_000, 4_500_000, 5_000_000, 5_500_000,
    5_700_000, 5_900_000, 6_100_000, 6_200_000, 6_300_000,
    6_400_000, 6_500_000, 6_700_000, 6_900_000, 7_000_000,
    7_100_000, 7_200_000, 7_400_000, 7_600_000, 7_800_000,
    7_900_000, 8_000_000, 8_200_000, 8_400_000, 8_600_000,
    8_800_000, 9_000_000, 9_200_000, 9_400_000, 9_600_000,
    9_800_000, 10_000_000, 10_200_000, 10_400_000, 10_600_000,
    10_800_000,
]


def arcgis_get(params, tries=4):
    url = f"{BASE}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "everest-seed/1"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
                try:
                    return json.loads(raw.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    time.sleep(5)
                    continue
        except Exception:
            time.sleep(3 * (i + 1))
    return {"error": {"code": -1, "message": "all retries failed"}}


def find_first_objectid(co_no):
    """Return the OBJECTID just before the first record of this county, or None."""
    # Phase 1: find the probe window where records appear
    found_probe = None
    prev_probe = 0

    for probe in PROBES:
        params = {
            "where": f"CO_NO={co_no} AND OBJECTID>{probe}",
            "outFields": "OBJECTID",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 1,
            "orderByFields": "OBJECTID",
        }
        data = arcgis_get(params)
        if data.get("error"):
            # 400 = scan too large OR no data; skip to next probe
            prev_probe = probe
            time.sleep(0.5)
            continue
        feats = data.get("features", [])
        if feats:
            found_probe = probe
            break
        # No features + no error = past county's range; try next (shouldn't happen here)
        prev_probe = probe
        time.sleep(0.5)

    if found_probe is None:
        return None  # county not found

    first_oid = found_probe["features"][0]["attributes"]["OBJECTID"] if False else (
        data["features"][0]["attributes"]["OBJECTID"]
    )

    # Phase 2: binary search between prev_probe and found_probe
    # Find the minimum probe value from which the query works (no 400)
    lo = prev_probe
    hi = found_probe  # this probe WORKS, try to find a lower one

    while hi - lo > 50_000:
        mid = (lo + hi) // 2
        params = {
            "where": f"CO_NO={co_no} AND OBJECTID>{mid}",
            "outFields": "OBJECTID",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 1,
            "orderByFields": "OBJECTID",
        }
        data = arcgis_get(params)
        if data.get("error"):
            lo = mid  # scan too large at mid, need higher start
            time.sleep(0.5)
        elif data.get("features"):
            hi = mid  # works at mid, try even lower
            time.sleep(0.5)
        else:
            lo = mid  # no data at this mid, push higher
            time.sleep(0.5)

    # hi is the lowest probe that works (no 400 error)
    # Use hi as the last_parcel_id so script starts from OBJECTID>hi
    return hi


def get_pending_counties():
    url = f"{SB}/rest/v1/fl_parcel_centroid_progress?status=eq.pending&order=co_no"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def seed_county(co_no, start_oid):
    import urllib.request
    body = json.dumps({"last_parcel_id": str(start_oid)}).encode()
    req = urllib.request.Request(
        f"{SB}/rest/v1/fl_parcel_centroid_progress?co_no=eq.{co_no}&status=eq.pending",
        data=body,
        method="PATCH",
    )
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header("Prefer", "return=minimal")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def main():
    counties = get_pending_counties()
    # Only seed counties with no progress (last_parcel_id = 0 or None)
    to_seed = [c for c in counties if not c.get("last_parcel_id") or
               str(c.get("last_parcel_id", "0")) in ("0", "None", "")]
    print(f"Counties to seed: {len(to_seed)}", flush=True)

    for c in to_seed:
        co_no = c["co_no"]
        name = c["county_name"]
        print(f"  co_no={co_no:3d} {name:20s} ... ", end="", flush=True)

        # First check: can OBJECTID>0 work? (quick probe)
        quick = arcgis_get({
            "where": f"CO_NO={co_no} AND OBJECTID>0",
            "outFields": "OBJECTID",
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": 1,
            "orderByFields": "OBJECTID",
        })
        if not quick.get("error") and quick.get("features"):
            print(f"OBJECTID>0 works → skip seeding", flush=True)
            continue
        if not quick.get("error") and not quick.get("features"):
            print(f"NO DATA FOUND for this county!", flush=True)
            continue

        # 400 error: find the correct starting OBJECTID
        print(f"needs seeding ... ", end="", flush=True)
        start = find_first_objectid(co_no)
        if start is None:
            print(f"FAILED to find OBJECTID", flush=True)
            continue

        seed_county(co_no, start)
        print(f"seeded last_parcel_id={start}", flush=True)
        time.sleep(0.3)

    print("Done.", flush=True)


if __name__ == "__main__":
    main()
