#!/usr/bin/env python3
"""
Simple county check using curl - no dependencies
"""
import subprocess
import os
import json

def check_county_with_curl(county_slug):
    """Check county status using curl instead of httpx"""
    supabase_url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
    supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not supabase_key:
        print("❌ No Supabase key available")
        return None
    
    try:
        # Call the evaluation function via curl
        cmd = [
            "curl", "-s",
            "-X", "POST",
            f"{supabase_url}/rest/v1/rpc/pencil_dod_evaluate_county",
            "-H", f"apikey: {supabase_key}",
            "-H", f"Authorization: Bearer {supabase_key}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({"county_slug_arg": county_slug})
        ]
        
        print(f"Checking {county_slug} metrics...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                pass_count = sum(1 for item in data if item.get('pass', False))
                
                print(f"\n=== {county_slug.upper()} METRICS ===")
                for item in data:
                    letter = item.get('letter', '?')
                    metric = item.get('metric')
                    passed = item.get('pass', False)
                    status = "✅" if passed else "❌"
                    print(f"  {letter}: {status} {metric}")
                
                print(f"\nPASS COUNT: {pass_count}/10")
                return {'pass_count': pass_count, 'data': data}
                
            except json.JSONDecodeError as e:
                print(f"❌ JSON decode error: {e}")
                print(f"Raw response: {result.stdout}")
                return None
        else:
            print(f"❌ Curl failed: {result.returncode}")
            print(f"STDERR: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking {county_slug}: {e}")
        return None

def main():
    """Check all shard 14 counties"""
    counties = ['hamilton', 'lake', 'seminole', 'volusia']
    
    print("=== SHARD-14 COUNTY STATUS CHECK ===")
    
    results = {}
    for county in counties:
        result = check_county_with_curl(county)
        results[county] = result
        
        if result:
            print(f"{county}: {result['pass_count']}/10 letters passing")
        else:
            print(f"{county}: CHECK FAILED")
        print()
    
    return results

if __name__ == "__main__":
    main()