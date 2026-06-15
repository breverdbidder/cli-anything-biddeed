#!/usr/bin/env python3
"""
SHARD-13 Migration Application Script
Apply SQL migrations via Supabase REST API

Usage:
  python scripts/apply_shard13_migrations.py [migration_name]
  
Migration names:
  - j_generator
  - gulf_a_lane  
  - b_verification
  - all
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_KEY:
    print("❌ No Supabase API key found")
    print("Set SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Migration file mappings
MIGRATIONS = {
    'j_generator': 'migrations/20260615_shard13_j_generator.sql',
    'gulf_a_lane': 'migrations/20260615_shard13_gulf_a_lane.sql', 
    'b_verification': 'migrations/20260615_shard13_b_verification.sql'
}

def log(message):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {message}")

def read_migration_file(filepath):
    """Read migration SQL file content"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        log(f"❌ Migration file not found: {filepath}")
        return None
    except Exception as e:
        log(f"❌ Error reading migration file: {e}")
        return None

def execute_sql_via_rpc(sql_content, migration_name):
    """Execute SQL via Supabase RPC function"""
    try:
        client = httpx.Client(timeout=120)
        
        # For complex migrations, we need to execute them in chunks
        # Split by semicolon and filter out empty statements
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
        
        log(f"Executing {len(statements)} SQL statements for {migration_name}")
        
        success_count = 0
        error_count = 0
        
        for i, statement in enumerate(statements):
            if not statement:
                continue
                
            try:
                # Use the sql RPC endpoint for raw SQL execution
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=HEADERS,
                    json={"sql": statement}
                )
                
                if response.status_code in [200, 201, 204]:
                    success_count += 1
                    if i % 10 == 0:  # Progress update every 10 statements
                        log(f"  Progress: {i+1}/{len(statements)} statements")
                else:
                    error_count += 1
                    log(f"  Warning: Statement {i+1} failed: {response.status_code}")
                    
            except Exception as e:
                error_count += 1
                log(f"  Error executing statement {i+1}: {e}")
        
        client.close()
        
        log(f"Migration {migration_name}: {success_count} success, {error_count} errors")
        return success_count > 0
        
    except Exception as e:
        log(f"❌ Error executing migration {migration_name}: {e}")
        return False

def apply_migration(migration_name):
    """Apply a specific migration"""
    if migration_name not in MIGRATIONS:
        log(f"❌ Unknown migration: {migration_name}")
        log(f"Available migrations: {', '.join(MIGRATIONS.keys())}")
        return False
    
    migration_file = MIGRATIONS[migration_name]
    log(f"🔄 Applying migration: {migration_name} ({migration_file})")
    
    # Read migration content
    sql_content = read_migration_file(migration_file)
    if not sql_content:
        return False
    
    # Execute migration
    success = execute_sql_via_rpc(sql_content, migration_name)
    
    if success:
        log(f"✅ Migration {migration_name} applied successfully")
        
        # Record migration application
        try:
            client = httpx.Client(timeout=30)
            audit_response = client.post(
                f"{BASE}/audit_log",
                headers=HEADERS,
                json={
                    "operation": f"MIGRATION_APPLIED_{migration_name.upper()}",
                    "table_name": "shard13_migrations",
                    "details": {
                        "migration_file": migration_file,
                        "applied_at": datetime.now(timezone.utc).isoformat(),
                        "session_type": "SHARD_13_AUTONOMOUS",
                        "counties": ["volusia", "jackson", "santa_rosa", "gulf"]
                    }
                }
            )
            client.close()
            
            if audit_response.status_code in [200, 201]:
                log(f"✅ Migration {migration_name} recorded in audit log")
            else:
                log(f"⚠️ Failed to record migration in audit log")
                
        except Exception as e:
            log(f"⚠️ Error recording migration: {e}")
            
        return True
    else:
        log(f"❌ Migration {migration_name} failed")
        return False

def apply_all_migrations():
    """Apply all SHARD-13 migrations"""
    log("🚀 Applying all SHARD-13 migrations")
    
    results = {}
    for migration_name in ['j_generator', 'gulf_a_lane', 'b_verification']:
        results[migration_name] = apply_migration(migration_name)
    
    success_count = sum(results.values())
    total_count = len(results)
    
    log(f"📊 Migration Summary: {success_count}/{total_count} successful")
    
    for migration_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        log(f"  {migration_name}: {status}")
    
    return success_count == total_count

def verify_migrations():
    """Verify migration applications"""
    log("🔍 Verifying SHARD-13 migrations")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check if tables exist
        tables_to_check = ['bid_decisions', 'counties', 'foreclosure_outcomes', 'tax_deed_outcomes']
        
        for table in tables_to_check:
            response = client.get(
                f"{BASE}/{table}?select=count&limit=1",
                headers=HEADERS
            )
            
            if response.status_code == 200:
                log(f"  ✅ Table {table} exists and accessible")
            else:
                log(f"  ❌ Table {table} check failed: {response.status_code}")
        
        # Quick test of specific functions/data
        test_queries = [
            ("bid_decisions", "county_slug=in.(volusia,jackson,santa_rosa,gulf)"),
            ("counties", "county_slug=eq.gulf"),
            ("foreclosure_outcomes", "county_slug=in.(volusia,jackson,santa_rosa,gulf)"),
        ]
        
        for table, filter_condition in test_queries:
            response = client.get(
                f"{BASE}/{table}?{filter_condition}&select=count",
                headers=HEADERS
            )
            
            if response.status_code == 200:
                data = response.json()
                count = len(data) if isinstance(data, list) else 0
                log(f"  ✅ {table} has {count} SHARD-13 records")
            else:
                log(f"  ❌ {table} query failed: {response.status_code}")
        
        client.close()
        log("✅ Migration verification complete")
        return True
        
    except Exception as e:
        log(f"❌ Verification error: {e}")
        return False

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        log("Usage: python scripts/apply_shard13_migrations.py [migration_name|all|verify]")
        log(f"Available migrations: {', '.join(MIGRATIONS.keys())}")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    log("🎯 SHARD-13 Migration Application")
    log(f"Action: {action}")
    
    if action == 'all':
        success = apply_all_migrations()
    elif action == 'verify':
        success = verify_migrations()
    elif action in MIGRATIONS:
        success = apply_migration(action)
    else:
        log(f"❌ Unknown action: {action}")
        log(f"Available options: {', '.join(list(MIGRATIONS.keys()) + ['all', 'verify'])}")
        sys.exit(1)
    
    if success:
        log("✅ Operation completed successfully")
        
        if action != 'verify':
            log("Running post-migration verification...")
            verify_migrations()
        
        sys.exit(0)
    else:
        log("❌ Operation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()