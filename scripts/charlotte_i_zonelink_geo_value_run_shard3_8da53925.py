"""
Charlotte County — Gold Standard shard-3 (dispatch 8da53925) letter I gap-fill.

63 rows in the I-gap list, mostly missing zone_link only (parcel_id known,
never linked to parcel_zones). A smaller subset also missing geo/value/addr.
Fetches property_address / lat-lon / assessed_value / zoning_code from the
live Charlotte County GIS ArcGIS REST "Ownership" layer 27 (same source used
by prior charlotte_county_agis3_zoning_live_* sessions, e.g. commit 66bd8c06,
5adb6163, 20260808_gold_standard_charlotte_i_zone_link_and_geocode.sql).

Source: https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27
Usage: python3 charlotte_i_zonelink_geo_value_run_shard3_8da53925.py <gap.json> <out.json>
"""
import json
import sys
import urllib.parse
import urllib.request

BASE = "https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27/query"


def fetch(account: str) -> dict:
    params = {
        "where": f"ACCOUNT='{account}'",
        "outFields": "ACCOUNT,FullPropertyAddress,zoningcode,assessedvalue,totvalue",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.load(resp)


def centroid(rings):
    ring = rings[0]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(ys) / len(ys), sum(xs) / len(xs)  # lat, lon


def fetch_gap_parcels(gap_rows: list) -> dict:
    results, errors = [], []
    for r in gap_rows:
        acct = r["parcel_id"]
        case = r["case_number"]
        if not acct or acct == "MULTIPLE PARCELS":
            errors.append({"case_number": case, "parcel_id": acct, "error": "no_single_parcel_id"})
            continue
        try:
            d = fetch(acct)
            feats = d.get("features", [])
            if not feats:
                errors.append({"case_number": case, "parcel_id": acct, "error": "no_feature_found"})
                continue
            attrs = feats[0]["attributes"]
            geom = feats[0].get("geometry")
            lat = lon = None
            if geom and geom.get("rings"):
                lat, lon = centroid(geom["rings"])
            addr = " ".join((attrs.get("FullPropertyAddress") or "").split()) or None
            zoning = (attrs.get("zoningcode") or "").strip() or None
            assessed = attrs.get("assessedvalue")
            totval = attrs.get("totvalue")
            assessed_f = float(assessed.strip()) if assessed and assessed.strip() else None
            totval_f = float(totval.strip()) if totval and totval.strip() else None
            results.append({
                "case_number": case, "parcel_id": acct, "address": addr,
                "lat": lat, "lon": lon, "zoning": zoning,
                "assessed": assessed_f, "market": totval_f,
                "missing": r.get("missing", []),
                "source_url": f"{BASE}?where=ACCOUNT='{acct}'",
            })
        except Exception as e:  # fail loud, don't swallow
            errors.append({"case_number": case, "parcel_id": acct, "error": str(e)})
    return {"results": results, "errors": errors}


if __name__ == "__main__":
    with open(sys.argv[1]) as f:
        gap_rows = json.load(f)
    out = fetch_gap_parcels(gap_rows)
    with open(sys.argv[2], "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps({"results": len(out["results"]), "errors": len(out["errors"])}))
