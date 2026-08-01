#!/usr/bin/env python3
"""
SHARD-3 dispatch 6cace789: diagnose + fix flagler G regression and seminole I gap.
Counties: seminole, hamilton, union, flagler, lake
"""
import os
import json
import httpx
import time
import urllib.request
import urllib.parse

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def mgmt_headers():
    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

def rest_get(path, params=""):
    client = httpx.Client(timeout=60)
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url = f"{url}?{params}"
    r = client.get(url, headers=sb_headers())
    return r

def rest_rpc(fn, body):
    client = httpx.Client(timeout=120)
    r = client.post(f"{SUPABASE_URL}/rest/v1/rpc/{fn}", headers=sb_headers(), json=body)
    return r

def mgmt_sql(query):
    client = httpx.Client(timeout=120)
    r = client.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=mgmt_headers(),
        json={"query": query}
    )
    return r

def evaluate_county(county):
    r = rest_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
    if r.status_code == 200:
        return r.json()
    r2 = rest_rpc("pencil_dod_evaluate_county", {"p_county": county})
    if r2.status_code == 200:
        return r2.json()
    print(f"  evaluator error {r.status_code}: {r.text[:200]}")
    return None

def print_eval(county, result):
    if not result:
        print(f"  {county}: NO DATA")
        return
    if isinstance(result, list):
        pass_count = sum(1 for x in result if x.get('pass'))
        print(f"  {county}: {pass_count}/10")
        for x in result:
            letter = x.get('letter', '?')
            metric = x.get('metric')
            passes = x.get('pass', False)
            detail = x.get('detail', '')
            status = "PASS" if passes else "FAIL"
            print(f"    {letter}: {status} metric={metric} [{detail}]")
    elif isinstance(result, dict):
        print(f"  {county}: {json.dumps(result)[:300]}")

print("="*60)
print("SHARD-3 DIAGNOSIS: seminole, hamilton, union, flagler, lake")
print("="*60)

print("\n=== CONNECTION TEST ===")
r = rest_get("fl_counties", "select=count&limit=1")
print(f"REST API: {r.status_code}")

if ACCESS_TOKEN:
    r2 = mgmt_sql("SELECT 'management_api_ok' as status")
    print(f"Mgmt API: {r2.status_code}")
else:
    print("No SUPABASE_ACCESS_TOKEN — mgmt API unavailable")

print("\n=== BEFORE STATE (pencil_dod_evaluate_county) ===")
COUNTIES = ['seminole', 'hamilton', 'union', 'flagler', 'lake']
before_states = {}
for county in COUNTIES:
    print(f"\n--- {county} ---")
    result = evaluate_county(county)
    before_states[county] = result
    print_eval(county, result)

print("\n=== FLAGLER G DIAGNOSIS ===")
diagnosis_sql = """
-- Check flagler parcel_zones and their district coverage
WITH flagler_parcels AS (
    SELECT DISTINCT mca.parcel_id
    FROM multi_county_auctions mca
    WHERE mca.county = 'flagler'
      AND mca.parcel_id IS NOT NULL
),
pz_data AS (
    SELECT pz.parcel_id, pz.zone_code, pz.jurisdiction_id, pz.source,
           zd.id as district_id, zd.far_regulated, zd.density_regulated,
           zs.max_far, zs.max_density_du_acre, zs.parking_per_1000sf
    FROM parcel_zones pz
    JOIN flagler_parcels fp ON fp.parcel_id = pz.parcel_id
    LEFT JOIN zoning_districts zd ON zd.id = pz.zoning_district_id
    LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
),
zone_issues AS (
    SELECT zone_code, jurisdiction_id, district_id, far_regulated, density_regulated,
           max_far, max_density_du_acre, parking_per_1000sf,
           COUNT(*) as parcel_count,
           CASE 
             WHEN far_regulated = true AND max_far IS NULL THEN 'FAR_REGULATED_NO_VALUE'
             WHEN far_regulated IS NULL THEN 'FAR_REGULATED_NULL'
             ELSE 'OK'
           END as far_status
    FROM pz_data
    GROUP BY zone_code, jurisdiction_id, district_id, far_regulated, density_regulated,
             max_far, max_density_du_acre, parking_per_1000sf
)
SELECT * FROM zone_issues ORDER BY parcel_count DESC;
"""

if ACCESS_TOKEN:
    r = mgmt_sql(diagnosis_sql)
    if r.status_code == 200:
        data = r.json()
        print(f"Zone issues: {json.dumps(data, indent=2, default=str)[:3000]}")
    else:
        print(f"Mgmt SQL error: {r.status_code} {r.text[:200]}")

