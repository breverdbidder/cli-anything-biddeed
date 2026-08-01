#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-2 (run 7858) — Live evaluation script
Counties: indian_river, citrus, lee, liberty, columbia
dispatch_id: c3b1e7cc-af0b-4094-91ec-9367bb290d54
"""
import os
import sys
import json
import httpx

REF = "mocerqjnksmhcjzxrewo"
SUPABASE_URL = os.environ.get("SUPABASE_URL", f"https://{REF}.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN")

COUNTIES = ["indian_river", "citrus", "lee", "liberty", "columbia"]

def run_mgmt(query: str):
    if not TOKEN:
        return None, "NO_TOKEN"
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = httpx.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers=h,
        json={"query": query},
        timeout=120
    )
    return r.status_code, r.json() if r.status_code == 200 else r.text

def run_rest_rpc(fn_name: str, params: dict):
    if not SUPABASE_KEY:
        return None, "NO_KEY"
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    r = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{fn_name}",
        headers=h,
        json=params,
        timeout=120
    )
    return r.status_code, r.json() if r.status_code in (200, 201) else r.text

def evaluate_all():
    results = {}
    for county in COUNTIES:
        print(f"\n--- Evaluating {county} ---")
        status, data = run_rest_rpc("pencil_dod_evaluate_county", {"p_county": county})
        if status == 200:
            results[county] = data
            print(json.dumps(data, indent=2, default=str))
        else:
            status2, data2 = run_mgmt(f"SELECT public.pencil_dod_evaluate_county('{county}')")
            if status2 == 200:
                results[county] = data2
                print(json.dumps(data2, indent=2, default=str))
            else:
                results[county] = {"error": str(data), "mgmt_error": str(data2)}
                print(f"ERROR: REST={status}/{data}, MGMT={status2}/{data2}")
    return results

def lee_gap_investigation():
    """Query specific lee gap rows per last session's next-session priorities"""
    print("\n=== LEE GAP INVESTIGATION ===")
    
    q1 = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value, auction_status
    FROM multi_county_auctions
    WHERE county = 'lee'
      AND (parcel_id IS NULL OR parcel_id IN ('MULTIPLE PARCELS', 'Property Appraiser'))
    ORDER BY case_number
    LIMIT 30;
    """
    s, d = run_mgmt(q1)
    print(f"\nLee null/bad parcel rows: status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str)[:4000])

    q2 = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value
    FROM multi_county_auctions
    WHERE county = 'lee' AND case_number = '20-CA-005572';
    """
    s, d = run_mgmt(q2)
    print(f"\nLee 20-CA-005572 (Danpark Loop hypothesis): status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str))

    q3 = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value
    FROM multi_county_auctions
    WHERE county = 'lee' AND case_number IN ('25-CA-002593', '25-CA-003385');
    """
    s, d = run_mgmt(q3)
    print(f"\nLee dedup collision (25-CA-002593/003385): status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str))

def columbia_gap_investigation():
    """Query columbia I gap"""
    print("\n=== COLUMBIA GAP INVESTIGATION ===")
    
    q = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value, zone_code
    FROM v_zoning_gold_standard_card
    WHERE county = 'columbia'
    ORDER BY case_number;
    """
    s, d = run_mgmt(q)
    print(f"\nColumbia card view: status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str)[:3000])

def citrus_gap_investigation():
    """Query citrus I gap rows - pending judgment cases"""
    print("\n=== CITRUS GAP INVESTIGATION ===")
    
    q = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value, auction_date,
           judgment_amount
    FROM multi_county_auctions
    WHERE county = 'citrus'
      AND (parcel_id IS NULL
           OR parcel_id IN ('MULTIPLE PARCELS', 'Property Appraiser')
           OR property_address IS NULL)
    ORDER BY auction_date;
    """
    s, d = run_mgmt(q)
    print(f"\nCitrus gap rows: status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str)[:4000])

def indian_river_investigation():
    """Check indian_river I margin fragility"""
    print("\n=== INDIAN RIVER I MARGIN CHECK ===")
    
    q = """
    SELECT case_number, property_address, parcel_id, latitude, longitude, assessed_value, zone_code
    FROM v_zoning_gold_standard_card
    WHERE county = 'indian_river'
      AND (parcel_id IS NULL
           OR parcel_id IN ('MULTIPLE PARCELS', 'Property Appraiser')
           OR zone_code IS NULL
           OR property_address IS NULL)
    ORDER BY case_number;
    """
    s, d = run_mgmt(q)
    print(f"\nIndian River incomplete card rows: status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str)[:3000])

def write_campaign_checkpoint():
    """Write session checkpoint to gold_standard_campaign"""
    print("\n=== WRITING SESSION CHECKPOINT ===")
    
    q = """
    INSERT INTO public.gold_standard_campaign
      (dispatch_id, county_slug, session_start_at, exit_reason)
    VALUES
      ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'indian_river', NOW(), 'session_running'),
      ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'citrus', NOW(), 'session_running'),
      ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'lee', NOW(), 'session_running'),
      ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'liberty', NOW(), 'session_running'),
      ('c3b1e7cc-af0b-4094-91ec-9367bb290d54', 'columbia', NOW(), 'session_running')
    ON CONFLICT DO NOTHING;
    """
    s, d = run_mgmt(q)
    print(f"Checkpoint insert: status={s}")
    if s == 200:
        print(json.dumps(d, indent=2, default=str))

if __name__ == "__main__":
    print("=== SHARD-2 RUN 7858 LIVE EVALUATION ===")
    print(f"TOKEN present: {bool(TOKEN)}")
    print(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}")
    
    results = evaluate_all()
    
    if TOKEN:
        lee_gap_investigation()
        columbia_gap_investigation()
        citrus_gap_investigation()
        indian_river_investigation()
    
    print("\n=== SUMMARY ===")
    for county, data in results.items():
        if isinstance(data, dict) and "error" not in data:
            passes = sum(1 for k, v in data.items() if isinstance(v, dict) and v.get("pass"))
            print(f"{county}: {passes}/10 pass")
        else:
            print(f"{county}: ERROR - {data}")
