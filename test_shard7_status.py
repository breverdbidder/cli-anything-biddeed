#!/usr/bin/env python3
"""
Test script to check current Gold Standard status for SHARD-7 counties
Queries the database to get actual current state
"""
import os
import sys
import httpx

# Environment setup
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

# SHARD-7 counties
COUNTIES = ['hillsborough', 'st_lucie', 'hernando', 'columbia', 'madison']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_db_connection():
    """Test basic database connectivity"""
    print("Testing database connection...")
    try:
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count", headers=sb_headers())
        if response.status_code == 200:
            print(f"✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def get_county_status():
    """Get current status for SHARD-7 counties"""
    print("\nQuerying county status...")
    client = httpx.Client(timeout=60)
    
    for county in COUNTIES:
        print(f"\n--- {county.upper()} ---")
        
        # Check if county exists in system
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/fl_counties?select=*&slug=eq.{county}",
                headers=sb_headers()
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    co_no = data[0]['co_no']
                    print(f"County found: CO_NO={co_no}")
                    
                    # Try to run evaluation function
                    try:
                        eval_response = client.post(
                            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                            headers=sb_headers(),
                            json={"county_slug": county}
                        )
                        
                        if eval_response.status_code == 200:
                            eval_data = eval_response.json()
                            print(f"Gold Standard Status: {eval_data}")
                        else:
                            print(f"Evaluation failed: {eval_response.status_code}")
                            print(f"Response: {eval_response.text}")
                            
                    except Exception as e:
                        print(f"Evaluation error: {e}")
                else:
                    print("County not found in fl_counties")
            else:
                print(f"Query failed: {response.status_code}")
                
        except Exception as e:
            print(f"Error querying {county}: {e}")

def check_multi_county_auctions():
    """Check auction data availability"""
    print("\nChecking auction data...")
    client = httpx.Client(timeout=60)
    
    for county in COUNTIES:
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county=eq.{county}",
                headers=sb_headers()
            )
            
            if response.status_code == 200:
                count_data = response.json()
                print(f"{county}: {len(count_data) if isinstance(count_data, list) else 'unknown'} auction records")
            else:
                print(f"{county}: Query failed ({response.status_code})")
                
        except Exception as e:
            print(f"{county}: Error - {e}")

def main():
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found in environment")
        sys.exit(1)
    
    print("SHARD-7 Gold Standard Status Check")
    print("=" * 50)
    print(f"Counties: {', '.join(COUNTIES)}")
    print(f"Database: {SUPABASE_URL}")
    
    # Test connection
    if not test_db_connection():
        sys.exit(1)
    
    # Get detailed status  
    get_county_status()
    
    # Check auction data
    check_multi_county_auctions()

if __name__ == "__main__":
    main()