print("\n=== FLAGLER G ZONE DISTRICT DETAILS ===")
zone_details_sql = """
SELECT 
    zd.id, zd.code, zd.name, zd.jurisdiction_id,
    j.name as jname,
    zd.far_regulated, zd.density_regulated,
    zs.max_far, zs.max_density_du_acre, zs.parking_per_1000sf,
    COUNT(pz.parcel_id) as parcel_count
FROM zoning_districts zd
JOIN jurisdictions j ON j.id = zd.jurisdiction_id
LEFT JOIN zone_standards zs ON zs.zoning_district_id = zd.id
LEFT JOIN parcel_zones pz ON pz.zoning_district_id = zd.id
    AND pz.parcel_id IN (
        SELECT parcel_id FROM multi_county_auctions WHERE county = 'flagler'
    )
WHERE j.county ILIKE 'flagler' OR j.name ILIKE '%flagler%' OR j.name ILIKE '%palm coast%'
   OR j.name ILIKE '%bunnell%' OR j.name ILIKE '%flagler beach%'
GROUP BY zd.id, zd.code, zd.name, zd.jurisdiction_id, j.name,
         zd.far_regulated, zd.density_regulated,
         zs.max_far, zs.max_density_du_acre, zs.parking_per_1000sf
ORDER BY parcel_count DESC NULLS LAST, zd.id;
"""

if ACCESS_TOKEN:
    r = mgmt_sql(zone_details_sql)
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2, default=str)[:4000])
    else:
        print(f"Error: {r.status_code} {r.text[:200]}")

print("\n=== SEMINOLE I DIAGNOSIS ===")
seminole_sql = """
-- Find seminole rows that fail card_complete
WITH card_check AS (
    SELECT 
        mca.case_number,
        mca.parcel_id,
        mca.property_address,
        mca.latitude,
        mca.longitude,
        mca.assessed_value,
        mca.market_value,
        (mca.property_address IS NOT NULL) as has_addr,
        (mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL) as has_geo,
        (COALESCE(mca.assessed_value, mca.market_value) IS NOT NULL) as has_value,
        (pz.parcel_id IS NOT NULL) as has_zone,
        pz.zone_code
    FROM multi_county_auctions mca
    LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
    WHERE mca.county = 'seminole'
)
SELECT case_number, parcel_id, has_addr, has_geo, has_value, has_zone, zone_code,
       property_address,
       CASE 
         WHEN has_addr AND has_geo AND has_value AND has_zone THEN 'COMPLETE'
         ELSE 'INCOMPLETE'
       END as card_status
FROM card_check
WHERE NOT (has_addr AND has_geo AND has_value AND has_zone)
ORDER BY case_number;
"""

if ACCESS_TOKEN:
    r = mgmt_sql(seminole_sql)
    if r.status_code == 200:
        data = r.json()
        print(f"Seminole I gap rows ({len(data)} total):")
        print(json.dumps(data, indent=2, default=str)[:4000])
    else:
        print(f"Error: {r.status_code} {r.text[:200]}")

print("\n=== FLAGLER I DIAGNOSIS ===")
flagler_i_sql = """
-- Find flagler rows that fail card_complete
WITH card_check AS (
    SELECT 
        mca.case_number,
        mca.parcel_id,
        mca.property_address,
        mca.latitude,
        mca.longitude,
        mca.assessed_value,
        mca.market_value,
        (mca.property_address IS NOT NULL) as has_addr,
        (mca.latitude IS NOT NULL AND mca.longitude IS NOT NULL) as has_geo,
        (COALESCE(mca.assessed_value, mca.market_value) IS NOT NULL) as has_value,
        (pz.parcel_id IS NOT NULL) as has_zone,
        pz.zone_code
    FROM multi_county_auctions mca
    LEFT JOIN parcel_zones pz ON pz.parcel_id = mca.parcel_id
    WHERE mca.county = 'flagler'
)
SELECT case_number, parcel_id, has_addr, has_geo, has_value, has_zone, zone_code,
       LEFT(property_address, 60) as addr_preview
FROM card_check
WHERE NOT (has_addr AND has_geo AND has_value AND has_zone)
ORDER BY case_number;
"""

if ACCESS_TOKEN:
    r = mgmt_sql(flagler_i_sql)
    if r.status_code == 200:
        data = r.json()
        print(f"Flagler I gap rows ({len(data)} total):")
        print(json.dumps(data, indent=2, default=str)[:4000])
    else:
        print(f"Error: {r.status_code} {r.text[:200]}")

print("\n=== FLAGLER C/D DIAGNOSIS ===")
flagler_cd_sql = """
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE parity_status = 'matched_clean') as matched_clean,
    COUNT(*) FILTER (WHERE parity_status = 'matched_any') as matched_any,
    COUNT(*) FILTER (WHERE parity_status IS NULL) as unmatched,
    COUNT(*) FILTER (WHERE parity_status NOT IN ('matched_clean','matched_any') AND parity_status IS NOT NULL) as other
FROM multi_county_auctions
WHERE county = 'flagler';
"""

if ACCESS_TOKEN:
    r = mgmt_sql(flagler_cd_sql)
    if r.status_code == 200:
        data = r.json()
        print(json.dumps(data, indent=2, default=str))

print("\n=== SEMINOLE I ARCGIS LOOKUP ===")
print("Will try scpafl.org ArcGIS for seminole gap rows...")

print("\n=== DIAGNOSIS COMPLETE ===")
print("Check output above, then apply the fix migration.")
