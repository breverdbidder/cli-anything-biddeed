#!/usr/bin/env python3
"""
ZONEWISE: Florida County Parcel Ingestion Pipeline
Ingests parcel data from FL GIO Statewide Cadastral API for any county.
Populates: sample_properties, fl_counties.total_parcels, county_jurisdictions

Data source: FL GIO Statewide Cadastral (10.8M parcels, Aug 2025)
API: https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0

Usage:
  python ingest_county.py --county 48          # Orange County (by DOR number)
  python ingest_county.py --county orange       # Orange County (by slug)
  python ingest_county.py --all                 # All 67 counties (counts only)
  python ingest_county.py --county 48 --full    # Full parcel ingestion
"""
import httpx, json, os, sys, time, argparse
from datetime import datetime, timezone
from collections import Counter

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
TELEGRAM_BOT = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")

FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0"

# FL DOR USE_CODE → Zone Classification crosswalk (standard across all 67 counties)
DOR_UC_MAP = {
    "000": "VAC-RES",   "001": "SFR",       "002": "MH",        "003": "MFR-10",
    "004": "MFR-CONDO", "005": "COOP",       "006": "RETIRE",    "007": "MISC-RES",
    "008": "MFR",       "009": "RES-COMMON", "010": "VAC-COM",   "011": "RETAIL",
    "012": "MIXED-USE", "013": "DEPT-STORE", "014": "SUPER",     "015": "REGIONAL",
    "016": "COMM-PARK", "017": "OFFICE",     "018": "PROF-SVC",  "019": "HOTEL",
    "020": "VAC-IND",   "021": "LIGHT-IND",  "022": "HEAVY-IND", "023": "LUMBER",
    "024": "PACKING",   "025": "MINING",     "026": "UTIL",      "027": "AUTO-SVC",
    "028": "PARKING",   "029": "WHOLESALE",  "030": "VAC-AG",    "031": "CROP",
    "032": "PASTURE",   "033": "TIMBER",     "034": "DAIRY",     "035": "BEE",
    "036": "NURSERY",   "037": "ORCHARD",    "038": "POULTRY",   "039": "AG-OTHER",
    "040": "VAC-INST",  "041": "CHURCH",     "042": "PVT-SCHOOL","043": "PVT-HOSP",
    "044": "NURSING",   "048": "CEMETERY",   "050": "GOV-OTHER", "051": "MILITARY",
    "052": "FOREST-ST", "053": "MUNI-OWNED", "054": "SCHOOL-BD", "055": "COLLEGE",
    "070": "CHURCH-EX", "071": "CHURCH-EX",  "072": "EDUCATION", "073": "HOSPITAL",
    "074": "NURSING-EX","077": "MISC-EXEMPT","080": "GOV-MUNI",  "081": "GOV-COUNTY",
    "082": "GOV-STATE", "083": "GOV-FED",    "084": "SCHOOL-PUB","085": "COLLEGE-PUB",
    "086": "HOSPITAL-PUB","087": "GOV-SPEC", "088": "WATER-MGMT","089": "CONSERVATION",
    "090": "LEASED-GOV","091": "UTIL-EX",    "092": "TRANSPORT", "093": "PARK-REC",
    "094": "HISTORIC",  "095": "CULTURAL",   "097": "MISC-GOV",  "099": "ACREAGE-NOT",
}

client = httpx.Client(timeout=60, headers={"User-Agent": "ZoneWise Research Pipeline"})

def telegram(msg):
    if TELEGRAM_BOT and TELEGRAM_CHAT:
        try:
            httpx.post(f"https://api.telegram.org/bot{TELEGRAM_BOT}/sendMessage",
                       data={"chat_id": TELEGRAM_CHAT, "text": msg[:4000]})
        except: pass
    print(msg)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates"
    }

def sb_get(table, params=""):
    r = client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers())
    return r.json() if r.status_code == 200 else []

def sb_upsert(table, rows, batch_size=500):
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        r = client.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=sb_headers(), json=batch)
        if r.status_code in (200, 201, 204):
            total += len(batch)
        else:
            print(f"  upsert err ({table}): {r.status_code} {r.text[:200]}", file=sys.stderr)
        time.sleep(0.3)
    return total

def sb_rpc(func_name, params=None):
    h = sb_headers()
    r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/{func_name}", headers=h, json=params or {})
    return r.json() if r.status_code == 200 else None

