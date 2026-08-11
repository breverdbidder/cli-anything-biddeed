"""
Charlotte County — Gold Standard letter I (card_complete) gap-fill.
Fetches property_address / lat-lon / assessed_value / zoning_code for
multi_county_auctions rows failing the I completeness check, from the
live Charlotte County GIS ArcGIS REST "Ownership" layer (same source
already used by prior charlotte_county_agis3_zoning_live_* sessions).

Source: https://agis3.charlottecountyfl.gov/arcgis/rest/services/Essentials/CCGISLayers/MapServer/27
Usage: python3 charlotte_i_card_completion.py  (reads gap parcel list, writes JSON results)
"""
import json
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
                "source_url": f"{BASE}?where=ACCOUNT='{acct}'",
            })
        except Exception as e:  # fail loud, don't swallow
            errors.append({"case_number": case, "parcel_id": acct, "error": str(e)})
    return {"results": results, "errors": errors}


if __name__ == "__main__":
    import sys
    with open(sys.argv[1]) as f:
        gap_rows = json.load(f)
    out = fetch_gap_parcels(gap_rows)
    print(json.dumps(out, indent=2))
