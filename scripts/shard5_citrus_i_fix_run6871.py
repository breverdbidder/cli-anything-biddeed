#!/usr/bin/env python3
"""
SHARD-5 Citrus I Fix — Run 6871 (2026-07-27)

Target: citrus I metric 93.7% (179/191) -> >=95% (need 182/191)
Need: 3 more card_complete rows

Context from prior sessions:
- bca41e8b (2026-07-18): 34 parcel_zones rows added, residual documented as:
  - 7 auctions with NULL parcel_id (genuinely unresolvable)
  - 1 ambiguous boundary (parcel 1199611)
  - ~4 calendar-sweep placeholder rows with no real address
- d574fe69 (2026-07-25): Fixed 2 more (2026-0134TD, 2026-0147TD) via TaxSmartWeb
  - Remaining 12 blocked by CAPTCHA on SCORSS, citrus.realforeclose.com 403,
    citruspa.org down for maintenance
    
Strategy for this session:
1. Query Supabase to identify the exact 12 failing rows + what fields are missing
2. Probe citruspa.org (may be back from maintenance) for property lookups
3. Use Citrus County BOCC GIS (maps.citrusbocc.com ArcGIS) for spatial lookups
4. Use FL GIO statewide cadastral for any rows with parcel_id but missing geo/value

The I criterion checks (from v_zoning_gold_standard_card):
  - property_address IS NOT NULL AND property_address <> ''
  - latitude IS NOT NULL
  - longitude IS NOT NULL  
  - COALESCE(assessed_value, market_value) IS NOT NULL
  - parcel_id present in parcel_zones with non-null zone_code

"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log(msg, tag="INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {tag}: {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_get(table, params_str):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params_str}"
    req = urllib.request.Request(url, headers=sb_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"GET {table} failed: {e}", "ERROR")
        return []

def sb_rpc(fn_name, args=None):
    url = f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}"
    data = json.dumps(args or {}).encode()
    req = urllib.request.Request(url, data=data, headers=sb_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"RPC {fn_name} failed: {e}", "ERROR")
        return None

def sb_sql(sql):
    """Execute raw SQL via Management API"""
    url = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
    mgmt_token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    if not mgmt_token:
        log("No SUPABASE_ACCESS_TOKEN for SQL exec", "WARN")
        return None
    headers = {
        "Authorization": f"Bearer {mgmt_token}",
        "Content-Type": "application/json"
    }
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except Exception as e:
        log(f"SQL exec failed: {e}", "ERROR")
        return None

def fetch_url(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GoldStandardResearch)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception as e:
        return None, 0

def probe_citruspa(parcel_id=None, address=None):
    """Probe citruspa.org property appraiser for parcel data"""
    log(f"Probing citruspa.org (parcel={parcel_id}, addr={address})...")
    
    # Test if citruspa.org is back up
    test_url = "https://www.citruspa.org/"
    content, status = fetch_url(test_url, timeout=10)
    if status != 200:
        log(f"citruspa.org status: {status} - still unavailable", "WARN")
        return None
    log(f"citruspa.org is UP (HTTP {status})", "INFO")
    
    # Try property search
    if parcel_id:
        search_url = f"https://www.citruspa.org/SearchParcel?parcel={urllib.parse.quote(str(parcel_id))}"
        content, status = fetch_url(search_url, timeout=15)
        if content:
            return content
    
    if address:
        search_url = f"https://www.citruspa.org/SearchAddress?address={urllib.parse.quote(str(address))}"
        content, status = fetch_url(search_url, timeout=15)
        if content:
            return content
    
    return None

def probe_citrus_gis_by_coords(lat, lon, buffer_m=15):
    """Query Citrus County BOCC GIS for zoning at lat/lon"""
    # Buffer in degrees (~15m)
    buf = buffer_m / 111000.0
    
    zoning_url = (
        "https://maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0/query"
        f"?geometry={lon-buf},{lat-buf},{lon+buf},{lat+buf}"
        "&geometryType=esriGeometryEnvelope"
        "&spatialRel=esriSpatialRelIntersects"
        "&outFields=HANSEN__PRCLZON_ZONING,DSECRIPT"
        "&f=json"
        "&returnGeometry=false"
    )
    content, status = fetch_url(zoning_url, timeout=20)
    if not content:
        log(f"Citrus GIS zoning query failed (HTTP {status})", "WARN")
        return None
    
    try:
        data = json.loads(content)
        features = data.get("features", [])
        if not features:
            return None
        zones = [f["attributes"].get("HANSEN__PRCLZON_ZONING", "") for f in features]
        log(f"GIS zones at ({lat:.4f},{lon:.4f}): {zones}")
        return features[0]["attributes"] if len(features) == 1 else None
    except Exception as e:
        log(f"GIS parse error: {e}", "ERROR")
        return None

def probe_fl_gio_parcel(parcel_id, co_no=19):
    """Look up parcel in FL GIO statewide cadastral by ALTKEY (integer parcel_id)"""
    base_url = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
    
    # Citrus parcels use ALTKEY (integer) field
    where = f"ALTKEY = {parcel_id} AND CO_NO = {co_no}"
    
    url = (f"{base_url}"
           f"?where={urllib.parse.quote(where)}"
           "&outFields=PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,NCONST_VAL"
           "&returnGeometry=true"
           "&outSR=4326"
           "&f=json")
    
    content, status = fetch_url(url, timeout=30)
    if not content:
        log(f"FL GIO query failed (HTTP {status}) for parcel {parcel_id}", "WARN")
        return None
    
    try:
        data = json.loads(content)
        features = data.get("features", [])
        if not features:
            log(f"No FL GIO features for ALTKEY={parcel_id}", "INFO")
            return None
        
        f = features[0]
        attrs = f["attributes"]
        geom = f.get("geometry", {})
        
        # Compute centroid from rings
        lat, lon = None, None
        if geom.get("rings"):
            ring = geom["rings"][0]
            lons = [pt[0] for pt in ring]
            lats = [pt[1] for pt in ring]
            lon = sum(lons) / len(lons)
            lat = sum(lats) / len(lats)
        
        addr = f"{attrs.get('PHY_ADDR1','')}, {attrs.get('PHY_CITY','')}, FL {attrs.get('PHY_ZIPCD','')}".strip(", ")
        
        return {
            "parcel_id": str(parcel_id),
            "address": addr,
            "lat": lat,
            "lon": lon,
            "just_value": attrs.get("JV"),
            "land_value": attrs.get("LND_VAL"),
        }
    except Exception as e:
        log(f"FL GIO parse error: {e}", "ERROR")
        return None

def probe_citrus_parcel_by_address(address):
    """Query Citrus BOCC GIS land development layer by address to get ALTKEY"""
    base_url = "https://maps.citrusbocc.com/server/rest/services/PublicData/LandDevelopment/MapServer/0/query"
    
    # Address search
    where = f"ADDRESS LIKE '%{address.upper().split(',')[0].strip()}%'"
    url = (f"{base_url}"
           f"?where={urllib.parse.quote(where)}"
           "&outFields=ALTKEY,ADDRESS,PARCELID,SITEZIP"
           "&returnGeometry=false"
           "&f=json")
    
    content, status = fetch_url(url, timeout=20)
    if not content:
        log(f"Citrus GIS parcel query failed (HTTP {status})", "WARN")
        return []
    
    try:
        data = json.loads(content)
        features = data.get("features", [])
        return [f["attributes"] for f in features]
    except Exception as e:
        log(f"Citrus GIS parse error: {e}", "ERROR")
        return []

def get_citrus_failing_i_rows():
    """Get the 12 failing citrus I rows from Supabase"""
    log("Querying Supabase for citrus auctions missing I criteria...")
    
    # Get all citrus auctions
    rows = sb_get("multi_county_auctions", 
                  "select=case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value&county=eq.citrus&limit=300")
    
    if not rows:
        log("No citrus rows found (credentials may be unavailable)", "WARN")
        return []
    
    log(f"Found {len(rows)} total citrus auctions")
    
    # Check which ones have parcel_zones entries
    incomplete = []
    for row in rows:
        issues = []
        
        if not row.get("property_address"):
            issues.append("no_address")
        if not row.get("latitude"):
            issues.append("no_lat")
        if not row.get("longitude"):
            issues.append("no_lon")
        if not row.get("assessed_value") and not row.get("market_value"):
            issues.append("no_value")
        if not row.get("parcel_id"):
            issues.append("no_parcel_id")
        
        if issues:
            incomplete.append({**row, "issues": issues})
    
    log(f"Found {len(incomplete)} auctions with missing I fields")
    return incomplete

def main():
    log("=== SHARD-5 Citrus I Fix — Run 6871 ===")
    
    if not SUPABASE_KEY:
        log("No SUPABASE_KEY — running in research-only mode", "WARN")
        
        # Demonstrate research plan based on known data from migration trail
        print("\n=== RESEARCH MODE (no DB credentials) ===")
        print("Known state from prior sessions (dispatch d574fe69, 2026-07-25):")
        print("  citrus I: 179/191 = 93.7% FAIL (need 182+ = 95.3%+)")
        print("  12 rows blocked, breakdown per dispatch bca41e8b (2026-07-18):")
        print("    - 7: NULL parcel_id (CA foreclosures, SCORSS CAPTCHA-gated)")
        print("    - 1: ambiguous zoning boundary (parcel 1199611)")
        print("    - ~4: calendar-sweep placeholder rows (no real address)")
        print("\nStrategy: use Citrus County GIS + citruspa.org to resolve")
        print("  parcel_id via case number lookup, then get address/geo/value")
        
        # Probe citruspa.org status
        print("\nProbing citruspa.org...")
        content, status = fetch_url("https://www.citruspa.org/", timeout=10)
        print(f"citruspa.org HTTP status: {status}")
        if content:
            print("citruspa.org is UP! First 200 chars:")
            print(content[:200])
        
        # Probe Citrus GIS
        print("\nProbing Citrus BOCC GIS...")
        content, status = fetch_url(
            "https://maps.citrusbocc.com/server/rest/services/PublicData/LandDevelopment/MapServer/0?f=json",
            timeout=15
        )
        print(f"Citrus GIS HTTP status: {status}")
        if content and status == 200:
            data = json.loads(content)
            print(f"Layer: {data.get('name', 'unknown')}")
        
        # Probe FL GIO
        print("\nProbing FL GIO statewide cadastral...")
        url = (
            "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services"
            "/Florida_Statewide_Cadastral/FeatureServer/0/query"
            "?where=CO_NO%3D19&resultRecordCount=1&outFields=PARCEL_ID,ALTKEY&f=json"
        )
        content, status = fetch_url(url, timeout=20)
        print(f"FL GIO HTTP status: {status}")
        if content and status == 200:
            data = json.loads(content)
            if data.get("features"):
                print(f"Sample feature: {data['features'][0]['attributes']}")
        
        return 0
    
    # Live DB mode
    log("DB credentials available — running live", "INFO")
    
    # Step 1: Get current state
    result = sb_rpc("pencil_dod_evaluate_county", {"p_county": "citrus"})
    if result:
        log(f"Current citrus state: {json.dumps(result)}", "VERIFIED")
        if isinstance(result, dict):
            i_detail = result.get("I", {})
            log(f"I: pass={i_detail.get('pass')}, metric={i_detail.get('metric')}, detail={i_detail.get('detail')}")
    
    # Step 2: Get failing rows
    failing = get_citrus_failing_i_rows()
    
    if not failing:
        log("No failing rows found or DB unavailable", "WARN")
        return 1
    
    log(f"\n12 failing citrus I rows (address + field issues):")
    for row in failing[:20]:
        log(f"  case={row['case_number']} parcel={row.get('parcel_id','NULL')} issues={row['issues']}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
