#!/usr/bin/env python3
"""
Apply the tier1 promotion migration to Supabase
"""
import os
import urllib.request

# Supabase configuration  
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY found in environment")
    exit(1)

def apply_migration():
    """Apply the migration by reading the SQL file and executing it"""
    
    # Read the migration file
    try:
        with open("migrations/20260612_tier1_promotion_automation.sql", "r") as f:
            migration_sql = f.read()
    except FileNotFoundError:
        print("❌ Migration file not found")
        return False
    
    print("🔄 Applying tier1 promotion migration...")
    print("=" * 50)
    
    # Split migration into individual statements
    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip()]
    
    success_count = 0
    total_statements = len(statements)
    
    for i, statement in enumerate(statements, 1):
        if not statement or statement.startswith('--'):
            continue
            
        print(f"Executing statement {i}/{total_statements}...")
        
        # Execute via Supabase SQL editor proxy
        data = statement.encode('utf-8')
        req = urllib.request.Request(
            f"{SUPABASE_URL}/sql",
            data=data,
            method="POST"
        )
        req.add_header("apikey", SUPABASE_KEY)
        req.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
        req.add_header("Content-Type", "application/sql")
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                if response.status == 200:
                    success_count += 1
                    print(f"   ✅ Statement {i} applied successfully")
                else:
                    print(f"   ❌ Statement {i} failed: HTTP {response.status}")
        except Exception as e:
            print(f"   ❌ Statement {i} failed: {e}")
    
    print("=" * 50)
    print(f"Migration complete: {success_count}/{total_statements} statements applied")
    
    return success_count > 0

if __name__ == "__main__":
    success = apply_migration()
    exit(0 if success else 1)