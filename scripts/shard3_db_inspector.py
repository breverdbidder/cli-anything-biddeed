#!/usr/bin/env python3
"""
SHARD-3 Database Inspector
Quick inspection tool to understand current state of assigned counties and available tables
"""
import os
import sys
import json

try:
    import httpx
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

ASSIGNED_COUNTIES = ['brevard', 'putnam', 'indian_river', 'walton', 'jefferson']

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
            print(f"📊 County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅" if letter_data.get('pass') else "❌"
                    print(f"  {letter}: {status} {metric}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def check_foreclosure_outcomes():
    """Check current foreclosure_outcomes for assigned counties"""
    try:
        client = httpx.Client(timeout=30)
        
        for county in ASSIGNED_COUNTIES:
            url = f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes"
            params = f"select=count&county=eq.{county}"
            
            r = client.get(f"{url}?{params}", headers=sb_headers())
            
            if r.status_code == 200:
                result = r.json()
                count = len(result) if result else 0
                print(f"📋 {county}: {count} foreclosure_outcomes records")
            else:
                print(f"⚠️ {county}: Could not check foreclosure_outcomes")
                
    except Exception as e:
        print(f"❌ Error checking foreclosure_outcomes: {e}")

def check_staging_tables():
    """Check for staging tables that might need mapping"""
    staging_tables = [
        'duval_clerk_grantor_recordings_staging',
        'duval_tax_deed_recordings_staging', 
        'brevard_fc_acclaim_raw',
        'brevard_clerk_recordings_staging'
    ]
    
    client = httpx.Client(timeout=30)
    
    print("🔍 Checking for staging tables...")
    
    for table in staging_tables:
        try:
            url = f"{SUPABASE_URL}/rest/v1/{table}"
            params = "select=count&limit=1"
            
            r = client.get(f"{url}?{params}", headers=sb_headers())
            
            if r.status_code == 200:
                result = r.json()
                count = len(result) if result else 0
                print(f"  ✅ {table}: {count} records")
            else:
                print(f"  ❌ {table}: Not accessible ({r.status_code})")
                
        except Exception as e:
            print(f"  ❌ {table}: Error - {e}")

def check_multi_county_auctions():
    """Check multi_county_auctions for assigned counties"""
    try:
        client = httpx.Client(timeout=30)
        
        print("📊 Multi-county auctions summary:")
        
        for county in ASSIGNED_COUNTIES:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            params = f"select=count&county=eq.{county}"
            
            r = client.get(f"{url}?{params}", headers=sb_headers())
            
            if r.status_code == 200:
                result = r.json()
                total_count = len(result) if result else 0
                
                # Also check sold_amount not null
                params_sold = f"select=count&county=eq.{county}&sold_amount=not.is.null"
                r_sold = client.get(f"{url}?{params_sold}", headers=sb_headers())
                
                sold_count = 0
                if r_sold.status_code == 200:
                    sold_result = r_sold.json()
                    sold_count = len(sold_result) if sold_result else 0
                
                print(f"  {county}: {total_count} total, {sold_count} with sold_amount")
            else:
                print(f"  ⚠️ {county}: Could not check multi_county_auctions")
                
    except Exception as e:
        print(f"❌ Error checking multi_county_auctions: {e}")

def main():
    print("🔍 SHARD-3 Database Inspector")
    print("Checking current state for assigned counties:", ", ".join(ASSIGNED_COUNTIES))
    print("=" * 70)
    
    if not test_connection():
        sys.exit(1)
    
    print("\n📊 Current Gold Standard Evaluations:")
    print("-" * 40)
    for county in ASSIGNED_COUNTIES:
        evaluate_county_current(county)
        print()
    
    print("\n📋 Foreclosure Outcomes Status:")
    print("-" * 40)
    check_foreclosure_outcomes()
    
    print("\n📦 Multi-County Auctions Status:")
    print("-" * 40)
    check_multi_county_auctions()
    
    print("\n🗂️ Staging Tables Status:")
    print("-" * 40)
    check_staging_tables()

if __name__ == "__main__":
    main()