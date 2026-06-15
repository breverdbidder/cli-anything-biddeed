#!/usr/bin/env python3
"""
Verify current gold standard metrics for Brevard and Duval counties.
Per HONESTY PROTOCOL: all claims must be VERIFIED with actual DB queries.
"""

import os
import asyncio
import httpx
from typing import Dict, Any, Optional

# Supabase connection details from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"

class GoldStandardDB:
    """Database client for gold standard metrics verification."""
    
    def __init__(self):
        # Get credentials from environment (should be available in GHA)
        self.url = SUPABASE_URL.rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
        if not self.key:
            raise ValueError("SUPABASE_SERVICE_KEY or SUPABASE_KEY environment variable required")
        
        self._headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    async def query_function(self, function_name: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Execute a Supabase function and return results."""
        try:
            url = f"{self.url}/rest/v1/rpc/{function_name}"
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(url, json=params or {}, headers=self._headers)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e)}

    async def query_table(self, table: str, params: Optional[Dict] = None) -> Any:
        """Query a table directly."""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    f"{self.url}/rest/v1/{table}",
                    params=params or {},
                    headers=self._headers,
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"error": str(e)}

async def verify_current_metrics():
    """Verify current gold standard metrics for Brevard and Duval."""
    db = GoldStandardDB()
    
    print("=== GOLD STANDARD METRICS VERIFICATION ===")
    print(f"Database: {SUPABASE_URL}")
    print(f"Timestamp: {asyncio.get_event_loop().time()}")
    print()
    
    # Verify connection first
    print("Testing database connection...")
    test_result = await db.query_table("ping", {"limit": "1"})
    if "error" in test_result:
        print(f"❌ Database connection failed: {test_result['error']}")
        return False
    print("✅ Database connection successful")
    print()
    
    # Query current metrics for each county using the evaluation function
    counties = ["brevard", "duval"]
    
    for county in counties:
        print(f"=== {county.upper()} COUNTY METRICS ===")
        
        # Use the pencil_dod_evaluate_county function mentioned in the brief
        result = await db.query_function("pencil_dod_evaluate_county", {"county_slug": county})
        
        if "error" in result:
            print(f"❌ Error querying {county}: {result['error']}")
            continue
        
        print(f"Raw evaluation result: {result}")
        
        # Try to extract metrics from the result
        if isinstance(result, dict):
            for key, value in result.items():
                print(f"  {key}: {value}")
        elif isinstance(result, list) and result:
            for metric in result:
                print(f"  {metric}")
        
        print()
    
    # Also try to query the gold_standard_county_status table directly
    print("=== COUNTY STATUS TABLE ===")
    status_result = await db.query_table("gold_standard_county_status", 
                                        {"county_slug": "in.(brevard,duval)"})
    
    if "error" in status_result:
        print(f"❌ Error querying county status: {status_result['error']}")
    else:
        print("County status records:")
        for record in status_result:
            print(f"  {record}")
    
    print()
    return True

if __name__ == "__main__":
    success = asyncio.run(verify_current_metrics())
    if not success:
        exit(1)