#!/usr/bin/env python3
"""
Test current status for brevard and duval counties - Shard 28 (loop run 28)
GOLD STANDARD AUTOPILOT-BD Session
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
    # For GitHub Actions, try to continue and show what we can
    print("🔄 Continuing with connection test...")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("⚠️  Skipping connection test (no API key)")
        return False
        
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
    if not SUPABASE_KEY:
        print(f"⚠️  Cannot evaluate {county_slug} (no API key)")
        return None
        
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function with statement timeout disabled
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    threshold = letter_data.get('threshold')
                    print(f"  {letter}: {status} {metric} (threshold: {threshold})")
            else:
                print(f"  No data returned for {county_slug}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def check_bid_decisions_state():
    """Check current state of bid_decisions table"""
    if not SUPABASE_KEY:
        print("⚠️  Cannot check bid_decisions (no API key)")
        return
        
    try:
        client = httpx.Client(timeout=30)
        
        # Check bid_decisions table
        r = client.get(f"{SUPABASE_URL}/rest/v1/bid_decisions?select=count", headers=sb_headers())
        if r.status_code == 200:
            count = len(r.json())
            print(f"📊 bid_decisions table: {count} rows")
            
            # Check with ml_score
            r = client.get(f"{SUPABASE_URL}/rest/v1/bid_decisions?select=ml_score&ml_score=not.is.null", headers=sb_headers())
            if r.status_code == 200:
                ml_count = len(r.json())
                print(f"   With ml_score: {ml_count}")
            
            # Check with factors
            r = client.get(f"{SUPABASE_URL}/rest/v1/bid_decisions?select=factors&factors=not.is.null", headers=sb_headers())
            if r.status_code == 200:
                factors_count = len(r.json())
                print(f"   With factors: {factors_count}")
                
        else:
            print(f"❌ Failed to check bid_decisions: {r.status_code}")
            
    except Exception as e:
        print(f"❌ Error checking bid_decisions: {e}")

if __name__ == "__main__":
    print("=== SHARD 28 DATABASE CONNECTIVITY TEST ===")
    print("Counties: brevard, duval")
    
    connected = test_connection()
    
    print("\n=== FRESH COUNTY EVALUATIONS (from issue briefing) ===")
    target_counties = ['brevard', 'duval']
    
    evaluation_results = {}
    for county in target_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        evaluation_results[county] = result
    
    print("\n=== BID DECISIONS STATE ===")
    check_bid_decisions_state()
    
    print("\n=== SPRINT ORDER SUMMARY ===")
    print("\n**BREVARD PRIORITIES:**")
    print("1. C/D ROOT CAUSE - clerk/official-records supplementary litmus")
    print("2. J GENERATOR - bid_decisions pipeline build")
    print("3. G HIT LIST - zone_standards NULL backfill")
    print("4. B RECONCILIATION - 134%% anomaly")
    
    print("\n**DUVAL PRIORITIES:**")
    print("1. G+I SUBSTRATE - zoning infrastructure build")
    print("2. C/D ROOT CAUSE - same litmus as brevard")
    print("3. J GENERATOR - county-agnostic")
    print("4. B RECONCILIATION - 110%% anomaly")
    
    if connected:
        print("\n✅ Database connectivity confirmed. Ready for implementation.")
    else:
        print("\n⚠️  Database connectivity issues. Will attempt with available tools.")