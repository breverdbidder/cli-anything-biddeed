#!/usr/bin/env python3
"""
Verify current Gold Standard status for Shard 24: brevard and duval counties
Run 24 as specified in issue #7715
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Note: This may be expected in GitHub Actions - will try with empty auth")

def sb_headers():
    headers = {
        "Content-Type": "application/json"
    }
    if SUPABASE_KEY:
        headers.update({
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}"
        })
    return headers

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
    print(f"\n🔍 Evaluating {county_slug} county...")
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
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    threshold = letter_data.get('threshold')
                    passed = letter_data.get('pass', False)
                    if passed:
                        pass_count += 1
                    
                    status_emoji = "✅" if passed else "❌"
                    metric_str = f"{metric:.1f}" if metric is not None else "NULL"
                    threshold_str = f" (threshold: {threshold})" if threshold is not None else ""
                    print(f"  {letter}: {status_emoji} {metric_str}{threshold_str}")
                    
                print(f"\nScore: {pass_count}/10")
                return result, pass_count
            else:
                print("No evaluation data returned")
                return None, 0
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None, 0
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None, 0

def main():
    print("=== SHARD 24 VERIFICATION: BREVARD & DUVAL ===")
    print("Run 24 - Gold Standard Autopilot Session")
    
    print("\n=== Database Connectivity Test ===")
    if not test_connection():
        print("Connection failed - continuing anyway in case of auth issues")
    
    # Our assigned counties for this shard
    target_counties = ['brevard', 'duval']
    
    print("\n=== Fresh County Evaluations ===")
    results = {}
    
    for county in target_counties:
        print(f"\n{'='*50}")
        result, score = evaluate_county_current(county)
        results[county] = {
            'result': result,
            'score': score
        }
    
    print(f"\n{'='*50}")
    print("=== SUMMARY ===")
    for county, data in results.items():
        score = data['score']
        print(f"{county.upper()}: {score}/10")
    
    print("\nNext steps:")
    print("1. Work Brevard priority: C/D root cause → J generator → G hitlist → B reconciliation")
    print("2. Work Duval priority: G+I substrate → C/D root cause → J generator → B reconciliation")
    print("3. Use ULTRALOOP verification protocols")
    print("4. Commit directly to main branch per SHIP-TO-MAIN mandate")

if __name__ == "__main__":
    main()