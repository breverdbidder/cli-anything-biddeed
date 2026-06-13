#!/usr/bin/env python3
"""
Quick shard-1 status check for Gold Standard Campaign
Queries current metrics for assigned counties: charlotte, palm_beach, hendry, st_johns, hardee
"""

import os
import sys
import json

# Environment setup per CLAUDE.md
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

if not SERVICE_KEY:
    print("ERROR: No Supabase service key found in environment")
    print("Expected: SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

def headers():
    return {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers())
        if r.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for a single county"""
    try:
        client = httpx.Client(timeout=60)
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"\n=== {county_slug.upper()} CURRENT METRICS ===")
            
            if isinstance(result, list):
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    
                    status_icon = "✅" if passes else "❌"
                    metric_display = f"metric={metric}" if metric is not None else "metric=null"
                    details = letter_data.get('details', '')
                    
                    print(f"  {letter} {status_icon} {metric_display} {details}")
                
                print(f"  TOTAL: {pass_count}/10 passing")
                return result, pass_count
            else:
                print(f"  Unexpected result format: {result}")
                return None, 0
        else:
            print(f"❌ Failed to evaluate {county_slug}: {r.status_code} - {r.text}")
            return None, 0
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None, 0

def main():
    print("=== SHARD-1 GOLD STANDARD STATUS CHECK ===")
    
    if not test_connection():
        sys.exit(1)
    
    # Assigned counties for shard-1
    assigned_counties = ['charlotte', 'palm_beach', 'hendry', 'st_johns', 'hardee']
    
    total_passes = 0
    total_possible = 0
    
    for county in assigned_counties:
        result, pass_count = evaluate_county(county)
        if result is not None:
            total_passes += pass_count
            total_possible += 10
    
    print(f"\n=== SHARD-1 SUMMARY ===")
    print(f"Total passes: {total_passes}/{total_possible}")
    print(f"Shard completion: {(total_passes/total_possible*100):.1f}%")
    
    # Identify highest leverage targets
    print(f"\n=== PRIORITY TARGETS ===")
    print("Based on failing counties, highest leverage fixes:")
    print("1. B (verified outcomes) - affects all counties")
    print("2. E (parcel linkage) - affects all counties") 
    print("3. J (deal completion) - affects all counties")
    print("4. F (tier1 sales) - affects all counties")

if __name__ == "__main__":
    main()