#!/usr/bin/env python3
"""
SHARD-10 verification script for Gold Standard counties:
palm_beach, escambia, okeechobee, franklin, union
"""
import os
import sys
import json
from datetime import datetime, timezone

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection using environment variables or hardcoded values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-10 assigned counties
ASSIGNED_COUNTIES = ['palm_beach', 'escambia', 'okeechobee', 'franklin', 'union']

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")
print(f"Assigned counties: {ASSIGNED_COUNTIES}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Expected SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable")
    sys.exit(1)

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
    print(f"\n--- Evaluating {county_slug} ---")
    try:
        client = httpx.Client(timeout=60)
        
        # Set timeout first
        client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/set_timeout",
            headers=sb_headers(),
            json={"timeout_ms": 0}
        )
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    if is_pass:
                        pass_count += 1
                    status = "✅" if is_pass else "❌"
                    print(f"  {letter}: {status} {metric}")
                print(f"  TOTAL: {pass_count}/10 passing")
                return result, pass_count
            else:
                print(f"  No evaluation data returned for {county_slug}")
                return None, 0
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None, 0
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None, 0

def get_auction_counts(county_slug):
    """Get auction counts for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Count total auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=sb_headers(),
            params={
                "select": "count",
                "county_slug": f"eq.{county_slug}"
            }
        )
        
        if r.status_code == 200:
            total_count = len(r.json()) if r.headers.get('content-range') else 0
            print(f"  Total auctions: {total_count}")
            return total_count
        else:
            print(f"  ❌ Failed to get auction count: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"  ❌ Error getting auction count: {e}")
        return 0

def get_parcel_linkage_status(county_slug):
    """Check parcel linkage status"""
    try:
        client = httpx.Client(timeout=30)
        
        # Count auctions with parcel_id
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=sb_headers(),
            params={
                "select": "parcel_id",
                "county_slug": f"eq.{county_slug}",
                "parcel_id": "not.is.null"
            }
        )
        
        if r.status_code == 200:
            linked_count = len(r.json())
            print(f"  Parcel-linked auctions: {linked_count}")
            return linked_count
        else:
            print(f"  ❌ Failed to get parcel linkage: {r.status_code}")
            return 0
            
    except Exception as e:
        print(f"  ❌ Error getting parcel linkage: {e}")
        return 0

def main():
    print("=== SHARD-10 Database Connectivity Test ===")
    
    if not test_connection():
        sys.exit(1)
    
    print("\n=== SHARD-10 Fresh County Evaluations ===")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    summary = {}
    total_passing_letters = 0
    
    for county in ASSIGNED_COUNTIES:
        result, pass_count = evaluate_county_current(county)
        get_auction_counts(county)
        get_parcel_linkage_status(county)
        
        summary[county] = {
            'pass_count': pass_count,
            'evaluation': result
        }
        total_passing_letters += pass_count
    
    print(f"\n=== SHARD-10 SUMMARY ===")
    print(f"Total passing letters: {total_passing_letters}/50")
    for county, data in summary.items():
        print(f"  {county}: {data['pass_count']}/10")
    
    print("\n=== PRIORITY ANALYSIS ===")
    # Analyze which counties need the most work
    county_scores = [(county, data['pass_count']) for county, data in summary.items()]
    county_scores.sort(key=lambda x: x[1])  # Sort by pass count (lowest first)
    
    print("Counties by priority (lowest scores = highest priority):")
    for county, score in county_scores:
        if score == 0:
            print(f"  🔴 {county}: {score}/10 (CRITICAL)")
        elif score < 3:
            print(f"  🟡 {county}: {score}/10 (HIGH)")
        elif score < 6:
            print(f"  🟢 {county}: {score}/10 (MEDIUM)")
        else:
            print(f"  ✅ {county}: {score}/10 (LOW)")

if __name__ == "__main__":
    main()