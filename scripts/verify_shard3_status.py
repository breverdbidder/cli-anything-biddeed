#!/usr/bin/env python3
"""
SHARD 3 Gold Standard Verification - broward, sumter, lake, walton, jefferson
Verification script for Gold Standard Campaign parallel session

Counties assigned to Shard 3:
- broward (2/10 PASSES)
- sumter (2/10 PASSES)  
- lake (1/10 PASS)
- walton (1/10 PASS)
- jefferson (0/10 PASSES)

Usage:
  python scripts/verify_shard3_status.py
"""
import os
import sys
import json
import httpx
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD 3 ASSIGNED COUNTIES
SHARD_3_COUNTIES = ['broward', 'sumter', 'lake', 'walton', 'jefferson']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def format_metric(metric):
    """Format metric value for display"""
    if metric is None:
        return "null"
    if isinstance(metric, (int, float)):
        if metric > 100:
            return f"{metric:.0f}"  # Show large numbers as integers
        else:
            return f"{metric:.1f}"  # Show percentages with 1 decimal
    return str(metric)

def print_county_evaluation(county_slug, evaluation):
    """Print formatted county evaluation results"""
    if not evaluation:
        print(f"❌ No evaluation data for {county_slug}")
        return
    
    pass_count = 0
    print(f"\n## {county_slug}")
    
    for letter_data in evaluation:
        letter = letter_data.get('letter', '?')
        metric = letter_data.get('metric')
        passes = letter_data.get('pass', False)
        
        if passes:
            pass_count += 1
        
        status = "PASS" if passes else "FAIL"
        metric_str = format_metric(metric)
        
        print(f"    {letter} {status} metric={metric_str}")
    
    print(f"    Total: {pass_count}/10")
    return pass_count

def check_multi_county_auctions_counts():
    """Check auction counts for our counties"""
    print("\n=== Multi County Auctions Counts ===")
    
    try:
        client = httpx.Client(timeout=30)
        
        for county in SHARD_3_COUNTIES:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=count",
                headers=sb_headers()
            )
            
            if r.status_code == 200:
                count = len(r.json())
                print(f"{county}: {count} auctions")
            else:
                print(f"{county}: ERROR - {r.status_code}")
                
    except Exception as e:
        print(f"Error checking auction counts: {e}")

def main():
    print("=" * 60)
    print("SHARD 3 GOLD STANDARD VERIFICATION")
    print("Counties: broward, sumter, lake, walton, jefferson")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    # Check auction counts
    check_multi_county_auctions_counts()
    
    print("\n=== Fresh County Evaluations ===")
    
    total_passes = 0
    county_results = {}
    
    for county in SHARD_3_COUNTIES:
        evaluation = evaluate_county_current(county)
        pass_count = print_county_evaluation(county, evaluation)
        
        if pass_count is not None:
            total_passes += pass_count
            county_results[county] = {
                'pass_count': pass_count,
                'evaluation': evaluation
            }
    
    print(f"\n=== SHARD 3 SUMMARY ===")
    print(f"Total passes across all counties: {total_passes}/50")
    print(f"Counties with 10/10: {len([c for c in county_results.values() if c['pass_count'] == 10])}")
    
    # Identify priority targets based on issue brief
    print(f"\n=== PRIORITY ANALYSIS ===")
    for county in SHARD_3_COUNTIES:
        if county in county_results:
            pass_count = county_results[county]['pass_count']
            if pass_count < 3:
                print(f"⚠️  {county} ({pass_count}/10) - CRITICAL - needs urgent attention")
            elif pass_count < 7:
                print(f"🔧 {county} ({pass_count}/10) - HIGH PRIORITY")
            elif pass_count < 10:
                print(f"✅ {county} ({pass_count}/10) - NEAR COMPLETION")
            else:
                print(f"🏆 {county} ({pass_count}/10) - CERTIFIED")
    
    # Based on brief priorities, focus areas:
    print(f"\n=== RECOMMENDED ACTION PLAN ===")
    print("Based on issue brief priorities:")
    print("1. BREVARD B+F PRIORITY - Focus on Brevard AcclaimWeb endpoint setup")
    print("2. C/D ROOT CAUSE - PropertyOnion coverage vs court records") 
    print("3. J GENERATOR - Build Shapira Formula bid_decisions pipeline")
    print("4. G ZONING - Backfill zone_standards for density/FAR gaps")

if __name__ == "__main__":
    main()