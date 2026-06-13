#!/usr/bin/env python3
"""
Apply SHARD-20 migration to Supabase
Per CLAUDE.md autonomous operations: NO HITL required for migrations
"""
import os
import sys

# Check environment first
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"SUPABASE_URL: {SUPABASE_URL}")
print(f"SUPABASE_KEY present: {'YES' if SUPABASE_KEY else 'NO'}")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY not available - cannot apply migration")
    print("Migration would create:")
    print("- fl_counties records for brevard/duval")  
    print("- multi_county_auctions additional columns")
    print("- duval_acclaim_harvest_queue table")
    print("- Functions: promote_tier1_from_outcomes, feed_acclaim_queue_duval, map_staged_to_outcomes_duval")
    print("- ULTRALOOP audit already exists per existing migration")
    sys.exit(1)

try:
    import httpx
    print("✅ httpx available for database operations")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Read the migration file
migration_file = "migrations/20260613_shard20_county_setup.sql"

try:
    with open(migration_file, 'r') as f:
        migration_sql = f.read()
    print(f"✅ Read migration file: {len(migration_sql)} characters")
except FileNotFoundError:
    print(f"❌ Migration file not found: {migration_file}")
    sys.exit(1)

# Apply migration via Supabase RPC
headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

base_url = f"{SUPABASE_URL}/rest/v1"

print("🔄 Applying SHARD-20 migration to Supabase...")

try:
    with httpx.Client() as client:
        response = client.post(
            f"{base_url}/rpc/execute_sql",
            headers=headers,
            json={"query": migration_sql},
            timeout=120.0
        )
        
        if response.status_code == 200:
            print("✅ SHARD-20 migration applied successfully")
            print("Migration included:")
            print("- brevard/duval county setup (co_no 9/16, frozen denominators)")
            print("- pipeline_counties configurations (brevard=clerk_html, duval=realauction)")
            print("- duval_acclaim_harvest_queue + staging tables")
            print("- promote_tier1_from_outcomes function (Letter F automation)")
            print("- feed_acclaim_queue_duval function (Letter B automation)")
            print("- map_staged_to_outcomes_duval function (CHAIN BREAK fix)")
        else:
            print(f"❌ Migration failed: {response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

except Exception as e:
    print(f"❌ Migration error: {e}")
    sys.exit(1)

print("🎯 Ready for SHARD-20 sprint execution")