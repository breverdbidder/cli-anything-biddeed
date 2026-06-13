#!/usr/bin/env python3
"""
Test script to verify SHARD-4 database connectivity and county status.
Quick validation before full session execution.
"""
import os
import httpx
import json

# Supabase connection  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Test counties
TEST_COUNTIES = ['broward', 'sarasota', 'indian_river', 'washington', 'lafayette']

def test_connection():
    """Test basic Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ SUPABASE_ANON_KEY environment variable not set")
        return False
        
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # Test basic table access
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=headers,
                params={"select": "county", "limit": "1"}
            )
            
            if response.status_code == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Database connection failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_county_evaluation(county_slug: str):
    """Test pencil_dod_evaluate_county function for a county"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    pass_count = sum(1 for r in result if r.get('pass', False))
                    print(f"✅ {county_slug}: {pass_count}/10 letters passing")
                    
                    # Show key metrics
                    key_letters = ['C', 'D', 'E', 'J']
                    for r in result:
                        letter = r.get('letter', '').upper()
                        if letter in key_letters:
                            metric = r.get('metric', 'null')
                            status = '✓' if r.get('pass', False) else '✗'
                            print(f"  {letter}: {status} {metric}")
                else:
                    print(f"⚠️ {county_slug}: No evaluation data returned")
            else:
                print(f"❌ {county_slug}: Evaluation failed ({response.status_code})")
                
    except Exception as e:
        print(f"❌ {county_slug}: Error - {e}")

def main():
    """Run connectivity tests for SHARD-4"""
    print("SHARD-4 Database Connectivity Test")
    print("=" * 40)
    
    # Test basic connection
    if not test_connection():
        return
    
    # Test county evaluations
    print(f"\nTesting county evaluations:")
    print("-" * 30)
    
    for county in TEST_COUNTIES:
        test_county_evaluation(county)
    
    print(f"\nTest complete. If all counties show metrics, the session script should work.")

if __name__ == "__main__":
    main()