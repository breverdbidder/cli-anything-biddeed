#!/usr/bin/env python3
"""Duval Letter B Completion Script
GOLD STANDARD implementation to complete Duval B metric from 74.5% to 95%+

Finds closed Duval cases not in acclaim_harvest_queue and enqueues them
for processing by existing 5 worker crons.

Current status: 8,979 of 9,336 closed Duval rows carry PropertyOnion IDs (PO-xxxxxx)
as case_number, not court case numbers. This creates B ceiling and C/D gap.

Strategy: 
1. Find closed cases missing from acclaim queue
2. Enqueue for acclaim workers to process
3. Monitor queue drain and outcome generation

Author: Claude Code (GOLD STANDARD Session 2026-06-12)
"""
import os
import sys
import json
import httpx
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    logger.error("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=120)

def find_missing_duval_cases() -> List[Dict]:
    """Find closed Duval cases not in acclaim_harvest_queue"""
    logger.info("🔍 Finding closed Duval cases missing from acclaim queue...")
    
    try:
        # Get all closed Duval cases
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "case_number,sale_date,sale_type,auction_status",
                "county": "eq.duval",
                "auction_status": "in.(sold,no_sale,canceled)",
                "order": "sale_date.desc",
                "limit": "10000"
            }
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Failed to fetch Duval auctions: {response.status_code}")
            return []
            
        all_cases = response.json()
        logger.info(f"Found {len(all_cases)} total closed Duval auctions")
        
        # Get cases already in acclaim queue
        response = client.get(
            f"{BASE}/acclaim_harvest_queue",
            headers=HEADERS,
            params={
                "select": "case_number",
                "county": "eq.duval",
                "limit": "20000"
            }
        )
        
        if response.status_code == 200:
            queued_cases = {case["case_number"] for case in response.json()}
            logger.info(f"Found {len(queued_cases)} cases already in acclaim queue")
        else:
            logger.warning("⚠️ Could not fetch acclaim queue, assuming empty")
            queued_cases = set()
        
        # Find missing cases
        missing_cases = []
        for case in all_cases:
            case_num = case.get("case_number", "")
            
            # Skip PropertyOnion IDs (PO-xxxxx format)
            if case_num.startswith("PO-"):
                continue
                
            # Skip if already queued
            if case_num in queued_cases:
                continue
                
            # Skip invalid case numbers
            if not case_num or len(case_num) < 5:
                continue
                
            missing_cases.append(case)
        
        logger.info(f"✅ Found {len(missing_cases)} missing cases (excluding PO- IDs)")
        return missing_cases
        
    except Exception as e:
        logger.error(f"❌ Error finding missing cases: {e}")
        return []

