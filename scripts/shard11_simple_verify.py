#!/usr/bin/env python3
"""
SHARD-11 Simple Verification 
Check current metrics using minimal dependencies
"""
import os
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def supabase_rpc(function_name, params=None):
    """Call Supabase RPC function"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{SUPABASE_URL}/rest/v1/rpc/{function_name}"
    data = json.dumps(params or {}).encode()
    
    try:
        req = Request(url, data=data, headers=headers)
        with urlopen(req, timeout=30) as response:
            if response.status == 200:
                return json.loads(response.read().decode())
            else:
                print(f"RPC {function_name} failed: HTTP {response.status}")
                return None
    except Exception as e:
        print(f"RPC {function_name} error: {e}")
        return None

def verify_county(county):
    """Verify single county using pencil_dod_evaluate_county"""
    print(f"\n📊 Verifying {county}...")
    
    result = supabase_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
    
    if not result:
        print(f"❌ {county}: Verification failed")
        return {}
    
    if isinstance(result, list):
        letters = {}
        for item in result:
            if isinstance(item, dict):
                letter = item.get('letter')
                passed = item.get('pass', False)
                metric = item.get('metric')
                
                status = "✅" if passed else "❌"
                letters[letter] = {
                    'pass': passed,
                    'metric': metric,
                    'status': status
                }
                
                print(f"  {letter}: {status} {metric}")
        
        pass_count = sum(1 for l in letters.values() if l['pass'])
        print(f"  📈 {county}: {pass_count}/10 letters passing")
        
        return {'letters': letters, 'pass_count': pass_count}
    else:
        print(f"  ✅ {county}: {result}")
        return {'result': result}

def main():
    print("🔍 SHARD-11 Simple Verification")
    print("="*50)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found")
        return
    
    counties = ['manatee', 'washington', 'miami_dade', 'gadsden', 'wakulla']
    results = {}
    
    for county in counties:
        results[county] = verify_county(county)
    
    # Summary
    print(f"\n{'='*50}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*50}")
    
    for county, data in results.items():
        pass_count = data.get('pass_count', '?')
        print(f"{county:12} : {pass_count}/10")
    
    print(f"\n✅ Verification completed for {len(counties)} counties")

if __name__ == "__main__":
    main()