def get_county_info(county_arg):
    """Resolve county argument to co_no and name."""
    counties = sb_get("fl_counties", "select=co_no,name,slug,total_parcels&order=co_no")
    if not counties:
        print("ERROR: Could not load fl_counties. Run migration first.", file=sys.stderr)
        sys.exit(1)
    
    if county_arg.isdigit():
        co_no = int(county_arg)
        match = [c for c in counties if c["co_no"] == co_no]
    else:
        slug = county_arg.lower().replace(" ", "_").replace("-", "_")
        match = [c for c in counties if c["slug"] == slug or c["name"].lower() == county_arg.lower()]
    
    if not match:
        print(f"ERROR: County '{county_arg}' not found. Valid: {', '.join(c['slug'] for c in counties)}")
        sys.exit(1)
    return match[0]

def fetch_fl_gio_parcels(co_no, fields="PARCEL_ID,DOR_UC,PHY_CITY,PHY_ADDR1,PHY_ZIPCD,JV,LND_VAL,NCONST_VAL,TOT_LVG_AR,NO_RES_UNT,ACT_YR_BLT",
                          batch_size=2000, count_only=False):
    """Fetch parcels from FL GIO Statewide Cadastral API."""
    base = f"{FL_GIO_BASE}/query"
    
    if count_only:
        # Use OBJECTID range approach since WHERE CO_NO=X times out on count
        # Instead, estimate by fetching max OBJECTID in range
        # Actually let's try a different approach - get a sample and extrapolate
        print(f"  Counting parcels for CO_NO={co_no}...")
        # Try pagination with minimal fields
        total = 0
        offset = 0
        while True:
            r = client.get(base, params={
                "where": f"CO_NO = {co_no}",
                "outFields": "OBJECTID",
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": str(batch_size),
                "f": "json"
            }, timeout=120)
            if r.status_code != 200:
                break
            data = r.json()
            features = data.get("features", [])
            if not features:
                break
            total += len(features)
            offset += batch_size
            if not data.get("exceededTransferLimit", False):
                break
            if total % 10000 == 0:
                print(f"    ... counted {total:,} so far")
            time.sleep(0.5)
        return total
    
    # Full fetch
    records = []
    offset = 0
    retries = 0
    
    while True:
        try:
            r = client.get(base, params={
                "where": f"CO_NO = {co_no}",
                "outFields": fields,
                "returnGeometry": "false",
                "resultOffset": str(offset),
                "resultRecordCount": str(batch_size),
                "f": "json"
            }, timeout=120)
            
            if r.status_code != 200:
                retries += 1
                if retries > 5: break
                time.sleep(5)
                continue
            
            data = r.json()
            if data.get("error"):
                retries += 1
                if retries > 5: break
                time.sleep(5)
                continue
            
            features = data.get("features", [])
            if not features:
                break
            
            for f in features:
                a = f.get("attributes", {})
                records.append(a)
            
            offset += batch_size
            retries = 0
            
            if not data.get("exceededTransferLimit", False):
                break
            
            if len(records) % 10000 == 0:
                print(f"    ... fetched {len(records):,} parcels")
            time.sleep(0.3)
            
        except Exception as e:
            retries += 1
            if retries > 5: break
            print(f"    retry {retries}: {e}")
            time.sleep(5)
    
    return records

