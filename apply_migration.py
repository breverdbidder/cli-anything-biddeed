#!/usr/bin/env python3
"""
Apply the Letter B migration to create verified outcomes tables
"""
import json
import os
import urllib.request
import urllib.parse

def apply_migration():
    """Apply the Letter B verified outcomes migration"""
    SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not SUPABASE_KEY:
        print("❌ CRITICAL: No SUPABASE_KEY found")
        return False
    
    # Read the migration SQL
    migration_path = "/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/migrations/20260610_letter_b_verified_outcomes.sql"
    try:
        with open(migration_path, 'r') as f:
            sql_content = f.read()
    except Exception as e:
        print(f"❌ Failed to read migration file: {e}")
        return False
    
    print(f"📝 Applying Letter B migration...")
    print(f"   Creating tables: tax_deed_outcomes, foreclosure_outcomes")
    
    # Apply migration via Supabase REST API
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = json.dumps({"sql": sql_content})
    
    try:
        req = urllib.request.Request(url, data=payload.encode(), headers=headers, method='POST')
        with urllib.request.urlopen(req) as response:
            result = response.read().decode()
            
        print("✅ Migration applied successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        
        # Try alternative approach using direct SQL endpoint
        try:
            print("🔄 Trying alternative SQL execution...")
            
            # Split SQL into individual statements
            statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
            
            for i, stmt in enumerate(statements):
                if not stmt:
                    continue
                    
                print(f"   Executing statement {i+1}/{len(statements)}...")
                
                # Use SQL endpoint directly
                sql_url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
                payload = json.dumps({"sql": stmt + ";"})
                
                req = urllib.request.Request(sql_url, data=payload.encode(), headers=headers, method='POST')
                with urllib.request.urlopen(req) as response:
                    response.read()  # consume response
                    
            print("✅ Migration applied via alternative method!")
            return True
            
        except Exception as e2:
            print(f"❌ Alternative method also failed: {e2}")
            return False

if __name__ == "__main__":
    if apply_migration():
        print("\n🎯 Letter B tables are ready for verified outcomes!")
    else:
        print("\n💥 Migration failed - check database connectivity")
        exit(1)