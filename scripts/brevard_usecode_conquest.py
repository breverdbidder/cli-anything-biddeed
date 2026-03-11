#!/usr/bin/env python3
"""
SUMMIT: USE_CODE CONQUEST V2
Fix: No Supabase reads. Use ignore-duplicates to skip existing rows server-side.
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

def sb_upsert_ignore(rows):
    """Upsert with ignore-duplicates: existing rows are PRESERVED, only new rows inserted."""
    total = 0
    errors = 0
    last_err = ""
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates"}
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            errors += len(batch)
            last_err = f"{resp.status_code}: {resp.text[:300]}"
            print(f"[batch {i//500}] {last_err}", file=sys.stderr)
        time.sleep(0.3)
        if (i + 500) % 50000 == 0:
            telegram(f"🏔️ Upserted: {total:,} ok, {errors:,} errors ({i+500:,}/{len(rows):,})")
    return total, errors, last_err

def sb_count():
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    before = sb_count()

    telegram(f"""🏔️ USE_CODE CONQUEST V2
Before: {before:,} / 351,585 ({before/351585*100:.1f}%)
Strategy: Blast ALL parcels, ignore-duplicates preserves existing zoning
No Supabase reads. No pagination. Just write.""")

    # Phase 1: Download ALL parcels with USE_CODE from BCPAO
    telegram("🏔️ Phase 1: Downloading ALL parcels from BCPAO...")
    rows = []
    offset = 0
    while True:
        resp = client.get(f"{GIS_PARCELS}/query", params={
            "where": "1=1",
            "outFields": "PARCEL_ID,USE_CODE,USE_CODE_DESCRIPTION,CITY,ZIP_CODE",
            "returnGeometry": "false",
            "f": "json", "resultOffset": offset, "resultRecordCount": 2000
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
            use_code = str(a.get("USE_CODE", "") or "").strip()
            use_desc = str(a.get("USE_CODE_DESCRIPTION", "") or "").strip()
            city = str(a.get("CITY", "") or "").strip()
            zone_val = use_desc if use_desc else (f"USE:{use_code}" if use_code else "UNCLASSIFIED")
            rows.append({
                "parcel_id": pid,
                "zone_code": zone_val,
                "jurisdiction": (city or "unincorporated").lower().replace(" ", "_"),
                "county": "brevard",
            })
        offset += len(features)
        if offset % 50000 == 0:
            telegram(f"🏔️ Phase 1: {offset:,} parcels downloaded...")
        if not data.get("exceededTransferLimit") and len(features) < 2000:
            break
        time.sleep(1)

    telegram(f"🏔️ Phase 1 done: {len(rows):,} parcels. Phase 2: Upserting (ignore-duplicates)...")

    # Phase 2: Upsert all — existing zoning rows preserved
    ok, errs, last_err = sb_upsert_ignore(rows)

    after = sb_count()
    net_new = after - before
    elapsed = int(time.time() - start)

    result = f"""🏔️ USE_CODE CONQUEST V2 RESULT

📊 UPSERT:
  Sent: {len(rows):,}
  OK: {ok:,}
  Errors: {errs:,}
  {'Last error: ' + last_err if errs > 0 else ''}

📈 SUPABASE:
  Before: {before:,}
  After: {after:,}
  Net new: {net_new:,}
  Coverage: {after/351585*100:.1f}%
  Safeguard (85%): {'✅' if after >= 298847 else '❌'} {after/351585*100:.1f}%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0"""
    telegram(result)

if __name__ == "__main__":
    main()
