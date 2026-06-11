#!/usr/bin/env python3
"""
Quick database test for GOLD STANDARD SHARD-8 counties
"""
import httpx

# Supabase configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"

def test_with_public_readonly():
    """Test connection with read-only access to get current metrics"""
    
    # Our assigned counties for shard-8
    counties = ['indian_river', 'volusia', 'lee', 'desoto', 'monroe']
    
    try:
        client = httpx.Client(timeout=30)
        
        print("=== Testing Public Read Access ===")
        
        # Try to get basic table info without auth (if RLS allows)
        r = client.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=county&limit=5")
        print(f"Public access test: {r.status_code}")
        
        if r.status_code == 401:
            print("❌ Auth required - need SUPABASE_KEY environment variable")
            return False
        elif r.status_code == 200:
            print("✅ Public read access available")
            
            # Get counts by county
            for county in counties:
                try:
                    r = client.get(f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county=eq.{county}")
                    if r.status_code == 200:
                        count_data = r.json()
                        if count_data and len(count_data) > 0:
                            count = count_data[0].get('count', 0)
                        else:
                            count = 0
                        print(f"  {county}: {count} auctions")
                    else:
                        print(f"  {county}: Error {r.status_code}")
                except Exception as e:
                    print(f"  {county}: Error - {e}")
            
            return True
        else:
            print(f"❌ Unexpected response: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    test_with_public_readonly()