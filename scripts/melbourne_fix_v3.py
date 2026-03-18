#!/usr/bin/env python3
"""
MELBOURNE FIX V3 — Fix 29K junk zones via layer 109 with correct CRS (EPSG:3857).
V2 Step 4 returned 0 because centroids were EPSG:2881 but layer 109 is EPSG:3857.
Fix: Request BCPAO parcels with outSR=3857 for centroids.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
MEL_ZONING = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/109"

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
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&jurisdiction=eq.melbourne{extra}", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    
    junk_filter = "&or=(zone_code.like.PUD*,zone_code.like.RU-*,zone_code.like.BU-*,zone_code.like.EU-*,zone_code.like.RR-*,zone_code.eq.AU,zone_code.eq.GU,zone_code.eq.IU,zone_code.like.TR-*,zone_code.eq.RP)"
    junk_before = sb_count(junk_filter)
    total_before = sb_count()
    
    telegram(f"""🏔️ MELBOURNE FIX V3 — CRS fix (EPSG:3857)
Melbourne: {total_before:,} rows, {junk_before:,} junk zones
Fix: Download BCPAO centroids in EPSG:3857, query Melbourne layer 109""")
    
    # Step 1: Get junk parcel_ids from Supabase
    junk_pids = []
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.melbourne{junk_filter}&select=parcel_id&offset={offset}&limit=1000&order=id.asc",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        )
        data = resp.json()
        if not data: break
        junk_pids.extend(r["parcel_id"] for r in data)
        if len(data) < 1000: break
        offset += 1000
        time.sleep(0.3)
    
    telegram(f"🏔️ Step 1: {len(junk_pids):,} junk parcel_ids loaded")
    junk_set = set(junk_pids)
    
    # Step 2: Download Melbourne BCPAO parcels with centroids in EPSG:3857
    telegram("🏔️ Step 2: Downloading BCPAO Melbourne parcels (EPSG:3857)...")
    pid_to_centroid = {}
    offset = 0
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "CITY='MELBOURNE'",
                "outFields": "PARCEL_ID",
                "returnGeometry": "true",
                "outSR": "3857",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            for f in batch:
                pid = f.get("attributes", {}).get("PARCEL_ID", "")
                geom = f.get("geometry", {})
                rings = geom.get("rings", [[]])
                if pid and pid in junk_set and rings and rings[0] and len(rings[0]) >= 3:
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    pid_to_centroid[pid] = (sum(xs)/len(xs), sum(ys)/len(ys))
            offset += len(batch)
            if offset % 20000 == 0:
                telegram(f"🏔️ Step 2: {offset:,} downloaded, {len(pid_to_centroid):,} junk matched")
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 80000: break
    
    telegram(f"🏔️ Step 2: {len(pid_to_centroid):,} junk parcels have 3857 centroids")
    
    # Step 3: Query Melbourne layer 109 per-centroid
    telegram("🏔️ Step 3: Querying Melbourne layer 109 (EPSG:3857)...")
    fixed = []
    errors = 0
    for i, (pid, (cx, cy)) in enumerate(pid_to_centroid.items()):
        try:
            resp = client.get(f"{MEL_ZONING}/query", params={
                "geometry": f"{cx},{cy}",
                "geometryType": "esriGeometryPoint",
                "inSR": "3857",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONE_ALL",
                "returnGeometry": "false",
                "f": "json"
            })
            feats = resp.json().get("features", [])
            if feats:
                z = (feats[0]["attributes"].get("ZONE_ALL") or "").strip()
                if z:
                    fixed.append({"parcel_id": pid, "zone_code": z,
                                 "jurisdiction": "melbourne", "county": "brevard"})
                else:
                    errors += 1
            else:
                errors += 1
        except:
            errors += 1
        
        if (i+1) % 50 == 0:
            time.sleep(0.3)
        if (i+1) % 2000 == 0:
            # Batch upsert every 2000
            if fixed:
                sb_upsert(fixed)
                telegram(f"🏔️ Step 3: {i+1}/{len(pid_to_centroid)}, {len(fixed)} fixed so far")
                fixed = []
    
    # Final batch
    upserted = 0
    if fixed:
        upserted = sb_upsert(fixed)
    
    # Final count
    time.sleep(2)
    junk_after = sb_count(junk_filter)
    total_after = sb_count()
    
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    county_total = int(cr.split("/")[1]) if "/" in cr else 0
    coverage = county_total / 351585 * 100
    
    elapsed = int(time.time() - start)
    
    telegram(f"""🏔️ MELBOURNE FIX V3 COMPLETE

📊 Melbourne:
  Before: {total_before:,} ({junk_before:,} junk)
  After: {total_after:,} ({junk_after:,} junk remaining)
  Fixed via layer 109: {len(pid_to_centroid) - errors:,}
  No match (outside zoning): {errors:,}

📈 BREVARD TOTAL:
  Records: {county_total:,} / 351,585
  Coverage: {coverage:.1f}%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
