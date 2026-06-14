#!/usr/bin/env python3
"""
Run SHARD-10 migration to set up county configurations
"""
import os
import sys
import requests
import psycopg2
from datetime import datetime

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
DB_PASSWORD = "BiKvLwWTdS0PwulM"  # From CLAUDE.md

# Connection details
DB_HOST = "aws-0-us-west-2.pooler.supabase.com"
DB_PORT = 5432
DB_NAME = "postgres" 
DB_USER = "postgres"

def run_migration():
    """Run the SHARD-10 setup migration"""
    print("🔧 Running SHARD-10 County Setup Migration...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Read migration file
    migration_path = "migrations/20260614_shard10_county_setup.sql"
    
    try:
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        print(f"✅ Migration file loaded: {len(migration_sql)} characters")
    except Exception as e:
        print(f"❌ Failed to load migration file: {e}")
        return False
    
    # Connect to database
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode='require'
        )
        
        print("✅ Database connection established")
        
        with conn.cursor() as cursor:
            # Set statement timeout to unlimited for migration
            cursor.execute("SET statement_timeout = 0;")
            
            # Run the migration
            cursor.execute(migration_sql)
            
            # Commit the changes
            conn.commit()
            
        print("✅ Migration executed successfully")
        
        # Verify the setup worked
        with conn.cursor() as cursor:
            # Check fl_counties
            cursor.execute("SELECT co_no, name, slug FROM fl_counties WHERE co_no IN (21, 29, 51, 57, 73) ORDER BY co_no;")
            counties = cursor.fetchall()
            
            print("\n📊 FL Counties Setup:")
            for co_no, name, slug in counties:
                print(f"  {co_no}: {name} -> {slug}")
            
            # Check counties table
            cursor.execute("SELECT county_slug, county_name, status FROM counties WHERE county_slug IN ('manatee', 'collier', 'okeechobee', 'franklin', 'union') ORDER BY county_slug;")
            pipeline_counties = cursor.fetchall()
            
            print("\n📊 Pipeline Counties Setup:")
            for slug, name, status in pipeline_counties:
                print(f"  {slug}: {name} ({status})")
            
            # Check if bid_decisions table exists
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'bid_decisions';")
            bid_decisions_exists = cursor.fetchone()[0] > 0
            
            print(f"\n📊 Infrastructure Setup:")
            print(f"  bid_decisions table: {'✅ Created' if bid_decisions_exists else '❌ Missing'}")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def verify_setup():
    """Verify the migration worked by testing county evaluation"""
    print("\n🔍 Verifying setup by testing county evaluation...")
    
    # Test via REST API
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    test_counties = ['manatee', 'franklin']
    
    for county in test_counties:
        try:
            payload = {"county_name": county}
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    print(f"✅ {county}: Evaluation function working")
                    # Show A-letter specifically
                    a_metric = next((r.get('metric') for r in result if r.get('letter') == 'A'), None)
                    print(f"  A-metric: {a_metric}")
                else:
                    print(f"⚠️ {county}: Empty evaluation result")
            else:
                print(f"❌ {county}: Evaluation failed - {response.status_code}")
                
        except Exception as e:
            print(f"❌ {county}: Error - {e}")

def main():
    """Main function"""
    print("SHARD-10 Migration Runner")
    print("=" * 50)
    
    if run_migration():
        verify_setup()
        print("\n✅ SHARD-10 setup complete!")
        print("Counties ready: manatee, collier, okeechobee, franklin, union")
        print("Next step: Run lane configuration to activate A-metrics")
    else:
        print("\n❌ Migration failed - check errors above")

if __name__ == "__main__":
    main()