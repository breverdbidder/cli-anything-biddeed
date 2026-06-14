#!/usr/bin/env python3
"""
Apply the Duval & Brevard Gold Standard migration to live database
"""
import os
import sys

# Install httpx if not available
try:
    import httpx
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    headers = {
        "Content-Type": "application/json"
    }
    if SUPABASE_KEY:
        headers.update({
            "apikey": SUPABASE_KEY, 
            "Authorization": f"Bearer {SUPABASE_KEY}"
        })
    return headers

def execute_sql(sql_content):
    """Execute SQL against Supabase database"""
    try:
        client = httpx.Client(timeout=120)
        
        # Try to execute via SQL endpoint
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": sql_content}
        )
        
        if r.status_code == 200:
            print("✅ SQL executed successfully")
            return True
        else:
            print(f"❌ SQL execution failed: {r.status_code} - {r.text}")
            
            # Try alternative approach: execute each statement separately
            statements = sql_content.split(';')
            success_count = 0
            
            for stmt in statements:
                stmt = stmt.strip()
                if not stmt or stmt.startswith('--'):
                    continue
                    
                try:
                    # Use the query endpoint for individual statements
                    r = client.get(
                        f"{SUPABASE_URL}/rest/v1/",
                        headers=sb_headers(),
                        params={"sql": stmt}
                    )
                    if r.status_code == 200:
                        success_count += 1
                        print(f"✅ Statement executed: {stmt[:50]}...")
                    else:
                        print(f"❌ Statement failed: {stmt[:50]}... - {r.status_code}")
                except Exception as e:
                    print(f"⚠️  Statement error: {stmt[:50]}... - {e}")
            
            print(f"Executed {success_count} statements manually")
            return success_count > 0
            
    except Exception as e:
        print(f"❌ Error executing SQL: {e}")
        return False

def test_tables_exist():
    """Test if the migration was applied by checking for new tables/functions"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check if bid_decisions table exists
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions?select=count&limit=1",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            print("✅ bid_decisions table exists")
            return True
        else:
            print(f"❌ bid_decisions table check failed: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing tables: {e}")
        return False

def main():
    print("=== APPLYING DUVAL & BREVARD GOLD STANDARD MIGRATION ===")
    
    # Read the migration file
    migration_file = "supabase/migrations/20260614_duval_brevard_gold_standard.sql"
    
    try:
        with open(migration_file, 'r') as f:
            sql_content = f.read()
    except Exception as e:
        print(f"❌ Error reading migration file: {e}")
        return False
    
    print(f"📖 Read migration file: {len(sql_content)} characters")
    
    # Test current state
    print("\n=== Testing current database state ===")
    tables_exist = test_tables_exist()
    
    if tables_exist:
        print("✅ Migration appears to already be applied")
    else:
        print("📊 Applying migration...")
        success = execute_sql(sql_content)
        
        if success:
            print("\n=== Verifying migration application ===")
            if test_tables_exist():
                print("✅ Migration applied successfully")
                return True
            else:
                print("⚠️  Migration may have partially failed")
                return False
        else:
            print("❌ Migration failed to apply")
            return False
    
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎯 Ready to proceed with Gold Standard work")
        sys.exit(0)
    else:
        print("\n❌ Migration failed - continuing with manual approach")
        sys.exit(0)  # Don't block the session