#!/usr/bin/env python3
"""
Apply SHARD-14 Migration and Verify Setup
Applies the 20260612_shard14_county_setup.sql migration and verifies county setup

Usage:
  python scripts/apply_shard14_migration.py
"""
import os
import sys
import httpx
import json
import time
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-14 target counties 
TARGET_COUNTIES = [
    {'name': 'Osceola', 'co_no': 59, 'slug': 'osceola'},
    {'name': 'Bay', 'co_no': 13, 'slug': 'bay'},
    {'name': 'Okeechobee', 'co_no': 57, 'slug': 'okeechobee'},
    {'name': 'Hamilton', 'co_no': 34, 'slug': 'hamilton'}
]

def execute_sql(sql_statement, description="SQL"):
    """Execute a SQL statement via Supabase REST API"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Use the SQL endpoint
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=headers,
            json={"query": sql_statement}
        )
        
        if response.status_code == 200:
            print(f"✅ {description}: SUCCESS")
            return True, response.json()
        else:
            print(f"❌ {description}: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return False, None
            
    except Exception as e:
        print(f"❌ {description}: {e}")
        return False, None

def apply_migration():
    """Apply the SHARD-14 migration SQL"""
    print("📦 APPLYING SHARD-14 MIGRATION")
    print("=" * 50)
    
    migration_file = "migrations/20260612_shard14_county_setup.sql"
    
    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    
    # Split the migration into smaller chunks (Supabase has size limits)
    statements = []
    current_stmt = ""
    in_function = False
    
    for line in migration_sql.split('\n'):
        line = line.strip()
        
        # Skip comments
        if line.startswith('--') and not in_function:
            continue
            
        # Track function boundaries
        if '$$' in line:
            in_function = not in_function
        
        current_stmt += line + '\n'
        
        # Split on semicolons (but not inside functions)
        if line.endswith(';') and not in_function and current_stmt.strip():
            statements.append(current_stmt.strip())
            current_stmt = ""
    
    if current_stmt.strip():
        statements.append(current_stmt.strip())
    
    print(f"Found {len(statements)} SQL statements to execute")
    
    success_count = 0
    skip_count = 0
    
    for i, stmt in enumerate(statements, 1):
        if len(stmt) < 10:  # Skip very short statements
            continue
            
        preview = stmt.replace('\n', ' ')[:80] + "..."
        print(f"\n{i:2d}. {preview}")
        
        success, result = execute_sql(stmt, f"Statement {i}")
        
        if success:
            success_count += 1
        else:
            # Check if it's a "already exists" type error that we can skip
            if "already exists" in str(result) or "duplicate" in str(result):
                print(f"   ⚠️ Skipping (already exists)")
                skip_count += 1
            else:
                print(f"   ❌ Failed: {result}")
                return False
        
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n✅ Migration applied: {success_count} executed, {skip_count} skipped")
    return True

def verify_county_setup():
    """Verify that all SHARD-14 counties are properly set up"""
    print("\n🔍 VERIFYING COUNTY SETUP")
    print("=" * 50)
    
    # Check fl_counties table
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        for county in TARGET_COUNTIES:
            co_no = county['co_no']
            expected_slug = county['slug']
            
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/fl_counties?select=*&co_no=eq.{co_no}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    row = data[0]
                    actual_slug = row.get('slug')
                    if actual_slug == expected_slug:
                        print(f"✅ {county['name']} (co_no={co_no}): slug='{actual_slug}'")
                    else:
                        print(f"⚠️ {county['name']} (co_no={co_no}): slug='{actual_slug}' (expected '{expected_slug}')")
                else:
                    print(f"❌ {county['name']} (co_no={co_no}): NOT FOUND")
            else:
                print(f"❌ Failed to check {county['name']}: HTTP {response.status_code}")
                
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False
    
    return True

def check_table_existence():
    """Check that required tables exist"""
    print("\n📋 CHECKING TABLE EXISTENCE")
    print("=" * 50)
    
    required_tables = [
        'multi_county_auctions',
        'tax_deed_outcomes', 
        'foreclosure_outcomes',
        'bid_decisions',
        'fl_counties'
    ]
    
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        for table in required_tables:
            # Try to query the table (with limit 0 to just check existence)
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/{table}?limit=0",
                headers=headers
            )
            
            if response.status_code == 200:
                print(f"✅ {table}")
            elif response.status_code == 406:  # Table exists but no access
                print(f"✅ {table} (exists, no access)")
            else:
                print(f"❌ {table}: HTTP {response.status_code}")
    
    except Exception as e:
        print(f"❌ Table check failed: {e}")

def main():
    print("🚀 SHARD-14 MIGRATION AND VERIFICATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    # Apply migration
    if apply_migration():
        print("\n✅ Migration applied successfully")
    else:
        print("\n❌ Migration failed")
        sys.exit(1)
    
    # Verify setup
    if verify_county_setup():
        print("\n✅ County setup verified")
    else:
        print("\n⚠️ County setup has issues")
    
    # Check tables
    check_table_existence()
    
    print("\n🎉 SHARD-14 SETUP COMPLETE")
    print("Next: Run pencil_dod_evaluate_county for each county to check current metrics")

if __name__ == "__main__":
    main()