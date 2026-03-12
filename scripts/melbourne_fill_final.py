#!/usr/bin/env python3
"""Melbourne final fill — simple, robust, no pagination bugs."""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

MEL_URL = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128"
WHERE = "ZONE_ALL IS NOT NULL AND ZONE_ALL <> ''"
FIELDS = "TaxAcct,ZONE_ALL,Lat,Long"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

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
        else:
            print(f"  upsert err: {resp.status_code} {resp.text[:100]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def main():
    start = time.time()
    telegram("🏔️ MELBOURNE FINAL FILL: Downloading 53K address points...")

    records = []
    offset = 0
    retries = 0

    while True:
        try:
            resp = client.get(f"{MEL_URL}/query", params={
                "where": WHERE,
                "outFields": FIELDS,
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": "2000",
                "f": "json"
            })

            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} at offset {offset}")
                retries += 1
                if retries > 5: break
                time.sleep(5)
                continue

            data = resp.json()

            if data.get("error"):
                print(f"  GIS error: {data['error']}")
                retries += 1
                if retries > 5: break
                time.sleep(5)
                continue

            features = data.get("features", [])
            if not features:
                print(f"  No features at offset {offset}, done.")
                break

            for f in features:
                a = f.get("attributes", {})
                tax = a.get("TaxAcct")
                zone = a.get("ZONE_ALL", "")
                if tax and zone and str(zone).strip():
                    records.append({
                        "parcel_id": str(tax),
                        "zone_code": str(zone).strip(),
                        "jurisdiction": "melbourne",
                        "county": "brevard",
                        "centroid_lat": a.get("Lat"),
                        "centroid_lon": a.get("Long"),
                    })

            offset += len(features)
            retries = 0

            if offset % 10000 == 0:
                telegram(f"🏔️ Melbourne: {offset:,} downloaded, {len(records):,} valid")

            exceeded = data.get("exceededTransferLimit", False)
            if not exceeded and len(features) < 2000:
                print(f"  Last page at offset {offset}")
                break

            time.sleep(2)

        except Exception as e:
            print(f"  Exception at offset {offset}: {e}", file=sys.stderr)
            retries += 1
            if retries > 5: break
            time.sleep(10)

    # Dedup
    seen = set()
    unique = []
    for r in records:
        if r["parcel_id"] not in seen:
            seen.add(r["parcel_id"])
            unique.append(r)

    zones = {}
    for r in unique:
        zones[r["zone_code"]] = zones.get(r["zone_code"], 0) + 1

    telegram(f"🏔️ Melbourne: {len(unique):,} unique parcels, {len(zones)} districts. Persisting...")

    persisted = 0
    if unique and SUPABASE_URL:
        persisted = sb_upsert(unique)

    elapsed = int(time.time() - start)
    top_zones = sorted(zones.items(), key=lambda x: -x[1])[:10]

    telegram(f"""🏔️ MELBOURNE FILL COMPLETE

📊 RESULTS:
  Downloaded: {offset:,} records
  Unique parcels: {len(unique):,}
  Persisted: {persisted:,}
  Districts: {len(zones)}
  
🏗️ TOP ZONES:
{chr(10).join(f'  {z}: {c:,}' for z,c in top_zones)}

⏱️ {elapsed//60}m {elapsed%60}s | 💰 $0""")

if __name__ == "__main__":
    main()
