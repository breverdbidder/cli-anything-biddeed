#!/usr/bin/env python3
"""
SHARD-5 Citrus I — Live Research Script (Run 6871, 2026-07-27)

Purpose:
  1. Query Supabase REST API for the 12 failing citrus I rows
  2. Probe citruspa.org (property appraiser) for each failing CA case
  3. Probe Citrus BOCC GIS for parcel data / zoning
  4. Output verified fixes to apply as a migration

Context (from migration trail):
  - Current state: 179/191 card_complete = 93.7% (FAIL, need >=95%)
  - Need 3+ more rows fixed
  - 12 remaining rows blocked because:
    - CA foreclosure cases have NULL parcel_id (SCORSS CAPTCHA-gated)
    - citruspa.org was down for maintenance on 2026-07-25
    - citrus.realforeclose.com returns HTTP 403

Approach:
  1. Get the failing rows (NULL parcel_id, no address, etc.)
  2. For each case: search citruspa.org for case number or defendant name
  3. If we get a parcel_id, query Citrus BOCC GIS ALTKEY for lat/lon
  4. Query ZONING_DESCR MapServer for zone_code
  5. Output the UPDATE + parcel_zones INSERT SQL

Usage:
  SUPABASE_KEY=<service_role> python3 scripts/shard5_citrus_i_live_research_run6871.py
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
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")

BOCC_LAND_URL = "https://maps.citrusbocc.com/server/rest/services/PublicData/LandDevelopment/MapServer/0/query"
BOCC_ZONE_URL = "https://maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0/query"
FL_GIO_URL = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"

def ts():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")

def log(msg, tag="INFO"):
    print(f"[{ts()}] {tag}: {msg}")

def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; GoldStandardShard5Research/6871)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception as e:
        return None, str(e)

def sb_get(table, params):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"sb_get {table} error: {e}", "ERROR")
        return []

def mgmt_sql(sql):
    """Execute SQL via Management API"""
    if not SUPABASE_ACCESS_TOKEN:
        log("No SUPABASE_ACCESS_TOKEN — cannot run Management API SQL", "WARN")
        return None
    url = f"https://api.supabase.com/v1/projects/mocerqjnksmhcjzxrewo/database/query"
    data = json.dumps({"query": sql}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        log(f"Management API error {e.code}: {body[:200]}", "ERROR")
        return None
    except Exception as e:
        log(f"Management API error: {e}", "ERROR")
        return None

def evaluate_county(county="citrus"):
    """Run pencil_dod_evaluate_county via RPC"""
    url = f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county"
    data = json.dumps({"p_county": county}).encode()
    req = urllib.request.Request(url, data=data, headers={
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"pencil_dod_evaluate_county error: {e}", "ERROR")
        return None

def get_failing_citrus_rows():
    """Get citrus auctions that are NOT card_complete per the I criterion"""
    sql = """
    SET statement_timeout = 0;
    SELECT
      mca.case_number,
      mca.parcel_id,
      mca.property_address,
      mca.latitude,
      mca.longitude,
      mca.assessed_value,
      mca.market_value,
      EXISTS (
        SELECT 1 FROM parcel_zones pz
        WHERE pz.parcel_id = mca.parcel_id
          AND pz.zone_code IS NOT NULL
      ) as has_zone
    FROM multi_county_auctions mca
    WHERE lower(mca.county) = 'citrus'
      AND NOT (
        mca.property_address IS NOT NULL
        AND mca.property_address <> ''
        AND mca.latitude IS NOT NULL
        AND mca.longitude IS NOT NULL
        AND COALESCE(mca.assessed_value, mca.market_value) IS NOT NULL
        AND mca.parcel_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM parcel_zones pz
          WHERE pz.parcel_id = mca.parcel_id
            AND pz.zone_code IS NOT NULL
        )
      )
    ORDER BY mca.case_number;
    """
    result = mgmt_sql(sql)
    if result:
        return result
    
    # Fallback: REST API for basic field check
    log("Management API unavailable — using REST fallback", "WARN")
    rows = sb_get("multi_county_auctions",
                  "select=case_number,parcel_id,property_address,latitude,longitude,assessed_value,market_value"
                  "&county=eq.citrus&limit=300")
    return rows

def bocc_lookup_by_altkey(altkey):
    """Get address + centroid from Citrus BOCC GIS LandDevelopment layer"""
    params = urllib.parse.urlencode({
        "where": f"ALTKEY={altkey}",
        "outFields": "ALTKEY,ADDRESS,SITEZIP,PARCELID",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json"
    })
    data, status = http_get(f"{BOCC_LAND_URL}?{params}")
    if not data or status != 200:
        return None
    
    features = data.get("features", [])
    if not features:
        return None
    
    f = features[0]
    attrs = f["attributes"]
    geom = f.get("geometry", {})
    
    lat, lon = None, None
    if geom.get("rings"):
        ring = geom["rings"][0]
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        lon = sum(lons) / len(lons)
        lat = sum(lats) / len(lats)
    
    return {
        "altkey": altkey,
        "address": attrs.get("ADDRESS", ""),
        "zip": attrs.get("SITEZIP", ""),
        "parcelid_raw": attrs.get("PARCELID", ""),
        "lat": lat,
        "lon": lon,
    }

def bocc_zone_at_point(lat, lon, buffer_m=15):
    """Get zone_code via point-in-polygon at Citrus BOCC GIS ZONING_DESCR"""
    buf = buffer_m / 111000.0
    params = urllib.parse.urlencode({
        "geometry": f"{lon-buf},{lat-buf},{lon+buf},{lat+buf}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "HANSEN__PRCLZON_ZONING,DSECRIPT",
        "returnGeometry": "false",
        "f": "json"
    })
    data, status = http_get(f"{BOCC_ZONE_URL}?{params}")
    if not data or status != 200:
        return None, None
    
    features = data.get("features", [])
    if len(features) == 1:
        attrs = features[0]["attributes"]
        return attrs.get("HANSEN__PRCLZON_ZONING"), attrs.get("DSECRIPT")
    elif len(features) > 1:
        zones = [f["attributes"].get("HANSEN__PRCLZON_ZONING") for f in features]
        unique = list(set(zones))
        if len(unique) == 1:
            return unique[0], features[0]["attributes"].get("DSECRIPT")
        log(f"Ambiguous zone at ({lat:.5f},{lon:.5f}): {zones}", "WARN")
        return None, None
    return None, None

def fl_gio_lookup_by_altkey(altkey, co_no=19):
    """Look up parcel from FL GIO statewide cadastral by ALTKEY"""
    params = urllib.parse.urlencode({
        "where": f"ALTKEY = {altkey} AND CO_NO = {co_no}",
        "outFields": "PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json"
    })
    data, status = http_get(f"{FL_GIO_URL}?{params}")
    if not data or status != 200:
        return None
    
    features = data.get("features", [])
    if not features:
        return None
    
    f = features[0]
    attrs = f["attributes"]
    geom = f.get("geometry", {})
    
    lat, lon = None, None
    if geom.get("rings"):
        ring = geom["rings"][0]
        lons = [pt[0] for pt in ring]
        lats = [pt[1] for pt in ring]
        lon = sum(lons) / len(lons)
        lat = sum(lats) / len(lats)
    
    addr = f"{attrs.get('PHY_ADDR1','')}, {attrs.get('PHY_CITY','')}, FL {attrs.get('PHY_ZIPCD','')}".strip(", ")
    
    return {
        "address": addr,
        "lat": lat,
        "lon": lon,
        "just_value": attrs.get("JV"),
    }

def citruspa_lookup(case_number):
    """Attempt citruspa.org lookup by case number (may be back from maintenance)"""
    # Try the main search page
    test_url = "https://www.citruspa.org/"
    data, status = http_get(test_url, timeout=10)
    if status != 200:
        log(f"citruspa.org status {status} — still unavailable", "WARN")
        return None
    
    log(f"citruspa.org UP (HTTP {status})", "INFO")
    
    # Try case search — format varies by county
    # Common Citrus PA search endpoints
    search_urls = [
        f"https://www.citruspa.org/SearchParcel?case={urllib.parse.quote(case_number)}",
        f"https://www.citruspa.org/QPublicOrg/api/search?q={urllib.parse.quote(case_number)}&county=citrus",
    ]
    
    for url in search_urls:
        content, status = http_get(url, timeout=15)
        if content and status == 200:
            log(f"citruspa.org search result for {case_number}: {str(content)[:200]}")
            return content
    
    return None

def main():
    log("=" * 60)
    log("SHARD-5 Citrus I Fix — Run 6871 (2026-07-27)")
    log("=" * 60)
    log(f"SUPABASE_KEY: {'set' if SUPABASE_KEY else 'NOT SET'}")
    log(f"SUPABASE_ACCESS_TOKEN: {'set' if SUPABASE_ACCESS_TOKEN else 'NOT SET'}")
    
    # Step 1: Get baseline evaluation
    log("\n--- Step 1: Baseline pencil_dod_evaluate_county('citrus') ---")
    if SUPABASE_KEY:
        baseline = evaluate_county("citrus")
        if baseline:
            log(f"BASELINE: {json.dumps(baseline)}", "VERIFIED")
        else:
            log("Could not evaluate — proceeding with known state from briefing", "WARN")
            baseline = {"I": {"pass": False, "metric": 93.7, "detail": "card_complete=179 of 191"}}
    else:
        log("No SUPABASE_KEY — using known state from briefing", "WARN")
        baseline = {"I": {"pass": False, "metric": 93.7, "detail": "card_complete=179 of 191"}}
    
    log(f"I criterion: pass={baseline.get('I',{}).get('pass')}, metric={baseline.get('I',{}).get('metric')}, detail={baseline.get('I',{}).get('detail')}")
    
    # Step 2: Get failing rows
    log("\n--- Step 2: Get failing I rows ---")
    rows = get_failing_citrus_rows()
    log(f"Retrieved {len(rows)} rows")
    
    if not rows:
        log("Cannot get rows — need DB access. Writing research plan instead.", "WARN")
        print_research_plan()
        return 0
    
    log("Failing rows:")
    for r in rows:
        cn = r.get("case_number", "?")
        pid = r.get("parcel_id", "NULL")
        addr = r.get("property_address", "NULL")
        lat = r.get("latitude", "NULL")
        val = r.get("assessed_value") or r.get("market_value")
        has_zone = r.get("has_zone", "?")
        log(f"  case={cn} parcel={pid} addr='{addr[:30] if addr else ''}' lat={lat} val={val} zone={has_zone}")
    
    # Step 3: For rows with a valid parcel_id but missing zone, look up zone
    log("\n--- Step 3: Research fixes for failing rows ---")
    fixes = []
    
    for r in rows:
        cn = r.get("case_number")
        pid = r.get("parcel_id")
        lat = r.get("latitude")
        lon = r.get("longitude")
        addr = r.get("property_address")
        val = r.get("assessed_value") or r.get("market_value")
        has_zone = r.get("has_zone", False)
        
        fix = {"case_number": cn, "parcel_id": pid, "issues": []}
        
        # If has parcel_id + lat/lon + value but no zone: get zone from GIS
        if pid and lat and lon and val and not has_zone:
            log(f"  {cn}: has parcel/geo/value, missing zone — querying GIS...")
            zone_code, zone_name = bocc_zone_at_point(float(lat), float(lon))
            if zone_code:
                fix["zone_code"] = zone_code
                fix["zone_name"] = zone_name
                fix["zone_source"] = "citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon shard5_run6871)"
                fixes.append(fix)
                log(f"    FOUND zone: {zone_code} ({zone_name})", "VERIFIED")
            else:
                log(f"    No single-match zone found (ambiguous boundary)", "WARN")
            time.sleep(0.5)
        
        # If has parcel_id but missing lat/lon or value: try BOCC GIS + FL GIO
        elif pid and pid.isdigit() and (not lat or not val):
            log(f"  {cn}: has parcel_id={pid}, missing geo/value — querying BOCC GIS...")
            bocc_data = bocc_lookup_by_altkey(pid)
            if bocc_data:
                fix.update({
                    "address": bocc_data["address"] + ", FL " + bocc_data["zip"],
                    "lat": bocc_data["lat"],
                    "lon": bocc_data["lon"],
                })
                log(f"    BOCC GIS: {fix.get('address')} lat={fix.get('lat')}", "VERIFIED")
            
            # Also try FL GIO for value
            gio_data = fl_gio_lookup_by_altkey(pid)
            if gio_data:
                fix["value"] = gio_data.get("just_value")
                if not fix.get("lat") and gio_data.get("lat"):
                    fix["lat"] = gio_data["lat"]
                    fix["lon"] = gio_data["lon"]
                    fix["address"] = gio_data["address"]
                log(f"    FL GIO: value={fix.get('value')}", "VERIFIED")
            
            # Get zone
            if fix.get("lat") and fix.get("lon"):
                zone_code, zone_name = bocc_zone_at_point(fix["lat"], fix["lon"])
                if zone_code:
                    fix["zone_code"] = zone_code
                    fix["zone_name"] = zone_name
                    fix["zone_source"] = "citrus_gis:maps.citrusbocc.com/server/rest/services/ZONING_DESCR/MapServer/0 (point-in-polygon shard5_run6871)"
                    fixes.append(fix)
                    log(f"    FOUND zone: {zone_code}", "VERIFIED")
            time.sleep(0.5)
        
        # If NULL parcel_id: try citruspa.org
        elif not pid:
            log(f"  {cn}: NULL parcel_id — trying citruspa.org...")
            # citruspa.org lookup
            pa_data = citruspa_lookup(cn)
            if pa_data:
                log(f"    citruspa.org returned data for {cn}", "VERIFIED")
                # Would need to parse HTML for parcel_id, address, etc.
                # If successful, add to fixes
            else:
                log(f"    citruspa.org: no result for {cn}", "WARN")
            time.sleep(1.0)
    
    # Step 4: Output fixes
    log(f"\n--- Step 4: Results — {len(fixes)} fixes found ---")
    
    if fixes:
        log("Fixes to apply:", "VERIFIED")
        for f in fixes:
            log(f"  case={f['case_number']}: zone={f.get('zone_code')} lat={f.get('lat')} val={f.get('value')}")
        
        # Generate SQL migration
        print("\n=== GENERATED SQL MIGRATION ===")
        print_migration_sql(fixes)
    else:
        log("No fixes found — DB access required", "WARN")
    
    return 0 if len(fixes) >= 3 else 1

def print_research_plan():
    """Print research plan based on known state"""
    print("""
