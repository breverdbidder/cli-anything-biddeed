#!/usr/bin/env python3
"""
PALM BAY CONQUEST — Runs on Hetzner (87.99.129.125)
Single-threaded, 1.5s delay, polite rate.
Processes 1000 parcels per invocation.
Cron: */10 * * * * cd /opt/zonewise && python3 palm_bay_hetzner.py >> /var/log/palm_bay.log 2>&1

Progress tracked via offset file. Sends Telegram on completion.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

BCPAO = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"
PB_ZONING = "https://gis.palmbayflorida.org/arcgis/rest/services/GrowthManagement/Zoning/MapServer/0"
BATCH = 1000
OFFSET_FILE = "/opt/zonewise/palm_bay_offset.txt"

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]}, timeout=10)
        except: pass
    print(msg)

def sb_upsert(rows):
    if not rows: return 0, 0
    c = httpx.Client(timeout=60)
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"}
    ok = err = 0
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        try:
            resp = c.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id",
                          headers=h, json=batch)
            ok += len(batch) if resp.status_code < 300 else 0
            err += len(batch) if resp.status_code >= 300 else 0
        except: err += len(batch)
    c.close()
    return ok, err

def main():
    # Read offset
    offset = 0
    if os.path.exists(OFFSET_FILE):
        offset = int(open(OFFSET_FILE).read().strip())
    
    if offset >= 79000:
        telegram("✅ Palm Bay conquest COMPLETE. All parcels processed.")
        return
    
    c = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})
    
    # Download batch of centroids
    params = {
        "where": "CITY='PALM BAY'",
        "outFields": "PARCEL_ID",
        "returnGeometry": "true",
        "outSR": "2881",
        "resultRecordCount": str(BATCH),
        "resultOffset": str(offset),
        "f": "json",
    }
    resp = c.get(f"{BCPAO}/query", params=params)
    features = resp.json().get("features", [])
    
    if not features:
        telegram(f"🏔️ Palm Bay: no more parcels at offset {offset}. Done!")
        open(OFFSET_FILE, 'w').write("79000")
        return
    
    # Query zoning for each centroid
    rows = []
    hits = misses = errors = 0
    
    for f in features:
        pid = f["attributes"]["PARCEL_ID"]
        rings = f["geometry"]["rings"][0]
        cx = sum(p[0] for p in rings) / len(rings)
        cy = sum(p[1] for p in rings) / len(rings)
        
        try:
            qparams = {
                "geometry": f"{cx:.0f},{cy:.0f}",
                "geometryType": "esriGeometryPoint",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "ZONING",
                "returnGeometry": "false",
                "f": "json",
                "inSR": "2881",
            }
            qresp = c.get(f"{PB_ZONING}/query", params=qparams)
            if qresp.status_code == 503:
                time.sleep(30)
                qresp = c.get(f"{PB_ZONING}/query", params=qparams)
            
            qdata = qresp.json()
            feats = qdata.get("features", [])
            if feats:
                zone = feats[0]["attributes"].get("ZONING", "")
                if zone:
                    rows.append({
                        "parcel_id": pid,
                        "zone_code": zone.strip(),
                        "jurisdiction": "palm_bay",
                        "county": "brevard",
                    })
                    hits += 1
                else: misses += 1
            else: misses += 1
        except Exception as e:
            errors += 1
            time.sleep(5)
        
        time.sleep(1.5)  # Polite rate
    
    c.close()
    
    # Upsert
    ok, err = sb_upsert(rows)
    
    # Save new offset
    new_offset = offset + len(features)
    open(OFFSET_FILE, 'w').write(str(new_offset))
    
    telegram(f"🏔️ Palm Bay batch: offset {offset}-{new_offset} | hits={hits} misses={misses} errors={errors} | upserted={ok}")

if __name__ == "__main__":
    main()
