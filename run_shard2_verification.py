#!/usr/bin/env python3
"""
Quick script to run the shard2 verification with proper environment setup
SHARD-2 counties: brevard, sarasota, jackson, st_lucie, holmes
"""
import os
import sys

# Set up environment variables as they would be in GitHub Actions
os.environ['SUPABASE_URL'] = "https://mocerqjnksmhcjzxrewo.supabase.co"
# The SUPABASE_SERVICE_KEY should be available from the environment
if not os.environ.get('SUPABASE_SERVICE_KEY'):
    print("ERROR: SUPABASE_SERVICE_KEY not found in environment")
    print("Available environment keys:", [k for k in os.environ.keys() if 'SUPA' in k.upper()])
    sys.exit(1)
    
os.environ['SUPABASE_KEY'] = os.environ['SUPABASE_SERVICE_KEY']

# Import and run the verification script
sys.path.insert(0, 'scripts')
from shard2_verification_protocol import main

if __name__ == "__main__":
    print("=== SHARD-2 GOLD STANDARD VERIFICATION ===")
    print("Counties: brevard, sarasota, jackson, st_lucie, holmes")
    print("Dispatch ID: 464969f4-742c-4182-8aad-5727210bef66")
    print("="*50)
    main()