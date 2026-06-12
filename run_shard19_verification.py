#!/usr/bin/env python3
"""
SHARD-19 Gold Standard Verification for Issue #7607
Counties: charlotte, citrus, broward

Based on existing test_db_connection.py pattern
"""
import os
import sys
import json
from datetime import datetime, timezone

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - installing...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'httpx'])
    import httpx

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")
print(f"API Key length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Available environment variables containing 'SUPA':")
    for key, value in os.environ.items():
        if 'SUPA' in key.upper():
            print(f"  {key}: {value[:20] if value else 'None'}...")
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
    """Run the pencil_dod_evaluate_county function for a single county - VERIFIED pattern"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function - use county_name parameter based on function signature
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
                    is_pass = letter_data.get('pass', False)
                    if is_pass:
                        pass_count += 1
                    status = "✅ PASS" if is_pass else "❌ FAIL"
                    detail = letter_data.get('detail', '')
                    print(f"  {letter}: {status} metric={metric} [{detail}]")
                print(f"  TOTAL: {pass_count}/10 letters passing")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def analyze_priority_fixes(county, evaluation):
    """Analyze which letters need priority fixes based on briefing"""
    if not evaluation or not isinstance(evaluation, list):
        return {"priority": "NO_DATA", "reason": "No evaluation data"}
    
    failing_letters = []
    metrics = {}
    
    for letter_data in evaluation:
        letter = letter_data.get('letter', '?')
        is_pass = letter_data.get('pass', False)
        metric = letter_data.get('metric')
        
        metrics[letter] = {
            'pass': is_pass,
            'metric': metric,
            'detail': letter_data.get('detail', '')
        }
        
        if not is_pass:
            failing_letters.append(letter)
    
    # Priority analysis based on briefing
    priority_map = {
        # Brevard Sprint Order from briefing
        'C': "C_D_ROOT_CAUSE",      # Parity clean issues  
        'D': "C_D_ROOT_CAUSE",      # Parity any issues
        'J': "J_GENERATOR",         # bid_decisions pipeline
        'G': "G_HIT_LIST",          # zone_standards backfill
        'B': "B_RECONCILIATION"     # verified_outcomes anomaly
    }
    
    # Find highest priority failing letter
    for letter in ['C', 'D', 'J', 'G', 'B', 'E', 'F', 'I', 'A', 'H']:
        if letter in failing_letters:
            return {
                "priority": priority_map.get(letter, "GENERAL_FIX"),
                "failing_letters": failing_letters,
                "primary_letter": letter,
                "metrics": metrics
            }
    
    return {
        "priority": "MAINTENANCE",
        "failing_letters": failing_letters,
        "metrics": metrics
    }

if __name__ == "__main__":
    print("=== SHARD-19 GOLD STANDARD VERIFICATION ===")
    print(f"Run 19 for Issue #7607 - {datetime.now(timezone.utc).isoformat()}")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Fresh County Evaluations ===")
    assigned_counties = ['charlotte', 'citrus', 'broward']
    results = {}
    
    for county in assigned_counties:
        print(f"\n--- {county} ---")
        evaluation = evaluate_county_current(county)
        
        if evaluation:
            results[county] = {
                'evaluation': evaluation,
                'priority_analysis': analyze_priority_fixes(county, evaluation),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            analysis = results[county]['priority_analysis']
            print(f"  Priority: {analysis.get('priority')}")
            print(f"  Primary letter: {analysis.get('primary_letter', 'none')}")
        else:
            results[county] = {
                'evaluation': None,
                'error': 'Failed to retrieve evaluation'
            }
    
    print("\n=== VERIFICATION SUMMARY ===")
    print(json.dumps(results, indent=2, default=str))
    
    # Save results for next phase
    with open("/tmp/shard19_verification.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to /tmp/shard19_verification.json")
    print("Ready for execution phase...")