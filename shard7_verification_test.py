#!/usr/bin/env python3
"""
SHARD-7 Gold Standard Verification - osceola, flagler, okaloosa, columbia, madison
Verifies current county metrics and identifies priority targets
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

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# SHARD-7 assigned counties
ASSIGNED_COUNTIES = ['osceola', 'flagler', 'okaloosa', 'columbia', 'madison']

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
        
        # Set timeout first as per HARD GUARDRAILS
        client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": "SET statement_timeout = 0;"}
        )
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"\n--- {county_slug.upper()} EVALUATION ---")
            
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass')
                    if is_pass:
                        pass_count += 1
                    status = "✅" if is_pass else "❌"
                    print(f"  {letter}: {status} {metric}")
                
                print(f"  TOTAL: {pass_count}/10")
                return result, pass_count
            else:
                print(f"  ⚠️ No evaluation data returned")
                return None, 0
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None, 0
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None, 0

def get_current_gold_standard_status():
    """Get current Gold Standard metrics for our assigned counties"""
    
    try:
        client = httpx.Client(timeout=30)
        
        # Try to get latest gold standard status for our counties
        counties_filter = ','.join(f'"{c}"' for c in ASSIGNED_COUNTIES)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=30"
        
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

def prioritize_targets():
    """Evaluate all shard counties and prioritize highest-leverage targets"""
    print("\n=== SHARD-7 PRIORITY ANALYSIS ===")
    
    county_scores = {}
    
    for county in ASSIGNED_COUNTIES:
        result, pass_count = evaluate_county_current(county)
        county_scores[county] = {
            'pass_count': pass_count,
            'evaluation': result
        }
    
    # Sort by pass count (ascending) to prioritize counties closest to gold
    sorted_counties = sorted(county_scores.items(), key=lambda x: x[1]['pass_count'], reverse=True)
    
    print("\n=== PRIORITY ORDER (highest impact first) ===")
    for i, (county, data) in enumerate(sorted_counties, 1):
        score = data['pass_count']
        print(f"{i}. {county.upper()}: {score}/10 passes")
        
        # Identify failing letters
        if data['evaluation']:
            failing_letters = []
            for letter_data in data['evaluation']:
                if not letter_data.get('pass'):
                    letter = letter_data.get('letter')
                    metric = letter_data.get('metric')
                    failing_letters.append(f"{letter}({metric})")
            
            if failing_letters:
                print(f"   Failing: {', '.join(failing_letters)}")
    
    return sorted_counties

if __name__ == "__main__":
    print("=== SHARD-7 GOLD STANDARD VERIFICATION ===")
    print("Counties: osceola, flagler, okaloosa, columbia, madison")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Current Gold Standard Status ===")
    status = get_current_gold_standard_status()
    if status:
        for county, data in status.items():
            print(f"\n{county}:")
            print(f"  Loop run: {data.get('loop_run_id')}")
            print(f"  Pass count: {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== Fresh County Evaluations & Priority Analysis ===")
    prioritize_targets()
    
    print("\n=== NEXT STEPS ===")
    print("1. Focus on highest-scoring counties first (closest to gold)")
    print("2. Address high-impact failing letters: B (verified outcomes), I (property cards), J (deal thesis)")
    print("3. Columbia & Madison need initial A-lane setup")
    print("4. Verify improvements with: SELECT public.pencil_dod_evaluate_county('<county>');")