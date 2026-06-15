#!/usr/bin/env python3
"""
SHARD-13 County Verification: volusia, jackson, santa_rosa, gulf
Quick connectivity test and baseline evaluation
"""
import os
import sys
import json

# Check for httpx
try:
    import httpx
    print("✅ httpx is available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Environment setup
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

print(f"Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase credentials found")
    print("Environment variables with 'SUP' in name:")
    for k, v in os.environ.items():
        if 'SUP' in k.upper():
            print(f"  {k}: {'[PRESENT]' if v else '[EMPTY]'}")
    sys.exit(1)

# Test connection
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

try:
    print(f"\n🔗 Testing connection to {SUPABASE_URL}")
    client = httpx.Client(timeout=30)
    
    # Test basic connection
    response = client.get(
        f"{SUPABASE_URL}/rest/v1/gold_standard_scoreboard?select=county_slug&limit=3",
        headers=headers
    )
    
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Database connection successful")
        print(f"Sample counties: {[row.get('county_slug') for row in data]}")
        
        # Quick test of county evaluation function for the assigned counties
        print("\n🔍 Testing county evaluations for SHARD-13 counties:")
        assigned_counties = ['volusia', 'jackson', 'santa_rosa', 'gulf']
        
        for county in assigned_counties:
            try:
                eval_response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers=headers,
                    json={"county_slug_arg": county}
                )
                
                if eval_response.status_code == 200:
                    result = eval_response.json()
                    if isinstance(result, list) and len(result) > 0:
                        passing = len([r for r in result if r.get('pass')])
                        total = len(result)
                        print(f"  {county}: {passing}/{total} letters passing")
                        
                        # Show critical failures
                        critical = ['B', 'I', 'J']
                        for letter_data in result:
                            letter = letter_data.get('letter')
                            if letter in critical and not letter_data.get('pass'):
                                metric = letter_data.get('metric')
                                print(f"    CRITICAL FAIL: {letter} = {metric}")
                    else:
                        print(f"  {county}: No evaluation data")
                else:
                    print(f"  {county}: Evaluation failed ({eval_response.status_code})")
                    
            except Exception as e:
                print(f"  {county}: Error - {e}")
        
        print("\n✅ Environment setup verification complete")
        print("Ready to execute autonomous session")
        
    else:
        print(f"❌ Connection failed: {response.text}")
        
    client.close()
    
except Exception as e:
    print(f"❌ Connection error: {e}")
    sys.exit(1)