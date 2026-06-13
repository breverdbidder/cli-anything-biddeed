#!/usr/bin/env python3
"""
Check current metrics for SHARD-10 counties: leon, baker, okaloosa, franklin, union
Also check priority brevard and duval metrics per directives.

Uses environment variables from GitHub Actions.
"""
import os
import sys
import json
from datetime import datetime, timezone

# Expected environment variables in GHA
SB_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

if not SB_KEY:
    print("ERROR: No SUPABASE_KEY or SUPABASE_SERVICE_KEY found")
    sys.exit(1)

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Install with: pip install httpx")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json"
    }

def query_county_evaluation(county_name: str) -> dict:
    """Query pencil_dod_evaluate_county function for a specific county."""
    try:
        response = httpx.post(
            f"{SB_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_name": county_name},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e), "county": county_name}

def query_gold_standard_loop() -> dict:
    """Query the full gold standard loop to get updated metrics."""
    try:
        response = httpx.post(
            f"{SB_URL}/rest/v1/rpc/gold_standard_loop",
            headers=sb_headers(),
            json={},
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    # Set statement timeout to 0 as required by CLAUDE.md
    print("Setting statement timeout to 0...")
    try:
        httpx.post(
            f"{SB_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": "SET statement_timeout = 0;"},
            timeout=30.0
        )
    except Exception as e:
        print(f"Warning: Could not set statement timeout: {e}")

    print("GOLD STANDARD SHARD-10 METRICS CHECK")
    print("=" * 50)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()

    # SHARD-10 counties
    shard_counties = ["leon", "baker", "okaloosa", "franklin", "union"]
    
    # Priority counties per directives
    priority_counties = ["brevard", "duval"]
    
    all_counties = shard_counties + priority_counties
    
    results = {}
    
    for county in all_counties:
        print(f"Evaluating {county}...")
        result = query_county_evaluation(county)
        results[county] = result
        
        if "error" in result:
            print(f"  ERROR: {result['error']}")
        else:
            # Parse the metrics from the result
            print(f"  Metrics: {json.dumps(result, indent=2)}")
        print()
    
    print("SUMMARY")
    print("=" * 50)
    for county in all_counties:
        result = results[county]
        if "error" not in result and isinstance(result, dict):
            # Try to parse the grade if available
            grade = result.get("grade", "UNKNOWN")
            print(f"{county:10}: {grade}")
        else:
            print(f"{county:10}: ERROR")
    
    # Save results to file
    with open("shard10_metrics_check.json", "w") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "shard_counties": shard_counties,
            "priority_counties": priority_counties,
            "results": results
        }, f, indent=2)
    
    print(f"\nResults saved to shard10_metrics_check.json")

if __name__ == "__main__":
    main()