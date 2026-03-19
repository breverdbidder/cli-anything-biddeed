#!/usr/bin/env python3
"""
SUMMIT: REAL ZONING — Replace USE_CODE with actual municipal zoning where GIS available.

Sources:
  1. West Melbourne: Parcels_View (direct — name=PARCEL_ID, zoningnew=zone) 11,339 parcels
  2. Titusville: CommunityDevelopment/15 Zoning polygons (EPSG:2881 STRtree) 2,371 polygons
  3. Melbourne: Layer 109 (EPSG:3857 per-centroid) — already running separately
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
TV_ZONING = "https://gis.titusville.com/arcgis/rest/services/CommunityDevelopment/MapServer/15"
WM_PARCELS = "https://cwm-gis.westmelbourne.org/server/rest/services/Hosted/West_Melbourne_Parcels_View/FeatureServer/0"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_upsert(rows):
    total = 0
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                          headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_count(extra=""):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard{extra}", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

# ═══ PRONG 1: West Melbourne — Direct download ═══
def conquer_west_melbourne():
    telegram("🏔️ WEST MELBOURNE: Downloading Parcels_View (direct zoning)...")
    
    rows = []
    offset = 0
    while True:
        try:
            resp = client.get(f"{WM_PARCELS}/query", params={
                "where": "zoningnew IS NOT NULL AND zoningnew <> ''",
                "outFields": "name,zoningnew,zoningdesc",
                "returnGeometry": "false",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            if "error" in data:
                print(f"WM error: {data['error']}", file=sys.stderr)
                break
            batch = data.get("features", [])
            if not batch: break
            for f in batch:
                a = f.get("attributes", {})
                pid = (a.get("name") or "").strip()
                zone = (a.get("zoningnew") or "").strip()
                if pid and zone:
                    rows.append({
                        "parcel_id": pid,
                        "zone_code": zone,
                        "jurisdiction": "west_melbourne",
                        "county": "brevard",
                    })
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"WM error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 15000: break
    
    # Dedupe by parcel_id
    seen = set()
    unique = []
    for r in rows:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)
    
    upserted = sb_upsert(unique) if unique else 0
    telegram(f"🏔️ WEST MELBOURNE: {len(unique):,} parcels with real zoning → {upserted:,} upserted")
    return upserted

# ═══ PRONG 2: Titusville — STRtree spatial join (EPSG:2881) ═══
def conquer_titusville():
    from shapely.geometry import Polygon, Point
    from shapely.strtree import STRtree
    
    telegram("🏔️ TITUSVILLE: Downloading zoning polygons (EPSG:2881)...")
    
    # Download zoning polygons
    features = []
    offset = 0
    while True:
        resp = client.get(f"{TV_ZONING}/query", params={
            "where": "1=1", "outFields": "Zone_Code",
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
    
    telegram(f"🏔️ TITUSVILLE: {len(features)} polygons. Building STRtree...")
    
    geometries = []
    zone_lookup = {}
    for f in features:
        geom_data = f.get("geometry", {})
        zone = (f.get("attributes", {}).get("Zone_Code") or "").strip()
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
    
    telegram(f"🏔️ TITUSVILLE: {len(geometries)} valid polygons. Downloading BCPAO parcels...")
    
    # Download Titusville parcels from BCPAO (EPSG:2881 — same CRS!)
    parcels = []
    offset = 0
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "CITY='TITUSVILLE'", "outFields": "PARCEL_ID",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            parcels.extend(batch)
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"TV parcel error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 35000: break
    
    telegram(f"🏔️ TITUSVILLE: {len(parcels):,} parcels. Spatial joining...")
    
    rows = []
    errors = 0
    for f in parcels:
        pid = f.get("attributes", {}).get("PARCEL_ID", "")
        geom = f.get("geometry", {})
        rings = geom.get("rings", [[]])
        if not pid or not rings or not rings[0] or len(rings[0]) < 3:
            errors += 1
            continue
        
        xs = [p[0] for p in rings[0]]
        ys = [p[1] for p in rings[0]]
        pt = Point(sum(xs)/len(xs), sum(ys)/len(ys))
        
        candidates = tree.query(pt)
        for idx in candidates:
            if geometries[idx].contains(pt):
                rows.append({
                    "parcel_id": pid,
                    "zone_code": zone_lookup[idx],
                    "jurisdiction": "titusville",
                    "county": "brevard",
                })
                break
    
    upserted = sb_upsert(rows) if rows else 0
    no_match = len(parcels) - len(rows) - errors
    telegram(f"🏔️ TITUSVILLE: {len(rows):,} matched → {upserted:,} upserted ({no_match} outside zoning)")
    return upserted

def main():
    start = time.time()
    before = sb_count()
    
    telegram(f"""🏔️ SUMMIT: REAL ZONING UPGRADE
Current: {before:,} / 351,585 ({before/351585*100:.1f}%)
Replacing USE_CODE with real municipal zoning where GIS available:
  1. West Melbourne: Direct parcel+zoning download (11K)
  2. Titusville: STRtree spatial join (2.4K polygons × 28K parcels)""")
    
    results = {}
    results["west_melbourne"] = conquer_west_melbourne()
    results["titusville"] = conquer_titusville()
    
    time.sleep(2)
    after = sb_count()
    elapsed = int(time.time() - start)
    
    # Count real zoning vs USE_CODE for upgraded cities
    wm_real = 0
    tv_real = 0
    for j, label in [("west_melbourne", "WM"), ("titusville", "TV")]:
        h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        offset = 0
        uc = 0
        real = 0
        while True:
            resp = client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{j}&select=zone_code&offset={offset}&limit=1000",
                headers=h)
            data = resp.json()
            if not data: break
            for r in data:
                z = r["zone_code"]
                if z in ("SFR","MH","VAC-RES","MFR-CONDO","MFR","RETAIL","OFFICE","GOV-MUNI") or z.startswith("UC-"):
                    uc += 1
                else:
                    real += 1
            if len(data) < 1000: break
            offset += 1000
            time.sleep(0.2)
        if j == "west_melbourne": wm_real = real
        else: tv_real = real
        telegram(f"🏔️ {label} quality: {real:,} real zoning ({real/(real+uc)*100:.0f}%), {uc} USE_CODE remaining")
    
    results_text = "\n".join(f"  {k}: {v:,} upserted" for k, v in results.items())
    
    telegram(f"""🏔️ SUMMIT: REAL ZONING UPGRADE COMPLETE

📊 Results:
{results_text}

📈 Quality:
  West Melbourne: {wm_real:,} real zoning codes
  Titusville: {tv_real:,} real zoning codes

📈 BREVARD: {after:,} / 351,585 ({after/351585*100:.1f}%)

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
