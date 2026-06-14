#!/usr/bin/env python3
"""
SHARD-7 County Status Verification
Counties: manatee, flagler, okaloosa, columbia, madison
"""

import httpx
import json
import os
import sys
from datetime import datetime

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug.upper()}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for letter_data in result if letter_data.get('pass'))
                print(f"   Overall: {pass_count}/10 letters passing")
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅ PASS" if letter_data.get('pass') else "❌ FAIL"
                    details = letter_data.get('details', '')
                    print(f"   {letter}: {status} metric={metric} [{details}]")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_gold_standard_status():
    """Get latest gold standard status for assigned counties"""
    assigned_counties = ['manatee', 'flagler', 'okaloosa', 'columbia', 'madison']
    
    try:
        client = httpx.Client(timeout=30)
        
        counties_filter = ','.join(f'"{c}"' for c in assigned_counties)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=25"
        
        r = client.get(f"{url}?{params}", headers=sb_headers())
        
        if r.status_code == 200:
            results = r.json()
            print(f"✅ Retrieved {len(results)} Gold Standard records")
            
            # Group by county and get latest for each
            latest_by_county = {}
            for record in results:
                county = record.get('county_slug')
                if county not in latest_by_county:
                    latest_by_county[county] = record
                    
            return latest_by_county
        else:
            print(f"❌ Failed to retrieve Gold Standard status: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error retrieving Gold Standard status: {e}")
        return None

def main():
    """Main verification function"""
    # Assigned SHARD-7 counties
    counties = ['manatee', 'flagler', 'okaloosa', 'columbia', 'madison']
    
    print("=== SHARD-7 COUNTY STATUS VERIFICATION ===")
    print(f"Session: 2026-06-14T16:00Z (Run 27)")
    print(f"Counties: {', '.join(counties)}")
    print()
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Historical Gold Standard Status ===")
    status = get_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== Fresh County Evaluations ===")
    for county in counties:
        print(f"\n--- {county} ---")
        evaluate_county_current(county)
        print("-" * 50)
    
    print("✅ Verification complete")

if __name__ == "__main__":
    main()