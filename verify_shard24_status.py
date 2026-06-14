#!/usr/bin/env python3
"""
Verify current status of SHARD-24 counties (citrus, broward, charlotte)
Get current Letter A-J metrics before starting ULTRALOOP protocol
"""
import os
import httpx
import json
from typing import Dict, Any

# Database connection - using values from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
# We'll need to handle missing SUPABASE_KEY gracefully
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-24 assigned counties per the issue brief
SHARD_COUNTIES = ['citrus', 'broward', 'charlotte']

def sb_headers():
    """Supabase headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def sb_rpc(function_name: str, params: Dict = None) -> Any:
    """Execute Supabase RPC function"""
    with httpx.Client(timeout=90) as client:
        try:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
                headers=sb_headers(),
                json=params or {}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"ERROR: RPC {function_name} failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"ERROR: RPC {function_name} exception: {e}")
            return None

def main():
    """Verify status of assigned counties"""
    print("=== SHARD-24 County Status Verification ===")
    print(f"Counties: {SHARD_COUNTIES}")
    print()
    
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_KEY not found in environment")
        return 1
    
    for county_slug in SHARD_COUNTIES:
        print(f"\n--- {county_slug.upper()} COUNTY ---")
        
        # Get current evaluation
        result = sb_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county_slug})
        
        if not result:
            print(f"ERROR: Failed to get evaluation for {county_slug}")
            continue
        
        # Display current status
        passed = 0
        failed = 0
        
        for letter_data in result:
            letter = letter_data.get('letter', '')
            metric = letter_data.get('metric', 0)
            passes = letter_data.get('pass', False)
            detail = letter_data.get('detail', '')
            
            status = "PASS" if passes else "FAIL"
            if passes:
                passed += 1
            else:
                failed += 1
            
            print(f"    {letter} {status} metric={metric} [{detail}]")
        
        print(f"    Summary: {passed}/10 PASS, {failed}/10 FAIL")
    
    return 0

if __name__ == "__main__":
    exit(main())