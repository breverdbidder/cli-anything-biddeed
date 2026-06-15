#!/usr/bin/env python3
"""
Shard-13 County Verification for GOLD STANDARD CAMPAIGN
Assigned counties: volusia, jackson, santa_rosa, gulf

Verify current metrics and start autonomous session work.
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - will need to install")
    sys.exit(1)

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    # Check GitHub Actions environment
    print("Available env vars:", [k for k in os.environ.keys() if 'SUPA' in k.upper()])
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
            if isinstance(result, list) and len(result) > 0:
                scores = {}
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅ PASS" if letter_data.get('pass') else "❌ FAIL"
                    detail = letter_data.get('detail', '')
                    scores[letter] = {
                        'metric': metric,
                        'pass': letter_data.get('pass'),
                        'detail': detail
                    }
                    print(f"  {letter}: {status} metric={metric} {detail}")
                return scores
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

if __name__ == "__main__":
    print("=== SHARD-13 County Verification ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== County Evaluations for GOLD STANDARD SHARD-13 ===")
    # Assigned counties from the issue brief
    assigned_counties = ['volusia', 'jackson', 'santa_rosa', 'gulf']
    
    county_results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        scores = evaluate_county_current(county)
        if scores:
            county_results[county] = scores
            
            # Calculate passing vs failing
            passing = len([l for l, data in scores.items() if data.get('pass')])
            total = len(scores)
            print(f"  Summary: {passing}/{total} letters passing")
    
    print("\n=== SUMMARY ===")
    for county, scores in county_results.items():
        passing = len([l for l, data in scores.items() if data.get('pass')])
        total = len(scores)
        print(f"{county}: {passing}/{total} letters passing")
        
        # Show critical failures (B, I, J)
        critical_letters = ['B', 'I', 'J']
        for letter in critical_letters:
            if letter in scores and not scores[letter].get('pass'):
                print(f"  CRITICAL FAIL: {letter} = {scores[letter].get('metric')}")
    
    # Save results for reference
    with open('/tmp/shard13_baseline.json', 'w') as f:
        json.dump(county_results, f, indent=2)
    
    print(f"\nBaseline results saved to /tmp/shard13_baseline.json")