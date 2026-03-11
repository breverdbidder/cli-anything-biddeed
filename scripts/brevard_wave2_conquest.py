#!/usr/bin/env python3
"""
SUMMIT WAVE 2: Titusville Spatial Join + County Overlap Check for Palm Bay/Cocoa

INTELLIGENCE:
- Titusville: gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15
  2,371 polygons, Zone_Code field, WKID 2881 (same as county!)
- Palm Bay: GIS down (TLS failures). Check county zoning layer overlap.
- Cocoa: No GIS found. Check county zoning layer overlap.
- County parcel layer has CITY field to filter municipally.
"""

import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

TITUSVILLE_ZONING = "https://gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15"
COUNTY_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
COUNTY_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try: httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage", data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def sb_upsert(rows):
    total = 0
    h = sb_headers()
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
        if resp.status_code in (200, 201, 204): total += len(batch)
        else: print(f"[upsert] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def download_polygons(url, zone_field):
    features, zones, offset = [], {}, 0
    while True:
        resp = client.get(f"{url}/query", params={
            "where": "1=1", "outFields": f"OBJECTID,{zone_field}",
            "returnGeometry": "true", "resultOffset": offset,
            "resultRecordCount": 1000, "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch: break
        features.extend(batch)
        for f in batch:
            z = f.get("attributes", {}).get(zone_field, "").strip()
            if z: zones[z] = zones.get(z, 0) + 1
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000: break
        time.sleep(1)
    return features, zones

def build_index(features, zone_field):
    from shapely.geometry import Polygon
    from shapely.strtree import STRtree
    geometries, lookup = [], {}
    for f in features:
        rings = f.get("geometry", {}).get("rings", [])
        zone = f.get("attributes", {}).get(zone_field, "").strip()
        if not rings or not zone or len(rings[0]) < 3: continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid:
                idx = len(geometries)
                geometries.append(geom)
                lookup[idx] = zone
        except: continue
    return STRtree(geometries), geometries, lookup

def download_parcels_by_city(city_name):
    """Download parcels from county layer filtered by CITY."""
    parcels, offset = [], 0
    city_filter = city_name.upper().ljust(20)  # CITY field is padded
    while True:
        try:
            resp = client.get(f"{COUNTY_PARCELS}/query", params={
                "where": f"CITY='{city_filter}' OR CITY='{city_name.upper()}'",
                "outFields": "PARCEL_ID",
                "returnGeometry": "true",
                "resultOffset": offset,
                "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            if not features: break
            for f in features:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get("PARCEL_ID", "")
                rings = geom.get("rings", [[]])
                if pid and rings and rings[0] and len(rings[0]) >= 3:
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    parcels.append({"parcel_id": str(pid), "lon": sum(xs)/len(xs), "lat": sum(ys)/len(ys)})
            offset += len(features)
            if offset % 20000 == 0: print(f"  {city_name}: {offset:,} parcels...")
            if not data.get("exceededTransferLimit", False) and len(features) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"  {city_name} error: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 200000: break
    return parcels

def spatial_join(tree, geometries, lookup, parcels):
    from shapely.geometry import Point
    results = []
    for p in parcels:
        pt = Point(p["lon"], p["lat"])
        for idx in tree.query(pt):
            if geometries[idx].contains(pt):
                results.append({
                    "parcel_id": p["parcel_id"], "zone_code": lookup[idx],
                    "centroid_lat": round(p["lat"], 6), "centroid_lon": round(p["lon"], 6),
                })
                break
    return results

def conquer_titusville():
    telegram("🏔️ TITUSVILLE: Downloading 2,371 zoning polygons...")
    features, zones = download_polygons(TITUSVILLE_ZONING, "Zone_Code")
    telegram(f"🏔️ TITUSVILLE: {len(features)} polygons, {len(zones)} districts. Building index...")
    tree, geometries, lookup = build_index(features, "Zone_Code")
    telegram(f"🏔️ TITUSVILLE: Downloading parcels (CITY=TITUSVILLE from county layer)...")
    parcels = download_parcels_by_city("TITUSVILLE")
    telegram(f"🏔️ TITUSVILLE: {len(parcels):,} parcels. Spatial join...")
    matched = spatial_join(tree, geometries, lookup, parcels)
    results = [{"parcel_id": m["parcel_id"], "zone_code": m["zone_code"],
                "jurisdiction": "titusville", "county": "brevard",
                "centroid_lat": m.get("centroid_lat"), "centroid_lon": m.get("centroid_lon")} for m in matched]
    upserted = sb_upsert(results) if results else 0
    pct = len(matched) / len(parcels) * 100 if parcels else 0
    telegram(f"🏔️ TITUSVILLE CONQUERED: {len(matched):,}/{len(parcels):,} ({pct:.1f}%), {len(zones)} districts, {upserted:,} persisted")
    return len(matched), zones

def county_overlap_check(city_name):
    """Check if county zoning layer covers parcels in this city."""
    telegram(f"🏔️ {city_name.upper()}: Checking county zoning overlap...")
    parcels = download_parcels_by_city(city_name)
    if not parcels:
        telegram(f"⚠️ {city_name.upper()}: 0 parcels downloaded")
        return 0, {}
    # Use already-downloaded county zoning index
    features, zones = download_polygons(COUNTY_ZONING, "ZONING")
    tree, geometries, lookup = build_index(features, "ZONING")
    matched = spatial_join(tree, geometries, lookup, parcels)
    results = [{"parcel_id": m["parcel_id"], "zone_code": m["zone_code"],
                "jurisdiction": city_name.lower(), "county": "brevard",
                "centroid_lat": m.get("centroid_lat"), "centroid_lon": m.get("centroid_lon")} for m in matched]
    upserted = sb_upsert(results) if results else 0
    pct = len(matched) / len(parcels) * 100 if parcels else 0
    telegram(f"🏔️ {city_name.upper()}: {len(matched):,}/{len(parcels):,} county overlap ({pct:.1f}%), {upserted:,} persisted")
    return len(matched), {}

def main():
    start = time.time()
    telegram(f"""🏔️ SUMMIT WAVE 2: TITUSVILLE + COUNTY OVERLAP
Titusville: Shapely spatial join (2,371 polygons)
Palm Bay + Cocoa: County zoning layer overlap check
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")

    totals = {}
    
    # 1. Titusville — dedicated zoning layer
    t_count, t_zones = conquer_titusville()
    totals["titusville"] = t_count
    
    # 2. Palm Bay — county overlap (their GIS is down)
    pb_count, _ = county_overlap_check("PALM BAY")
    totals["palm_bay"] = pb_count
    
    # 3. Cocoa — county overlap
    c_count, _ = county_overlap_check("COCOA")
    totals["cocoa"] = c_count
    
    # 4. Rockledge, West Melbourne, Cocoa Beach — county overlap
    for city in ["ROCKLEDGE", "WEST MELBOURNE", "COCOA BEACH", "SATELLITE BEACH", "CAPE CANAVERAL", "INDIALANTIC"]:
        count, _ = county_overlap_check(city)
        totals[city.lower().replace(" ", "_")] = count
    
    elapsed = int(time.time() - start)
    total_new = sum(totals.values())
    prev = 133324  # Unincorp + Melbourne + Malabar
    
    telegram(f"""🏔️ SUMMIT WAVE 2 COMPLETE

📊 THIS SESSION:
{chr(10).join(f'  {k}: {v:,}' for k, v in totals.items() if v > 0)}
  Session total: {total_new:,}

📈 BREVARD CUMULATIVE:
  Previous: {prev:,}
  + Wave 2: {total_new:,}
  = Total: {prev + total_new:,} / 351,585
  Coverage: {(prev + total_new) / 351585 * 100:.1f}%

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
