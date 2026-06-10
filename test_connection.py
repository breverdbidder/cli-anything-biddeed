#!/usr/bin/env python3
"""Quick test to connect to Supabase and get county data"""

import httpx
import os

SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"

def test_connection():
    # From CLAUDE.md, we know the project is mocerqjnksmhcjzxrewo.supabase.co
    # Let's try to connect without key first to see what happens
    
    client = httpx.Client(timeout=30, headers={"User-Agent": "GoldStandard-Test"})
    
    # Try a simple GET request to the REST API
    try:
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=3")
        print(f"Status: {response.status_code}")
        print(f"Headers: {response.headers}")
        if response.status_code == 200:
            data = response.json()
            print(f"Data sample: {data[:1] if data else 'empty'}")
        else:
            print(f"Response text: {response.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")
    
    client.close()

if __name__ == "__main__":
    test_connection()