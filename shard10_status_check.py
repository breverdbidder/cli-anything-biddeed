#!/usr/bin/env python3
"""
SHARD-10 Status Check: sarasota, hernando, pasco, franklin, union
Verify current metrics for autonomous session planning
"""
import os
import sys
import json
from datetime import datetime

try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"SHARD-10 STATUS CHECK - {datetime.now().isoformat()}")
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

def evaluate_shard10_counties():
    """Evaluate all SHARD-10 counties: sarasota, hernando, pasco, franklin, union"""
    shard10_counties = ['sarasota', 'hernando', 'pasco', 'franklin', 'union']
    results = {}
    
    try:
        client = httpx.Client(timeout=60)
        
        for county in shard10_counties:
            print(f"\n📊 EVALUATING {county.upper()}:")
            
            # Call the pencil_dod_evaluate_county function
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            
            if r.status_code == 200:
                result = r.json()
                results[county] = result
                
                pass_count = 0
                letter_details = {}
                
                if isinstance(result, list) and len(result) > 0:
                    for letter_data in result:
                        letter = letter_data.get('letter', '?')
                        metric = letter_data.get('metric')
                        is_pass = letter_data.get('pass', False)
                        
                        if is_pass:
                            pass_count += 1
                            
                        status = "✅ PASS" if is_pass else "❌ FAIL"
                        print(f"  {letter}: {status} metric={metric}")
                        
                        letter_details[letter] = {
                            'metric': metric,
                            'pass': is_pass,
                            'raw_data': letter_data
                        }
                
                print(f"  SCORE: {pass_count}/10")
                results[county]['summary'] = {
                    'pass_count': pass_count,
                    'total': 10,
                    'letters': letter_details
                }
                
            else:
                print(f"❌ Failed to evaluate {county}: {r.status_code} - {r.text}")
                results[county] = {'error': r.text}
                
    except Exception as e:
        print(f"❌ Error during evaluation: {e}")
        return None
        
    return results

def analyze_work_priorities(results):
    """Analyze results and determine work priorities per CRITERION-PARALLEL PIVOT"""
    print(f"\n🎯 SHARD-10 WORK PRIORITY ANALYSIS:")
    
    priority_counties = []
    zero_counties = []
    
    for county, data in results.items():
        if 'error' in data:
            print(f"❌ {county}: Database error - cannot analyze")
            continue
            
        summary = data.get('summary', {})
        pass_count = summary.get('pass_count', 0)
        
        if pass_count == 0:
            zero_counties.append(county)
        else:
            priority_counties.append((county, pass_count))
    
    # Sort by pass count (highest first for optimization)
    priority_counties.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📈 WORK ORDER (CRITERION-PARALLEL PIVOT):")
    
    if priority_counties:
        print(f"\n1. OPTIMIZATION TARGETS (existing passes):")
        for county, passes in priority_counties:
            letters = results[county]['summary']['letters']
            failing_letters = [l for l, d in letters.items() if not d['pass']]
            print(f"  {county}: {passes}/10 - Fix {len(failing_letters)} letters: {', '.join(failing_letters)}")
    
    if zero_counties:
        print(f"\n2. BOOTSTRAP TARGETS (zero passes):")
        for county in zero_counties:
            print(f"  {county}: 0/10 - Full pipeline bootstrap needed")
    
    # Analyze specific letter patterns
    print(f"\n📋 LETTER-SPECIFIC PATTERNS:")
    letter_analysis = {}
    for county, data in results.items():
        if 'summary' in data:
            for letter, letter_data in data['summary']['letters'].items():
                if letter not in letter_analysis:
                    letter_analysis[letter] = {'pass': 0, 'fail': 0, 'counties': []}
                
                if letter_data['pass']:
                    letter_analysis[letter]['pass'] += 1
                else:
                    letter_analysis[letter]['fail'] += 1
                    letter_analysis[letter]['counties'].append(county)
    
    for letter in sorted(letter_analysis.keys()):
        data = letter_analysis[letter]
        if data['fail'] > 0:
            counties_str = ', '.join(data['counties'])
            print(f"  {letter}: {data['fail']}/{data['pass']+data['fail']} failing - {counties_str}")

def main():
    print("=== SHARD-10 GOLD STANDARD STATUS CHECK ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== EVALUATING SHARD-10 COUNTIES ===")
    results = evaluate_shard10_counties()
    
    if results:
        print(f"\n=== STORING RESULTS FOR SESSION PLANNING ===")
        
        # Save results to file for reference
        with open('shard10_current_status.json', 'w') as f:
            json.dump(results, f, indent=2)
        print("✅ Results saved to shard10_current_status.json")
        
        analyze_work_priorities(results)
        
        print(f"\n🚀 SESSION READY:")
        print(f"- Run time: {datetime.now().strftime('%H:%M:%S UTC')}")
        print(f"- Counties evaluated: {len(results)}")
        print(f"- Database connection: verified")
        print(f"- Results available for autonomous planning")
    else:
        print("❌ County evaluation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()