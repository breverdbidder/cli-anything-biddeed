#!/usr/bin/env python3
"""
Quick test for SHARD-1 database access and status check
"""
import os
import httpx

# Credentials should be available via GitHub Actions secrets
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Supabase URL: {SUPABASE_URL}")
print(f"API Key available: {bool(SUPABASE_KEY)}")

if SUPABASE_KEY:
    print(f"API Key prefix: {SUPABASE_KEY[:20]}...")

def test_basic_access():
    """Test basic database access"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        client = httpx.Client(timeout=30)
        
        # Test basic connection
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        print(f"Connection test: {r.status_code}")
        
        if r.status_code == 200:
            print("✅ Database connection successful!")
            
            # Test one county evaluation
            print("\\nTesting county evaluation for charlotte...")
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug_arg": "charlotte"}
            )
            
            if r.status_code == 200:
                result = r.json()
                print(f"✅ Charlotte evaluation successful")
                if isinstance(result, list) and len(result) > 0:
                    pass_count = sum(1 for x in result if x.get('pass'))
                    print(f"Charlotte status: {pass_count}/10 pass")
                return True
            else:
                print(f"❌ County evaluation failed: {r.status_code}")
                return False
        else:
            print(f"❌ Database connection failed: {r.status_code} - {r.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if test_basic_access():
        print("\\n✅ Ready to proceed with SHARD-1 autonomous work!")
    else:
        print("\\n❌ Database access issues - need to resolve before proceeding")