#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-6 Bootstrap: washington, flagler, martin, seminole, franklin, jefferson, union
Ensures our assigned counties have baseline data ingested before working on Letters A-J

Usage:
  python scripts/gold_standard_shard6_bootstrap.py --check
  python scripts/gold_standard_shard6_bootstrap.py --bootstrap
"""
import os
import sys
import subprocess
import httpx
import argparse
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# My assigned counties from the issue description
TARGET_COUNTIES = [
    {'name': 'Washington', 'slug': 'washington', 'current_score': '2/10'},
    {'name': 'Flagler', 'slug': 'flagler', 'current_score': '1/10'},
    {'name': 'Martin', 'slug': 'martin', 'current_score': '1/10'},
    {'name': 'Seminole', 'slug': 'seminole', 'current_score': '1/10'},
    {'name': 'Franklin', 'slug': 'franklin', 'current_score': '0/10'},
    {'name': 'Jefferson', 'slug': 'jefferson', 'current_score': '0/10'},
    {'name': 'Union', 'slug': 'union', 'current_score': '0/10'}
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

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def get_county_co_no(slug):
    """Get county number from slug via fl_counties table"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?slug=eq.{slug}&select=co_no,name",
            headers=sb_headers()
        )
        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return data['co_no'], data['name']
        else:
            print(f"❌ Could not find county {slug} in fl_counties table")
            return None, None
    except Exception as e:
        print(f"❌ Error getting county {slug}: {e}")
        return None, None

def check_county_status(slug):
    """Check current status for a county across all key tables"""
    co_no, name = get_county_co_no(slug)
    if co_no is None:
        return None
        
    try:
        client = httpx.Client(timeout=30)
        
        # Check multi_county_auctions (main auction table)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=sb_headers()
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check zoning_assignments  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?county=eq.{slug}&select=count",
            headers=sb_headers()
        )
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check sample_properties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties?co_no=eq.{co_no}&select=count",
            headers=sb_headers()
        )
        sample_count = len(response.json()) if response.status_code == 200 else 0
        
        status = {
            'county': name,
            'slug': slug,
            'co_no': co_no,
            'auctions': auction_count,
            'zoning_assignments': zoning_count,
            'sample_properties': sample_count,
            'needs_baseline_ingestion': auction_count == 0 and zoning_count == 0
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {slug} status: {e}")
        return None

def evaluate_county_current(slug):
    """Run the pencil_dod_evaluate_county function for fresh metrics"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function  
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ Failed to evaluate county {slug}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {slug}: {e}")
        return None

def display_county_metrics(slug, metrics):
    """Display the A-J letter metrics in a readable format"""
    if not metrics:
        print(f"  {slug}: No metrics available")
        return
        
    print(f"\n{slug.upper()} County Metrics:")
    letter_status = {}
    
    for item in metrics:
        letter = item.get('letter', '?')
        metric = item.get('metric')
        passed = item.get('pass', False)
        status = "PASS" if passed else "FAIL"
        
        if metric is not None:
            print(f"  {letter}: {status} metric={metric}")
        else:
            print(f"  {letter}: {status} metric=null")
        
        letter_status[letter] = passed
    
    # Calculate pass count
    pass_count = sum(1 for passed in letter_status.values() if passed)
    print(f"  Overall: {pass_count}/10 letters passing")

def ingest_zero_state_counties():
    """Ingest baseline data for counties with 0 auctions"""
    zero_state_cos = {
        'franklin': 19,   # from migration schema
        'jefferson': 33,
        'union': 63
    }
    
    print("\n🏗️ Bootstrapping zero-state counties...")
    for slug, co_no in zero_state_cos.items():
        print(f"\n--- Ingesting {slug} (CO_NO={co_no}) ---")
        
        # Run count first
        try:
            result = subprocess.run([
                'python3', 'scripts/ingest_county.py', '--county', str(co_no)
            ], capture_output=True, text=True, timeout=300, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
            
            if result.returncode == 0:
                print(f"✅ Count successful for {slug}")
                print(result.stdout[-200:])  # Last 200 chars
                
                # Run full ingestion
                print(f"📦 Starting full ingestion for {slug}...")
                result = subprocess.run([
                    'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
                ], capture_output=True, text=True, timeout=3600, cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
                
                if result.returncode == 0:
                    print(f"✅ Full ingestion successful for {slug}")
                    print(result.stdout[-200:])
                else:
                    print(f"❌ Full ingestion failed for {slug}: {result.stderr}")
            else:
                print(f"❌ Count failed for {slug}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ Ingestion timed out for {slug}")
        except Exception as e:
            print(f"❌ Error ingesting {slug}: {e}")

def main():
    parser = argparse.ArgumentParser(description='GOLD STANDARD WAVE2-SHARD-6 Bootstrap')
    parser.add_argument('--check', action='store_true', help='Check current county status only')
    parser.add_argument('--bootstrap', action='store_true', help='Bootstrap missing county data')
    parser.add_argument('--ingest-zero', action='store_true', help='Ingest baseline data for zero-state counties')
    parser.add_argument('--county', help='Check specific county only')
    args = parser.parse_args()

    if not any([args.check, args.bootstrap, args.ingest_zero]):
        parser.print_help()
        sys.exit(1)

    print("=" * 80)
    print("GOLD STANDARD WAVE2-SHARD-6 Status Check")
    print("Assigned Counties: washington, flagler, martin, seminole, franklin, jefferson, union")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    # If checking specific county
    if args.county:
        TARGET_COUNTIES[:] = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        if not TARGET_COUNTIES:
            print(f"❌ County '{args.county}' not in assigned shard")
            sys.exit(1)
    
    print(f"\n🔍 Checking status for {len(TARGET_COUNTIES)} counties...")
    
    counties_status = []
    for county in TARGET_COUNTIES:
        status = check_county_status(county['slug'])
        if status:
            counties_status.append(status)
            print(f"  {status['county']:15s} | "
                  f"Auctions: {status['auctions']:>6} | "
                  f"Zoning: {status['zoning_assignments']:>6} | "
                  f"Samples: {status['sample_properties']:>6} | "
                  f"Baseline: {'MISSING' if status['needs_baseline_ingestion'] else 'OK'}")
    
    if args.check:
        print(f"\n📊 Running fresh evaluations for all counties...")
        for county in counties_status:
            slug = county['slug']
            print(f"\n--- Evaluating {county['county']} ({slug}) ---")
            metrics = evaluate_county_current(slug)
            display_county_metrics(slug, metrics)
    
    if args.bootstrap:
        # Identify counties that need baseline ingestion
        counties_to_bootstrap = [s for s in counties_status if s['needs_baseline_ingestion']]
        
        if not counties_to_bootstrap:
            print("\n✅ All counties have baseline data!")
        else:
            print(f"\n📋 Counties needing baseline ingestion: {len(counties_to_bootstrap)}")
            for county in counties_to_bootstrap:
                print(f"  - {county['county']} (CO_NO={county['co_no']})")
            
            print("\nTo bootstrap these counties, run:")
            for county in counties_to_bootstrap:
                print(f"  python scripts/ingest_county.py --county {county['co_no']} --full")

    if args.ingest_zero:
        ingest_zero_state_counties()
    
    print("\n🎯 Next Steps:")
    print("1. For counties with 0 auctions: Run A-lane scrapers to populate multi_county_auctions")
    print("2. For failing B metrics: Build verified outcome scrapers (independent data sources)")
    print("3. For failing I metrics: Complete property card data (address+geo+value+zoned)")
    print("4. For failing J metrics: Enable Shapira deal thesis pipeline")

if __name__ == "__main__":
    main()