=== RESEARCH PLAN (no DB access) ===

Known failing rows from prior session (dispatch d574fe69, 2026-07-25):
  - 12 CA foreclosure cases with NULL parcel_id
  - Blocked by: SCORSS CAPTCHA, citrus.realforeclose.com 403

Approach to fix:
  1. Probe citruspa.org (down for maintenance on 2026-07-25, try now)
  2. Use Citrus County BOCC GIS (maps.citrusbocc.com) for spatial queries
  3. Use FL GIO statewide cadastral for alternative parcel lookup

If we can fix 3+ rows, citrus goes from 179/191 (93.7%) to 182/191 (95.3%) = PASS.

The key unlock: parcel_id from citruspa.org case search → BOCC GIS for geo/zone.
""")

def print_migration_sql(fixes):
    """Print the SQL migration for the fixes found"""
    print("-- SHARD-5 Citrus I fix — Run 6871 (2026-07-27)")
    print("-- dispatch_id: a308fac7-567f-4a7b-8a1f-4a2f4d37be36")
    print()
    print("BEGIN;")
    print()
    
    for fix in fixes:
        cn = fix["case_number"]
        pid = fix.get("parcel_id")
        addr = fix.get("address")
        lat = fix.get("lat")
        lon = fix.get("lon")
        val = fix.get("value")
        zone_code = fix.get("zone_code")
        zone_name = fix.get("zone_name", "")
        zone_src = fix.get("zone_source", "")
        
        # UPDATE multi_county_auctions
        updates = []
        if addr:
            updates.append(f"property_address = {sql_str(addr)}")
        if lat:
            updates.append(f"latitude = {lat}")
        if lon:
            updates.append(f"longitude = {lon}")
        if val:
            updates.append(f"assessed_value = {val}")
        if pid and pid != fix.get("parcel_id"):
            updates.append(f"parcel_id = {sql_str(pid)}")
        
        if updates:
            set_clause = ",\n    ".join(updates)
            print(f"UPDATE multi_county_auctions SET")
            print(f"    {set_clause}")
            print(f"WHERE lower(county) = 'citrus' AND case_number = {sql_str(cn)};")
            print()
        
        # INSERT parcel_zones
        if zone_code and pid:
            print(f"INSERT INTO parcel_zones (parcel_id, jurisdiction_id, zone_code, zone_name, source)")
            print(f"SELECT {sql_str(pid)}, 1327, {sql_str(zone_code)}, {sql_str(zone_name)}, {sql_str(zone_src)}")
            print(f"WHERE NOT EXISTS (SELECT 1 FROM parcel_zones WHERE parcel_id = {sql_str(pid)});")
            print()
    
    print("COMMIT;")

def sql_str(s):
    if s is None:
        return "NULL"
    escaped = str(s).replace("'", "''")
    return f"'{escaped}'"

if __name__ == "__main__":
    sys.exit(main())
