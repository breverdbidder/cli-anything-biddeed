#!/usr/bin/env python3
"""
SUMMIT: GAP CLOSER — Use BCPAO USE_CODE crosswalk for municipalities without GIS.
Downloads ALL gap parcels from BCPAO, maps USE_CODE → zone classification, upserts.

Targets: Cape Canaveral, Cocoa Beach, IHB, Melbourne Beach, Indialantic, 
         Malabar, Palm Shores, Melbourne Village, Grant-Valkaria + any other gaps.
"""
import httpx, json, os, sys, time
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
GIS_PARCELS = "https://gis.brevardfl.gov/gissrv/rest/services/Base_Map/Parcel_New_WKID2881/MapServer/5"

client = httpx.Client(timeout=60, headers={"User-Agent": "Mozilla/5.0 (ZoneWise Research)"})

# FL DOR USE_CODE → Zone Classification crosswalk
# Source: FL Dept of Revenue Property Tax Rules, Ch. 12D-8
USE_CODE_MAP = {
    # Residential
    "00": "VAC-RES",    # Vacant residential
    "01": "SFR",        # Single Family
    "02": "MH",         # Mobile Home
    "03": "MFR-10",     # Multi-family <10 units
    "04": "MFR-CONDO",  # Condominium
    "05": "COOP",       # Cooperatives
    "06": "RETIRE",     # Retirement homes
    "07": "MISC-RES",   # Misc residential
    "08": "MFR",        # Multi-family
    "09": "RES-COMMON", # Residential common
    # Commercial
    "10": "VAC-COM",    # Vacant commercial
    "11": "RETAIL",     # Stores/retail
    "12": "MIXED-USE",  # Mixed use
    "13": "DEPT-STORE", # Department stores
    "14": "SUPER",      # Supermarkets
    "15": "REGIONAL",   # Regional malls
    "16": "COMM-PARK",  # Community shopping
    "17": "OFFICE",     # Office buildings
    "18": "PROF-SVC",   # Professional services
    "19": "HOTEL",      # Hotels
    # Industrial / Tourist / Agricultural  
    "20": "VAC-IND",    # Vacant industrial
    "21": "LIGHT-IND",  # Light manufacturing
    "22": "HEAVY-IND",  # Heavy industrial
    "23": "LUMBER",     # Lumber yards
    "24": "PACKING",    # Packing plants
    "25": "MINING",     # Mining
    "26": "UTIL",       # Utilities
    "27": "AUTO-SVC",   # Auto service
    "28": "PARKING",    # Parking
    "29": "WHOLESALE",  # Wholesale
    "30": "VAC-AG",     # Vacant agricultural
    "31": "CROP",       # Cropland
    "32": "PASTURE",    # Pasture
    "33": "TIMBER",     # Timberland
    "34": "DAIRY",      # Dairies
    "35": "BEE",        # Beekeeping
    "36": "NURSERY",    # Nurseries
    "37": "ORCHARD",    # Orchards
    "38": "POULTRY",    # Poultry
    "39": "AG-OTHER",   # Other agriculture
    # Institutional / Government
    "40": "VAC-INST",   # Vacant institutional
    "41": "CHURCH",     # Churches
    "42": "PRIVATE-SCHOOL", # Private schools
    "43": "PRIVATE-HOSP", # Private hospitals
    "44": "NURSING",    # Nursing homes
    "48": "CEMETERIES", # Cemeteries
    "50": "GOV-OTHER",  # Government
    "70": "CHURCH",     # Religious 
    "71": "CHURCH",     # Religious
    "72": "EDUCATION",  # Educational
    "73": "HOSPITAL",   # Hospitals
    "74": "NURSING-EX", # Nursing exempt
    "77": "MISC-EXEMPT",# Miscellaneous exempt
    "80": "GOV-MUNI",   # Municipally owned
    "81": "GOV-COUNTY", # County owned
    "82": "GOV-STATE",  # State owned
    "83": "GOV-FED",    # Federal owned
    "84": "GOV-MILITARY",# Military
    "85": "GOV-FOREST", # Forest/park
    "86": "SCHOOL-PUB", # Public schools
    "87": "COLLEGE",    # Public colleges
    "88": "HOSPITAL-PUB",# Public hospitals
    "89": "GOV-OTHER",  # Other government
    "90": "LEASEHOLD",  # Leasehold
    "91": "UTIL-ELECT", # Electric utility
    "92": "UTIL-GAS",   # Gas utility
    "93": "UTIL-PHONE", # Telephone
    "94": "UTIL-WATER", # Water/sewer
    "95": "RIGHTS",     # Rights-of-way
    "96": "WATER-MGMT", # Water management
    "97": "OUTDOOR-REC",# Outdoor recreation
    "98": "MINING-MIN", # Mineral rights
    "99": "ACREAGE",    # Acreage not zoned ag
}

# Cities to target (no accessible GIS)
GAP_CITIES = {
    "CAPE CANAVERAL": "cape_canaveral",
    "COCOA BEACH": "cocoa_beach",
    "INDIAN HARBOUR BEACH": "indian_harbour_beach",
    "MELBOURNE BEACH": "melbourne_beach",
    "INDIALANTIC": "indialantic",
    "MALABAR": "malabar",
    "PALM SHORES": "palm_shores",
    "MELBOURNE VILLAGE": "melbourne_village",
    "GRANT": "grant_valkaria",
    "GRANT-VALKARIA": "grant_valkaria",
    # Also catch stragglers in bigger cities
    "MERRITT ISLAND": "merritt_island",
    "BAREFOOT BAY": "barefoot_bay",
}

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
        resp = client.post(f"{SUPABASE_URL}/rest/v1/zoning_assignments?on_conflict=parcel_id", headers=h, json=batch)
        if resp.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"[upsert error] {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_existing_pids(jurisdiction):
    """Get all existing parcel_ids for a jurisdiction."""
    h = sb_headers()
    h["Prefer"] = "count=exact"
    pids = set()
    offset = 0
    while True:
        resp = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?jurisdiction=eq.{jurisdiction}&select=parcel_id&offset={offset}&limit=1000",
            headers=h
        )
        data = resp.json()
        if not data: break
        for r in data:
            pids.add(r.get("parcel_id", ""))
        if len(data) < 1000: break
        offset += 1000
        time.sleep(0.3)
    return pids

