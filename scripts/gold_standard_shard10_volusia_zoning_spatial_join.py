#!/usr/bin/env python3
"""Volusia G/I fix: spatial join of gold-standard auction parcels to real Volusia
County GIS zoning polygons (maps1.vcgov.org CountywideZoning MapServer).

Step 1 (this script): pull real parcel geometry (layer 0, PID field == our
12-digit parcel_id), compute a true polygon centroid (shoelace method, no
guessing), point-in-polygon query against layer 2 (Countywide Zoning) to get
the REAL zone code per parcel. Writes results to /tmp/volusia_parcel_zones.json
for the next step to insert into parcel_zones. No fabricated data -- every
zone code traces to a live GIS query captured in the output file.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "https://maps1.vcgov.org/arcgis/rest/services/CountywideZoning/MapServer"


def arcgis_get(path, params):
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == 5:
                print(f"GIVEUP {path}: {e}", file=sys.stderr)
                return {}
            time.sleep(3)


def ring_centroid(ring):
    # standard polygon centroid (shoelace), exterior ring only
    a = 0.0
    cx = 0.0
    cy = 0.0
    n = len(ring)
    for i in range(n - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        a += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    a *= 0.5
    if abs(a) < 1e-9:
        # degenerate ring, fall back to vertex average
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx /= (6 * a)
    cy /= (6 * a)
    return cx, cy


def largest_ring(rings):
    def area(ring):
        a = 0.0
        for i in range(len(ring) - 1):
            x0, y0 = ring[i]
            x1, y1 = ring[i + 1]
            a += x0 * y1 - x1 * y0
        return abs(a) / 2
    return max(rings, key=area)


OUT_PATH = "/tmp/volusia_parcel_zones.json"


def save(out, misses, pids):
    result = {"zoned": out, "misses": misses,
              "pids_not_found_in_gis": [p for p in pids if p not in out and p not in misses]}
    json.dump(result, open(OUT_PATH, "w"), indent=2)


def main():
    pids = json.load(open(sys.argv[1]))  # list of parcel_id strings
    out = {}
    misses = []
    if len(sys.argv) > 2 and sys.argv[2] == "--resume" and __import__("os").path.exists(OUT_PATH):
        prior = json.load(open(OUT_PATH))
        out = prior.get("zoned", {})
        misses = prior.get("misses", [])
        pids = [p for p in pids if p not in out and p not in misses]
        print(f"RESUME: {len(out)} already zoned, {len(misses)} misses, {len(pids)} remaining", file=sys.stderr)
    CHUNK = 25
    for i in range(0, len(pids), CHUNK):
        chunk = pids[i:i + CHUNK]
        where = " OR ".join(f"PID='{p}'" for p in chunk)
        data = arcgis_get("0/query", {
            "where": where,
            "outFields": "PID,CITYNAME,ADDRFULL",
            "returnGeometry": "true",
            "f": "json",
        })
        for feat in data.get("features", []):
            pid = feat["attributes"]["PID"]
            rings = feat.get("geometry", {}).get("rings")
            if not rings:
                continue
            ring = largest_ring(rings)
            cx, cy = ring_centroid(ring)
            zdata = arcgis_get("2/query", {
                "geometry": f"{cx},{cy}",
                "geometryType": "esriGeometryPoint",
                "inSR": "2881",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "OriginalZoningCode,GenericZoningCode,GenericDescription,JurisdictionCode,JURISD,Z_DESCRIP,GENL_ZCODE,JUR_ZONING,CityName",
                "returnGeometry": "false",
                "f": "json",
            })
            zfeats = zdata.get("features", [])
            if zfeats:
                out[pid] = zfeats[0]["attributes"]
                out[pid]["_centroid"] = [cx, cy]
                out[pid]["_appraiser_city"] = feat["attributes"].get("CITYNAME")
            else:
                misses.append(pid)
        save(out, misses, pids)
        print(f"processed {min(i+CHUNK,len(pids))}/{len(pids)} pids, "
              f"{len(out)} zoned, {len(misses)} misses", file=sys.stderr)

    save(out, misses, pids)
    not_in_gis = [p for p in pids if p not in out and p not in misses]
    print(f"DONE: {len(out)} zoned, {len(misses)} no-intersect, "
          f"{len(not_in_gis)} not-in-gis-parcels")


if __name__ == "__main__":
    main()
