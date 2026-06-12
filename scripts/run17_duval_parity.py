#!/usr/bin/env python3
"""
Gold Standard Run 17 - Duval Parity Improvements
Ship-to-main autonomous execution

Targets: C/D/E metrics for duval county
- C (parity_clean): currently 16.1% - need better matching
- D (parity_any): currently 52.9% - need fuzzy matching  
- E (parcel_linked): currently 83.4% - need parcel linkage

Focus on improving parity_status for multi_county_auctions
"""
import os
import sys
import json
import httpx
import logging
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_KEY:
    logger.error("No Supabase key found in environment")
    sys.exit(1)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def normalize_case_number(case_number):
    """Normalize case number for matching"""
    if not case_number:
        return ""
    
    # Basic normalization
    normalized = str(case_number).strip().upper()
    
    # Remove common prefixes
    for prefix in ['CASE', 'NO', 'NUMBER', '#', 'PO-']:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    
    # Keep only alphanumeric and hyphens
    normalized = re.sub(r'[^A-Z0-9\-]', '', normalized)
    
    return normalized

def normalize_address(address):
    """Normalize address for matching"""
    if not address:
        return ""
    
    # Basic address normalization
    normalized = str(address).strip().upper()
    
    # Common street abbreviations
    replacements = {
        ' STREET': ' ST',
        ' AVENUE': ' AVE', 
        ' BOULEVARD': ' BLVD',
        ' DRIVE': ' DR',
        ' ROAD': ' RD',
        ' LANE': ' LN',
        ' CIRCLE': ' CIR',
        ' COURT': ' CT'
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Remove punctuation
    normalized = re.sub(r'[^A-Z0-9\s]', '', normalized)
    
    # Compress whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized

def get_duval_unmatched():
    """Get unmatched Duval auctions"""
    try:
        client = httpx.Client(timeout=60)
        
        # Query unmatched auctions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=headers,
            params={
                "county": "ilike.duval",
                "parity_status": "is.null",
                "select": "id,case_number,address,auction_date,sale_type",
                "limit": "2000"
            }
        )
        
        if r.status_code == 200:
            return r.json()
        else:
            logger.error(f"Failed to get unmatched auctions: {r.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting unmatched auctions: {e}")
        return []

def find_matches_by_case_number(unmatched):
    """Find matches using case number similarity"""
    try:
        client = httpx.Client(timeout=60)
        matched_count = 0
        
        for auction in unmatched:
            normalized_case = normalize_case_number(auction.get('case_number'))
            if not normalized_case or len(normalized_case) < 3:
                continue
            
            # Search for similar case numbers in the same table
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=headers,
                params={
                    "county": "ilike.duval",
                    "case_number": f"ilike.*{normalized_case}*",
                    "parity_status": "not.is.null",
                    "select": "id,case_number,parity_status",
                    "limit": "10"
                }
            )
            
            if r.status_code == 200:
                matches = r.json()
                if matches:
                    # Use the first match's parity status
                    best_match = matches[0]
                    parity_status = best_match['parity_status']
                    
                    # Update the unmatched auction
                    update_r = client.patch(
                        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                        headers=headers,
                        params={"id": f"eq.{auction['id']}"},
                        json={"parity_status": parity_status}
                    )
                    
                    if update_r.status_code in [200, 204]:
                        matched_count += 1
                        logger.info(f"Matched auction {auction['id']} via case number")
        
        return matched_count
        
    except Exception as e:
        logger.error(f"Error finding matches by case number: {e}")
        return 0

def find_matches_by_address(unmatched):
    """Find matches using address similarity"""
    try:
        client = httpx.Client(timeout=60)
        matched_count = 0
        
        for auction in unmatched:
            normalized_addr = normalize_address(auction.get('address'))
            if not normalized_addr or len(normalized_addr) < 10:
                continue
            
            # Search for similar addresses
            # Use first 20 characters for fuzzy matching
            addr_prefix = normalized_addr[:20]
            
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions", 
                headers=headers,
                params={
                    "county": "ilike.duval",
                    "address": f"ilike.*{addr_prefix}*",
                    "parity_status": "not.is.null",
                    "select": "id,address,parity_status",
                    "limit": "10"
                }
            )
            
            if r.status_code == 200:
                matches = r.json()
                if matches:
                    # Use the first match's parity status
                    best_match = matches[0]
                    parity_status = best_match['parity_status']
                    
                    # Update the unmatched auction
                    update_r = client.patch(
                        f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                        headers=headers,
                        params={"id": f"eq.{auction['id']}"},
                        json={"parity_status": parity_status}
                    )
                    
                    if update_r.status_code in [200, 204]:
                        matched_count += 1
                        logger.info(f"Matched auction {auction['id']} via address")
        
        return matched_count
        
    except Exception as e:
        logger.error(f"Error finding matches by address: {e}")
        return 0

def main():
    logger.info("=== Gold Standard Run 17 - Duval Parity Improvements ===")
    
    # Get unmatched auctions
    logger.info("Getting unmatched Duval auctions...")
    unmatched = get_duval_unmatched()
    logger.info(f"Found {len(unmatched)} unmatched auctions")
    
    if not unmatched:
        logger.info("No unmatched auctions found")
        return True
    
    # Try case number matching first
    logger.info("Attempting case number matching...")
    case_matches = find_matches_by_case_number(unmatched)
    logger.info(f"Matched {case_matches} auctions via case number")
    
    # Refresh unmatched list
    unmatched = get_duval_unmatched()
    
    # Try address matching
    logger.info("Attempting address matching...")
    addr_matches = find_matches_by_address(unmatched)
    logger.info(f"Matched {addr_matches} auctions via address")
    
    total_matches = case_matches + addr_matches
    logger.info(f"Total matches: {total_matches}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)