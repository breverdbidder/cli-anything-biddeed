#!/usr/bin/env python3
"""
SHARD-12 Session Runner with Environment Verification
This script tests the environment and runs the autonomous session
"""
import os
import sys
import subprocess
import json
from datetime import datetime, timezone

def check_environment():
    """Check required environment variables"""
    print("🔍 Environment Check")
    print("-" * 30)
    
    # Check Supabase credentials
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not supabase_url:
        print("❌ SUPABASE_URL not found")
        return False
    else:
        print(f"✅ SUPABASE_URL: {supabase_url}")
    
    if not supabase_key:
        print("❌ SUPABASE_KEY not found")
        return False
    else:
        print("✅ SUPABASE_KEY: Set (hidden)")
    
    return True

def check_python_packages():
    """Check required Python packages"""
    print("\n📦 Python Package Check")
    print("-" * 30)
    
    required = ['httpx', 'json', 'datetime', 'logging']
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\nMissing packages: {missing}")
        print("Installing missing packages...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install packages")
            return False
    
    return True

def run_session():
    """Execute the autonomous session"""
    print("\n🚀 Running SHARD-12 Autonomous Session")
    print("=" * 50)
    
    try:
        # Execute the main session script
        result = subprocess.run([
            sys.executable, 
            'shard12_autonomous_session.py'
        ], 
        capture_output=True, 
        text=True,
        cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed'
        )
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        print(f"\nExit code: {result.returncode}")
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Failed to run session: {e}")
        return False

def main():
    print("GOLD STANDARD SHARD-12 Session Runner")
    print(f"Start time: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)
    
    # Step 1: Environment check
    if not check_environment():
        print("\n❌ Environment check failed")
        return False
    
    # Step 2: Package check
    if not check_python_packages():
        print("\n❌ Package check failed")
        return False
    
    # Step 3: Run the session
    success = run_session()
    
    if success:
        print("\n✅ SHARD-12 session completed successfully")
    else:
        print("\n❌ SHARD-12 session failed")
    
    print(f"\nEnd time: {datetime.now(timezone.utc).isoformat()}")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)