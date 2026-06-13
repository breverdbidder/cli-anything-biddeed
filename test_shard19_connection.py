#!/usr/bin/env python3
"""
Test database connectivity for SHARD-19 (charlotte, citrus, broward) 
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection using environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-19 counties from issue brief
SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")
print(f"Target counties: {', '.join(SHARD19_COUNTIES)}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        # Check all environment variables for debugging
        print("Available env vars with 'SUPABASE' or 'DB':")
        for key in os.environ.keys():
            if 'SUPABASE' in key or 'DB' in key:
                print(f"  {key}")
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
        
        # Try both parameter patterns used in other scripts
        for param_name in ["county_slug_arg", "county_name"]:
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={param_name: county_slug}
            )
            
            if r.status_code == 200:
                result = r.json()
                print(f"✅ County evaluation for {county_slug} using parameter '{param_name}':")
                if isinstance(result, list) and len(result) > 0:
                    total_pass = sum(1 for item in result if item.get('pass', False))
                    print(f"  Score: {total_pass}/10")
                    for letter_data in result:
                        letter = letter_data.get('letter', '?')
                        metric = letter_data.get('metric')
                        status = "✅" if letter_data.get('pass') else "❌"
                        context = letter_data.get('context', {})
                        
                        # Extract key context info for failed letters
                        context_str = ""
                        if not letter_data.get('pass') and context:
                            ctx_parts = []
                            for key in ['fc', 'td', 'verified', 'closed_sold', 'matched_clean', 'matched_any', 'parcel_linked']:
                                if key in context:
                                    ctx_parts.append(f"{key}={context[key]}")
                            if ctx_parts:
                                context_str = f" [{' '.join(ctx_parts)}]"
                        
                        print(f"  {letter}: {status} {metric}{context_str}")
                return result
            elif r.status_code != 400:  # Not a parameter issue
                print(f"❌ Failed to evaluate county {county_slug} with {param_name}: {r.status_code} - {r.text}")
                return None
                
        print(f"❌ Failed to evaluate county {county_slug} with both parameter patterns")
        return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-19 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== SHARD-19 County Evaluations ===")
    county_results = {}
    for county in SHARD19_COUNTIES:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county_current(county)
        county_results[county] = result
        
    print(f"\n=== SUMMARY ===")
    print("From issue brief expected:")
    print("charlotte (3/10): A✓ H✓ | B❌ null | C❌ 10.1 | D✓ 97.4 | E❌ 43.8 | F❌ 2.1 | G❌ null | I❌ null | J❌ 0.0")
    print("citrus (3/10): A✓ H✓ E✓ | B❌ null | C❌ 9.5 | D❌ 75.3 | E✓ 95.3 | F❌ 6.1 | G❌ null | I❌ null | J❌ 0.0")  
    print("broward (2/10): A✓ H✓ | B❌ null | C❌ 19.4 | D❌ 47.7 | E❌ 20.6 | F❌ 2.5 | G❌ null | I❌ null | J❌ 0.0")