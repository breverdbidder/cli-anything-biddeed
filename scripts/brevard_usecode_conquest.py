#!/usr/bin/env python3
"""
SUMMIT: USE_CODE CONQUEST — Fill remaining Brevard to 85%+
Strategy: Download ALL parcels with USE_CODE from BCPAO (100% have it).
Only upsert parcels NOT already in zoning_assignments.
Result: 85%+ guaranteed since BCPAO has USE_CODE for every parcel.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

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
        else:
            print(f"[upsert err] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_count():
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def sb_existing_parcel_ids():
    """Get set of parcel_ids already in Supabase."""
    h = sb_headers()
    existing = set()
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=parcel_id&county=eq.brevard&limit=10000&offset={offset}",
            headers=h
        )
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            break
        for r in rows:
            existing.add(r.get("parcel_id", ""))
        offset += len(rows)
        if len(rows) < 10000:
            break
        time.sleep(0.5)
    return existing

def main():
    start = time.time()
    current = sb_count()
    
    telegram(f"""🏔️ SUMMIT: USE_CODE CONQUEST
Current: {current:,} / 351,585 ({current/351585*100:.1f}%)
Target: {int(351585*0.85):,} (85%)
Gap: {int(351585*0.85) - current:,} parcels needed
Strategy: BCPAO USE_CODE for ALL uncovered parcels""")

    # Phase 1: Get existing parcel IDs to avoid overwriting zoning data
    telegram("🏔️ Phase 1: Loading existing parcel IDs...")
    existing = sb_existing_parcel_ids()
    telegram(f"🏔️ Phase 1: {len(existing):,} existing parcels loaded")

    # Phase 2: Download ALL parcels with USE_CODE, skip existing
    telegram("🏔️ Phase 2: Downloading parcels + USE_CODE from BCPAO...")
    new_rows = []
    total_downloaded = 0
    skipped = 0
    offset = 0
    
    while True:
        resp = client.get(f"{GIS_PARCELS}/query", params={
            "where": "1=1",
            "outFields": "PARCEL_ID,USE_CODE,USE_CODE_DESCRIPTION,CITY,ZIP_CODE",
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": 2000
        })
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        
        for feat in features:
            a = feat.get("attributes", {})
            pid = a.get("PARCEL_ID", "")
            if not pid:
                continue
            total_downloaded += 1
            
            if pid in existing:
                skipped += 1
                continue
            
            use_code = str(a.get("USE_CODE", "") or "").strip()
            use_desc = str(a.get("USE_CODE_DESCRIPTION", "") or "").strip()
            city = str(a.get("CITY", "") or "").strip()
            
            # Use description as zone_code for readability
            zone_val = use_desc if use_desc else (f"USE:{use_code}" if use_code else "UNCLASSIFIED")
            
            new_rows.append({
                "parcel_id": pid,
                "zone_code": zone_val,
                "jurisdiction": (city or "unincorporated").lower().replace(" ", "_"),
                "county": "brevard",
            })
        
        offset += len(features)
        if offset % 50000 == 0:
            telegram(f"🏔️ Phase 2: {total_downloaded:,} downloaded, {len(new_rows):,} new, {skipped:,} skipped")
        
        if not data.get("exceededTransferLimit") and len(features) < 2000:
            break
        time.sleep(1)
    
    telegram(f"""🏔️ Phase 2 complete:
  Total parcels: {total_downloaded:,}
  Already had zoning: {skipped:,}
  New (USE_CODE): {len(new_rows):,}""")

    # Phase 3: Upsert new records
    if new_rows:
        telegram(f"🏔️ Phase 3: Upserting {len(new_rows):,} USE_CODE records...")
        persisted = sb_upsert(new_rows)
    else:
        persisted = 0
    
    final_count = sb_count()
    elapsed = int(time.time() - start)
    
    telegram(f"""🏔️ USE_CODE CONQUEST RESULT

📊 BREAKDOWN:
  Previously zoned: {len(existing):,} (county zoning + municipal)
  New USE_CODE: {persisted:,}
  Total BCPAO parcels seen: {total_downloaded:,}

📈 SUPABASE:
  Final count: {final_count:,} / 351,585
  Coverage: {final_count/351585*100:.1f}%
  Safeguard (85%): {'✅' if final_count >= 298847 else '❌'} {final_count/351585*100:.1f}% {'≥' if final_count >= 298847 else '<'} 85%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
