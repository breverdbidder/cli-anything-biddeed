#!/usr/bin/env python3
"""
Quick test of Supabase connectivity using the shared utilities
"""
import sys
import os

# Add the shared module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

try:
    from cli_anything_shared.supabase import get_client, health_check
    print("✅ Shared supabase module imported successfully")
    
    # Test health check
    if health_check():
        print("✅ Database health check passed")
        
        # Try to get a client and do a simple query
        client = get_client()
        print("✅ Supabase client created successfully")
        
        # Query gold_standard_county_status for our counties
        assigned_counties = ['charlotte', 'suwannee', 'lee', 'washington', 'lafayette']
        
        # Simple count query first
        result = client.table('gold_standard_county_status').select('count', count='exact').execute()
        print(f"✅ Total gold_standard_county_status records: {result.count}")
        
    else:
        print("❌ Database health check failed")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()