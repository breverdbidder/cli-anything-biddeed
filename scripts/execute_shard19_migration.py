#!/usr/bin/env python3
"""
Simple SHARD-19 Migration Executor  
=================================
Executes the migration and verifies basic table counts

Usage:
  python scripts/execute_shard19_migration.py
"""
import httpx
import json
import os

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY required")
    exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

def check_table_counts():
    """Check if our data was added"""
    print("🔍 Checking table counts...")
    
    counties = ['charlotte', 'citrus', 'broward']
    
    for county in counties:
        # Check foreclosure outcomes
        try:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?county_slug=eq.{county}&select=case_number",
                headers=HEADERS
            )
            if r.status_code == 200:
                count = len(r.json())
                print(f"  ✅ {county}: {count} foreclosure_outcomes")
            else:
                print(f"  ❌ {county}: Error checking foreclosure_outcomes")
        except:
            print(f"  ❌ {county}: Failed to check foreclosure_outcomes")
        
        # Check bid decisions
        try:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/bid_decisions?county_slug=eq.{county}&select=case_number",
                headers=HEADERS
            )
            if r.status_code == 200:
                count = len(r.json())
                print(f"  ✅ {county}: {count} bid_decisions")
            else:
                print(f"  ❌ {county}: Error checking bid_decisions")
        except:
            print(f"  ❌ {county}: Failed to check bid_decisions")

def run_county_evaluation(county):
    """Run pencil_dod_evaluate_county for a county"""
    print(f"\n📊 Evaluating {county}...")
    
    try:
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"  {county.upper()} Gold Standard Results:")
            for item in result:
                letter = item.get('letter', '?')
                metric = item.get('metric', 0)
                is_pass = item.get('pass', False)
                status = "✅" if is_pass else "❌"
                print(f"    {letter}: {status} {metric}")
            return result
        else:
            print(f"  ❌ Failed to evaluate {county}: {r.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Error evaluating {county}: {e}")
        return None

if __name__ == "__main__":
    print("🚀 SHARD-19 Migration Check & County Evaluation")
    print("=" * 50)
    
    # Check if migration data exists
    check_table_counts()
    
    # Evaluate all counties
    counties = ['charlotte', 'citrus', 'broward']
    all_results = {}
    
    for county in counties:
        result = run_county_evaluation(county)
        if result:
            all_results[county] = result
    
    # Summary
    print(f"\n🎯 SUMMARY:")
    print(f"Counties evaluated: {len(all_results)}")
    
    for county, results in all_results.items():
        passes = sum(1 for r in results if r.get('pass', False))
        print(f"  {county}: {passes}/10 letters passing")
    
    print(f"\n✅ Evaluation complete!")