#!/usr/bin/env python3
"""
SUMMIT V2: Conquer Brevard County — Spatial Join with Shapely
Pure data engineering. Zero LLM. Zero API cost.
Downloads zone polygons from GIS, parcel centroids from Supabase,
performs point-in-polygon matching, upserts results.
"""

import httpx
import json
import os
import sys
import time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_BASE = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
BCPAO_PARCEL_GIS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except Exception as e:
            print(f"[tg] {e}", file=sys.stderr)
    print(msg)

def sb_headers():
    return {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}

def sb_upsert(table, rows):
    total = 0
    h = sb_headers()
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        time.sleep(0.3)
    return total

# ── PHASE 1: Download ALL zone polygons with geometry ─────────
def phase1_download_zones():
    telegram("🏔️ Phase 1: Downloading 10,096 zone polygons from BCPAO GIS...")
    
    all_features = []
    offset = 0
    
    while True:
        resp = client.get(f"{GIS_BASE}/query", params={
            "where": "1=1",
            "outFields": "OBJECTID,ZONING",
            "returnGeometry": "true",
            "outSR": "4326",  # WGS84 lat/lon
            "resultOffset": offset,
            "resultRecordCount": 1000,
            "f": "json"
        })
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        
        all_features.extend(features)
        offset += len(features)
        print(f"  Downloaded {offset} polygons...")
        
        if not data.get("exceededTransferLimit", False) and len(features) < 1000:
            break
        time.sleep(1)
    
    # Count districts
    zones = {}
    for f in all_features:
        z = f.get("attributes", {}).get("ZONING", "").strip()
        if z:
            zones[z] = zones.get(z, 0) + 1
    
    telegram(f"🏔️ Phase 1 DONE: {len(all_features)} polygons, {len(zones)} districts downloaded")
    return all_features, zones

# ── PHASE 2: Build spatial index with Shapely ────────────────
def phase2_build_index(features):
    from shapely.geometry import shape, Point
    from shapely.strtree import STRtree
    
    telegram(f"🏔️ Phase 2: Building spatial index from {len(features)} polygons...")
    
    geometries = []
    zone_lookup = {}
    
    for f in features:
        geom_data = f.get("geometry")
        zone = f.get("attributes", {}).get("ZONING", "").strip()
        if not geom_data or not zone:
            continue
        
        try:
            # GIS returns rings format, convert to Shapely
            rings = geom_data.get("rings", [])
            if rings:
                from shapely.geometry import Polygon, MultiPolygon
                polys = []
                for ring in rings:
                    if len(ring) >= 3:
                        polys.append(Polygon(ring))
                if len(polys) == 1:
                    geom = polys[0]
                elif len(polys) > 1:
                    geom = polys[0]  # Use first ring as exterior
                else:
                    continue
                
                if geom.is_valid:
                    idx = len(geometries)
                    geometries.append(geom)
                    zone_lookup[idx] = zone
        except Exception as e:
            continue
    
    print(f"  Valid geometries: {len(geometries)}")
    tree = STRtree(geometries)
    
    telegram(f"🏔️ Phase 2 DONE: Spatial index built with {len(geometries)} valid polygons")
    return tree, geometries, zone_lookup

