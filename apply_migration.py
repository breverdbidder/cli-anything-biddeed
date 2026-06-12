#!/usr/bin/env python3
"""
Apply migration via SQL execution using urllib (no external dependencies)
"""
import urllib.request
import urllib.parse
import json
import os

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1vY2VycWpua3NtaGNqenhyZXdvIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTcxODEzNTQwMywiZXhwIjoyMDMzNzExNDAzfQ.Gf-cZyO5WQOd6qXbIXTnfQRGjgBgWVoZbJO2LoN_pTc"

def execute_sql(sql):
    """Execute SQL via Supabase RPC"""
    # Create RPC call to execute raw SQL
    payload = {"query": sql}
    body = json.dumps(payload).encode()
    
    request = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
        data=body,
        method="POST"
    )
    request.add_header("apikey", SUPABASE_KEY)
    request.add_header("Authorization", f"Bearer {SUPABASE_KEY}")
    request.add_header("Content-Type", "application/json")
    
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = response.read().decode()
            return response.status, result
    except Exception as e:
        return None, str(e)

def main():
    # Read migration file
    migration_path = "supabase/migrations/20260612_gold_standard_tier1_promote.sql"
    with open(migration_path, 'r') as f:
        sql = f.read()
    
    print(f"Applying migration: {migration_path}")
    print(f"SQL length: {len(sql)} characters")
    
    # Execute the migration
    status, result = execute_sql(sql)
    
    if status == 200:
        print("✅ Migration applied successfully")
        print(f"Result: {result}")
    else:
        print(f"❌ Migration failed with status: {status}")
        print(f"Error: {result}")
    
    return 0 if status == 200 else 1

if __name__ == "__main__":
    exit(main())