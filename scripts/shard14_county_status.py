#!/usr/bin/env python3
"""
SHARD-14 County Status Checker
Evaluates current Gold Standard metrics for osceola, bay, okeechobee, hamilton counties

Usage:
  python scripts/shard14_county_status.py
"""
import os
import sys
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-14 target counties 
TARGET_COUNTIES = [
    {'name': 'Osceola', 'co_no': 59, 'slug': 'osceola'},
    {'name': 'Bay', 'co_no': 13, 'slug': 'bay'},
    {'name': 'Okeechobee', 'co_no': 43, 'slug': 'okeechobee'},
    {'name': 'Hamilton', 'co_no': 34, 'slug': 'hamilton'}
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

def query_county_evaluation(county_slug):
    """Query the pencil_dod_evaluate_county function for current status"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Call the stored function
        response = client.post(
            f"{SUPABASE_URL}/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug}
        )
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"❌ Failed to evaluate {county_slug}: {e}")
        return None

def get_auction_counts(county_slug):
    """Get basic auction counts for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Get total auctions count
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county=eq.{county_slug}",
            headers=headers
        )
        
        if response.status_code == 200:
            return len(response.json())
        else:
            return 0
            
    except Exception as e:
        print(f"❌ Failed to get auction counts for {county_slug}: {e}")
        return 0

def format_metric(metric):
    """Format a metric value for display"""
    if metric is None:
        return "null"
    if isinstance(metric, (int, float)):
        return f"{metric:.1f}" if metric != int(metric) else str(int(metric))
    return str(metric)

def calculate_pass_count(evaluation):
    """Calculate how many letters pass for a county"""
    if not evaluation:
        return 0
    return sum(1 for row in evaluation if row.get('pass', False))

def main():
    print("🔍 SHARD-14 COUNTY STATUS CHECK")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    print()
    print("County Status Summary:")
    print("-" * 60)
    
    total_pass_count = 0
    county_results = {}
    
    for county in TARGET_COUNTIES:
        county_name = county['name']
        county_slug = county['slug']
        
        print(f"\n## {county_name.upper()} ({county_slug})")
        
        # Get basic auction count
        auction_count = get_auction_counts(county_slug)
        print(f"    Total auctions: {auction_count}")
        
        # Get detailed evaluation
        evaluation = query_county_evaluation(county_slug)
        
        if evaluation:
            pass_count = calculate_pass_count(evaluation)
            total_pass_count += pass_count
            county_results[county_slug] = {
                'pass_count': pass_count,
                'evaluation': evaluation,
                'auction_count': auction_count
            }
            
            print(f"    Letters passing: {pass_count}/10")
            
            # Show each letter status
            for row in evaluation:
                letter = row.get('letter', '?')
                passes = '✅' if row.get('pass', False) else '❌'
                metric = format_metric(row.get('metric'))
                detail = row.get('detail', '')
                
                print(f"    {letter} {passes} metric={metric} [{detail}]")
        else:
            print("    ❌ Failed to evaluate county")
            county_results[county_slug] = {
                'pass_count': 0,
                'evaluation': None,
                'auction_count': auction_count
            }
    
    print()
    print("=" * 60)
    print("SHARD-14 SUMMARY")
    print("=" * 60)
    print(f"Total letters passing across all counties: {total_pass_count}/40")
    print(f"Average pass rate per county: {total_pass_count/len(TARGET_COUNTIES):.1f}/10")
    print()
    
    # Priority analysis
    print("PRIORITY ANALYSIS:")
    print("-" * 30)
    
    # Find counties by pass count
    county_priority = sorted(
        [(k, v['pass_count'], v['auction_count']) for k, v in county_results.items()], 
        key=lambda x: (x[1], x[2])  # Sort by pass count, then auction count
    )
    
    for rank, (county_slug, pass_count, auction_count) in enumerate(county_priority, 1):
        if pass_count == 0:
            priority = "BOOTSTRAP NEEDED"
        elif pass_count < 3:
            priority = "CRITICAL"
        elif pass_count < 7:
            priority = "HIGH"
        else:
            priority = "LOW"
        
        print(f"{rank}. {county_slug:12s} {pass_count:2d}/10  {auction_count:5d} auctions  {priority}")
    
    print()
    print("RECOMMENDED WORK ORDER:")
    print("-" * 30)
    print("1. Hamilton (if 0/10): Complete bootstrap - basic data ingestion")
    print("2. Focus on critical letters B, I, J for counties with >0 auctions")  
    print("3. Letters B: Independent verified outcomes from clerk sources")
    print("4. Letters I: Property card enrichment (address + geo + value)")
    print("5. Letters J: Shapira Formula deal thesis pipeline")
    print()

if __name__ == "__main__":
    main()