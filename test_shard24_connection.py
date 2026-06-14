#!/usr/bin/env python3
"""
Test database connection and verify current status for shard 24 counties.
Targeting: citrus, broward, charlotte
"""

import os
import json
import sys

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = (os.environ.get("SUPABASE_KEY", "") or 
                os.environ.get("SUPABASE_SERVICE_KEY", "") or 
                os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

def sb_headers():
    """Supabase headers for REST API calls"""
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        return False
        
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        print(f"Connection status: {r.status_code}")
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
            print(f"✅ County evaluation for {county_slug}:")
            
            passing_count = 0
            letter_details = []
            
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passed = letter_data.get('pass', False)
                    if passed:
                        passing_count += 1
                    status = "✅" if passed else "❌"
                    print(f"  {letter}: {status} {metric}")
                    letter_details.append({
                        'letter': letter,
                        'metric': metric,
                        'passed': passed
                    })
            
            print(f"  Total passing: {passing_count}/10")
            return {
                'county': county_slug,
                'passing_count': passing_count,
                'total_count': 10,
                'letters': letter_details,
                'raw_result': result
            }
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def main():
    """Main function to test shard 24 counties"""
    print("=== SHARD 24 CONNECTION & VERIFICATION TEST ===")
    print("Targeting counties: citrus, broward, charlotte")
    print(f"Using Supabase URL: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    print()
    
    # Test database connection
    if not test_connection():
        sys.exit(1)
    
    # Test counties with fresh evaluation
    counties = ["citrus", "broward", "charlotte"]
    results = {}
    
    print("\n=== FRESH COUNTY EVALUATIONS (VERIFIED) ===")
    for county in counties:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county_current(county)
        if result:
            results[county] = result
    
    # Summary
    print(f"\n=== SESSION 24 SUMMARY (HONESTY PROTOCOL: VERIFIED) ===")
    print(f"Counties evaluated: {len(results)}/{len(counties)}")
    
    if results:
        for county, result in results.items():
            passing = result['passing_count']
            print(f"  {county}: {passing}/10 letters passing")
            
            # Identify failing letters for priority targeting
            failing_letters = [l['letter'] for l in result['letters'] if not l['passed']]
            if failing_letters:
                print(f"    Failing: {', '.join(failing_letters)}")
    
    print(f"\nSession ready for ULTRALOOP execution on failing letters")
    print(f"SHIP-TO-MAIN protocol: Direct commits, no PRs, immediate verification")
    
    return results

if __name__ == "__main__":
    main()