def ingest_county(county_arg, full=False):
    """Ingest a single county's parcel data."""
    county = get_county_info(county_arg)
    co_no = county["co_no"]
    name = county["name"]
    
    telegram(f"🏔️ ZONEWISE: Starting {'full' if full else 'count'} ingestion for {name} County (CO_NO={co_no})")
    
    if not full:
        # Count only - just update total_parcels
        total = fetch_fl_gio_parcels(co_no, count_only=True)
        # Update fl_counties
        client.patch(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}",
            headers=sb_headers(),
            json={"total_parcels": total}
        )
        # Initialize conquest status
        sb_upsert("county_conquest_status", [{"co_no": co_no, "status": "pending"}])
        telegram(f"✅ {name} County: {total:,} parcels counted")
        return total
    
    # Full ingestion
    start = time.time()
    records = fetch_fl_gio_parcels(co_no)
    elapsed_fetch = time.time() - start
    telegram(f"📦 {name}: Fetched {len(records):,} parcels in {elapsed_fetch:.0f}s")
    
    if not records:
        telegram(f"❌ {name}: No records fetched!")
        return 0
    
    # Analyze jurisdictions (cities)
    city_counts = Counter(r.get("PHY_CITY", "").strip() for r in records)
    
    # Update total_parcels
    client.patch(
        f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}",
        headers=sb_headers(),
        json={"total_parcels": len(records)}
    )
    
    # Transform to sample_properties format
    sp_rows = []
    for r in records:
        city = (r.get("PHY_CITY") or "").strip()
        parcel_id = (r.get("PARCEL_ID") or "").strip()
        if not parcel_id:
            continue
        sp_rows.append({
            "co_no": co_no,
            "parcel_id": parcel_id,
            "address": (r.get("PHY_ADDR1") or "").strip(),
            "city": city,
            "zip_code": (r.get("PHY_ZIPCD") or "").strip(),
            "use_code": (r.get("DOR_UC") or "").strip(),
            "land_value": r.get("LND_VAL"),
            "building_value": r.get("NCONST_VAL"),
        })
    
    # Upsert to sample_properties
    upserted = sb_upsert("sample_properties", sp_rows)
    telegram(f"💾 {name}: Upserted {upserted:,} to sample_properties")
    
    # Create zoning_assignments from DOR_UC crosswalk
    za_rows = []
    for r in records:
        parcel_id = (r.get("PARCEL_ID") or "").strip()
        dor_uc = (r.get("DOR_UC") or "").strip()
        city = (r.get("PHY_CITY") or "UNINCORPORATED").strip()
        if not parcel_id:
            continue
        
        zone_code = DOR_UC_MAP.get(dor_uc, f"DOR-{dor_uc}" if dor_uc else None)
        jurisdiction = city.lower().replace(" ", "_").replace("-", "_").replace(".", "")
        
        za_rows.append({
            "co_no": co_no,
            "parcel_id": parcel_id,
            "zone_code": zone_code,
            "jurisdiction": jurisdiction,
            "county": county["slug"],
            "dor_uc": dor_uc,
            "zone_source": "dor_use_code",
            "zone_confidence": "low",  # Will be upgraded when GIS zoning data is added
        })
    
    za_upserted = sb_upsert("zoning_assignments", za_rows)
    telegram(f"🗺️ {name}: Upserted {za_upserted:,} to zoning_assignments (DOR baseline)")
    
    # Create/update county_jurisdictions
    jurisdiction_rows = []
    for city, count in city_counts.most_common():
        city_clean = city.strip() if city else "UNINCORPORATED"
        slug = city_clean.lower().replace(" ", "_").replace("-", "_").replace(".", "")
        is_inc = slug != "unincorporated" and slug != ""
        jurisdiction_rows.append({
            "co_no": co_no,
            "jurisdiction": slug or "unincorporated",
            "display_name": city_clean or "Unincorporated",
            "is_incorporated": is_inc,
            "total_parcels": count,
            "zoned_parcels": count,  # All have DOR baseline
            "coverage_pct": 100.0,   # DOR baseline = 100% but low confidence
            "zone_source": "dor_use_code",
        })
    
    sb_upsert("county_jurisdictions", jurisdiction_rows)
    
    # Update conquest status
    sb_upsert("county_conquest_status", [{
        "co_no": co_no,
        "parcels_ingested": len(records),
        "parcels_with_zone": len(za_rows),
        "parcels_from_usecode": len(za_rows),
        "coverage_pct": 100.0,  # DOR baseline
        "status": "in_progress",  # Needs municipal GIS upgrade
        "jurisdictions_total": len(city_counts),
        "jurisdictions_done": 0,  # None have real GIS zoning yet
        "notes": f"DOR baseline only. Needs municipal GIS for real zoning codes.",
    }])
    
    elapsed_total = time.time() - start
    telegram(f"✅ {name} County: INGESTED {len(records):,} parcels, "
             f"{len(city_counts)} jurisdictions, {elapsed_total:.0f}s total. "
             f"DOR baseline = low confidence. Needs GIS upgrade.")
    return len(records)

def count_all_counties():
    """Count parcels for all 67 counties (lightweight scan)."""
    telegram("🏔️ ZONEWISE: Counting all 67 Florida counties...")
    counties = sb_get("fl_counties", "select=co_no,name,slug&order=co_no")
    
    results = []
    for c in counties:
        co_no = c["co_no"]
        name = c["name"]
        total = fetch_fl_gio_parcels(co_no, count_only=True)
        results.append({"co_no": co_no, "name": name, "total": total})
        
        # Update fl_counties
        client.patch(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}",
            headers=sb_headers(),
            json={"total_parcels": total}
        )
        # Initialize conquest status
        sb_upsert("county_conquest_status", [{"co_no": co_no, "status": "pending"}])
        
        print(f"  {name:20s} CO={co_no:2d}  {total:>10,} parcels")
        time.sleep(1)
    
    grand_total = sum(r["total"] for r in results)
    telegram(f"✅ ALL 67 COUNTIES: {grand_total:,} total parcels counted and saved to fl_counties")
    return results

def main():
    parser = argparse.ArgumentParser(description="ZoneWise Florida County Parcel Ingestion")
    parser.add_argument("--county", type=str, help="County number (1-67) or slug")
    parser.add_argument("--all", action="store_true", help="Count all 67 counties")
    parser.add_argument("--full", action="store_true", help="Full parcel ingestion (not just count)")
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not set", file=sys.stderr)
        sys.exit(1)
    
    if args.all:
        count_all_counties()
    elif args.county:
        ingest_county(args.county, full=args.full)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
