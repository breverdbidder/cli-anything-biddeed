#!/usr/bin/env python3
"""
SHARD-8 Quick Check: Verify current status and next actions for assigned counties
Counties: hillsborough(29), alachua(1), nassau(45), desoto(14), monroe(44)
"""
import os
import sys
import json

try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Our assigned counties and their CO_NO mappings
# NOTE: Nassau (45) is assigned to SHARD-12, removed per PARALLEL-FLEET RULES
SHARD8_COUNTIES = {
    'hillsborough': 29,
    'alachua': 1, 
    'desoto': 14,
    'monroe': 44
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def check_auction_counts():
    """Check auction counts for our counties - A letter prerequisite"""
    print("\n=== A-LETTER PREREQUISITE CHECK ===")
    
    client = httpx.Client(timeout=30)
    
    for county_name, co_no in SHARD8_COUNTIES.items():
        try:
            # Check multi_county_auctions table
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count()&county=eq.{county_name}",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                count_data = r.json()
                if count_data and len(count_data) > 0:
                    count = count_data[0].get('count', 0)
                    if count > 0:
                        print(f"✅ {county_name}: {count:,} auctions (A-letter data exists)")
                    else:
                        print(f"❌ {county_name}: 0 auctions (needs A-letter ingestion)")
                else:
                    print(f"❌ {county_name}: 0 auctions (needs A-letter ingestion)")
            else:
                print(f"❌ {county_name}: Query failed ({r.status_code})")
                
        except Exception as e:
            print(f"❌ {county_name}: Error checking auctions - {e}")

def check_fl_counties_status():
    """Check fl_counties table for parcel counts"""
    print("\n=== FL_COUNTIES PARCEL STATUS ===")
    
    client = httpx.Client(timeout=30)
    
    try:
        co_nos = list(SHARD8_COUNTIES.values())
        co_filter = ','.join(str(x) for x in co_nos)
        
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?select=co_no,name,slug,total_parcels&co_no=in.({co_filter})",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            counties_data = r.json()
            for county in counties_data:
                co_no = county.get('co_no')
                name = county.get('name')
                total_parcels = county.get('total_parcels')
                
                if total_parcels and total_parcels > 0:
                    print(f"✅ {name}: {total_parcels:,} parcels in FL GIO")
                else:
                    print(f"❌ {name}: No parcel count (needs baseline ingestion)")
        else:
            print(f"❌ Failed to get fl_counties data: {r.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking fl_counties: {e}")

def run_pencil_evaluations():
    """Run fresh pencil_dod_evaluate_county for all assigned counties"""
    print("\n=== FRESH GOLD STANDARD EVALUATIONS (LIVE) ===")
    
    client = httpx.Client(timeout=60)
    results = {}
    
    for county_name, co_no in SHARD8_COUNTIES.items():
        try:
            print(f"\n--- {county_name} (CO_NO={co_no}) ---")
            
            # Call the RPC function
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county_name}
            )
            
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, list) and len(result) > 0:
                    passes = 0
                    for letter_data in result:
                        letter = letter_data.get('letter', '?')
                        metric = letter_data.get('metric')
                        is_pass = letter_data.get('pass', False)
                        status = "✅" if is_pass else "❌"
                        
                        print(f"  {letter}: {status} {metric}")
                        if is_pass:
                            passes += 1
                    
                    print(f"  TOTAL: {passes}/10 letters passing")
                    results[county_name] = {'passes': passes, 'detail': result}
                else:
                    print(f"  ❌ No evaluation data returned")
                    results[county_name] = {'passes': 0, 'detail': []}
            else:
                print(f"  ❌ Evaluation failed: {r.status_code} - {r.text}")
                results[county_name] = {'passes': 0, 'detail': []}
                
        except Exception as e:
            print(f"  ❌ Error evaluating {county_name}: {e}")
            results[county_name] = {'passes': 0, 'detail': []}
    
    return results

def generate_action_plan(evaluation_results):
    """Generate prioritized action plan based on results"""
    print("\n=== ACTION PLAN PRIORITIZATION ===")
    
    # Sort counties by pass count (lowest first = highest priority)
    sorted_counties = sorted(evaluation_results.items(), key=lambda x: x[1]['passes'])
    
    print("\n🎯 **PRIORITY ORDER** (lowest scores = highest priority):")
    for county_name, data in sorted_counties:
        passes = data['passes']
        co_no = SHARD8_COUNTIES[county_name]
        
        if passes == 0:
            print(f"1. **{county_name}** (CO_NO={co_no}): {passes}/10 - ZERO letters, needs A-letter basic ingestion")
        elif passes < 3:
            print(f"2. **{county_name}** (CO_NO={co_no}): {passes}/10 - Critical improvements needed")
        elif passes < 6:
            print(f"3. **{county_name}** (CO_NO={co_no}): {passes}/10 - Moderate improvements needed")
        else:
            print(f"4. **{county_name}** (CO_NO={co_no}): {passes}/10 - Fine-tuning needed")
    
    # Specific next actions
    print("\n🔧 **IMMEDIATE NEXT ACTIONS**:")
    
    zero_counties = [name for name, data in sorted_counties if data['passes'] == 0]
    if zero_counties:
        print(f"- Run A-letter ingestion for: {', '.join(zero_counties)}")
        print(f"  Commands: python3 scripts/ingest_county.py --county <co_no> --full")
        for county in zero_counties:
            co_no = SHARD8_COUNTIES[county]
            print(f"    python3 scripts/ingest_county.py --county {co_no} --full  # {county}")
    
    # Find counties with some progress
    partial_counties = [name for name, data in sorted_counties if 0 < data['passes'] < 10]
    if partial_counties:
        print(f"- Targeted improvements for: {', '.join(partial_counties)}")
        print(f"  Focus on failing letters from evaluation above")

if __name__ == "__main__":
    print("=== SHARD-8 COUNTY STATUS CHECK ===")
    print(f"Assigned Counties: {list(SHARD8_COUNTIES.keys())}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        sys.exit(1)
    
    # Check prerequisites
    check_auction_counts()
    check_fl_counties_status()
    
    # Get live evaluations
    results = run_pencil_evaluations()
    
    # Generate action plan
    generate_action_plan(results)
    
    print(f"\n=== STATUS: READY FOR AUTONOMOUS WORK ===")
    print("Use results above to prioritize next actions.")