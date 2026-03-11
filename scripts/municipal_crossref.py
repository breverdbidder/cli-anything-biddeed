#!/usr/bin/env python3
"""
SUMMIT: MUNICIPAL CROSSREF — Melbourne (128K) + Cocoa (8.9K)
Melbourne: Address Points have TaxAcct+ZONE_ALL → crossref via BCPAO TaxAcct→PARCEL_ID
Cocoa: Direct PARCEL_ID+Zoning from AGOL
"""
import httpx, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

MELB_ADDR = "https://maps.mlbfl.org/services/rest/services/AGOL/CommunityDevelopmentViewer_AGOL/MapServer/128"
COCOA_URL = "https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/Cocoa_Zoning_with_Split_Lots/FeatureServer/0"
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

c = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Agent)"}, follow_redirects=True)

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

def gis_query(url, params):
    offset = 0
    while True:
        p = {**params, "resultOffset": str(offset), "f": "json"}
        r = c.get(f"{url}/query", params=p)
        data = r.json()
        feats = data.get("features", [])
        if not feats: break
        yield from feats
        offset += len(feats)
        if not data.get("exceededTransferLimit") and len(feats) < int(params.get("resultRecordCount", 2000)):
            break
        time.sleep(1)

def main():
    start = time.time()
    telegram("🏔️ MUNICIPAL CROSSREF — Melbourne + Cocoa\n")

    # ═══ STEP 1: Build TaxAcct→PARCEL_ID crossref ═══
    telegram("🏔️ Step 1: Building TaxAcct→PARCEL_ID crossref from BCPAO...")
    xref = {}
    for feat in gis_query(GIS_PARCELS, {"where": "TaxAcct IS NOT NULL",
                                         "outFields": "PARCEL_ID,TaxAcct",
                                         "returnGeometry": "false",
                                         "resultRecordCount": "2000"}):
        a = feat.get("attributes", {})
        pid = (a.get("PARCEL_ID") or "").strip()
        tax = a.get("TaxAcct")
        if pid and tax:
            xref[str(tax)] = pid
        if len(xref) % 50000 == 0 and len(xref) > 0:
            telegram(f"  Crossref: {len(xref):,}")
    
    telegram(f"  Crossref complete: {len(xref):,} mappings")

    # ═══ STEP 2: Melbourne Address Points → Zoning ═══
    telegram("\n🏔️ Step 2: Melbourne — 128K address points with ZONE_ALL...")
    melb_records = []
    for feat in gis_query(MELB_ADDR, {"where": "ZONE_ALL IS NOT NULL",
                                       "outFields": "TaxAcct,ZONE_ALL",
                                       "returnGeometry": "false",
                                       "resultRecordCount": "2000"}):
        a = feat.get("attributes", {})
        tax = a.get("TaxAcct")
        zone = (a.get("ZONE_ALL") or "").strip()
        if tax and zone:
            pid = xref.get(str(tax))
            if pid:
                melb_records.append({"parcel_id": pid, "zone_code": zone,
                                    "jurisdiction": "melbourne", "county": "brevard"})
    
    # Dedup
    seen = {}
    for r in melb_records: seen[r["parcel_id"]] = r
    melb_records = list(seen.values())
    telegram(f"  Melbourne: {len(melb_records):,} records (TaxAcct→PID matched)")
    
    if melb_records:
        ok, err = sb_upsert(melb_records)
        telegram(f"  Upserted: {ok:,} ok, {err:,} err")

    # ═══ STEP 3: Cocoa — Direct PARCEL_ID + Zoning ═══
    telegram("\n🏔️ Step 3: Cocoa — 8.9K parcels with Name=PARCEL_ID...")
    cocoa_records = []
    for feat in gis_query(COCOA_URL, {"where": "Zoning IS NOT NULL",
                                       "outFields": "Name,Zoning",
                                       "returnGeometry": "false",
                                       "resultRecordCount": "2000"}):
        a = feat.get("attributes", {})
        pid = (a.get("Name") or "").strip()
        zone = (a.get("Zoning") or "").strip()
        if pid and zone:
            cocoa_records.append({"parcel_id": pid, "zone_code": zone,
                                 "jurisdiction": "cocoa", "county": "brevard"})
    
    seen = {}
    for r in cocoa_records: seen[r["parcel_id"]] = r
    cocoa_records = list(seen.values())
    telegram(f"  Cocoa: {len(cocoa_records):,} records")
    
    if cocoa_records:
        ok, err = sb_upsert(cocoa_records)
        telegram(f"  Upserted: {ok:,} ok, {err:,} err")

    elapsed = int(time.time() - start)
    telegram(f"""
🏔️ MUNICIPAL CROSSREF COMPLETE

  Melbourne: {len(melb_records):,} parcels zoned
  Cocoa: {len(cocoa_records):,} parcels zoned
  Crossref: {len(xref):,} TaxAcct→PID mappings used

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
