#!/usr/bin/env python3
"""
SHARD-20 STATUS VERIFICATION - AUTOPILOT RUN 20
Target counties: brevard, duval
Verifies current gold standard metrics before execution
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("SUPABASE_KEY not found in environment")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

TARGET_COUNTIES = ['brevard', 'duval']

def query_supabase(sql: str) -> dict:
    """Execute SQL query via Supabase RPC"""
    try:
        with httpx.Client() as client:
            response = client.post(
                f"{BASE}/rpc/execute_sql",
                headers=HEADERS,
                json={"query": sql},
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        logger.error(f"Query error: {e}")
        return None

def verify_county_status(county: str) -> dict:
    """Get current gold standard metrics for a county"""
    logger.info(f"Verifying status for {county}...")
    
    sql = f"SELECT public.pencil_dod_evaluate_county('{county}');"
    result = query_supabase(sql)
    
    if result:
        return result[0] if result else {}
    else:
        logger.error(f"Failed to get status for {county}")
        return {}

def main():
    logger.info("SHARD-20 STATUS VERIFICATION - Starting...")
    logger.info(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    logger.info(f"Session start: {datetime.now(timezone.utc).isoformat()}")
    
    all_status = {}
    
    for county in TARGET_COUNTIES:
        status = verify_county_status(county)
        all_status[county] = status
        
        if status:
            logger.info(f"{county.upper()} STATUS:")
            logger.info(json.dumps(status, indent=2))
        else:
            logger.error(f"Failed to get status for {county}")
    
    # Summary
    logger.info("\n=== SHARD-20 CURRENT METRICS SUMMARY ===")
    for county, status in all_status.items():
        if status and 'pencil_dod_evaluate_county' in status:
            metrics = status['pencil_dod_evaluate_county']
            logger.info(f"{county.upper()}: {json.dumps(metrics, separators=(',', ':'))}")
    
    return all_status

if __name__ == "__main__":
    main()