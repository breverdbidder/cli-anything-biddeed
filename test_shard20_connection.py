#!/usr/bin/env python3
"""
SHARD-20 Database Connectivity Test
Counties: charlotte, citrus, broward
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - trying to continue with manual approach")
    sys.exit(1)

# Setup Supabase connection using environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")
print(f"API Key length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

# Show available environment variables for debugging
env_vars = [k for k in os.environ.keys() if 'SUPA' in k.upper() or 'DB' in k.upper()]
print(f"Available DB-related env vars: {env_vars}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Available environment variables:", [k for k in os.environ.keys() if any(term in k.upper() for term in ['SUPA', 'KEY', 'TOKEN', 'SECRET'])])
    sys.exit(1)

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
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            print(f"Response: {r.text[:200]}")
            return True
        else:
            print(f"❌ Database connection failed: {r.status_code}")
            print(f"Response: {r.text[:500]}")
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
            pass_count = 0
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passed = letter_data.get('pass', False)
                    if passed:
                        pass_count += 1
                    status = "✅" if passed else "❌"
                    print(f"  {letter}: {status} {metric}")
                print(f"  TOTAL: {pass_count}/10 letters passing")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code}")
            print(f"Response: {r.text[:500]}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-20 Database Connectivity Test ===")
    
    if not test_connection():
        print("❌ Basic connection failed - cannot proceed with evaluations")
        sys.exit(1)
    
    print("\n=== Fresh County Evaluations (SHARD-20) ===")
    assigned_counties = ['charlotte', 'citrus', 'broward']
    
    all_results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county_current(county)
        all_results[county] = result
    
    # Summary
    print("\n" + "="*60)
    print("SHARD-20 SUMMARY")
    print("="*60)
    
    for county in assigned_counties:
        result = all_results[county]
        if result and isinstance(result, list):
            pass_count = sum(1 for item in result if item.get('pass', False))
            print(f"{county.upper()}: {pass_count}/10 letters passing")
        else:
            print(f"{county.upper()}: EVALUATION_FAILED")