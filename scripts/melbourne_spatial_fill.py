#!/usr/bin/env python3
"""Melbourne spatial fill — Shapely STRtree with proper CRS transform.
Downloads Melbourne zoning polygons (EPSG:3857) and county parcels (EPSG:2881).
Transforms parcel centroids to match zoning CRS before point-in-polygon."""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

MEL_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_upsert(rows):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    total = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        time.sleep(0.3)
    return total

def main():
    from shapely.geometry import Polygon, Point
    from shapely.strtree import STRtree
    from pyproj import Transformer
    
    start = time.time()
    telegram("🏔️ MELBOURNE SPATIAL: CRS-corrected Shapely join starting...")
    
    # Phase 1: Download zoning polygons in NATIVE CRS (don't convert — request in 2881)
    telegram("🏔️ Phase 1: Downloading Melbourne zoning in EPSG:2881 (match parcels)...")
    features = []
    offset = 0
    while True:
        resp = client.get(f"{MEL_ZONING}/query", params={
            "where": "1=1",
            "outFields": "ZONE_ALL,MIN_LOT_SF,MAX_HT_FT,MIN_FT_SB1,MIN_R_SB1",
            "returnGeometry": "true",
            "outSR": "2881",
            "resultOffset": offset, "resultRecordCount": 1000, "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch: break
        features.extend(batch)
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000: break
        time.sleep(1)
    
    telegram(f"🏔️ Phase 1: {len(features)} polygons downloaded in EPSG:2881")
    
    # Phase 2: Build STRtree
    geometries = []
    zone_lookup = {}
    for f in features:
        geom_data = f.get("geometry", {})
        attrs = f.get("attributes", {})
        zone = (attrs.get("ZONE_ALL") or "").strip()
        if not geom_data or not zone: continue
        rings = geom_data.get("rings", [])
        if not rings or len(rings[0]) < 3: continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid:
                idx = len(geometries)
                geometries.append(geom)
                zone_lookup[idx] = zone
        except: continue
    
    tree = STRtree(geometries)
    districts = set(zone_lookup.values())
    telegram(f"🏔️ Phase 2: STRtree — {len(geometries)} polygons, {len(districts)} districts")
    
    # Phase 3: Download Melbourne parcels (already in EPSG:2881) and spatial join
    telegram("🏔️ Phase 3: Downloading Melbourne parcels + spatial join...")
    offset = 0
    matched = 0
    total = 0
    buffer = []
    
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "CITY LIKE '%MELBOURNE%' AND CITY NOT LIKE '%WEST%' AND CITY NOT LIKE '%VILLAGE%' AND CITY NOT LIKE '%BEACH%'",
                "outFields": "PARCEL_ID",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            
            for f in batch:
                pid = f.get("attributes", {}).get("PARCEL_ID", "")
                rings = f.get("geometry", {}).get("rings", [[]])
                if pid and rings and rings[0] and len(rings[0]) >= 3:
                    total += 1
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    pt = Point(sum(xs)/len(xs), sum(ys)/len(ys))
                    
                    candidates = tree.query(pt)
                    zone = None
                    for idx in candidates:
                        if geometries[idx].contains(pt):
                            zone = zone_lookup.get(idx)
                            break
                    if zone:
                        matched += 1
                        buffer.append({
                            "parcel_id": pid,
                            "zone_code": zone,
                            "jurisdiction": "melbourne",
                            "county": "brevard",
                        })
                    if len(buffer) >= 5000:
                        sb_upsert(buffer)
                        buffer = []
            
            offset += len(batch)
            if offset % 10000 == 0:
                telegram(f"🏔️ Melbourne spatial: {offset:,} parcels, {matched:,} matched ({matched/total*100:.0f}%)")
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(2)
        except Exception as e:
            print(f"Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 100000: break
    
    if buffer:
        sb_upsert(buffer)
    
    elapsed = int(time.time() - start)
    pct = matched / total * 100 if total else 0
    telegram(f"""🏔️ MELBOURNE SPATIAL COMPLETE

📊 RESULTS:
  Total parcels: {total:,}
  Matched to zone: {matched:,} ({pct:.0f}%)
  Districts: {len(districts)}
  
Combined with address points (32,934):
  Total Melbourne: ~{matched + 32934:,} / 62,135

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
