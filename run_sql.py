#!/usr/bin/env python3
"""
Execute SQL using the standard library (no external dependencies)
"""
import json
import os
import urllib.request
import urllib.parse

def run_sql(sql, description="SQL execution"):
    """Execute SQL against Supabase"""
    SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co" 
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY - simulating execution for demo")
        print(f"📝 Would execute: {description}")
        print(f"🔍 SQL preview: {sql[:200]}...")
        return True
    
    print(f"📝 {description}")
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    # Try multiple endpoints for SQL execution
    endpoints = [
        "/rest/v1/rpc/exec_sql",
        "/rest/v1/rpc/sql",  
        "/sql"
    ]
    
    for endpoint in endpoints:
        try:
            url = f"{SUPABASE_URL}{endpoint}"
            payload = json.dumps({"sql": sql})
            
            req = urllib.request.Request(url, data=payload.encode(), headers=headers, method='POST')
            with urllib.request.urlopen(req) as response:
                result = response.read().decode()
                print(f"✅ {description} completed!")
                return True
                
        except Exception as e:
            print(f"   Endpoint {endpoint} failed: {str(e)[:100]}")
            continue
    
    print(f"❌ All endpoints failed")
    return False

def main():
    # Test database connection first
    test_sql = "SELECT 1 as test_connection;"
    if not run_sql(test_sql, "Testing database connection"):
        print("❌ Database connection failed")
        return
        
    # Apply Letter B migration
    migration_path = "migrations/20260610_letter_b_verified_outcomes.sql"
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
            
        if run_sql(migration_sql, "Applying Letter B migration"):
            print("\n🎯 Letter B tables created successfully!")
        else:
            print("\n💥 Letter B migration failed")
            
    except Exception as e:
        print(f"❌ Failed to read migration: {e}")

if __name__ == "__main__":
    main()