def map_use_code(use_code):
    """Map FL DOR USE_CODE to zone classification."""
    if not use_code or len(use_code) < 2:
        return None
    prefix = use_code[:2]
    return USE_CODE_MAP.get(prefix, f"UC-{prefix}")

def download_city_parcels(city_name):
    """Download all parcels for a city from BCPAO with centroids."""
    parcels = []
    offset = 0
    where = f"CITY='{city_name}'"
    
    while True:
        try:
            resp = client.get(f"{GIS_PARCELS}/query", params={
                "where": where,
                "outFields": "PARCEL_ID,CITY,USE_CODE,USE_CODE_DESCRIPTION",
                "returnGeometry": "true",
                "resultOffset": offset, "resultRecordCount": 2000, "f": "json"
            })
            data = resp.json()
            batch = data.get("features", [])
            if not batch: break
            
            for f in batch:
                attrs = f.get("attributes", {})
                geom = f.get("geometry", {})
                pid = attrs.get("PARCEL_ID", "")
                rings = geom.get("rings", [[]])
                
                if pid and rings and rings[0] and len(rings[0]) >= 3:
                    xs = [p[0] for p in rings[0]]
                    ys = [p[1] for p in rings[0]]
                    parcels.append({
                        "pid": pid,
                        "use_code": (attrs.get("USE_CODE") or "").strip(),
                        "use_desc": (attrs.get("USE_CODE_DESCRIPTION") or "").strip(),
                        "cx": sum(xs)/len(xs),
                        "cy": sum(ys)/len(ys),
                    })
            
            offset += len(batch)
            if not data.get("exceededTransferLimit", False) and len(batch) < 2000: break
            time.sleep(1)
        except Exception as e:
            print(f"Error at {offset} for {city_name}: {e}", file=sys.stderr)
            time.sleep(5)
            offset += 2000
            if offset > 100000: break
    
    return parcels

def main():
    start = time.time()
    
    telegram("🏔️ SUMMIT: GAP CLOSER — USE_CODE crosswalk for municipalities without GIS")
    
    total_upserted = 0
    total_skipped = 0
    total_downloaded = 0
    city_results = []
    
    for bcpao_city, jurisdiction in GAP_CITIES.items():
        city_start = time.time()
        
        # Get existing parcel_ids
        existing = sb_existing_pids(jurisdiction)
        
        # Download from BCPAO
        parcels = download_city_parcels(bcpao_city)
        total_downloaded += len(parcels)
        
        # Filter to only NEW parcels
        new_parcels = [p for p in parcels if p["pid"] not in existing]
        
        if not new_parcels:
            city_results.append(f"  {bcpao_city}: {len(parcels)} parcels, 0 new (already complete)")
            continue
        
        # Map USE_CODE → zone classification
        rows = []
        for p in new_parcels:
            zone = map_use_code(p["use_code"])
            if zone:
                rows.append({
                    "parcel_id": p["pid"],
                    "zone_code": zone,
                    "jurisdiction": jurisdiction,
                    "county": "brevard",
                })
        
        # Upsert
        upserted = sb_upsert(rows) if rows else 0
        total_upserted += upserted
        total_skipped += len(new_parcels) - len(rows)
        
        elapsed = int(time.time() - city_start)
        city_results.append(f"  {bcpao_city}: {len(parcels)} total, {len(existing)} existing, {upserted} new upserted ({elapsed}s)")
        
        telegram(f"🏔️ {bcpao_city}: +{upserted} new ({len(parcels)} total, {len(existing)} existing)")
    
    # Final count
    time.sleep(2)
    h = sb_headers()
    h["Prefer"] = "count=exact"
    resp = client.get(f"{SUPABASE_URL}/rest/v1/zoning_assignments?select=id&limit=1&county=eq.brevard", headers=h)
    cr = resp.headers.get("content-range", "")
    final = int(cr.split("/")[1]) if "/" in cr else 0
    
    elapsed = int(time.time() - start)
    coverage = final / 351585 * 100
    target = int(351585 * 0.85)
    safeguard = "✅ MET" if final >= target else f"❌ {coverage:.1f}% < 85%"
    
    results_text = "\n".join(city_results)
    
    telegram(f"""🏔️ SUMMIT GAP CLOSER RESULT

📊 USE_CODE CROSSWALK:
  Cities processed: {len(GAP_CITIES)}
  Parcels downloaded: {total_downloaded:,}
  New upserted: {total_upserted:,}
  Skipped (no USE_CODE): {total_skipped}

📋 Per-City:
{results_text}

📈 SUPABASE TOTAL:
  Records: {final:,} / 351,585
  Coverage: {coverage:.1f}%
  Safeguard (85%): {safeguard}
  Target: {target:,}

⏱️ Duration: {elapsed//60}m {elapsed%60}s
💰 Cost: $0""")

if __name__ == "__main__":
    main()
