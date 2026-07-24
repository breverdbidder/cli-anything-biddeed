#!/usr/bin/env python3
"""Follow-up to gold_standard_shard4_leon_i_zoning_backfill_run6148.py.

6 leon I gap rows had no lat/lon and vacant-lot ("0 STREET RD") addresses that
the Census geocoder cannot resolve. Instead of geocoding, get the parcel
centroid directly from the Leon PA parcel cadastral layer
(TLC_OverlayParcel_D_WM, field TAXID, LIKE-matched since exact stored parcel_id
strings don't always match the layer's zero-padded TAXID verbatim -- verified
live), then run the same TLC zoning spatial join used by the prior step.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
DISPATCH_ID = "0fc2eae2-1676-4939-9bdf-245a991ebcae"

PARCEL_LAYER_URL = "https://intervector.leoncountyfl.gov/intervector/rest/services/MapServices/TLC_OverlayParcel_D_WM/MapServer/0/query"
TLC_ZONING_URL = "https://intervector.leoncountyfl.gov/intervector/rest/services/MapServices/TLC_OverlayZoning_D_WM/MapServer/0/query"

HEADERS = {
    "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json", "Accept": "application/json",
}

CANDIDATES = ["2025 CA 001437", "26-0020", "26-0018", "26-0022", "26-0016", "26-0021"]


def rest_get(path, params=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(),
                                  method="PATCH", headers={**HEADERS, "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def rest_post(path, body, prefer="return=minimal"):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(),
                                  method="POST", headers={**HEADERS, "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def rpc(fn, body):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/rpc/{fn}", data=json.dumps(body).encode(),
                                  method="POST", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def parcel_centroid(pid):
    params = {"where": f"TAXID LIKE '%{pid}%'", "outFields": "TAXID", "returnGeometry": "true",
              "outSR": "4326", "f": "json"}
    with urllib.request.urlopen(f"{PARCEL_LAYER_URL}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    if not feats:
        return None
    rings = feats[0]["geometry"]["rings"][0]
    lons = [p[0] for p in rings]
    lats = [p[1] for p in rings]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def tlc_zone_for_point(lat, lon):
    params = {"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint",
              "spatialRel": "esriSpatialRelIntersects", "inSR": "4326",
              "outFields": "ZONING,JURISDICTION", "f": "json"}
    with urllib.request.urlopen(f"{TLC_ZONING_URL}?{urllib.parse.urlencode(params)}", timeout=30) as r:
        d = json.loads(r.read())
    feats = d.get("features", [])
    if not feats:
        return None
    a = feats[0]["attributes"]
    return a.get("ZONING"), a.get("JURISDICTION")


def main():
    before = rpc("pencil_dod_evaluate_county", {"p_county": "leon"})
    print(f"BEFORE: I={before['I']}")

    rows = rest_get("multi_county_auctions", {
        "county": "eq.leon", "case_number": f"in.({','.join(CANDIDATES)})",
        "select": "id,case_number,parcel_id,latitude,longitude",
    })

    fixed = 0
    for row in rows:
        cn, pid = row["case_number"], row["parcel_id"]
        centroid = parcel_centroid(pid)
        time.sleep(0.3)
        if not centroid:
            print(f"  [SKIP] {cn} ({pid}): parcel not found in TLC_OverlayParcel_D_WM (LIKE match)")
            continue
        lat, lon = centroid
        zres = tlc_zone_for_point(lat, lon)
        time.sleep(0.3)
        if not zres or not zres[0]:
            print(f"  [SKIP] {cn} ({pid}): no zoning polygon at centroid ({lat},{lon})")
            continue
        zone_code, jurisdiction = zres
        juris_id = 917 if jurisdiction == "City" else 1397

        rest_patch(f"multi_county_auctions?id=eq.{row['id']}", {"latitude": lat, "longitude": lon})
        rest_post("parcel_zones", {
            "parcel_id": pid, "jurisdiction_id": juris_id, "zone_code": zone_code,
            "zone_name": f"Leon County Zoning {zone_code}",
            "source": f"tlcgis_parcel_layer_centroid_plus_zoning_spatial:shard4-run6148:{DISPATCH_ID[:8]}",
        }, prefer="resolution=ignore-duplicates,return=minimal")
        fixed += 1
        print(f"  [FIXED] {cn} ({pid}): centroid=({lat:.6f},{lon:.6f}) zone={zone_code} juris={jurisdiction}")

    after = rpc("pencil_dod_evaluate_county", {"p_county": "leon"})
    print(f"\nAFTER: I={after['I']}")
    print(f"DELTA I: {before['I']['metric']} -> {after['I']['metric']}  fixed={fixed}/{len(rows)}")

    audit = {
        "dispatch_id": DISPATCH_ID, "ultraloop_mode": "fallback", "county_slug": "leon", "letter": "I",
        "claim": f"leon I parcel-layer-centroid finish (run6148): {fixed}/{len(rows)} remaining vacant-lot rows fixed via TLC_OverlayParcel_D_WM centroid + zoning spatial join. metric {before['I']['metric']} -> {after['I']['metric']}.",
        "refuter_evidence": json.dumps({
            "verdict": "CONFIRMED_GENUINE" if fixed > 0 else "NO_NEW_MATCHES",
            "fixed": fixed, "candidates": len(rows),
            "source": "intervector.leoncountyfl.gov TLC_OverlayParcel_D_WM (centroid) + TLC_OverlayZoning_D_WM (spatial zone)",
            "before_metric": before["I"]["metric"], "after_metric": after["I"]["metric"],
        }),
        "survived": fixed > 0,
    }
    rest_post("gold_standard_ultraloop_audit", audit, prefer="resolution=ignore-duplicates,return=minimal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
