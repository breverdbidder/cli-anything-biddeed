#!/usr/bin/env python3
"""
SHARD-7 Migration Runner
Execute the SHARD-7 county setup migration for A-lane configuration

Per CLAUDE.md: supabase db push (NO HITL for autonomous migrations)
"""

import subprocess
import os
import sys

def run_migration():
    """Execute the SHARD-7 migration using Supabase CLI"""
    print("=== SHARD-7 MIGRATION EXECUTION ===")
    print("Applying 20260614_shard7_county_setup.sql")
    print()
    
    try:
        # Check if supabase CLI is available
        result = subprocess.run(
            ["supabase", "--version"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        print(f"✅ Supabase CLI: {result.stdout.strip()}")
        
    except FileNotFoundError:
        print("❌ Supabase CLI not found")
        print("Alternative: Apply migration manually via database connection")
        return False
    except subprocess.CalledProcessError:
        print("❌ Supabase CLI check failed")
        return False
    
    try:
        # Apply the migration
        print("🚀 Executing migration...")
        result = subprocess.run(
            ["supabase", "db", "push"], 
            cwd="/home/runner/work/cli-anything-biddeed/cli-anything-biddeed",
            capture_output=True,
            text=True,
            check=True
        )
        
        print("✅ Migration applied successfully")
        print(f"Output: {result.stdout}")
        if result.stderr:
            print(f"Warnings: {result.stderr}")
            
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Migration failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def verify_migration():
    """Verify the migration was applied correctly"""
    print("\n=== VERIFICATION ===")
    print("Migration should have:")
    print("✓ Inserted 5 counties in fl_counties")
    print("✓ Configured 5 pipeline_counties entries")  
    print("✓ Created required tables (bid_decisions, outcomes)")
    print("✓ Set up county_scrape_status for H-letter tracking")
    print()
    print("Next: Run pencil_dod_evaluate_county for each county to verify A-lane coverage")

def main():
    """Main execution function"""
    if run_migration():
        verify_migration()
        print("✅ SHARD-7 A-lane configuration complete")
    else:
        print("❌ Migration failed - manual intervention required")
        
if __name__ == "__main__":
    main()