#!/usr/bin/env python3
"""
SUMMIT: USE_CODE Gap Fill — Fill ALL remaining city gaps via BCPAO USE_CODE crosswalk.
Targets: Satellite Beach, Cocoa Beach, Cocoa, Malabar, Merritt Island, Rockledge, 
         Melbourne, West Melbourne, Cape Canaveral + any other gaps.
"""
import httpx, json, os, sys, time

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

USE_CODE_MAP = {
    "00": "VAC-RES", "01": "SFR", "02": "MH", "03": "MFR-10", "04": "MFR-CONDO",
    "05": "COOP", "06": "RETIRE", "07": "MISC-RES", "08": "MFR", "09": "RES-COMMON",
    "10": "VAC-COM", "11": "RETAIL", "12": "MIXED-USE", "13": "DEPT-STORE",
    "14": "SUPER", "15": "REGIONAL", "16": "COMM-PARK", "17": "OFFICE",
    "18": "PROF-SVC", "19": "HOTEL", "20": "VAC-IND", "21": "LIGHT-IND",
    "22": "HEAVY-IND", "23": "LUMBER", "24": "PACKING", "25": "MINING",
    "26": "UTIL", "27": "AUTO-SVC", "28": "PARKING", "29": "WHOLESALE",
    "30": "VAC-AG", "31": "CROP", "32": "PASTURE", "33": "TIMBER",
    "34": "DAIRY", "35": "BEE", "36": "NURSERY", "37": "ORCHARD",
    "38": "POULTRY", "39": "AG-OTHER", "40": "VAC-INST", "41": "CHURCH",
    "42": "PRIVATE-SCHOOL", "43": "PRIVATE-HOSP", "44": "NURSING",
    "48": "CEMETERIES", "50": "GOV-OTHER", "70": "CHURCH", "71": "CHURCH",
    "72": "EDUCATION", "73": "HOSPITAL", "74": "NURSING-EX", "77": "MISC-EXEMPT",
    "80": "GOV-MUNI", "81": "GOV-COUNTY", "82": "GOV-STATE", "83": "GOV-FED",
    "84": "GOV-MILITARY", "85": "GOV-FOREST", "86": "SCHOOL-PUB", "87": "COLLEGE",
    "88": "HOSPITAL-PUB", "89": "GOV-OTHER", "90": "LEASEHOLD", "91": "UTIL-ELECT",
    "92": "UTIL-GAS", "93": "UTIL-PHONE", "94": "UTIL-WATER", "95": "RIGHTS",
    "96": "WATER-MGMT", "97": "OUTDOOR-REC", "98": "MINING-MIN", "99": "ACREAGE",
}

CITIES = {
    "SATELLITE BEACH": "satellite_beach",
    "COCOA BEACH": "cocoa_beach",
    "COCOA": "cocoa",
    "MALABAR": "malabar",
    "MERRITT ISLAND": "merritt_island",
    "ROCKLEDGE": "rockledge",
    "CAPE CANAVERAL": "cape_canaveral",
    "TITUSVILLE": "titusville",
    "WEST MELBOURNE": "west_melbourne",
}

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

def sb_existing_pids(jurisdiction):
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
    pids = set()
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{jurisdiction}&select=parcel_id&offset={offset}&limit=5000&order=id.asc",
            headers=h)
        data = resp.json()
        if not data: break
        pids.update(r["parcel_id"] for r in data)
        if len(data) < 5000: break
        offset += 5000
        time.sleep(0.3)
    return pids

def map_use_code(use_code):
    if not use_code or len(use_code) < 2: return None
    return USE_CODE_MAP.get(use_code[:2], f"UC-{use_code[:2]}")

def main():
    start = time.time()
    
    # Get before count
    h = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}", "Prefer": "count=exact"}
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    before = int(cr.split("/")[1]) if "/" in cr else 0
    
    telegram(f"""🏔️ SUMMIT: USE_CODE GAP FILL
Current: {before:,} / 351,585 ({before/351585*100:.1f}%)
Targets: {', '.join(CITIES.values())}""")
    
    total_added = 0
    results = []
    
    for bcpao_city, jurisdiction in CITIES.items():
        existing = sb_existing_pids(jurisdiction)
        
        # Download from BCPAO
        parcels = []
        offset = 0
        where = f"CITY='{bcpao_city}'"
        while True:
            try:
                resp = client.get(f"{GIS_PARCELS}/query", params={
                    "where": where, "outFields": "PARCEL_ID,USE_CODE",
                    "returnGeometry": "false",
                    "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
                })
                data = resp.json()
                batch = data.get("features", [])
                if not batch: break
                parcels.extend(batch)
                offset += len(batch)
                if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
                time.sleep(1)
            except Exception as e:
                print(f"Error {bcpao_city} at {offset}: {e}", file=sys.stderr)
                time.sleep(5)
                offset += 2000
                if offset > 100000: break
        
        # Filter to missing, map USE_CODE
        rows = []
        for f in parcels:
            a = f.get("attributes", {})
            pid = a.get("PARCEL_ID", "")
            if pid and pid not in existing:
                zone = map_use_code((a.get("USE_CODE") or "").strip())
                if zone:
                    rows.append({"parcel_id": pid, "zone_code": zone,
                                "jurisdiction": jurisdiction, "county": "brevard"})
        
        upserted = sb_upsert(rows) if rows else 0
        total_added += upserted
        gap = len(parcels) - len(existing)
        results.append(f"  {bcpao_city}: {len(parcels)} BCPAO, {len(existing)} existing, +{upserted} new")
        
        if upserted > 0:
            telegram(f"🏔️ {bcpao_city}: +{upserted} new ({len(parcels)} BCPAO, {len(existing)} existing)")
    
    # Final count
    time.sleep(2)
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    after = int(cr.split("/")[1]) if "/" in cr else 0
    coverage = after / 351585 * 100
    elapsed = int(time.time() - start)
    
    results_text = "\n".join(results)
    
    telegram(f"""🏔️ SUMMIT USE_CODE GAP FILL COMPLETE

📋 Per-City:
{results_text}

📈 BREVARD:
  Before: {before:,} ({before/351585*100:.1f}%)
  After: {after:,} ({coverage:.1f}%)
  Added: +{total_added:,}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
