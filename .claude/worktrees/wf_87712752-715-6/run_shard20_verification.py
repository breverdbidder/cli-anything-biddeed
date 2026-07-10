#!/usr/bin/env python3
"""
Quick script to run the shard20 verification with proper environment setup
"""
import os
import sys

# Set up environment variables as they would be in GitHub Actions
os.environ['SUPABASE_URL'] = "https://mocerqjnksmhcjzxrewo.supabase.co"
# The SUPABASE_SERVICE_KEY should be available from the environment
if not os.environ.get('SUPABASE_SERVICE_KEY'):
    print("ERROR: SUPABASE_SERVICE_KEY not found in environment")
    sys.exit(1)
    
os.environ['SUPABASE_KEY'] = os.environ['SUPABASE_SERVICE_KEY']

# Import and run the verification script
sys.path.insert(0, 'scripts')
from verify_shard20_status import main

if __name__ == "__main__":
    main()