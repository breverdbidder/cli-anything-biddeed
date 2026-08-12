#!/usr/bin/env python3
"""
Lake County Gold Standard session check script.
Queries live Supabase DB for current state.
"""
import os
import json
import urllib.request
import urllib.error
import sys

TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
REF = "mocerqjnksmhcjzxrewo"

def run_sql(query):
    if not TOKEN:
        print("ERROR: SUPABASE_ACCESS_TOKEN not set")
        return None
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        data=body,
        method="POST"
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP ERROR {e.code}: {e.read().decode()[:500]}")
        return None

def main():
    print("=== Lake County Gold Standard Current State ===")
    
    result = run_sql("SELECT public.pencil_dod_evaluate_county('lake')")
    if result:
        print("pencil_dod_evaluate_county('lake'):")
        print(json.dumps(result, indent=2))
    
    print("\n=== Lake County parity breakdown ===")
    result2 = run_sql("""
        SET statement_timeout = 0;
        SELECT 
            parity_status,
            COUNT(*) as cnt,
            array_agg(case_number ORDER BY case_number) as cases
        FROM multi_county_auctions
        WHERE lower(county) = 'lake'
        GROUP BY parity_status
        ORDER BY cnt DESC
    """)
    if result2:
        print(json.dumps(result2, indent=2)[:5000])

    print("\n=== Lake County unlinked parcels (E) ===")
    result3 = run_sql("""
        SELECT case_number, property_address, parcel_id, auction_status
        FROM multi_county_auctions
        WHERE lower(county) = 'lake'
          AND parcel_id IS NULL
        ORDER BY case_number
        LIMIT 20
    """)
    if result3:
        print(json.dumps(result3, indent=2)[:3000])

    print("\n=== Lake County bid_decisions (J) ===")
    result4 = run_sql("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE ml_score IS NOT NULL) as has_ml_score,
            COUNT(*) FILTER (WHERE factors IS NOT NULL AND factors->>'distress_location' IS NOT NULL) as has_factors
        FROM bid_decisions
        WHERE county_slug = 'lake'
    """)
    if result4:
        print(json.dumps(result4, indent=2))

    print("\n=== Lake County G zoning status ===")
    result5 = run_sql("""
        SELECT 
            zd.jurisdiction_id,
            j.name as jurisdiction_name,
            COUNT(DISTINCT zd.id) as district_count,
            COUNT(CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 1 END) as has_density,
            COUNT(CASE WHEN zs.max_far IS NOT NULL THEN 1 END) as has_far
        FROM zoning_districts zd
        JOIN jurisdictions j ON j.id = zd.jurisdiction_id
        LEFT JOIN zone_standards zs ON zs.zone_district_id = zd.id
        WHERE j.county_slug = 'lake'
        GROUP BY zd.jurisdiction_id, j.name
        ORDER BY district_count DESC
    """)
    if result5:
        print(json.dumps(result5, indent=2)[:3000])

if __name__ == "__main__":
    main()
