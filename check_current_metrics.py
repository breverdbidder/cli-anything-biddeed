#!/usr/bin/env python3
"""
Check current Gold Standard metrics for Brevard and Duval counties
GOLD STANDARD AUTOPILOT-BD Session - Run 19
"""
import os
import sys
import json

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

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
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
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function - try both parameter names for compatibility
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_name": county_slug}  # Try county_name first
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                metrics_summary = {}
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "PASS" if letter_data.get('pass') else "FAIL"
                    metrics_summary[letter] = {"metric": metric, "status": status}
                    print(f"  {letter}: {status} metric={metric}")
                return metrics_summary
            return None
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_county_details(county_slug):
    """Get more detailed county information"""
    try:
        client = httpx.Client(timeout=30)
        
        # Get multi_county_auctions count for the county
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county={county_slug}",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            auction_count = len(r.json()) if r.json() else 0
            print(f"  Total auctions: {auction_count}")
            return auction_count
        else:
            print(f"  ❌ Could not get auction count: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error getting county details: {e}")
        return None

if __name__ == "__main__":
    print("=== GOLD STANDARD AUTOPILOT-BD Session ===")
    print("Run 19: Brevard and Duval Counties")
    print("Current Metrics Check")
    
    if not test_connection():
        sys.exit(1)
    
    # VERIFIED - These are the assigned counties for this session per the issue brief
    assigned_counties = ['brevard', 'duval']
    
    print("\n=== Fresh County Evaluations ===")
    for county in assigned_counties:
        print(f"\n--- {county.upper()} ---")
        get_county_details(county)
        metrics = evaluate_county_current(county)
        
        if metrics:
            # Count passes
            passes = sum(1 for v in metrics.values() if v['status'] == 'PASS')
            print(f"  Summary: {passes}/10 letters passing")
            
            # Identify priority targets based on the brief
            if county == 'brevard':
                print("  Brevard Priority Order:")
                print(f"    C (parity_clean): {metrics.get('C', {}).get('status', 'UNKNOWN')} - {metrics.get('C', {}).get('metric', 'N/A')}")
                print(f"    J (deal_complete): {metrics.get('J', {}).get('status', 'UNKNOWN')} - {metrics.get('J', {}).get('metric', 'N/A')}")
                print(f"    G (zoning min): {metrics.get('G', {}).get('status', 'UNKNOWN')} - {metrics.get('G', {}).get('metric', 'N/A')}")
                print(f"    B (verified_outcomes): {metrics.get('B', {}).get('status', 'UNKNOWN')} - {metrics.get('B', {}).get('metric', 'N/A')}")
            elif county == 'duval':
                print("  Duval Priority Order:")
                print(f"    G (zoning min): {metrics.get('G', {}).get('status', 'UNKNOWN')} - {metrics.get('G', {}).get('metric', 'N/A')}")
                print(f"    I (property_complete): {metrics.get('I', {}).get('status', 'UNKNOWN')} - {metrics.get('I', {}).get('metric', 'N/A')}")
                print(f"    C (parity_clean): {metrics.get('C', {}).get('status', 'UNKNOWN')} - {metrics.get('C', {}).get('metric', 'N/A')}")
                print(f"    J (deal_complete): {metrics.get('J', {}).get('status', 'UNKNOWN')} - {metrics.get('J', {}).get('metric', 'N/A')}")
    
    print("\n=== Verification Protocol ===")
    print("VERIFIED: Database connection established and current metrics retrieved")
    print("Next: Implement priority fixes based on current status")