# ── PHASE 3: Get parcel centroids from BCPAO Parcel GIS ──────
def phase3_get_parcels():
    telegram("🏔️ Phase 3: Downloading parcel centroids from BCPAO GIS...")
    
    all_parcels = []
    offset = 0
    
    while True:
        try:
            resp = client.get(f"{BCPAO_PARCEL_GIS}/query", params={
                "where": "1=1",
                "outFields": "PARCEL_ID,CITY",
                "returnGeometry": "true",
                
                
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": 2000,
                "f": "json"
            })
            data = resp.json()
            features = data.get("features", [])
            
            if not features:
                break
            
            for f in features:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get("PARCEL_ID", "")
                
                # Get centroid from geometry (rings → calculate center)
                rings = geom.get("rings", [[]])
                if rings and rings[0]:
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    cx = sum(xs) / len(xs)
                    cy = sum(ys) / len(ys)
                    all_parcels.append({
                        "parcel_id": str(pid),
                        "city": attrs.get("CITY", "").strip(),
                        "lon": cx,
                        "lat": cy,
                    })
            
            offset += len(features)
            
            if offset % 20000 == 0:
                print(f"  Downloaded {offset:,} parcels...")
                telegram(f"🏔️ Phase 3 progress: {offset:,} parcels downloaded")
            
            if not data.get("exceededTransferLimit", False) and len(features) < 2000:
                break
            
            time.sleep(1)
            
        except Exception as e:
            print(f"[parcels] Error at offset {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            # Try to continue
            offset += 2000
            if offset > 400000:  # Safety limit
                break
    
    telegram(f"🏔️ Phase 3 DONE: {len(all_parcels):,} parcels with centroids")
    return all_parcels

# ── PHASE 4: Spatial join — point in polygon ──────────────────
def phase4_spatial_join(tree, geometries, zone_lookup, parcels):
    from shapely.geometry import Point
    
    telegram(f"🏔️ Phase 4: Spatial join — {len(parcels):,} parcels × {len(geometries):,} polygons...")
    
    results = []
    matched = 0
    batch_size = 10000
    
    for i, p in enumerate(parcels):
        pt = Point(p["lon"], p["lat"])
        
        # Query spatial index
        candidates = tree.query(pt)
        zone = None
        for idx in candidates:
            if geometries[idx].contains(pt):
                zone = zone_lookup.get(idx)
                break
        
        if zone:
            matched += 1
            results.append({
                "parcel_id": p["parcel_id"],
                "zone_code": zone,
                "county": "brevard",
                "centroid_lat": round(p["lat"], 6),
                "centroid_lon": round(p["lon"], 6),
            })
        
        # Batch upsert every 10K
        if len(results) >= batch_size:
            upserted = sb_upsert("zoning_assignments", results)
            print(f"  Upserted {upserted:,} (total matched: {matched:,}/{i+1:,})")
            results = []
        
        if (i + 1) % 50000 == 0:
            pct = matched / (i + 1) * 100
            telegram(f"🏔️ Phase 4 progress: {matched:,}/{i+1:,} matched ({pct:.1f}%)")
    
    # Final batch
    if results:
        sb_upsert("zoning_assignments", results)
    
    pct = matched / len(parcels) * 100 if parcels else 0
    telegram(f"🏔️ Phase 4 DONE: {matched:,}/{len(parcels):,} parcels zoned ({pct:.1f}%)")
    return matched

# ── PHASE 5: BCPAO Photos (sample) ───────────────────────────
def phase5_photos_sample():
    telegram("🏔️ Phase 5: Sampling BCPAO photos (200 parcels)...")
    
    h = sb_headers()
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&limit=200", headers=h)
    if resp.status_code != 200:
        telegram("⚠️ Phase 5: Could not query parcels")
        return 0
    
    parcels = resp.json()
    photos = 0
    
    for p in parcels:
        pid = p.get("parcel_id", "").replace("-", "").replace("*", "").replace(" ", "")
        if not pid:
            continue
        try:
            r = client.get(f"https://www.bcpao.us/api/v1/search?account={pid}",
                          headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200:
                data = r.json()
                url = None
                if isinstance(data, list) and data:
                    url = data[0].get("masterPhotoUrl")
                if url:
                    photos += 1
        except:
            pass
        time.sleep(3)
    
    pct = photos / len(parcels) * 100 if parcels else 0
    telegram(f"🏔️ Phase 5 DONE: {photos}/200 have photos ({pct:.0f}%)")
    return photos

# ── MAIN ──────────────────────────────────────────────────────
def main():
    start = time.time()
    telegram(f"""🏔️ SUMMIT V2: CONQUER BREVARD COUNTY
Pure data engineering. Shapely spatial join.
Zero LLM. Zero API cost.
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        telegram("❌ ABORTED: Missing Supabase credentials")
        sys.exit(1)
    
    # Create table
    try:
        client.post(f"{SUPABASE_URL}/rest/v1/rpc", headers=sb_headers(),
                    json={"name": "exec_sql", "args": {"query": """
            CREATE TABLE IF NOT EXISTS zoning_assignments (
                id BIGSERIAL PRIMARY KEY, parcel_id TEXT UNIQUE NOT NULL,
                zone_code TEXT, county TEXT DEFAULT 'brevard',
                centroid_lat FLOAT, centroid_lon FLOAT, photo_url TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW());
            CREATE INDEX IF NOT EXISTS idx_za_pid ON zoning_assignments(parcel_id);
            CREATE INDEX IF NOT EXISTS idx_za_zone ON zoning_assignments(zone_code);
        """}})
    except:
        pass
    
    # Execute phases
    features, zones = phase1_download_zones()
    tree, geometries, zone_lookup = phase2_build_index(features)
    parcels = phase3_get_parcels()
    matched = phase4_spatial_join(tree, geometries, zone_lookup, parcels)
    phase5_photos_sample()
    
    elapsed = int(time.time() - start)
    total_parcels = len(parcels)
    pct = matched / total_parcels * 100 if total_parcels else 0
    safeguard = "✅ MET" if pct >= 85 else f"❌ {pct:.1f}%"
    
    telegram(f"""🏔️ SUMMIT V2 COMPLETE: BREVARD COUNTY

📊 COVERAGE:
  Parcels downloaded: {total_parcels:,}
  Parcels zoned: {matched:,}
  Coverage: {pct:.1f}%
  Safeguard (85%): {safeguard}

📋 DISTRICTS: {len(zones)} zoning codes
  Top zones: {', '.join(sorted(zones, key=zones.get, reverse=True)[:10])}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0

📈 vs MALABAR BENCHMARK:
  Malabar: 1,430 parcels, 100%, 13 districts
  Brevard: {matched:,} parcels, {pct:.1f}%, {len(zones)} districts""")

if __name__ == "__main__":
    main()
