#!/usr/bin/env python3
"""
Verify current status for brevard and duval counties
"""
import os
import sys
import httpx
import json

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co" 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for brevard or duval"""
    try:
        client = httpx.Client(timeout=60)
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        print(f"\n=== {county_slug.upper()} CURRENT STATUS ===")
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    status = "✅" if passes else "❌"
                    print(f"  {letter}: {status} {metric}")
                print(f"\nScore: {pass_count}/10")
                return result
            else:
                print(f"  ❌ No data returned for {county_slug}")
                return None
        else:
            print(f"  ❌ API error {r.status_code}: {r.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

if __name__ == "__main__":
    print("🎯 GOLD STANDARD SHARD-7: LEON, CLAY, MIAMI_DADE, COLUMBIA, MADISON STATUS VERIFICATION")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        # Try common secret names in GitHub Actions
        SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
        if not SUPABASE_KEY:
            print("❌ No Supabase keys found in environment")
            sys.exit(1)
        else:
            print("✅ Found alternative Supabase key")
    
    # Test connection
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)
    
    # Evaluate our assigned counties for SHARD-7
    assigned_counties = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']
    
    for county in assigned_counties:
        evaluate_county(county)
    
    print("\n" + "="*50)
    print("📋 SHARD-7 STATUS VERIFICATION COMPLETE")
    print("Ready for autonomous execution on assigned counties...")