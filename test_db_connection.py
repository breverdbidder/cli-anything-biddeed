#!/usr/bin/env python3
"""Test database connection and query county status for gold standard."""

import os
import sys

def test_db_connection():
    """Test Supabase connection and query county data."""
    try:
        # Check environment variables
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
        
        if not url or not key:
            print("Missing Supabase credentials")
            print(f"SUPABASE_URL: {'SET' if url else 'NOT SET'}")
            print(f"SUPABASE_KEY: {'SET' if key else 'NOT SET'}")
            return False
            
        # Try to import and create client
        try:
            from supabase import create_client
        except ImportError:
            print("Installing supabase...")
            os.system("pip install supabase")
            from supabase import create_client
            
        client = create_client(url, key)
        
        # Test basic connectivity
        response = client.table("fl_counties").select("co_no,name").limit(3).execute()
        print(f"✓ Database connection successful. Found {len(response.data)} counties.")
        
        # Query our target counties
        target_counties = ["citrus", "leon", "palm_beach"]
        for county_name in target_counties:
            result = client.table("fl_counties").select("*").eq("name", county_name.replace("_", " ").title()).execute()
            if result.data:
                county = result.data[0]
                print(f"✓ Found {county['name']} (co_no={county['co_no']})")
            else:
                print(f"✗ County {county_name} not found")
                
        return True
        
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    if test_db_connection():
        print("Database connection test passed!")
    else:
        print("Database connection test failed!")
        sys.exit(1)