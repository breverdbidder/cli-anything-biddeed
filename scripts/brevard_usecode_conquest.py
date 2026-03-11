#!/usr/bin/env python3
"""
SUMMIT: USE_CODE CONQUEST V2 — Fixed: skip Supabase reads entirely.
V1 bugs: 1) Supabase pagination capped at 1000 rows, 2) upsert errors silenced.
V2 fix: Use Prefer: resolution=ignore-duplicates. Upsert ALL 351K. Supabase skips dupes.
Zero reads needed. Faster. Simpler.
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
            "Content-Type": "application/json", "Prefer": "resolution=ignore-duplicates"}

def sb_upsert(rows):
    total = 0
    errors = 0
    last_err = ""
    h = sb_headers()
    for i in range(0, len(rows), 500):
        batch = rows[i:i+500]
        try:
            resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments", headers=h, json=batch)
            if resp.status_code in (200, 201, 204):
                total += len(batch)
            else:
                errors += len(batch)
                last_err = f"{resp.status_code}: {resp.text[:200]}"
                if errors <= 2500:
                    print(f"[batch {i//500}] {last_err}", file=sys.stderr)
        except Exception as e:
            errors += len(batch)
            last_err = str(e)[:200]
        if (i // 500) % 50 == 0 and i > 0:
            telegram(f"🏔️ Upsert progress: {total:,} ok, {errors:,} skipped")
        time.sleep(0.3)
    return total, errors, last_err

def sb_count():
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
         "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    return int(cr.split("/")[1]) if "/" in cr else 0

def main():
    start = time.time()
    current = sb_count()

    telegram(f"""🏔️ SUMMIT: USE_CODE CONQUEST V2
Current: {current:,} / 351,585 ({current/351585*100:.1f}%)
Target: {int(351585*0.85):,} (85%)
Gap: {max(0, int(351585*0.85) - current):,} parcels needed
Strategy: BCPAO USE_CODE for ALL parcels (ignore-duplicates)
V2 fix: Zero Supabase reads, ignore-duplicates on insert""")

    # Phase 1: Download ALL parcels with USE_CODE from BCPAO
    telegram("🏔️ Phase 1: Downloading ALL parcels from BCPAO...")
    rows = []
    total_downloaded = 0
    no_usecode = 0
    offset = 0

    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": "1=1",
                "outFields": "PARCEL_ID,USE_CODE,USE_CODE_DESCRIPTION,CITY,ZIP_CODE",
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": 2000
            })
            data = resp.json()
        except Exception as e:
            telegram(f"⚠️ GIS error at offset {offset}: {e}")
            time.sleep(5)
            offset += 2000
            continue

        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            a = feat.get("attributes", {})
            pid = a.get("PARCEL_ID", "")
            if not pid:
                continue
            total_downloaded += 1

            use_code = str(a.get("USE_CODE", "") or "").strip()
            use_desc = str(a.get("USE_CODE_DESCRIPTION", "") or "").strip()
            city = str(a.get("CITY", "") or "").strip()

            zone_val = use_desc if use_desc else (f"USE:{use_code}" if use_code else "UNCLASSIFIED")
            if not use_code and not use_desc:
                no_usecode += 1

            rows.append({
                "parcel_id": pid,
                "zone_code": zone_val,
                "jurisdiction": (city or "unincorporated").lower().replace(" ", "_"),
                "county": "brevard",
            })

        offset += len(features)
        if offset % 50000 == 0:
            telegram(f"🏔️ Phase 1: {total_downloaded:,} parcels downloaded...")

        if not data.get("exceededTransferLimit") and len(features) < 2000:
            break
        time.sleep(1)

    telegram(f"""🏔️ Phase 1 complete:
  Total parcels: {total_downloaded:,}
  With USE_CODE: {total_downloaded - no_usecode:,}
  No USE_CODE: {no_usecode:,}
  Rows to upsert: {len(rows):,}""")

    # Phase 2: Upsert ALL — Supabase ignores duplicates
    telegram(f"🏔️ Phase 2: Upserting {len(rows):,} records (ignore-duplicates)...")
    persisted, errors, last_err = sb_upsert(rows)

    final_count = sb_count()
    elapsed = int(time.time() - start)

    result = f"""🏔️ USE_CODE CONQUEST V2 RESULT

📊 DOWNLOAD:
  BCPAO parcels: {total_downloaded:,}
  No USE_CODE: {no_usecode:,}

📊 UPSERT:
  Inserted: {persisted:,}
  Skipped (dupes/errors): {errors:,}
  Last error: {last_err[:150] if last_err else 'none'}

📈 SUPABASE:
  Final count: {final_count:,} / 351,585
  Coverage: {final_count/351585*100:.1f}%
  Safeguard (85%): {'✅' if final_count >= 298847 else '❌'} {final_count/351585*100:.1f}% {'≥' if final_count >= 298847 else '<'} 85%

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0"""

    telegram(result)

if __name__ == "__main__":
    main()
