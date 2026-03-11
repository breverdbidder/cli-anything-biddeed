#!/usr/bin/env python3
"""
SUMMIT: PHOTO URL FILL — All 351K Brevard parcels.
Pattern: https://www.bcpao.us/photos/{first2digits}/{TaxAcct}011.jpg
Source: BCPAO GIS layer TaxAcct field.
"""
import httpx, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

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

def main():
    start = time.time()
    telegram("🏔️ PHOTO URL FILL — All Brevard parcels\nPattern: bcpao.us/photos/{prefix}/{TaxAcct}011.jpg")

    # Download PARCEL_ID + TaxAcct (no geometry = fast)
    mapping = {}
    offset = 0
    while True:
        r = c.get(f"{GIS_PARCELS}/query", params={
            "where": "TaxAcct IS NOT NULL", "outFields": "PARCEL_ID,TaxAcct",
            "returnGeometry": "false", "resultOffset": offset,
            "resultRecordCount": 2000, "f": "json"
        })
        feats = r.json().get("features", [])
        if not feats: break
        for f in feats:
            a = f["attributes"]
            pid = (a.get("PARCEL_ID") or "").strip()
            tax = a.get("TaxAcct")
            if pid and tax:
                prefix = str(tax)[:2]
                mapping[pid] = f"https://www.bcpao.us/photos/{prefix}/{tax}011.jpg"
        offset += len(feats)
        if offset % 50000 == 0:
            telegram(f"🏔️ Phase 1: {offset:,} downloaded, {len(mapping):,} mapped")
        if not r.json().get("exceededTransferLimit") and len(feats) < 2000:
            break
        time.sleep(1)

    telegram(f"🏔️ Phase 1 complete: {len(mapping):,} parcels mapped to photo URLs")

    # Upsert to Supabase
    rows = [{"parcel_id": pid, "photo_url": url, "county": "brevard"} for pid, url in mapping.items()]
    telegram(f"🏔️ Phase 2: Upserting {len(rows):,} photo URLs...")

    ok, err = sb_upsert(rows)

    # Verify
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    r = c.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard&photo_url=not.is.null",
              headers=h)
    cr = r.headers.get("content-range", "")
    filled = int(cr.split("/")[1]) if "/" in cr else 0

    elapsed = int(time.time() - start)
    telegram(f"""🏔️ PHOTO URL FILL RESULT

📊 GIS Download: {len(mapping):,} parcels with TaxAcct
📊 Upsert: {ok:,} ok, {err:,} errors
📈 Supabase photo_url filled: {filled:,} / 351,585
⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
