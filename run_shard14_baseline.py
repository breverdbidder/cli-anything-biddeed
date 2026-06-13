#!/usr/bin/env python3
"""
SHARD-14 Gold Standard Baseline - Autonomous Session
Run current county evaluations and get baseline metrics for targeted improvements
"""
import os
import sys
import subprocess

# Set environment variables as mentioned in CLAUDE.md
os.environ["SUPABASE_URL"] = "https://mocerqjnksmhcjzxrewo.supabase.co"

# Check if we can access the verification script that was created
script_path = "scripts/verify_shard14_status.py"

if os.path.exists(script_path):
    print("=== SHARD-14 AUTONOMOUS SESSION BASELINE ===")
    print("Running county evaluation script...")
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, 
                              text=True, 
                              timeout=120)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
            
        print(f"\nReturn code: {result.returncode}")
        
    except subprocess.TimeoutExpired:
        print("❌ Script timed out after 2 minutes")
    except Exception as e:
        print(f"❌ Error running script: {e}")
else:
    print(f"❌ Script not found: {script_path}")

# If that fails, try direct httpx approach with minimal verification
print("\n=== FALLBACK: Direct Database Test ===")
try:
    import httpx
    
    url = "https://mocerqjnksmhcjzxrewo.supabase.co/rest/v1"
    
    # Try to get some basic database info without auth first
    with httpx.Client(timeout=10) as client:
        # Try a basic endpoint that might be publicly accessible
        test_endpoints = [
            f"{url}/fl_counties?select=count&limit=1",
            f"{url}/multi_county_auctions?select=count&limit=1"
        ]
        
        for endpoint in test_endpoints:
            try:
                response = client.get(endpoint)
                print(f"Test {endpoint}: {response.status_code}")
                if response.status_code in [200, 401, 403]:  # 401/403 means endpoint exists
                    print("✅ Database is accessible (auth needed for full access)")
                    break
            except Exception as e:
                print(f"❌ {endpoint}: {e}")
                
except ImportError:
    print("❌ httpx not available")
except Exception as e:
    print(f"❌ Fallback test failed: {e}")

print("\n=== NEXT STEPS ===")
print("1. Database connection test completed")
print("2. This session will proceed with available data sources")
print("3. Will implement Gold Standard improvements based on issue brief")