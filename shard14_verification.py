#!/usr/bin/env python3
"""
SHARD-14 Gold Standard Verification: volusia, lake, seminole, hamilton
Run 27 status check and metrics evaluation
"""
import os
import sys
import json
import httpx
from datetime import datetime

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# For debugging connection issues
print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY present: {bool(SUPABASE_KEY)}")
print(f"Environment SUPABASE_KEY starts with: {SUPABASE_KEY[:10] + '...' if SUPABASE_KEY else 'NOT_SET'}")

# Shard 14 assigned counties
ASSIGNED_COUNTIES = ['volusia', 'lake', 'seminole', 'hamilton']

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
            print(f"\n=== {county_slug.upper()} EVALUATION ===")
            pass_count = 0
            metrics_summary = {}
            
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passed = letter_data.get('pass', False)
                    status = "✅ PASS" if passed else "❌ FAIL"
                    
                    if passed:
                        pass_count += 1
                    
                    metrics_summary[letter] = {
                        'metric': metric,
                        'passed': passed,
                        'status': status
                    }
                    
                    print(f"    {letter}: {status} metric={metric}")
                
                print(f"\n{county_slug}: {pass_count}/10 letters passing")
                return {'county': county_slug, 'pass_count': pass_count, 'metrics': metrics_summary, 'raw': result}
            else:
                print(f"❌ No data returned for {county_slug}")
                return {'county': county_slug, 'pass_count': 0, 'metrics': {}, 'raw': None}
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_gold_standard_status():
    """Get current Gold Standard status for our assigned counties"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get latest status for our counties
        counties_filter = ','.join(f'"{c}"' for c in ASSIGNED_COUNTIES)
        url = f"{SUPABASE_URL}/rest/v1/gold_standard_county_status"
        params = f"select=*&county_slug=in.({counties_filter})&order=loop_run_id.desc&limit=20"
        
        r = client.get(f"{url}?{params}", headers=sb_headers())
        
        if r.status_code == 200:
            results = r.json()
            print(f"✅ Retrieved {len(results)} Gold Standard historical records")
            
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

def analyze_priorities(county_results):
    """Analyze current status and identify highest-leverage fixes"""
    print("\n=== PRIORITY ANALYSIS ===")
    
    priorities = {}
    
    for county_data in county_results:
        if not county_data:
            continue
            
        county = county_data['county']
        metrics = county_data['metrics']
        pass_count = county_data['pass_count']
        
        print(f"\n{county.upper()} ({pass_count}/10):")
        
        # Identify failing letters with highest leverage
        failing_letters = []
        for letter, data in metrics.items():
            if not data['passed']:
                failing_letters.append(letter)
                
        priorities[county] = {
            'pass_count': pass_count,
            'failing_letters': failing_letters,
            'metrics': metrics
        }
        
        if pass_count == 0:
            print(f"  🚨 BLANK SLATE: All letters failing - needs basic ingestion")
        elif pass_count < 3:
            print(f"  🔴 CRITICAL: Only {pass_count} passing - focus on A (coverage) first")
        elif pass_count < 7:
            print(f"  🟡 MODERATE: {pass_count} passing - focus on C/D parity, E linkage")
        else:
            print(f"  🟢 CLOSE: {pass_count} passing - focus on remaining gaps")
            
        print(f"  Failing letters: {', '.join(failing_letters)}")
        
    return priorities

if __name__ == "__main__":
    print("=== SHARD-14 GOLD STANDARD VERIFICATION ===")
    print(f"Counties: {', '.join(ASSIGNED_COUNTIES)}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== HISTORICAL STATUS CHECK ===")
    historical_status = get_gold_standard_status()
    if historical_status:
        for county, data in historical_status.items():
            print(f"{county}: Loop {data.get('loop_run_id')} - {data.get('pass_count', 'N/A')}/10")
    
    print("\n=== FRESH EVALUATION (VERIFIED) ===")
    current_results = []
    
    for county in ASSIGNED_COUNTIES:
        result = evaluate_county_current(county)
        if result:
            current_results.append(result)
    
    print("\n=== PRIORITY RECOMMENDATIONS ===")
    priorities = analyze_priorities(current_results)
    
    # Summary for session planning
    print(f"\n=== SHARD-14 SESSION SUMMARY ===")
    total_letters_passing = sum(r['pass_count'] for r in current_results if r)
    total_possible = len(ASSIGNED_COUNTIES) * 10
    
    print(f"Total progress: {total_letters_passing}/{total_possible} letters passing")
    print(f"Counties needing work: {len([c for c in current_results if c and c['pass_count'] < 10])}")
    
    # Highest leverage opportunities
    print(f"\nHIGHEST LEVERAGE FIXES:")
    for county_data in current_results:
        if county_data and county_data['pass_count'] < 10:
            county = county_data['county']
            failing = len(county_data['metrics']) - county_data['pass_count']
            print(f"  {county}: {failing} letters failing - check A/H first, then C/D/E")