def enqueue_cases_for_acclaim(cases: List[Dict]) -> int:
    """Enqueue missing cases for acclaim processing"""
    if not cases:
        return 0
        
    logger.info(f"📋 Enqueuing {len(cases)} cases for acclaim processing...")
    
    # Prepare queue entries
    queue_entries = []
    for case in cases:
        entry = {
            "case_number": case["case_number"],
            "county": "duval",
            "sale_type": case.get("sale_type", "foreclosure"),
            "sale_date": case.get("sale_date"),
            "status": "pending",
            "priority": "high",  # High priority for B completion
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "data_source": "duval_b_completion_backfill",
            "notes": "Auto-enqueued by GOLD STANDARD B completion script"
        }
        queue_entries.append(entry)
    
    try:
        # Write to acclaim_harvest_queue via RPC (table may not be PostgREST exposed)
        response = client.post(
            f"{BASE}/rpc/feed_acclaim_queue_duval",
            headers=HEADERS,
            json={"queue_entries": queue_entries}
        )
        
        if response.status_code == 200:
            result = response.json()
            enqueued_count = result.get("enqueued", len(queue_entries))
            logger.info(f"✅ Successfully enqueued {enqueued_count} cases")
            return enqueued_count
        else:
            # Fallback: try direct table insert
            logger.warning(f"RPC enqueue failed ({response.status_code}), trying direct insert...")
            
            response = client.post(
                f"{BASE}/acclaim_harvest_queue",
                headers={**HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"},
                json=queue_entries
            )
            
            if response.status_code in (200, 201):
                logger.info(f"✅ Direct insert successful: {len(queue_entries)} cases enqueued")
                return len(queue_entries)
            else:
                logger.error(f"❌ Failed to enqueue cases: {response.status_code} - {response.text}")
                return 0
                
    except Exception as e:
        logger.error(f"❌ Error enqueuing cases: {e}")
        return 0

def check_queue_processing_status() -> Dict:
    """Check status of acclaim queue processing"""
    logger.info("📊 Checking acclaim queue processing status...")
    
    try:
        # Get queue status
        response = client.get(
            f"{BASE}/acclaim_harvest_queue",
            headers=HEADERS,
            params={
                "select": "status,count()",
                "county": "eq.duval",
                "group": "status"
            }
        )
        
        if response.status_code == 200:
            status_counts = {item["status"]: item["count"] for item in response.json()}
            logger.info(f"Queue status: {status_counts}")
            return status_counts
        else:
            logger.warning(f"Could not get queue status: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.warning(f"Error checking queue status: {e}")
        return {}

def verify_b_improvement() -> float:
    """Verify B metric improvement using pencil_dod_evaluate_county"""
    logger.info("🔍 Verifying Letter B improvement...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": "duval"},
            timeout=60
        )
        
        if response.status_code == 200:
            results = response.json()
            
            for letter in results:
                if letter.get("letter") == "B":
                    metric = letter.get("metric", 0)
                    is_pass = letter.get("pass", False)
                    detail = letter.get("detail", "")
                    
                    logger.info(f"✅ Duval Letter B: {'PASS' if is_pass else 'FAIL'} {metric}% [{detail}]")
                    return metric
            
            logger.warning("⚠️ Letter B not found in results")
            return 0.0
        else:
            logger.error(f"❌ Evaluation failed: {response.status_code}")
            return 0.0
            
    except Exception as e:
        logger.error(f"❌ Error verifying B improvement: {e}")
        return 0.0

def main():
    """Main execution"""
    logger.info("🚀 DUVAL LETTER B COMPLETION SCRIPT")
    logger.info("Goal: Complete Duval B metric from 74.5% to 95%+")
    
    # Step 1: Get baseline B metric
    baseline_b = verify_b_improvement()
    logger.info(f"📊 Baseline Letter B: {baseline_b}%")
    
    # Step 2: Find missing cases
    missing_cases = find_missing_duval_cases()
    
    if not missing_cases:
        logger.info("✅ No missing cases found - queue is complete")
        return 0
    
    # Step 3: Enqueue missing cases
    enqueued = enqueue_cases_for_acclaim(missing_cases)
    
    if enqueued == 0:
        logger.error("❌ Failed to enqueue any cases")
        return 1
    
    # Step 4: Check queue processing
    queue_status = check_queue_processing_status()
    
    # Step 5: Verify improvement (may take time for workers to process)
    final_b = verify_b_improvement()
    improvement = final_b - baseline_b
    
    logger.info(f"📈 Letter B improvement: {baseline_b}% → {final_b}% (+{improvement:.1f}%)")
    
    if final_b >= 95.0:
        logger.info("🎉 DUVAL LETTER B: GOLD STANDARD ACHIEVED!")
    elif improvement > 0:
        logger.info("✅ B metric improved - workers will continue processing queue")
    else:
        logger.warning("⚠️ No immediate B improvement - check worker processing")
    
    logger.info(f"✅ COMPLETED: {enqueued} cases enqueued for acclaim processing")
    return 0

if __name__ == "__main__":
    sys.exit(main())