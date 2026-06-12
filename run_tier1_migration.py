#!/usr/bin/env python3
"""
Run the tier1 promotion migration and execute initial data collection
"""
import os
import json
import urllib.request
import urllib.parse

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY found in environment")
    exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def sb_rpc(func_name, params=None):
    """Call a Supabase RPC function"""
    payload = json.dumps(params or {}).encode()
    req = urllib.request.Request(f"{BASE}/rpc/{func_name}", data=payload, method="POST")
    req.add_header("apikey", SUPABASE_KEY)
    req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    req.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, response.read().decode()
    except Exception as e:
        return 0, str(e)

def test_connection():
    """Test basic Supabase connectivity"""
    try:
        req = urllib.request.Request(f"{BASE}/fl_counties?select=count&limit=1")
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status == 200
    except:
        return False

def main():
    print("🔍 TIER1 PROMOTION MIGRATION EXECUTION")
    print("=" * 50)
    
    # Test connection
    if not test_connection():
        print("❌ Database connection failed")
        return False
    
    print("✅ Database connection successful")
    
    # Run tier1 promotion function
    print("\n📊 EXECUTING TIER1 PROMOTION...")
    status, result = sb_rpc("promote_tier1_from_outcomes")
    
    if status == 200:
        print("✅ Tier1 promotion completed")
        try:
            data = json.loads(result)
            for row in data:
                county = row.get('county_slug', 'unknown')
                promoted = row.get('promoted_count', 0)
                available = row.get('total_available', 0)
                print(f"   {county}: promoted {promoted}, total available {available}")
        except:
            print(f"   Raw result: {result}")
    else:
        print(f"⚠️ Tier1 promotion warning: {status} - {result}")
    
    # Check current tier1 coverage  
    print("\n📈 CHECKING TIER1 COVERAGE...")
    status, result = sb_rpc("check_tier1_coverage")
    
    if status == 200:
        print("✅ Tier1 coverage check completed")
        try:
            data = json.loads(result)
            for row in data:
                county = row.get('county_slug', 'unknown')
                total = row.get('total_closed', 0)
                with_tier1 = row.get('with_tier1', 0)
                coverage = row.get('coverage_pct', 0)
                print(f"   {county}: {with_tier1}/{total} ({coverage:.1f}%)")
        except:
            print(f"   Raw result: {result}")
    else:
        print(f"⚠️ Coverage check warning: {status} - {result}")
    
    # Feed Brevard acclaim queue
    print("\n🔄 FEEDING BREVARD ACCLAIM QUEUE...")
    status, result = sb_rpc("feed_acclaim_queue_brevard")
    
    if status == 200:
        print("✅ Brevard queue feeding completed")
        try:
            queued_count = json.loads(result)
            print(f"   Queued {queued_count} new cases for harvest")
        except:
            print(f"   Raw result: {result}")
    else:
        print(f"⚠️ Queue feeding warning: {status} - {result}")
    
    # Run county evaluations for verification
    print("\n📋 VERIFICATION - COUNTY EVALUATIONS...")
    for county in ['brevard', 'duval']:
        print(f"\n--- {county} ---")
        status, result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
        
        if status == 200:
            try:
                data = json.loads(result)
                for row in data:
                    letter = row.get('letter', '?').upper()
                    is_pass = row.get('pass', False)
                    metric = row.get('metric', 'N/A')
                    status_emoji = "✅" if is_pass else "❌"
                    print(f"   Letter {letter}: {status_emoji} {metric}")
            except:
                print(f"   Raw result: {result}")
        else:
            print(f"   ❌ Evaluation failed: {status} - {result}")
    
    print("\n" + "=" * 50)
    print("TIER1 MIGRATION EXECUTION COMPLETE")
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)