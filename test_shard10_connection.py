#!/usr/bin/env python3
"""
Test Supabase connection for SHARD-10 work
"""
import os
import sys
import requests

# Try to set up environment variables as they would be in GitHub Actions
os.environ['SUPABASE_URL'] = "https://mocerqjnksmhcjzxrewo.supabase.co"

# Check for service key in environment
if os.environ.get('SUPABASE_SERVICE_KEY'):
    os.environ['SUPABASE_KEY'] = os.environ['SUPABASE_SERVICE_KEY']
    print("✅ Using SUPABASE_SERVICE_KEY from environment")
elif os.environ.get('SUPABASE_ANON_KEY'):
    os.environ['SUPABASE_KEY'] = os.environ['SUPABASE_ANON_KEY']
    print("⚠️ Using SUPABASE_ANON_KEY (limited permissions)")
else:
    print("❌ No SUPABASE keys found in environment")
    print("Available env vars:", [k for k in os.environ.keys() if 'SUPABASE' in k.upper()])
    sys.exit(1)

# Import our verification script
from verify_shard10_status import test_connection, get_county_evaluation

def main():
    print("🔧 Testing SHARD-10 database connection...")
    
    if test_connection():
        print("\n🔍 Testing county evaluation function...")
        result = get_county_evaluation('manatee')
        if result:
            print("✅ County evaluation function working")
            print(f"Sample result for manatee: {result}")
        else:
            print("❌ County evaluation function failed")
    else:
        print("❌ Basic connection test failed")

if __name__ == "__main__":
    main()