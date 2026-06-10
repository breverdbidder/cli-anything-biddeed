#!/usr/bin/env python3
"""
Apply foreclosure_outcomes migration to live Supabase database
Per CLAUDE.md autonomous operations: migrations are approved for non-destructive schema changes
"""

import os
import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

def apply_migration():
    """Apply the foreclosure_outcomes migration"""
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY required")
        return False
    
    # Read migration SQL
    migration_path = "/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/migrations/20260610_foreclosure_outcomes.sql"
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
    except Exception as e:
        print(f"❌ Failed to read migration file: {e}")
        return False
    
    print(f"📄 Read migration: {len(migration_sql)} characters")
    
    # Apply migration via Supabase REST API
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use RPC to execute SQL
    payload = {
        "query": migration_sql
    }
    
    print("🚀 Applying migration to live database...")
    
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                print("✅ Migration applied successfully")
                result = response.json()
                print(f"📊 Result: {result}")
                return True
            else:
                # Try alternative method using raw SQL endpoint
                print(f"⚠️  RPC method failed ({response.status_code}), trying direct SQL...")
                
                # Direct SQL execution (alternative approach)
                sql_payload = {"query": migration_sql}
                
                response2 = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/sql",
                    headers=headers,
                    json=sql_payload
                )
                
                if response2.status_code == 200:
                    print("✅ Migration applied successfully (direct SQL)")
                    return True
                else:
                    print(f"❌ Migration failed: {response2.status_code}")
                    print(f"Response: {response2.text[:500]}")
                    return False
                    
    except Exception as e:
        print(f"❌ Migration error: {e}")
        return False

def verify_migration():
    """Verify the migration was applied correctly"""
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Check if table exists
    check_query = """
    SELECT table_name, column_name 
    FROM information_schema.columns 
    WHERE table_name = 'foreclosure_outcomes' 
    ORDER BY ordinal_position;
    """
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                headers=headers,
                params={"query": check_query}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    print(f"✅ Table verification: foreclosure_outcomes has {len(result)} columns")
                    columns = [row.get('column_name') for row in result]
                    print(f"📋 Columns: {', '.join(columns[:10])}")  # Show first 10
                    return True
                else:
                    print("❌ Table not found in schema")
                    return False
            else:
                print(f"❌ Verification failed: {response.status_code}")
                return False
                
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def main():
    """Main execution"""
    print("🎯 GOLD STANDARD Letter B: Applying foreclosure_outcomes migration")
    
    # Apply migration
    if apply_migration():
        print("⏳ Verifying migration...")
        if verify_migration():
            print("🎉 Migration completed successfully!")
            return 0
        else:
            print("⚠️  Migration applied but verification failed")
            return 1
    else:
        print("❌ Migration failed")
        return 1

if __name__ == "__main__":
    exit(main())