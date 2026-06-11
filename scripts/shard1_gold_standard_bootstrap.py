#!/usr/bin/env python3
"""
SHARD-1 GOLD STANDARD County Bootstrap: charlotte, polk, escambia, pasco, hardee
Ensures our assigned counties have baseline data ingested before working on Letters B-J

Usage:
  python scripts/shard1_gold_standard_bootstrap.py
"""
import os
import sys
import subprocess
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-1 counties from the issue description (co_no from fl_counties)
TARGET_COUNTIES = [
    {'name': 'Charlotte', 'co_no': 12, 'slug': 'charlotte'},
    {'name': 'Polk', 'co_no': 61, 'slug': 'polk'}, 
    {'name': 'Escambia', 'co_no': 25, 'slug': 'escambia'},
    {'name': 'Pasco', 'co_no': 57, 'slug': 'pasco'},
    {'name': 'Hardee', 'co_no': 33, 'slug': 'hardee'}
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

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"📊 Gold Standard Status for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for letter_data in result if letter_data.get('pass'))
                print(f"  OVERALL: {pass_count}/10 pass")
                
                # Group results by pass/fail for better readability
                passed = []
                failed = []
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    if letter_data.get('pass'):
                        passed.append(f"{letter} (metric={metric})")
                    else:
                        context = letter_data.get('context', '')
                        failed.append(f"{letter} (metric={metric}) {context}")
                
                if passed:
                    print(f"  ✅ PASSING: {', '.join(passed)}")
                if failed:
                    print(f"  ❌ FAILING: {', '.join(failed)}")
                    
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def check_county_status(co_no, name, slug):
    """Check current ingestion status for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check fl_counties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
            headers=headers
        )
        fl_county = response.json()[0] if response.status_code == 200 and response.json() else None
        
        # Check multi_county_auctions  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        status = {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'auctions': auction_count,
            'needs_basic_ingestion': auction_count == 0
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {name} status: {e}")
        return None

def main():
    print("=" * 80)
    print("SHARD-1 GOLD STANDARD County Bootstrap")
    print("Target Counties: charlotte, polk, escambia, pasco, hardee")
    print("Ship-to-main mandate: work directly on main branch")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    print("\\n🔍 Checking current county status...")
    
    counties_status = []
    county_evaluations = []
    
    for county in TARGET_COUNTIES:
        # Check basic status
        status = check_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            counties_status.append(status)
            print(f"  {status['county']:15s} | "
                  f"Parcels: {status['total_parcels']:>8,} | "
                  f"Auctions: {status['auctions']:>5} | "
                  f"Status: {'NEEDS_INGESTION' if status['needs_basic_ingestion'] else 'HAS_DATA'}")
    
    print("\\n📈 Running fresh Gold Standard evaluations...")
    for county in TARGET_COUNTIES:
        print(f"\\n--- {county['slug'].upper()} ---")
        evaluation = evaluate_county_current(county['slug'])
        county_evaluations.append({
            'county': county['slug'],
            'evaluation': evaluation
        })
    
    # Analyze what work is needed
    print("\\n🎯 SHARD-1 ANALYSIS:")
    priority_work = []
    
    for eval_data in county_evaluations:
        county = eval_data['county']
        evaluation = eval_data['evaluation']
        
        if evaluation:
            pass_count = sum(1 for letter_data in evaluation if letter_data.get('pass'))
            failing_letters = [letter_data.get('letter') for letter_data in evaluation if not letter_data.get('pass')]
            
            print(f"  {county}: {pass_count}/10 pass, failing={failing_letters}")
            
            # According to issue: B, I, J are critical three
            critical_failing = [letter for letter in failing_letters if letter in ['B', 'I', 'J']]
            if critical_failing:
                priority_work.append({
                    'county': county,
                    'critical_failing': critical_failing,
                    'all_failing': failing_letters,
                    'pass_count': pass_count
                })
    
    if priority_work:
        print(f"\\n🚨 HIGH-LEVERAGE WORK IDENTIFIED ({len(priority_work)} counties):")
        for work in sorted(priority_work, key=lambda x: x['pass_count'], reverse=True):
            print(f"  {work['county']}: CRITICAL={work['critical_failing']}, ALL_FAILING={work['all_failing']}")
    
    print(f"\\n✅ SHARD-1 status assessment complete!")
    print(f"\\nNext: Focus on highest-leverage failing letters for each county")
    print(f"Priority order based on issue guidance:")
    print(f"  1. Brevard AcclaimWeb endpoint for B+F (if brevard in shard)")  
    print(f"  2. Duval PO→court case_number repair for C/D/B")
    print(f"  3. County-specific B (verified outcomes) fixes")
    print(f"  4. E (parcel linkage) fixes to unlock downstream pipeline")

if __name__ == "__main__":
    main()