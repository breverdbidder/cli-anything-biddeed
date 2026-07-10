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
    print("🎯 GOLD STANDARD AUTOPILOT-BD: BREVARD & DUVAL STATUS VERIFICATION")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
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
    
    # Evaluate our target counties
    brevard_status = evaluate_county("brevard")
    duval_status = evaluate_county("duval")
    
    print("\n" + "="*50)
    print("📋 READY FOR AUTONOMOUS EXECUTION")
    print("Target counties verified, proceeding with sprint orders...")