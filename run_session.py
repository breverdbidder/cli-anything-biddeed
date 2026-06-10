#!/usr/bin/env python3
"""
Execute the autonomous session by importing the script
"""
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

try:
    import autonomous_county_fix
    
    print("Starting Gold Standard Wave2-Shard-5 session...")
    success = autonomous_county_fix.main()
    
    if success:
        print("\n✅ Session completed successfully")
    else:
        print("\n❌ Session failed")
        
except Exception as e:
    print(f"❌ Error running session: {e}")
    import traceback
    traceback.print_exc()