#!/usr/bin/env python3
"""
SUMMIT: Fill ALL Brevard jurisdiction gaps to 85%.
Strategy: For each under-85% jurisdiction, download parcels from county GIS
filtered by CITY, spatial join against county zoning layer.
The county zoning layer covers most of Brevard — parcels that fall in
municipal areas often still intersect county zone polygons.
"""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

GIS_ZONING = "https://gis.brevardfl.gov/gissrv/rest/services/Planning_Development/Zoning_WKID2881/MapServer/0"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

GAPS = {
    "unincorporated": {"target": 75350, "city_filter": "CITY = '                    ' OR CITY IS NULL"},
    "cocoa": {"target": 29882, "city_filter": "CITY LIKE '%COCOA%' AND CITY NOT LIKE '%BEACH%'"},
    "titusville": {"target": 28118, "city_filter": "CITY LIKE '%TITUSVILLE%'"},
    "rockledge": {"target": 17869, "city_filter": "CITY LIKE '%ROCKLEDGE%'"},
    "cape_canaveral": {"target": 7355, "city_filter": "CITY LIKE '%CAPE CANAVERAL%'"},
    "melbourne_beach": {"target": 7337, "city_filter": "CITY LIKE '%MELBOURNE BEACH%'"},
    "indialantic": {"target": 5205, "city_filter": "CITY LIKE '%INDIALANTIC%'"},
    "indian_harbour_beach": {"target": 4496, "city_filter": "CITY LIKE '%INDIAN HARBOUR%'"},
    "malabar": {"target": 1430, "city_filter": "CITY LIKE '%MALABAR%'"},
    "melbourne_village": {"target": 319, "city_filter": "CITY LIKE '%MELBOURNE VILLAGE%'"},
}

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
    
    start = time.time()
    telegram(f"""🏔️ SUMMIT: FILL ALL BREVARD GAPS TO 85%
Jurisdictions to fill: {len(GAPS)}
Target: Every jurisdiction ≥85%
Started: {datetime.now(timezone.utc).strftime('%H:%M UTC')}""")
    
    # Build STRtree from county zoning (once, reuse for all)
    telegram("🏔️ Building county zoning STRtree...")
    features = []
    offset = 0
    while True:
        resp = client.get(f"{GIS_ZONING}/query", params={
            "where": "1=1", "outFields": "ZONING",
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
    
    geometries = []
    zone_lookup = {}
    for f in features:
        rings = f.get("geometry", {}).get("rings", [])
        zone = (f.get("attributes", {}).get("ZONING") or "").strip()
        if not zone or not rings or len(rings[0]) < 3: continue
        try:
            geom = Polygon(rings[0])
            if geom.is_valid:
                idx = len(geometries)
                geometries.append(geom)
                zone_lookup[idx] = zone
        except: continue
    
    tree = STRtree(geometries)
    telegram(f"🏔️ STRtree ready: {len(geometries)} polygons")
    
    # Process each gap jurisdiction
    results = {}
    for jur, config in GAPS.items():
        jur_display = jur.replace("_", " ").title()
        city_filter = config["city_filter"]
        target = config["target"]
        
        telegram(f"🏔️ {jur_display}: Downloading parcels...")
        
        offset = 0
        matched = 0
        total = 0
        buffer = []
        
        while True:
            try:
                resp = client.get(f"{GIS_PARCELS}/query", params={
                    "where": city_filter,
                    "outFields": "PARCEL_ID,CITY",
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
                                "jurisdiction": jur,
                                "county": "brevard",
                            })
                        if len(buffer) >= 5000:
                            sb_upsert(buffer)
                            buffer = []
                
                offset += len(batch)
                if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
                time.sleep(1)
            except Exception as e:
                print(f"  {jur} error at {offset}: {e}", file=sys.stderr)
                time.sleep(5)
                offset += 2000
                if offset > 200000: break
        
        if buffer:
            sb_upsert(buffer)
        
        pct = matched / target * 100 if target else 0
        status = "✅" if pct >= 85 else "⚠️" if pct >= 50 else "❌"
        results[jur] = {"matched": matched, "total": total, "target": target, "pct": pct}
        telegram(f"{status} {jur_display}: {matched:,}/{total:,} matched ({pct:.0f}% of target {target:,})")
        time.sleep(2)
    
    elapsed = int(time.time() - start)
    
    met = [j for j,r in results.items() if r["pct"] >= 85]
    missed = [j for j,r in results.items() if r["pct"] < 85]
    
    telegram(f"""🏔️ SUMMIT GAP FILL COMPLETE

✅ MET 85% ({len(met)}): {', '.join(met) if met else 'none'}
❌ BELOW 85% ({len(missed)}): {', '.join(missed) if missed else 'none'}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
