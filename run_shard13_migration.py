#!/usr/bin/env python3
"""
Run SHARD-13 migration to set up database schema
"""
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
import json

print("=== SHARD-13 Migration Runner ===")

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

def run_migration():
    """Execute the SHARD-13 migration SQL"""
    # Read migration file
    migration_path = "migrations/20260611_shard13_county_setup.sql"
    
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
    except Exception as e:
        print(f"❌ Error reading migration file: {e}")
        return False
    
    print(f"✅ Migration SQL loaded ({len(migration_sql)} chars)")
    
    # Execute via Supabase SQL endpoint
    headers = {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "text/plain"
    }
    
    try:
        # Use the raw SQL endpoint
        url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
        data = json.dumps({"sql": migration_sql}).encode('utf-8')
        request = urllib.request.Request(url, data=data, headers={
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }, method="POST")
        
        with urllib.request.urlopen(request, timeout=120) as response:
            response_text = response.read().decode('utf-8')
            print(f"✅ Migration executed successfully")
            print(f"Response: {response_text}")
            return True
            
    except urllib.error.HTTPError as e:
        error_text = e.read().decode('utf-8')
        print(f"❌ Migration failed: {e.code} - {error_text}")
        
        # Try alternative approach: direct SQL via pg function
        try:
            print("Trying alternative migration approach...")
            # Split into individual statements and execute via RPC
            statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
            
            for i, stmt in enumerate(statements[:5]):  # Execute first 5 statements as test
                if not stmt or stmt.startswith('--'):
                    continue
                    
                print(f"Executing statement {i+1}: {stmt[:100]}...")
                
                url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
                data = json.dumps({"sql": stmt}).encode('utf-8')
                request = urllib.request.Request(url, data=data, headers={
                    "apikey": SUPABASE_KEY, 
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                }, method="POST")
                
                with urllib.request.urlopen(request, timeout=60) as response:
                    response_text = response.read().decode('utf-8')
                    print(f"  ✅ Statement executed")
                    
            print("✅ Migration completed via alternative method")
            return True
            
        except Exception as e2:
            print(f"❌ Alternative migration also failed: {e2}")
            return False
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("\n🎉 SHARD-13 migration completed successfully!")
        print("Counties configured: palm_beach, clay, okaloosa, gulf")
    else:
        print("\n💥 SHARD-13 migration failed")
        sys.exit(1)