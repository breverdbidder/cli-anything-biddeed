#!/usr/bin/env python3
"""
GOLD STANDARD SHARD 10: leon, volusia, martin, franklin, union
Check current status and evaluate county metrics for the assigned shard.
"""
import os
import sys
import httpx
import json
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# My assigned shard counties from the issue
SHARD_COUNTIES = [
    {'name': 'Leon', 'co_no': 37, 'slug': 'leon'},
    {'name': 'Volusia', 'co_no': 64, 'slug': 'volusia'},
    {'name': 'Martin', 'co_no': 47, 'slug': 'martin'},
    {'name': 'Franklin', 'co_no': 26, 'slug': 'franklin'},
    {'name': 'Union', 'co_no': 62, 'slug': 'union'}
]

def check_supabase_connection():
    """Verify we can connect to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        response.raise_for_status()
        print("✅ Supabase connection verified")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def evaluate_county(county_name):
    """Run the pencil_dod_evaluate_county function for a specific county"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Call the evaluation function
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_name": county_name}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Evaluation failed for {county_name}: {response.status_code} {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county_name}: {e}")
        return None

def check_basic_county_status(co_no, name, slug):
    """Check basic ingestion status for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check multi_county_auctions
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check zoning_assignments  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check sample_properties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        sample_count = len(response.json()) if response.status_code == 200 else 0
        
        return {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'auctions': auction_count,
            'zoning_assignments': zoning_count,
            'sample_properties': sample_count,
            'needs_basic_ingestion': auction_count == 0
        }
        
    except Exception as e:
        print(f"❌ Error checking {name} basic status: {e}")
        return None

def main():
    print("=" * 70)
    print("GOLD STANDARD SHARD 10: leon, volusia, martin, franklin, union")
    print("=" * 70)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    print("\n🔍 Checking basic county status...")
    
    basic_status_list = []
    for county in SHARD_COUNTIES:
        status = check_basic_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            basic_status_list.append(status)
            print(f"  {status['county']:12s} | "
                  f"Auctions: {status['auctions']:>6} | "
                  f"Zoning: {status['zoning_assignments']:>6} | "
                  f"Samples: {status['sample_properties']:>6} | "
                  f"Status: {'NEEDS_A_LEVEL' if status['needs_basic_ingestion'] else 'HAS_DATA'}")
    
    print("\n📊 Running gold standard evaluations...")
    
    evaluation_results = {}
    for county in SHARD_COUNTIES:
        result = evaluate_county(county['slug'])
        if result:
            evaluation_results[county['slug']] = result
            print(f"✅ Evaluated {county['name']}")
        else:
            print(f"❌ Failed to evaluate {county['name']}")
    
    print("\n" + "=" * 70)
    print("GOLD STANDARD METRICS SUMMARY")
    print("=" * 70)
    
    for county_slug, result in evaluation_results.items():
        county_name = next(c['name'] for c in SHARD_COUNTIES if c['slug'] == county_slug)
        print(f"\n{county_name.upper()}:")
        print(json.dumps(result, indent=2))
    
    # Identify highest priority targets
    print("\n" + "=" * 70)
    print("PRIORITY ANALYSIS")
    print("=" * 70)
    
    zero_letter_counties = []
    incomplete_counties = []
    
    for county_slug, result in evaluation_results.items():
        county_name = next(c['name'] for c in SHARD_COUNTIES if c['slug'] == county_slug)
        passed_letters = result.get('letters_passed', 0)
        
        if passed_letters == 0:
            zero_letter_counties.append(county_name)
        elif passed_letters < 10:
            incomplete_counties.append((county_name, passed_letters))
    
    if zero_letter_counties:
        print(f"🚨 ZERO LETTERS PASSED: {', '.join(zero_letter_counties)}")
        print("   → Priority: A-level ingestion (basic data pipeline)")
    
    if incomplete_counties:
        print(f"\n🔧 PARTIAL COMPLETION:")
        for name, letters in incomplete_counties:
            print(f"   {name}: {letters}/10 letters")
    
    print("\nNext actions based on current status:")
    print("1. franklin/union (0/10): Run A-level ingestion first")
    print("2. Existing counties: Focus on B, I, J letters (critical three)")
    print("3. Wire all implementations to schedulers")
    print("4. Execute verification protocol")

if __name__ == "__main__":
    main()