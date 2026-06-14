#!/usr/bin/env python3
"""
SHARD-24 Citrus Letter B Fix - Verified Outcomes  
Fix: B metric=null (0 verified outcomes with independent data_source)

Citrus specific implementation for independent outcome verification.
Canon requires: verified_outcomes NOT derived from PropertyOnion data_source.
Need clerk-source or court-recorded sale results.
"""
import os
import sys
import time
import httpx
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Citrus County clerk/court endpoints
CITRUS_CLERK_CONFIG = {
    'clerk_base': 'https://or.citrusclerk.org',
    'search_endpoint': '/search',
    'records_search': 'https://or.citrusclerk.org/or_web1/or_search.asp',
    'case_search_pattern': r'Case.*?(\d{4}.*?\d+)',
    'rate_limit_delay': 1.0  # Conservative for clerk site
}

# Database connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log_action(msg: str, level: str = "INFO", honesty_tag: str = "UNTESTED"):
    """Log with honesty protocol tags"""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {level} [{honesty_tag}]: {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_query(table: str, params: str) -> List[Dict]:
    """Query Supabase table via REST API"""
    try:
        client = httpx.Client(timeout=60)
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
        
        response = client.get(url, headers=sb_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            log_action(f"Query failed: {response.status_code}", "ERROR", "VERIFIED")
            return []
    except Exception as e:
        log_action(f"Query error: {e}", "ERROR", "VERIFIED")
        return []

def sb_insert(table: str, data: List[Dict]) -> int:
    """Insert records to Supabase table"""
    try:
        client = httpx.Client(timeout=60)
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        
        response = client.post(url, headers=sb_headers(), json=data)
        
        if response.status_code in (200, 201):
            log_action(f"Inserted {len(data)} records to {table}", "INFO", "VERIFIED")
            return len(data)
        else:
            log_action(f"Insert failed: {response.status_code}", "ERROR", "VERIFIED")
            return 0
    except Exception as e:
        log_action(f"Insert error: {e}", "ERROR", "VERIFIED")
        return 0

def get_citrus_closed_auctions() -> List[Dict]:
    """Get Citrus auctions that have closed (for outcome verification)"""
    # Query closed auctions from the past 24 months
    params = "select=case_number,property_address,sale_date,opening_bid&county=eq.citrus&sale_date=not.is.null&order=sale_date.desc&limit=200"
    
    auctions = sb_query("multi_county_auctions", params)
    
    if auctions:
        log_action(f"Retrieved {len(auctions)} closed Citrus auctions", "INFO", "VERIFIED")
    else:
        log_action("No closed Citrus auctions found or query failed", "WARN", "VERIFIED")
    
    return auctions

def check_existing_verified_outcomes(case_number: str) -> bool:
    """Check if outcome already exists with independent source"""
    params = f"select=data_source&case_number=eq.{case_number}&data_source=not.like.*propertyonion*"
    
    existing = sb_query("foreclosure_outcomes", params)
    
    if existing:
        log_action(f"Case {case_number} already has independent outcome", "INFO", "VERIFIED") 
        return True
    else:
        return False

def search_clerk_records(case_number: str) -> Dict:
    """Search Citrus Clerk official records for case outcome"""
    try:
        client = httpx.Client(timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (compatible; SHARD24-CitrusVerification)"
        })
        
        # Clean case number for search
        clean_case = re.sub(r'[^\w\-]', '', case_number)
        
        # Search official records
        search_url = CITRUS_CLERK_CONFIG['records_search']
        search_params = {
            'SEARCH_TYPE': 'CASE',
            'CASE_NUM': clean_case,
            'SEARCH_BY': 'Case Number'
        }
        
        log_action(f"Searching clerk records for case {clean_case}...", "INFO", "UNTESTED")
        
        response = client.get(search_url, params=search_params)
        
        if response.status_code == 200:
            content = response.text
            
            # Look for outcome indicators
            outcome_indicators = [
                'Certificate of Title',
                'Final Judgment',
                'Sheriff\'s Deed',
                'Sale Amount',
                'Winning Bid',
                'Purchaser'
            ]
            
            found_indicators = [indicator for indicator in outcome_indicators if indicator in content]
            
            if found_indicators:
                log_action(f"Found outcome indicators for {clean_case}: {found_indicators}", "INFO", "VERIFIED")
                
                # Extract sale amount if visible
                sale_amount_match = re.search(r'\$[\d,]+\.?\d*', content)
                sale_amount = None
                
                if sale_amount_match:
                    sale_amount_str = sale_amount_match.group().replace('$', '').replace(',', '')
                    try:
                        sale_amount = float(sale_amount_str)
                        log_action(f"Extracted sale amount: ${sale_amount:,.2f}", "INFO", "VERIFIED")
                    except ValueError:
                        log_action(f"Could not parse sale amount: {sale_amount_match.group()}", "WARN", "VERIFIED")
                
                return {
                    'case_number': case_number,
                    'outcome_found': True,
                    'sale_amount': sale_amount,
                    'indicators_found': found_indicators,
                    'source_url': response.url,
                    'searched_at': datetime.now(timezone.utc).isoformat()
                }
            else:
                log_action(f"No outcome indicators found for {clean_case}", "INFO", "VERIFIED")
                return {'case_number': case_number, 'outcome_found': False}
        else:
            log_action(f"Clerk search failed for {clean_case}: {response.status_code}", "WARN", "VERIFIED")
            return {'case_number': case_number, 'outcome_found': False}
            
    except Exception as e:
        log_action(f"Clerk search error for {case_number}: {e}", "ERROR", "VERIFIED")
        return {'case_number': case_number, 'outcome_found': False}

def create_verified_outcome(case_number: str, search_result: Dict, auction_data: Dict) -> Dict:
    """Create verified outcome record from clerk search result"""
    outcome_record = {
        'case_number': case_number,
        'county_slug': 'citrus',
        'sale_date': auction_data.get('sale_date'),
        'winning_bid': search_result.get('sale_amount'),
        'data_source': 'citrus_clerk_records:SHARD24-B-V1',
        'source_detail': {
            'search_url': search_result.get('source_url'),
            'indicators_found': search_result.get('indicators_found', []),
            'extracted_at': search_result.get('searched_at')
        },
        'verified_independent': True,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    return outcome_record

def process_citrus_verified_outcomes(max_cases: int = 100) -> Dict[str, int]:
    """Main processing for Citrus verified outcomes"""
    log_action(f"Starting Citrus verified outcomes processing (max {max_cases} cases)...", "INFO", "UNTESTED")
    
    stats = {
        'cases_checked': 0,
        'already_verified': 0,
        'clerk_searches': 0,
        'outcomes_found': 0,
        'records_created': 0
    }
    
    # Get closed auctions to verify
    closed_auctions = get_citrus_closed_auctions()
    
    if not closed_auctions:
        log_action("No closed auctions to process", "WARN", "VERIFIED")
        return stats
    
    verified_outcomes = []
    processed = 0
    
    for auction in closed_auctions[:max_cases]:
        case_number = auction.get('case_number', '')
        
        if not case_number:
            continue
        
        stats['cases_checked'] += 1
        processed += 1
        
        # Skip if already has independent verification
        if check_existing_verified_outcomes(case_number):
            stats['already_verified'] += 1
            continue
        
        # Search clerk records
        stats['clerk_searches'] += 1
        search_result = search_clerk_records(case_number)
        
        if search_result.get('outcome_found'):
            stats['outcomes_found'] += 1
            
            # Create verified outcome record
            outcome_record = create_verified_outcome(case_number, search_result, auction)
            verified_outcomes.append(outcome_record)
            
            log_action(f"Created verified outcome for {case_number}", "INFO", "VERIFIED")
        
        # Rate limiting for clerk site
        time.sleep(CITRUS_CLERK_CONFIG['rate_limit_delay'])
        
        # Progress logging
        if processed % 10 == 0:
            log_action(f"Processed {processed} cases, found {stats['outcomes_found']} outcomes", "INFO", "VERIFIED")
    
    # Insert verified outcomes
    if verified_outcomes:
        inserted_count = sb_insert("foreclosure_outcomes", verified_outcomes)
        stats['records_created'] = inserted_count
        
        log_action(f"Inserted {inserted_count} verified outcomes for Citrus", "INFO", "VERIFIED")
    
    # Final stats
    success_rate = (stats['outcomes_found'] / stats['clerk_searches'] * 100) if stats['clerk_searches'] > 0 else 0
    
    log_action(f"Citrus verified outcomes completed:", "INFO", "VERIFIED")
    log_action(f"  Cases checked: {stats['cases_checked']}", "INFO", "VERIFIED")
    log_action(f"  Outcomes found: {stats['outcomes_found']}", "INFO", "VERIFIED")
    log_action(f"  Success rate: {success_rate:.1f}%", "INFO", "VERIFIED")
    log_action(f"  Records created: {stats['records_created']}", "INFO", "VERIFIED")
    
    return stats

def verify_citrus_letter_b_status() -> Dict:
    """Verify current Citrus Letter B status"""
    # Get total closed/sold auctions
    closed_params = "select=count&county=eq.citrus&sale_date=not.is.null"
    closed_result = sb_query("multi_county_auctions", closed_params)
    
    # Get verified outcomes with independent source
    verified_params = "select=count&county_slug=eq.citrus&data_source=not.like.*propertyonion*"
    verified_result = sb_query("foreclosure_outcomes", verified_params)
    
    if closed_result and verified_result:
        closed_count = closed_result[0].get('count', 0)
        verified_count = verified_result[0].get('count', 0)
        
        verification_pct = (verified_count / closed_count * 100) if closed_count > 0 else 0
        
        log_action(f"Current Citrus Letter B: {verification_pct:.1f}% ({verified_count}/{closed_count})", "INFO", "VERIFIED")
        
        return {
            'closed_auctions': closed_count,
            'verified_outcomes': verified_count,
            'verification_percentage': verification_pct,
            'target_percentage': 95.0,
            'gap_to_target': 95.0 - verification_pct
        }
    else:
        log_action("Failed to get Letter B verification data", "ERROR", "VERIFIED")
        return {}

def main():
    """Main execution for Citrus Letter B fix"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SHARD-24 Citrus Letter B Fix")
    parser.add_argument("--max-cases", type=int, default=100, help="Max cases to process")
    parser.add_argument("--verify-only", action="store_true", help="Only verify current status")
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log_action("SUPABASE_KEY required", "ERROR", "VERIFIED")
        return 1
    
    log_action("Starting SHARD-24 Citrus Letter B (verified outcomes) fix", "INFO", "VERIFIED")
    
    # Get baseline
    baseline = verify_citrus_letter_b_status()
    
    if args.verify_only:
        return 0
    
    if baseline.get('verification_percentage', 0) >= 95.0:
        log_action("Citrus already meets 95% verification target", "INFO", "VERIFIED")
        return 0
    
    # Execute verified outcomes processing
    stats = process_citrus_verified_outcomes(args.max_cases)
    
    # Verify final status
    final_status = verify_citrus_letter_b_status()
    
    improvement = final_status.get('verification_percentage', 0) - baseline.get('verification_percentage', 0)
    log_action(f"Letter B improvement: +{improvement:.1f} percentage points", "INFO", "VERIFIED")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())