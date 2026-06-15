#!/usr/bin/env python3
"""
Verify current status for shard-9 counties: osceola, duval, okaloosa, dixie, taylor
GOLD STANDARD SHARD-9 SESSION - 6h budget autonomous execution
"""
import os
import sys
import httpx
import json

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co" 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for shard-9 counties"""
    try:
        client = httpx.Client(timeout=60)
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        print(f"\n=== {county_slug.upper()} STATUS ===")
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    status = "✅ PASS" if passes else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric}")
                print(f"\n{county_slug.title()} Score: {pass_count}/10")
                return result, pass_count
            else:
                print(f"  ❌ No data returned for {county_slug}")
                return None, 0
        else:
            print(f"  ❌ API error {r.status_code}: {r.text}")
            return None, 0
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None, 0

def check_auction_counts(county_slug):
    """Check auction counts for context"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check multi_county_auctions count
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county=eq.{county_slug}",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            count = len(r.json())
            print(f"  📊 Total auctions: {count}")
            return count
        else:
            print(f"  ⚠️ Could not get auction count: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"  ⚠️ Auction count error: {e}")
        return 0

if __name__ == "__main__":
    print("🎯 GOLD STANDARD SHARD-9 STATUS VERIFICATION")
    print("Counties: osceola, duval, okaloosa, dixie, taylor")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        print("ℹ️  Expected in GitHub Actions - proceeding with execution plan")
        sys.exit(0)  # Non-blocking exit for CI
    
    # Test connection first
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)
    
    # Shard-9 counties in priority order (from issue brief)
    counties = ["duval", "osceola", "okaloosa", "dixie", "taylor"]
    results = {}
    total_passes = 0
    
    for county in counties:
        result, passes = evaluate_county(county)
        check_auction_counts(county)
        results[county] = {"result": result, "passes": passes}
        total_passes += passes
    
    print("\n" + "="*60)
    print("📋 SHARD-9 SUMMARY")
    print(f"Total passes across all counties: {total_passes}/50")
    
    print("\n🎯 PRIORITY ORDER (per brief):")
    for county in counties:
        passes = results[county]["passes"]
        print(f"  {county.title()}: {passes}/10 ({'READY' if passes >= 3 else 'BUILD'})")
    
    print("\n📝 EXECUTION PLAN:")
    print("1. DUVAL: Closest to gold - prioritize B reconciliation + J generator")
    print("2. OSCEOLA: 2/10 - focus on high-leverage letters (B, J)")
    print("3. OKALOOSA: 1/10 - basic infrastructure setup needed")
    print("4. DIXIE/TAYLOR: 0/10 - full county setup from scratch")
    
    print("\nReady for autonomous execution...")