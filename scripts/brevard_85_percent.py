#!/usr/bin/env python3
"""
SUMMIT: REACH 85% BREVARD — Full county spatial join (recovers lost 98K)
+ all municipal data already in Supabase from previous waves.
Target: 298,847 parcels (85% of 351,585)
"""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
TARGET = int(351585 * 0.85)

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
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
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        time.sleep(0.3)
    return total

def sb_count():
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    
    current = sb_count()
    telegram(f"""🏔️ SUMMIT: 85% BREVARD CONQUEST
Current in Supabase: {current:,} / 351,585 ({current/351585*100:.1f}%)
Target: {TARGET:,} (85%)
Gap: {TARGET - current:,} parcels needed
Strategy: Full county spatial join to recover lost 98K + catch new""")
    
    from shapely.geometry import Polygon, Point
    from shapely.strtree import STRtree
    
    # Phase 1: Download zone polygons
    telegram("🏔️ Phase 1: Downloading county zone polygons...")
    features = []
    offset = 0
    while True:
        resp = client.get(f"{GIS_ZONING}/query", params={
            "where": "1=1", "outFields": "OBJECTID,ZONING",
            "returnGeometry": "true", "resultOffset": offset,
            "resultRecordCount": 1000, "f": "json"
        })
        data = resp.json()
        batch = data.get("features", [])
        if not batch: break
        features.extend(batch)
        offset += len(batch)
        if not data.get("exceededTransferLimit", False) and len(batch) < 1000: break
        time.sleep(1)
    
    # Phase 2: Build STRtree
    telegram(f"🏔️ Phase 2: Building STRtree from {len(features)} polygons...")
    geometries = []
    zone_lookup = {}
    for f in features:
        geom_data = f.get("geometry", {})
        zone = f.get("attributes", {}).get("ZONING", "").strip()
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
    telegram(f"🏔️ Phase 2: {len(geometries)} valid polygons indexed")
    
    # Phase 3: Download ALL parcels and spatial join
    telegram("🏔️ Phase 3: Downloading ALL 351K parcels + spatial join...")
    offset = 0
    total_downloaded = 0
    matched_count = 0
    batch_buffer = []
    
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "1=1", "outFields": "PARCEL_ID,CITY",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            
            for f in batch:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get("PARCEL_ID", "")
                city = attrs.get("CITY", "").strip()
                rings = geom.get("rings", [[]])
                
                if pid and rings and rings[0] and len(rings[0]) >= 3:
                    total_downloaded += 1
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
                        matched_count += 1
                        batch_buffer.append({
                            "parcel_id": pid,
                            "zone_code": zone,
                            "jurisdiction": city.lower() if city else "unincorporated",
                            "county": "brevard",
                        })
                    
                    if len(batch_buffer) >= 5000:
                        sb_upsert(batch_buffer)
                        batch_buffer = []
            
            offset += len(batch)
            if offset % 50000 == 0:
                pct = matched_count / total_downloaded * 100 if total_downloaded else 0
                telegram(f"🏔️ Phase 3: {offset:,} parcels, {matched_count:,} matched ({pct:.0f}%)")
            
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 400000: break
    
    if batch_buffer:
        sb_upsert(batch_buffer)
    
    # Final count
    time.sleep(2)
    final_count = sb_count()
    elapsed = int(time.time() - start)
    coverage = final_count / 351585 * 100
    safeguard = "✅ MET" if final_count >= TARGET else f"❌ {coverage:.1f}% < 85%"
    
    telegram(f"""🏔️ SUMMIT 85% RESULT

📊 SPATIAL JOIN:
  Parcels downloaded: {total_downloaded:,}
  Matched to zone: {matched_count:,}
  Match rate: {matched_count/total_downloaded*100:.1f}%

📈 SUPABASE TOTAL (with previous waves):
  Records: {final_count:,} / 351,585
  Coverage: {coverage:.1f}%
  Safeguard (85%): {safeguard}
  Target was: {TARGET:,}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
