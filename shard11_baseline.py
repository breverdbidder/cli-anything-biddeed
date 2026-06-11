#!/usr/bin/env python3
"""
SHARD-11 BASELINE EVALUATION
Get current status for: orange, baker, miami_dade, gadsden, wakulla
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
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection 
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    # Try to get from GitHub Actions secrets context
    print("Checking for GitHub Actions environment...")
    # In GitHub Actions, secrets are passed as environment variables
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
            
            letter_results = {}
            pass_count = 0
            
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    detail = letter_data.get('detail', '')
                    status = "✅ PASS" if is_pass else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric} [{detail}]")
                    
                    letter_results[letter] = {
                        'pass': is_pass,
                        'metric': metric,
                        'detail': detail
                    }
                    
                    if is_pass:
                        pass_count += 1
                        
            print(f"  TOTAL: {pass_count}/10 letters passing")
            
            return {
                'county': county_slug,
                'pass_count': pass_count,
                'letters': letter_results,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return {
                'county': county_slug,
                'error': f"HTTP {r.status_code}: {r.text}",
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return {
            'county': county_slug,
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

def analyze_priorities(results):
    """Analyze results and identify priority work"""
    print("\n" + "="*60)
    print("🎯 PRIORITY ANALYSIS")
    print("="*60)
    
    priorities = []
    
    for county_result in results:
        county = county_result['county']
        
        if county_result.get('error'):
            print(f"{county}: ⚠️ Evaluation failed - {county_result['error']}")
            priorities.append((county, 1000, 0, "EVALUATION_FAILED"))  # Highest priority for broken evaluation
            continue
            
        pass_count = county_result.get('pass_count', 0)
        letters = county_result.get('letters', {})
        
        # Priority scoring
        priority_score = (10 - pass_count) * 10  # Base score from failures
        priority_desc = []
        
        # Critical letter analysis
        critical_fails = []
        if not letters.get('B', {}).get('pass', True):  # Verified outcomes
            priority_score += 50
            critical_fails.append('B(verified)')
        if not letters.get('I', {}).get('pass', True):  # Property card completion  
            priority_score += 40
            critical_fails.append('I(property)')
        if not letters.get('J', {}).get('pass', True):  # Deal completion
            priority_score += 30
            critical_fails.append('J(deals)')
        if not letters.get('E', {}).get('pass', True):  # Parcel linkage
            priority_score += 25
            critical_fails.append('E(parcels)')
        if not letters.get('H', {}).get('pass', True):  # Freshness
            priority_score += 20
            critical_fails.append('H(fresh)')
        
        priority_desc = f"Pass={pass_count}/10, Critical fails: {', '.join(critical_fails) if critical_fails else 'None'}"
        
        priorities.append((county, priority_score, pass_count, priority_desc))
        print(f"{county}: Score={priority_score} ({priority_desc})")
    
    # Sort by priority score (highest first)
    priorities.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📋 RECOMMENDED WORK ORDER:")
    for i, (county, score, passes, desc) in enumerate(priorities, 1):
        print(f"{i}. {county.upper()}: {desc}")
    
    return priorities

if __name__ == "__main__":
    print("🚀 SHARD-11 BASELINE EVALUATION")
    print("Counties: orange, baker, miami_dade, gadsden, wakulla")
    print("="*60)
    
    if not test_connection():
        sys.exit(1)
    
    print(f"\n=== FRESH COUNTY EVALUATIONS ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}) ===")
    
    # SHARD-11 assigned counties
    shard11_counties = ['orange', 'baker', 'miami_dade', 'gadsden', 'wakulla']
    results = []
    
    for county in shard11_counties:
        print(f"\n--- {county.upper()} ---")
        result = evaluate_county_current(county)
        results.append(result)
    
    # Analyze and prioritize
    priorities = analyze_priorities(results)
    
    # Save baseline for session tracking
    baseline_data = {
        'session_start': datetime.now(timezone.utc).isoformat(),
        'shard': 'SHARD-11',
        'counties': shard11_counties,
        'evaluations': results,
        'priorities': [(county, score, passes, desc) for county, score, passes, desc in priorities]
    }
    
    with open('shard11_baseline.json', 'w') as f:
        json.dump(baseline_data, f, indent=2)
    
    print(f"\n✅ Baseline saved to shard11_baseline.json")
    print(f"🎯 Ready to begin targeted improvements for {len(priorities)} counties")
    print(f"⏱️  Session start: {baseline_data['session_start']}")