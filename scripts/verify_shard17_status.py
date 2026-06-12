#!/usr/bin/env python3
"""
SHARD-17 STATUS VERIFICATION
Quick verification of current Gold Standard status for charlotte, citrus, broward
"""
import requests
import os
import sys

# Supabase connection  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def verify_county(county_slug):
    """Verify a single county using the pencil_dod_evaluate_county function"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result and isinstance(result, list):
                pass_count = sum(1 for item in result if item.get('pass'))
                failing_letters = [item.get('letter') for item in result if not item.get('pass')]
                
                print(f"\n{county_slug.upper()}:")
                print(f"  Score: {pass_count}/10")
                print(f"  Status: {'✅ PASSING' if pass_count >= 7 else '❌ FAILING'}")
                
                if failing_letters:
                    print(f"  Failing Letters: {', '.join(failing_letters)}")
                    
                # Show critical letter details
                for item in result:
                    letter = item.get('letter')
                    if letter in ['B', 'I', 'J']:  # Critical letters
                        status = "✅" if item.get('pass') else "❌"
                        metric = item.get('metric', 'N/A')
                        print(f"    {letter} (Critical): {status} {metric}")
                
                return pass_count
                
        else:
            print(f"❌ Failed to evaluate {county_slug}: {response.status_code}")
            return 0
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return 0

def main():
    print("🎯 SHARD-17 STATUS VERIFICATION")
    print("=" * 40)
    print("Counties: charlotte, citrus, broward")
    print("Critical Letters: B, I, J")
    print("=" * 40)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found in environment")
        print("Set environment variable or run from GitHub Actions")
        sys.exit(1)
    
    # Test connection
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(f"{SUPABASE_URL}/rest/v1/audit_log", 
                              headers=headers, params={"limit": "1"}, timeout=10)
        
        if response.status_code != 200:
            print("❌ Database connection failed")
            sys.exit(1)
            
        print("✅ Database connection successful")
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)
    
    # Verify each county
    total_score = 0
    counties = ['charlotte', 'citrus', 'broward']
    
    for county in counties:
        score = verify_county(county)
        total_score += score
    
    # Summary
    avg_score = total_score / len(counties)
    print(f"\n📊 SUMMARY:")
    print(f"  Total Score: {total_score}/30")
    print(f"  Average: {avg_score:.1f}/10")
    print(f"  Status: {'✅ ON TRACK' if avg_score >= 7 else '❌ NEEDS WORK'}")
    
    if avg_score < 7:
        print(f"\n🔧 RECOMMENDATION: Run pipeline fixes")
        print(f"   python3 scripts/run_shard17_now.py")

if __name__ == "__main__":
    main()