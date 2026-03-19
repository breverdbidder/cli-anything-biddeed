#!/usr/bin/env python3
"""
SUMMIT: DEDUP — For each over-count city, delete rows whose parcel_id
doesn't exist in BCPAO for that city.
"""
import httpx, json, os, sys, time, urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

CITIES = [
    ("COCOA", "cocoa"),
    ("COCOA BEACH", "cocoa_beach"),
    ("WEST MELBOURNE", "west_melbourne"),
    ("SATELLITE BEACH", "satellite_beach"),
    ("MALABAR", "malabar"),
    ("MELBOURNE", "melbourne"),
]

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_get_all(jurisdiction):
    """Get ALL parcel_ids + row ids for a jurisdiction, paginated properly."""
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    rows = []
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{jurisdiction}&select=id,parcel_id&order=id.asc&offset={offset}&limit=1000",
            headers=h)
        data = resp.json()
        if not data: break
        rows.extend(data)
        if len(data) < 1000: break
        offset += 1000
        time.sleep(0.3)
    return rows

def bcpao_pids(city):
    """Get ALL parcel_ids from BCPAO for a city."""
    pids = set()
    offset = 0
    where = f"CITY='{city}'"
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": where, "outFields": "PARCEL_ID",
                "returnGeometry": "false",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            for f in batch:
                pid = f.get("attributes", {}).get("PARCEL_ID", "")
                if pid: pids.add(pid)
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error {city} at {offset}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 100000: break
    return pids

def sb_delete_ids(ids):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    total = 0
    for i in range(0, len(ids), 200):
        batch = ids[i:i+200]
        id_filter = ",".join(str(x) for x in batch)
        resp = client.delete(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?id=in.({id_filter})", headers=h)
        if resp.status_code in (200, 204):
            total += len(batch)
        else:
            print(f"[delete] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def main():
    start = time.time()
    
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    before = int(cr.split("/")[1]) if "/" in cr else 0
    
    telegram(f"🏔️ SUMMIT DEDUP: Cleaning over-count cities. Before: {before:,}")
    
    total_deleted = 0
    results = []
    
    for bcpao_city, jurisdiction in CITIES:
        # Get canonical BCPAO parcel_ids
        canonical = bcpao_pids(bcpao_city)
        
        # Get ALL DB rows for this jurisdiction
        db_rows = sb_get_all(jurisdiction)
        
        # Find rows NOT in BCPAO
        orphans = [r for r in db_rows if r["parcel_id"] not in canonical]
        
        if orphans:
            deleted = sb_delete_ids([r["id"] for r in orphans])
            total_deleted += deleted
            results.append(f"  {bcpao_city}: {len(db_rows)} DB, {len(canonical)} BCPAO, {deleted} deleted")
            telegram(f"🏔️ {bcpao_city}: -{deleted} orphans removed ({len(db_rows)} DB → {len(db_rows)-deleted})")
        else:
            results.append(f"  {bcpao_city}: {len(db_rows)} DB, {len(canonical)} BCPAO, 0 orphans")
    
    time.sleep(2)
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    after = int(cr.split("/")[1]) if "/" in cr else 0
    
    elapsed = int(time.time() - start)
    results_text = "\n".join(results)
    
    telegram(f"""🏔️ SUMMIT DEDUP COMPLETE

📋 Per-City:
{results_text}

📈 BREVARD:
  Before: {before:,}
  After: {after:,}
  Deleted: -{total_deleted:,}
  Coverage: {after/351585*100:.1f}%

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
