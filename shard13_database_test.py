#!/usr/bin/env python3
"""
Simple database connectivity test for SHARD-13
"""
import os
import sys

# Check for httpx
try:
    import httpx
    print("✅ httpx is available")
except ImportError:
    print("❌ httpx not available")
    # Try to see what packages are available
    import subprocess
    result = subprocess.run([sys.executable, '-m', 'pip', 'list'], capture_output=True, text=True)
    print("Available packages (first 10 lines):")
    print('\n'.join(result.stdout.split('\n')[:10]))
    sys.exit(1)

# Test basic environment
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")

# Check for common Supabase environment variables
supabase_vars = ['SUPABASE_URL', 'SUPABASE_KEY', 'SUPABASE_SERVICE_KEY', 'SUPABASE_ANON_KEY']
available_vars = {}
for var in supabase_vars:
    value = os.environ.get(var, '')
    available_vars[var] = bool(value)
    print(f"{var}: {'Present' if value else 'Not found'}")

# If we have the basic connection info, try a simple connection
supabase_url = os.environ.get('SUPABASE_URL', 'https://mocerqjnksmhcjzxrewo.supabase.co')
supabase_key = os.environ.get('SUPABASE_KEY') or os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_ANON_KEY')

if supabase_key:
    print(f"\n🔗 Attempting connection to {supabase_url}")
    
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        client = httpx.Client(timeout=30)
        # Simple test query
        response = client.get(
            f"{supabase_url}/rest/v1/gold_standard_scoreboard?select=county_slug&limit=5",
            headers=headers
        )
        
        print(f"Response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Database connection successful")
            print(f"Sample counties in scoreboard: {[row.get('county_slug') for row in data[:3]]}")
        else:
            print(f"❌ Connection failed: {response.text}")
            
        client.close()
    except Exception as e:
        print(f"❌ Connection error: {e}")
else:
    print("❌ No Supabase credentials found")
    print("Available environment variables containing 'SUP':")
    for k, v in os.environ.items():
        if 'SUP' in k.upper():
            print(f"  {k}: {'[PRESENT]' if v else '[EMPTY]'}")