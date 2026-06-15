#!/usr/bin/env python3
"""
Apply Duval G+I Substrate Build Migration
SHARD-8 autonomous session - SHIP TO MAIN
"""
import os
import httpx
import json
from datetime import datetime

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

def read_migration_file():
    """Read the Duval G+I substrate migration SQL"""
    with open('supabase/migrations/20260615_duval_gi_substrate_build.sql', 'r') as f:
        return f.read()

def execute_sql(sql_content):
    """Execute SQL against Supabase via REST API"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json"
    }
    
    # Split SQL into statements (simple split on semicolons)
    statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]
    
    results = []
    for i, stmt in enumerate(statements):
        if stmt.startswith('--') or not stmt:
            continue
            
        print(f"Executing statement {i+1}/{len(statements)}: {stmt[:50]}...")
        
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=headers,
                    json={"sql": stmt},
                    timeout=30
                )
            
            if response.status_code == 200:
                results.append(f"✅ Statement {i+1} executed successfully")
            else:
                results.append(f"⚠️ Statement {i+1} failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            results.append(f"❌ Statement {i+1} error: {e}")
    
    return results

def verify_migration():
    """Verify the migration was applied successfully"""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    verification_queries = [
        "SELECT COUNT(*) as jurisdiction_count FROM jurisdictions WHERE county = 'Duval'",
        "SELECT COUNT(*) as districts_count FROM zoning_districts zd JOIN jurisdictions j ON zd.jurisdiction_id = j.id WHERE j.county = 'Duval'",
        "SELECT COUNT(*) as standards_count FROM zone_standards zs JOIN zoning_districts zd ON zs.zoning_district_id = zd.id JOIN jurisdictions j ON zd.jurisdiction_id = j.id WHERE j.county = 'Duval'",
        "SELECT COUNT(*) as parcels_zoned FROM parcel_zones pz JOIN jurisdictions j ON pz.jurisdiction_id = j.id WHERE j.county = 'Duval'"
    ]
    
    results = {}
    for query in verification_queries:
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=headers,
                    json={"sql": query},
                    timeout=10
                )
            
            if response.status_code == 200:
                data = response.json()
                results[query] = data
            else:
                results[query] = f"Failed: {response.status_code}"
                
        except Exception as e:
            results[query] = f"Error: {e}"
    
    return results

def main():
    print("🚀 SHARD-8 DUVAL G+I SUBSTRATE BUILD")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("="*60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY not found in environment")
        print("Migration cannot proceed without database credentials")
        print("This is expected in some Claude Code environments")
        return
    
    print("📖 Reading migration file...")
    sql_content = read_migration_file()
    print(f"✅ Migration loaded: {len(sql_content)} characters")
    
    print("\n🔧 Executing migration...")
    results = execute_sql(sql_content)
    
    for result in results:
        print(result)
    
    print("\n🔍 Verifying migration results...")
    verification = verify_migration()
    
    for query, result in verification.items():
        print(f"Query: {query[:50]}...")
        print(f"Result: {result}")
        print()
    
    print("="*60)
    print("🎯 DUVAL G+I SUBSTRATE BUILD COMPLETE")
    print("Next: Run verification protocol to measure G and I metrics")

if __name__ == "__main__":
    main()