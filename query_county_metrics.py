#!/usr/bin/env python3
"""
Query current county metrics for gold standard campaign.
"""
import os
import sys
import httpx

# Configuration
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    return {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

def query_county_metrics(county_name):
    """Query metrics for a specific county using pencil_dod_evaluate_county function."""
    try:
        r = httpx.post(
            f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_name": county_name},
            timeout=30.0
        )
        if r.status_code == 200:
            return r.json()
        else:
            print(f"Error querying {county_name}: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"Exception querying {county_name}: {e}")
        return None

def main():
    if not SB_KEY:
        print("Error: SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable not set")
        sys.exit(1)
    
    counties = ["charlotte", "citrus", "broward"]
    
    for county in counties:
        print(f"\n=== {county.upper()} METRICS ===")
        metrics = query_county_metrics(county)
        if metrics:
            print(f"Raw response: {metrics}")
        else:
            print(f"Failed to get metrics for {county}")

if __name__ == "__main__":
    main()