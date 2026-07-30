#!/usr/bin/env python3
"""Volusia I fix (gold-standard shard-3): spatial join of gold-standard auction
parcels to real Volusia County GIS zoning polygons (maps1.vcgov.org
CountywideZoning MapServer), AND opportunistic lat/long backfill onto
multi_county_auctions from the same GIS call.

Forked from scripts/gold_standard_shard10_volusia_zoning_spatial_join.py. The
only functional change: that script computed a polygon centroid manually in
the native SRID (2881, FL East State Plane feet) via a shoelace method because
pyproj was not available to reproject to WGS84. This fork instead requests
geometry directly in WGS84 by passing outSR=4326 on the layer-0 query and
inSR=4326 on the layer-2 point-in-polygon query -- ArcGIS REST reprojects
server-side, so no local reprojection math is needed. This gives lat/long
directly from the same call, which is then PATCHed onto
multi_county_auctions.latitude/longitude for rows missing geo, solving the I
geo gap and the zoning gap in one pass.

Step 1: pull real parcel geometry (layer 0, PID field == our 12-digit
parcel_id) in WGS84, compute centroid (shoelace method on WGS84 coords is fine
for these small in-county-scale polygons -- centroid accuracy at this
precision is more than adequate for point-in-polygon zoning lookup and lat/
long display), point-in-polygon query against layer 2 (Countywide Zoning) to
get the REAL zone code per parcel.
Step 2 (this script, same pass): INSERT resolved parcels into parcel_zones
(source='arcgis_live_lookup_shard3_volusia_stlucie') and PATCH
multi_county_auctions.latitude/longitude for the matching rows missing geo.

No fabricated data -- every zone code and lat/long traces to a live GIS query.
Volusia jurisdiction_id mapping (JUR_ID) is reused verbatim from
scripts/gold_standard_shard10_apply_zoning_research.py. Rows whose GIS
CITYNAME does not match any known jurisdiction and are not obviously
unincorporated are SKIPPED and logged explicitly (BLANK > WRONG) -- never
guess a jurisdiction_id.

Usage:
  python3 scripts/gold_standard_shard3_volusia_zoning_geo_fix.py '["pid1","pid2",...]'
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BASE = "https://maps1.vcgov.org/arcgis/rest/services/CountywideZoning/MapServer"

JUR_ID = {
    'Daytona Beach': 938, 'DeBary': 1139, 'DeLand': 823, 'Deltona': 897,
    'Edgewater': 1135, 'Holly Hill': 1136, 'Lake Helen': 1141,
    'New Smyrna Beach': 911, 'Oak Hill': 1143, 'Orange City': 1138,
    'Ormond Beach': 819, 'Pierson': 1142, 'Port Orange': 885,
    'South Daytona': 1137,
}
JUR_ID_LOWER = {k.lower(): v for k, v in JUR_ID.items()}
UNINCORPORATED_JUR_ID = 1511  # 'Volusia County (Unincorporated)' -- confirmed live this session
DAYTONA_SHORES_JUR_ID = 1512  # 'Daytona Beach Shores' -- confirmed live this session
PONCE_INLET_JUR_ID = 1140     # 'Ponce Inlet' -- confirmed live this session

UNINCORPORATED_LABELS = {"unincorporated", "volusia county", "", None}


def resolve_jurisdiction_id(city_label):
    if city_label is None:
        return UNINCORPORATED_JUR_ID, "no CITYNAME -> unincorporated"
    low = city_label.strip().lower()
    if low in UNINCORPORATED_LABELS:
        return UNINCORPORATED_JUR_ID, f"CITYNAME={city_label!r} -> unincorporated"
    if "daytona beach shores" in low:
        return DAYTONA_SHORES_JUR_ID, f"CITYNAME={city_label!r} -> Daytona Beach Shores"
    if "ponce inlet" in low:
        return PONCE_INLET_JUR_ID, f"CITYNAME={city_label!r} -> Ponce Inlet"
    if low in JUR_ID_LOWER:
        return JUR_ID_LOWER[low], f"CITYNAME={city_label!r} -> {city_label}"
    for name, jid in JUR_ID.items():
        if name.lower() in low or low in name.lower():
            return jid, f"CITYNAME={city_label!r} fuzzy-matched -> {name}"
    return None, f"CITYNAME={city_label!r} UNRESOLVED -- skipped, not guessed"


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
    if abs(a) < 1e-12:
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


def rest_post(path, body, prefer="return=representation"):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="POST",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": prefer})
    with urllib.request.urlopen(req, timeout=60) as r:
        if prefer == "return=minimal":
            return None
        return json.loads(r.read())


def rest_get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}",
                                  headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def rest_patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}", data=json.dumps(body).encode(), method="PATCH",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json", "Prefer": "return=representation"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    pids = json.loads(sys.argv[1])
    pids = sorted(set(pids))
    zoned = {}
    misses = []
    unresolved_jur = []

    CHUNK = 25
    for i in range(0, len(pids), CHUNK):
        chunk = pids[i:i + CHUNK]
        where = " OR ".join(f"PID='{p}'" for p in chunk)
        data = arcgis_get("0/query", {
            "where": where,
            "outFields": "PID,CITYNAME,ADDRFULL",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        })
        for feat in data.get("features", []):
            pid = feat["attributes"]["PID"]
            rings = feat.get("geometry", {}).get("rings")
            if not rings:
                misses.append(pid)
                continue
            ring = largest_ring(rings)
            lon, lat = ring_centroid(ring)  # WGS84: x=lon, y=lat
            zdata = arcgis_get("2/query", {
                "geometry": f"{lon},{lat}",
                "geometryType": "esriGeometryPoint",
                "inSR": "4326",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "OriginalZoningCode,GenericZoningCode,GenericDescription,JurisdictionCode,JURISD,Z_DESCRIP,GENL_ZCODE,JUR_ZONING,CityName",
                "returnGeometry": "false",
                "f": "json",
            })
            zfeats = zdata.get("features", [])
            if zfeats:
                attrs = zfeats[0]["attributes"]
                zoned[pid] = {
                    "attrs": attrs,
                    "lat": lat,
                    "lon": lon,
                    "appraiser_city": feat["attributes"].get("CITYNAME"),
                }
            else:
                misses.append(pid)
        print(f"processed {min(i+CHUNK,len(pids))}/{len(pids)} pids, "
              f"{len(zoned)} zoned, {len(misses)} misses", file=sys.stderr)
        time.sleep(0.3)

    not_in_gis = [p for p in pids if p not in zoned and p not in misses]

    parcel_zones_inserted = 0
    geo_patched = 0

    for pid, info in zoned.items():
        attrs = info["attrs"]
        zone_code = attrs.get("OriginalZoningCode") or attrs.get("GenericZoningCode") or attrs.get("GENL_ZCODE") or attrs.get("JUR_ZONING")
        zone_name = attrs.get("GenericDescription") or attrs.get("Z_DESCRIP")
        city_label = attrs.get("CityName") or info.get("appraiser_city")
        jur_id, reason = resolve_jurisdiction_id(city_label)
        if jur_id is None:
            unresolved_jur.append({"parcel_id": pid, "reason": reason})
            continue
        if not zone_code:
            misses.append(pid)
            continue

        existing = rest_get(f"parcel_zones?parcel_id=eq.{pid}&jurisdiction_id=eq.{jur_id}&select=id")
        if not existing:
            try:
                rest_post("parcel_zones", {
                    "parcel_id": pid,
                    "jurisdiction_id": jur_id,
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "source": "arcgis_live_lookup_shard3_volusia_stlucie",
                }, prefer="return=minimal")
                parcel_zones_inserted += 1
                print(f"  INSERT parcel_zones pid={pid} jur={jur_id} zone={zone_code} ({reason})")
            except Exception as e:
                print(f"  parcel_zones INSERT FAILED for {pid}: {e}")
                continue
        else:
            print(f"  SKIP parcel_zones (already exists) pid={pid} jur={jur_id}")

        # Opportunistic lat/long backfill onto multi_county_auctions rows missing geo
        try:
            rows = rest_get(
                f"multi_county_auctions?parcel_id=eq.{pid}&county=eq.volusia"
                f"&or=(latitude.is.null,longitude.is.null)&select=id,latitude,longitude")
        except Exception as e:
            print(f"  MCA lookup FAILED for {pid}: {e}")
            rows = []
        for row in rows:
            patch_body = {}
            if row.get("latitude") is None:
                patch_body["latitude"] = info["lat"]
            if row.get("longitude") is None:
                patch_body["longitude"] = info["lon"]
            if patch_body:
                try:
                    rest_patch(f"multi_county_auctions?id=eq.{row['id']}", patch_body)
                    geo_patched += 1
                    print(f"    geo PATCH id={row['id']} lat={info['lat']:.5f} lon={info['lon']:.5f}")
                except Exception as e:
                    print(f"    geo PATCH FAILED for {row['id']}: {e}")

    print(f"\nDONE: zoned={len(zoned)} parcel_zones_inserted={parcel_zones_inserted} "
          f"geo_patched={geo_patched} no_intersect_misses={len(misses)} "
          f"not_in_gis_parcels={len(not_in_gis)} unresolved_jurisdiction={len(unresolved_jur)}")
    if not_in_gis:
        print(f"NOT_IN_GIS (parcel not found in layer 0): {not_in_gis}")
    if misses:
        print(f"NO_ZONE_INTERSECT: {misses}")
    if unresolved_jur:
        print(f"UNRESOLVED_JURISDICTION (skipped, not guessed): {json.dumps(unresolved_jur)}")

    result = {
        "zoned_pids": list(zoned.keys()),
        "parcel_zones_inserted": parcel_zones_inserted,
        "geo_patched": geo_patched,
        "not_in_gis": not_in_gis,
        "no_zone_intersect": misses,
        "unresolved_jurisdiction": unresolved_jur,
    }
    json.dump(result, open("/tmp/volusia_shard3_zoning_geo_result.json", "w"), indent=2)


if __name__ == "__main__":
    main()
