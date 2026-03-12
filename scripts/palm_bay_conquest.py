#!/usr/bin/env python3
"""
PALM BAY V3 — Server-side spatial query. No Shapely needed.
Instead of downloading polygons + local STRtree:
  1. Download parcels with centroids
  2. Query zoning layer AT each centroid using ArcGIS server-side geometry
  
Batched: send envelope of 100 parcels, get all zoning that intersects.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BASE = "https://gis.palmbayflorida.org/arcgis/rest/services"
PARCELS = f"{BASE}/CommonServices/Parcels/FeatureServer/0"
ZONING = f"{BASE}/GrowthManagement/Zoning/MapServer/0"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise)"})

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
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = c.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                      headers=h, json=batch)
        if resp.status_code in (200, 201, 204): ok += len(batch)
        else: err += len(batch)
        time.sleep(0.3)
    return ok, err

def get_zoning_at_point(x, y):
    """Query Palm Bay zoning layer at a specific point. Server-side spatial query."""
    try:
        r = c.get(f"{ZONING}/query", params={
            "geometry": f"{x},{y}",
            "geometryType": "esriGeometryPoint",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "ZONING",
            "returnGeometry": "false",
            "f": "json"
        }, timeout=10)
        feats = r.json().get("features", [])
        if feats:
            return feats[0]["attributes"].get("ZONING", "")
    except:
        pass
    return None

def main():
    start = time.time()
    telegram("🏔️ PALM BAY V3 — Server-side spatial query\n")

    # Step 1: Test connectivity
    try:
        r = c.get(f"{ZONING}?f=json", timeout=15)
        telegram(f"  Zoning layer: HTTP {r.status_code}")
        if r.status_code != 200:
            telegram("  ❌ Not accessible")
            return
    except Exception as e:
        telegram(f"  ❌ {e}")
        return

    # Step 2: Quick test — query zoning at a known point
    telegram("  Testing server-side spatial query...")
    test = get_zoning_at_point(770000, 1310000)  # Approx Palm Bay center in CRS 2881
    telegram(f"  Test result: {test}")

    # Step 3: Download ALL parcels with centroid coordinates
    telegram("\n🏔️ Step 2: Downloading parcels with geometry...")
    parcels = []
    offset = 0
    while True:
        try:
            r = c.get(f"{PARCELS}/query", params={
                "where": "1=1",
                "outFields": "ParcelId",
                "returnGeometry": "true",
                "returnCentroid": "true",
                "resultOffset": offset,
                "resultRecordCount": 1000,
                "f": "json"
            }, timeout=30)
            data = r.json()
            feats = data.get("features", [])
            if not feats: break
            
            for f in feats:
                pid = (str(f["attributes"].get("ParcelId", "")) or "").strip()
                if not pid: continue
                
                # Get centroid — from returnCentroid or calculate from rings
                cent = f.get("centroid")
                if cent:
                    parcels.append({"pid": pid, "x": cent.get("x"), "y": cent.get("y")})
                else:
                    rings = f.get("geometry", {}).get("rings", [])
                    if rings:
                        ring = rings[0]
                        cx = sum(p[0] for p in ring) / len(ring)
                        cy = sum(p[1] for p in ring) / len(ring)
                        parcels.append({"pid": pid, "x": cx, "y": cy})
            
            offset += len(feats)
            if offset % 10000 == 0:
                telegram(f"  {offset:,} parcels downloaded...")
            if not data.get("exceededTransferLimit") and len(feats) < 1000:
                break
            time.sleep(1)
        except Exception as e:
            telegram(f"  Error at {offset}: {e}")
            time.sleep(5)
            offset += 1000
            if offset > 100000: break

    telegram(f"  Total parcels: {len(parcels):,}")

    # Deduplicate
    seen = {}
    for p in parcels:
        if p["pid"] not in seen:
            seen[p["pid"]] = p
    parcels = list(seen.values())
    telegram(f"  Unique parcels: {len(parcels):,}")

    # Step 4: Server-side zoning lookup for each parcel
    telegram("\n🏔️ Step 3: Server-side zoning lookup...")
    rows = []
    no_zone = 0
    errors = 0
    
    for i, p in enumerate(parcels):
        if p["x"] is None or p["y"] is None:
            no_zone += 1
            continue
        
        zone = get_zoning_at_point(p["x"], p["y"])
        if zone:
            rows.append({
                "parcel_id": p["pid"],
                "zone_code": zone,
                "jurisdiction": "palm_bay",
                "county": "brevard"
            })
        else:
            no_zone += 1
        
        if (i + 1) % 5000 == 0:
            telegram(f"  {i+1:,}/{len(parcels):,} — {len(rows):,} zoned, {no_zone:,} unzoned")
        
        # Rate limit — Palm Bay server, be gentle
        if (i + 1) % 50 == 0:
            time.sleep(0.5)

    telegram(f"\n  Results: {len(rows):,} zoned, {no_zone:,} unzoned, {errors:,} errors")

    # Step 5: Upsert
    if rows:
        telegram(f"\n🏔️ Step 4: Upserting {len(rows):,} records...")
        ok, err = sb_upsert(rows)
        telegram(f"  Upserted: {ok:,} ok, {err:,} err")

    elapsed = int(time.time() - start)
    telegram(f"""
🏔️ PALM BAY V3 COMPLETE

📊 Parcels: {len(parcels):,}
📊 Zoned: {len(rows):,} ({len(rows)/max(len(parcels),1)*100:.0f}%)
📊 Unzoned: {no_zone:,}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
