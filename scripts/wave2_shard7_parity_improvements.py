#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-7: Parity Matching Improvements
Counties: alachua, gilchrist, miami_dade, walton, gadsden, lafayette, wakulla
Letters C & D: Improve parity_status matching rates to ≥95%

Based on improve_parity_matching.py but customized for SHARD-7 counties
"""
import httpx
import json
import os
import sys
import argparse
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# WAVE2-SHARD-7 counties
SHARD_COUNTIES = ['alachua', 'gilchrist', 'miami_dade', 'walton', 'gadsden', 'lafayette', 'wakulla']

client = httpx.Client(timeout=60)

def supabase_get(table: str, params: str = "", limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}?{params}&limit={limit}"
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_update(table: str, filters: str, updates: Dict) -> int:
    """Update records in Supabase table"""
    try:
        url = f"{BASE}/{table}?{filters}"
        response = client.patch(url, headers=HEADERS, json=updates)
        response.raise_for_status()
        return 1
    except Exception as e:
        logger.error(f"Error updating {table}: {e}")
        return 0

def normalize_address(addr: str) -> str:
    """Normalize address for better matching"""
    if not addr:
        return ""
    
    # Basic normalization
    addr = addr.upper().strip()
    
    # Common street type abbreviations
    replacements = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE', 
        r'\bBOULEVARD\b': 'BLVD',
        r'\bDRIVE\b': 'DR',
        r'\bLANE\b': 'LN',
        r'\bROAD\b': 'RD',
        r'\bCIRCLE\b': 'CIR',
        r'\bCOURT\b': 'CT',
        r'\bPLACE\b': 'PL',
        r'\bTRAIL\b': 'TRL',
        r'\bWAY\b': 'WAY',
        r'\bNORTH\b': 'N',
        r'\bSOUTH\b': 'S',
        r'\bEAST\b': 'E',
        r'\bWEST\b': 'W'
    }
    
    for pattern, replacement in replacements.items():
        addr = re.sub(pattern, replacement, addr)
    
    # Remove extra whitespace and punctuation
    addr = re.sub(r'[^\w\s]', ' ', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    
    return addr

def normalize_case_number(case_num: str) -> str:
    """Normalize case number for better matching"""
    if not case_num:
        return ""
    
    # Remove common prefixes/suffixes and normalize format
    case_num = case_num.upper().strip()
    case_num = re.sub(r'^(CASE|NO\.?|#)\s*', '', case_num)
    case_num = re.sub(r'\s*-\s*', '-', case_num)
    
    return case_num

def fuzzy_match_score(str1: str, str2: str) -> float:
    """Simple fuzzy matching score between 0-1"""
    if not str1 or not str2:
        return 0.0
    
    str1, str2 = str1.upper(), str2.upper()
    
    # Exact match
    if str1 == str2:
        return 1.0
    
    # Substring match
    if str1 in str2 or str2 in str1:
        return 0.8
    
    # Word overlap
    words1 = set(str1.split())
    words2 = set(str2.split())
    if words1 and words2:
        overlap = len(words1 & words2) / len(words1 | words2)
        return overlap * 0.7
    
    return 0.0

def improve_parity_for_county(county_slug: str) -> Dict:
    """Improve parity matching for a single county"""
    logger.info(f"Starting parity improvement for {county_slug}")
    
    # Get unmatched auctions
    unmatched_auctions = supabase_get(
        "multi_county_auctions",
        f"county=eq.{county_slug}&parity_status=in.(no_match,needs_review)&select=id,case_number,property_address,sale_date,auction_date"
    )
    
    if not unmatched_auctions:
        logger.info(f"No unmatched auctions found for {county_slug}")
        return {"updated": 0, "matched_clean": 0, "matched_divergent": 0}
    
    logger.info(f"Found {len(unmatched_auctions)} unmatched auctions for {county_slug}")
    
    # Get PropertyOnion data for comparison
    po_data = supabase_get(
        "property_onion_auctions", 
        f"county_name=ilike.%{county_slug}%&select=case_number,property_address,sale_date,auction_date"
    )
    
    logger.info(f"Found {len(po_data)} PropertyOnion records for comparison")
    
    results = {"updated": 0, "matched_clean": 0, "matched_divergent": 0}
    
    for auction in unmatched_auctions:
        best_match = None
        best_score = 0.0
        match_type = None
        
        auction_case = normalize_case_number(auction.get("case_number", ""))
        auction_addr = normalize_address(auction.get("property_address", ""))
        auction_sale_date = auction.get("sale_date")
        auction_auction_date = auction.get("auction_date")
        
        for po_record in po_data:
            po_case = normalize_case_number(po_record.get("case_number", ""))
            po_addr = normalize_address(po_record.get("property_address", ""))
            po_sale_date = po_record.get("sale_date")
            po_auction_date = po_record.get("auction_date")
            
            # Case number matching
            case_score = fuzzy_match_score(auction_case, po_case) if auction_case and po_case else 0
            
            # Address matching
            addr_score = fuzzy_match_score(auction_addr, po_addr) if auction_addr and po_addr else 0
            
            # Date matching
            date_score = 0
            if auction_sale_date and po_sale_date:
                date_score = 1.0 if auction_sale_date == po_sale_date else 0.5
            elif auction_auction_date and po_auction_date:
                date_score = 1.0 if auction_auction_date == po_auction_date else 0.5
            
            # Combined score
            total_score = (case_score * 0.5) + (addr_score * 0.3) + (date_score * 0.2)
            
            if total_score > best_score and total_score > 0.6:  # Threshold for matching
                best_match = po_record
                best_score = total_score
                
                # Determine match type
                if total_score >= 0.9:
                    match_type = "matched_clean"
                else:
                    match_type = "matched_divergent"
        
        # Update auction with best match
        if best_match and match_type:
            update_data = {
                "parity_status": match_type,
                "parity_confidence": best_score,
                "parity_updated_at": datetime.now().isoformat()
            }
            
            if supabase_update("multi_county_auctions", f"id=eq.{auction['id']}", update_data):
                results["updated"] += 1
                results[match_type] += 1
                logger.info(f"Updated auction {auction['id']} with {match_type} (score: {best_score:.2f})")
    
    logger.info(f"Completed parity improvement for {county_slug}: {results}")
    return results

def backfill_missing_dates(county_slug: str) -> int:
    """Backfill missing auction dates from case numbers or other sources"""
    logger.info(f"Backfilling missing dates for {county_slug}")
    
    # Get auctions with missing dates
    missing_dates = supabase_get(
        "multi_county_auctions",
        f"county=eq.{county_slug}&(auction_date=is.null,sale_date=is.null)&select=id,case_number,property_address"
    )
    
    updated = 0
    for auction in missing_dates:
        # Try to extract date from case number
        case_num = auction.get("case_number", "")
        
        # Common patterns: 2024CA001234, 24-CA-1234, etc.
        date_match = re.search(r'(20\d{2}|\d{2})', case_num)
        if date_match:
            year = date_match.group(1)
            if len(year) == 2:
                year = "20" + year
            
            # Estimate date based on year (rough heuristic)
            estimated_date = f"{year}-06-15"  # Mid-year estimate
            
            update_data = {
                "auction_date": estimated_date,
                "date_source": "estimated_from_case_number"
            }
            
            if supabase_update("multi_county_auctions", f"id=eq.{auction['id']}", update_data):
                updated += 1
    
    logger.info(f"Backfilled {updated} missing dates for {county_slug}")
    return updated

def main():
    parser = argparse.ArgumentParser(description="WAVE2-SHARD-7 Parity Matching Improvements")
    parser.add_argument("--county", choices=SHARD_COUNTIES, help="Specific county to process")
    parser.add_argument("--all-counties", action="store_true", help="Process all SHARD-7 counties")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    counties_to_process = [args.county] if args.county else SHARD_COUNTIES if args.all_counties else []
    
    if not counties_to_process:
        parser.print_help()
        sys.exit(1)
    
    logger.info(f"Starting parity improvement for counties: {counties_to_process}")
    
    total_results = {"updated": 0, "matched_clean": 0, "matched_divergent": 0, "dates_backfilled": 0}
    
    for county in counties_to_process:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {county}")
        logger.info(f"{'='*60}")
        
        # Improve parity matching
        county_results = improve_parity_for_county(county)
        for key in ["updated", "matched_clean", "matched_divergent"]:
            total_results[key] += county_results.get(key, 0)
        
        # Backfill missing dates
        dates_backfilled = backfill_missing_dates(county)
        total_results["dates_backfilled"] += dates_backfilled
    
    logger.info(f"\n{'='*60}")
    logger.info("FINAL RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total updated: {total_results['updated']}")
    logger.info(f"Matched clean: {total_results['matched_clean']}")
    logger.info(f"Matched divergent: {total_results['matched_divergent']}")
    logger.info(f"Dates backfilled: {total_results['dates_backfilled']}")
    
    # Calculate improvement percentages
    for county in counties_to_process:
        logger.info(f"\nRe-evaluating {county} after improvements...")
        # This would need the evaluation function to show before/after

if __name__ == "__main__":
    main()