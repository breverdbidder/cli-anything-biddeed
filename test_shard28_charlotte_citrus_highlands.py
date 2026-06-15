#!/usr/bin/env python3
"""
Test current status for charlotte, citrus, highlands counties - Shard 28 (loop run 28)
GOLD STANDARD AUTOPILOT-NEXT Session
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

def check_multi_county_auctions_counts():
    """Check current state of multi_county_auctions for our counties"""
    if not SUPABASE_KEY:
        print("⚠️  Cannot check multi_county_auctions (no API key)")
        return
        
    try:
        client = httpx.Client(timeout=30)
        target_counties = ['charlotte', 'citrus', 'highlands']
        
        for county in target_counties:
            # Check total auctions
            r = client.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count()&county=eq.{county}", headers=sb_headers())
            if r.status_code == 200:
                data = r.json()
                count = data[0]['count'] if data else 0
                print(f"📊 {county}: {count} auctions")
            else:
                print(f"❌ Failed to check {county}: {r.status_code}")
                
    except Exception as e:
        print(f"❌ Error checking multi_county_auctions: {e}")

if __name__ == "__main__":
    print("=== SHARD 28 DATABASE CONNECTIVITY TEST ===")
    print("Counties: charlotte, citrus, highlands")
    
    connected = test_connection()
    
    print("\n=== AUCTION COUNTS ===")
    check_multi_county_auctions_counts()
    
    print("\n=== FRESH COUNTY EVALUATIONS ===")
    target_counties = ['charlotte', 'citrus', 'highlands']
    
    evaluation_results = {}
    for county in target_counties:
        print(f"\n--- {county} ---")
        result = evaluate_county_current(county)
        evaluation_results[county] = result
    
    print("\n=== PRIORITIES FROM BRIEFING ===")
    print("\n**CHARLOTTE (2/10):**")
    print("- A PASS (249), H FAIL (74.0h)")
    print("- Priority fixes: B (verified outcomes), C/D (parity), E (parcel linkage), F (tier1 sold), G (zoning), I (property cards), J (deal complete)")
    
    print("\n**CITRUS (2/10):**") 
    print("- A PASS (1666), E PASS (95.3%), H FAIL (61.6h)")
    print("- Priority fixes: B (verified outcomes), C/D (parity), F (tier1 sold), G (zoning), I (property cards), J (deal complete)")
    
    print("\n**HIGHLANDS (2/10):**")
    print("- A PASS (80), D PASS (97.5%), H FAIL (598.4h)")
    print("- Priority fixes: B (verified outcomes), C (parity), E (parcel linkage), F (tier1 sold), G (zoning), I (property cards), J (deal complete)")
    
    if connected:
        print("\n✅ Database connectivity confirmed. Ready for implementation.")
    else:
        print("\n⚠️  Database connectivity issues. Will attempt with available tools.")