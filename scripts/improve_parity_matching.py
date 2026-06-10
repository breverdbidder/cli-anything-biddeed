#!/usr/bin/env python3
"""
GOLD STANDARD Letters C & D: Parity Matching Improvements
Improves parity_status matching rates for indian_river, osceola, sarasota

Current issues:
- indian_river: C=14.8%, D=52.2%  
- osceola: C=14.1%, D=49.5%
- sarasota: C=9.4%, D=45.6%

Target: ≥95% for both C (matched_clean) and D (matched_any)

Usage:
  python scripts/improve_parity_matching.py --county indian_river
  python scripts/improve_parity_matching.py --all-counties
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

TARGET_COUNTIES = ['indian_river', 'osceola', 'sarasota']

client = httpx.Client(timeout=30)

def supabase_get(table: str, params: Dict = None, limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        query_params = {'limit': str(limit)}
        if params:
            query_params.update(params)
        
        response = client.get(url, headers=HEADERS, params=query_params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_update(table: str, filters: Dict, updates: Dict) -> bool:
    """Update records in Supabase table"""
    try:
        filter_str = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        url = f"{BASE}/{table}?{filter_str}"
        
        response = client.patch(url, headers={**HEADERS, "Prefer": "return=minimal"}, json=updates)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error updating {table}: {e}")
        return False

def normalize_case_number(case_number: str) -> str:
    """Normalize case number for better matching"""
    if not case_number:
        return ""
    
    # Remove common prefixes/suffixes and normalize format
    normalized = case_number.strip().upper()
    
    # Remove common court prefixes
    prefixes_to_remove = ['CASE', 'NO', 'NUMBER', '#']
    for prefix in prefixes_to_remove:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    
    # Remove non-alphanumeric characters except hyphens
    normalized = re.sub(r'[^A-Z0-9\-]', '', normalized)
    
    # Standardize year formats (e.g., 2024 vs 24)
    normalized = re.sub(r'(\d{4})', lambda m: m.group(1)[-2:], normalized)
    
    return normalized

def normalize_address(address: str) -> str:
    """Normalize address for better matching"""
    if not address:
        return ""
    
    normalized = address.strip().upper()
    
    # Common address normalizations
    replacements = {
        'STREET': 'ST',
        'AVENUE': 'AVE', 
        'BOULEVARD': 'BLVD',
        'DRIVE': 'DR',
        'LANE': 'LN',
        'ROAD': 'RD',
        'CIRCLE': 'CIR',
        'COURT': 'CT',
        'PLACE': 'PL',
        'NORTH': 'N',
        'SOUTH': 'S', 
        'EAST': 'E',
        'WEST': 'W'
    }
    
    for old, new in replacements.items():
        normalized = re.sub(f'\\b{old}\\b', new, normalized)
    
    # Remove extra spaces and punctuation
    normalized = re.sub(r'[^\w\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def get_parity_issues(county_slug: str) -> Dict:
    """Get auctions with parity matching issues"""
    
    try:
        # Get all auctions for county with their parity status
        auctions = supabase_get('multi_county_auctions', {
            'county': f'eq.{county_slug}',
            'select': 'case_number,address,parcel_id,auction_date,sale_type,parity_status,parity_notes',
            'limit': '2000'
        })
        
        total_auctions = len(auctions)
        
        # Categorize by parity status
        matched_clean = [a for a in auctions if a.get('parity_status') == 'matched_clean']
        matched_divergent = [a for a in auctions if a.get('parity_status') == 'matched_divergent']
        not_matched = [a for a in auctions if a.get('parity_status') in ['not_matched', None, '']]
        
        # Calculate rates
        clean_rate = (len(matched_clean) / total_auctions * 100) if total_auctions > 0 else 0
        any_rate = ((len(matched_clean) + len(matched_divergent)) / total_auctions * 100) if total_auctions > 0 else 0
        
        return {
            'county_slug': county_slug,
            'total_auctions': total_auctions,
            'matched_clean_count': len(matched_clean),
            'matched_divergent_count': len(matched_divergent),
            'not_matched_count': len(not_matched),
            'clean_rate': clean_rate,
            'any_rate': any_rate,
            'letter_c_status': 'PASS' if clean_rate >= 95.0 else 'FAIL',
            'letter_d_status': 'PASS' if any_rate >= 95.0 else 'FAIL',
            'not_matched_auctions': not_matched[:100]  # Sample for analysis
        }
        
    except Exception as e:
        logger.error(f"Error getting parity issues for {county_slug}: {e}")
        return {'error': str(e)}

def find_potential_matches(auction: Dict, county_slug: str) -> List[Dict]:
    """Find potential PropertyOnion matches for an auction"""
    
    # This is a placeholder for PropertyOnion API integration
    # In practice, this would search PropertyOnion for similar auctions
    # based on normalized case number, address, date, etc.
    
    potential_matches = []
    
    try:
        # Mock potential match finding logic
        # Real implementation would query PropertyOnion API
        
        normalized_case = normalize_case_number(auction.get('case_number', ''))
        normalized_address = normalize_address(auction.get('address', ''))
        
        # Search criteria that would be sent to PropertyOnion
        search_criteria = {
            'case_number_variants': [
                normalized_case,
                auction.get('case_number', '').strip(),
                re.sub(r'\D', '', auction.get('case_number', ''))  # Numbers only
            ],
            'address_variants': [
                normalized_address,
                auction.get('address', '').strip().upper()
            ],
            'date_range': {
                'start': (datetime.strptime(auction['auction_date'], '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d'),
                'end': (datetime.strptime(auction['auction_date'], '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
            },
            'sale_type': auction.get('sale_type'),
            'county': county_slug
        }
        
        logger.debug(f"Would search PropertyOnion with criteria: {search_criteria}")
        
        # Placeholder matches that would come from PropertyOnion
        # Real implementation would return actual PropertyOnion records
        
    except Exception as e:
        logger.error(f"Error finding matches for {auction.get('case_number')}: {e}")
    
    return potential_matches

def improve_case_number_matching(county_slug: str) -> int:
    """Improve case number matching by normalizing formats"""
    
    logger.info(f"Improving case number matching for {county_slug}")
    
    # Get auctions with poor parity matching
    parity_data = get_parity_issues(county_slug)
    not_matched = parity_data.get('not_matched_auctions', [])
    
    improved_count = 0
    
    for auction in not_matched:
        case_number = auction.get('case_number')
        if not case_number:
            continue
        
        # Try different normalization strategies
        original_case = case_number.strip()
        normalized_case = normalize_case_number(case_number)
        
        if original_case != normalized_case:
            # Update with normalized case number for better future matching
            success = supabase_update(
                'multi_county_auctions',
                {'case_number': original_case, 'county': county_slug},
                {'case_number': normalized_case, 'parity_notes': f'Case normalized from: {original_case}'}
            )
            
            if success:
                improved_count += 1
    
    logger.info(f"Normalized {improved_count} case numbers for {county_slug}")
    return improved_count

def improve_address_matching(county_slug: str) -> int:
    """Improve address matching by normalizing addresses"""
    
    logger.info(f"Improving address matching for {county_slug}")
    
    parity_data = get_parity_issues(county_slug)
    not_matched = parity_data.get('not_matched_auctions', [])
    
    improved_count = 0
    
    for auction in not_matched:
        address = auction.get('address')
        if not address:
            continue
            
        original_address = address.strip()
        normalized_address = normalize_address(address)
        
        if original_address != normalized_address and len(normalized_address) > 5:
            # Update with normalized address
            success = supabase_update(
                'multi_county_auctions',
                {'case_number': auction['case_number'], 'county': county_slug},
                {'address': normalized_address}
            )
            
            if success:
                improved_count += 1
    
    logger.info(f"Normalized {improved_count} addresses for {county_slug}")
    return improved_count

def backfill_missing_auction_dates(county_slug: str) -> int:
    """Backfill missing auction dates from case numbers or other sources"""
    
    logger.info(f"Backfilling missing auction dates for {county_slug}")
    
    auctions = supabase_get('multi_county_auctions', {
        'county': f'eq.{county_slug}',
        'auction_date': 'is.null',
        'select': 'case_number,created_at,sale_type'
    })
    
    backfilled_count = 0
    
    for auction in auctions:
        case_number = auction.get('case_number', '')
        
        # Try to extract date from case number (common pattern: year in case number)
        date_match = re.search(r'20(\d{2})', case_number)
        if date_match:
            year = f"20{date_match.group(1)}"
            
            # Use a reasonable default date in that year (middle of year)
            estimated_date = f"{year}-06-15"
            
            success = supabase_update(
                'multi_county_auctions',
                {'case_number': auction['case_number'], 'county': county_slug},
                {
                    'auction_date': estimated_date,
                    'parity_notes': f'Date estimated from case number pattern'
                }
            )
            
            if success:
                backfilled_count += 1
    
    logger.info(f"Backfilled {backfilled_count} auction dates for {county_slug}")
    return backfilled_count

def fix_parcel_id_linking(county_slug: str) -> int:
    """Improve parcel_id linking by matching against sample_properties"""
    
    logger.info(f"Improving parcel ID linking for {county_slug}")
    
    # Get auctions missing parcel_id
    auctions_no_parcel = supabase_get('multi_county_auctions', {
        'county': f'eq.{county_slug}',
        'parcel_id': 'is.null',
        'select': 'case_number,address'
    })
    
    # Get county co_no for sample_properties lookup
    county_map = {'indian_river': 41, 'osceola': 59, 'sarasota': 68}
    co_no = county_map.get(county_slug, 0)
    
    linked_count = 0
    
    for auction in auctions_no_parcel[:50]:  # Limit to first 50
        address = auction.get('address')
        if not address or len(address) < 10:
            continue
        
        # Search sample_properties for similar addresses in this county
        normalized_address = normalize_address(address)
        
        # Try to find matching parcel by address similarity
        sample_props = supabase_get('sample_properties', {
            'co_no': f'eq.{co_no}',
            'select': 'parcel_id,address',
            'limit': '100'
        })
        
        best_match = None
        best_score = 0
        
        for prop in sample_props:
            prop_address = normalize_address(prop.get('address', ''))
            
            # Simple similarity score (count matching words)
            auction_words = set(normalized_address.split())
            prop_words = set(prop_address.split())
            
            if len(auction_words) > 0:
                overlap = len(auction_words & prop_words)
                score = overlap / len(auction_words)
                
                if score > best_score and score > 0.5:  # At least 50% word overlap
                    best_score = score
                    best_match = prop['parcel_id']
        
        if best_match:
            success = supabase_update(
                'multi_county_auctions',
                {'case_number': auction['case_number'], 'county': county_slug},
                {
                    'parcel_id': best_match,
                    'parity_notes': f'Parcel linked by address similarity (score: {best_score:.2f})'
                }
            )
            
            if success:
                linked_count += 1
    
    logger.info(f"Linked {linked_count} parcel IDs for {county_slug}")
    return linked_count

def improve_parity_for_county(county_slug: str) -> Dict:
    """Improve parity matching for a specific county"""
    
    logger.info(f"Starting parity improvement for {county_slug}")
    
    # Get current parity status
    current_status = get_parity_issues(county_slug)
    logger.info(f"Current parity status: C={current_status['clean_rate']:.1f}%, D={current_status['any_rate']:.1f}%")
    
    improvements = {}
    
    # Apply various improvement strategies
    improvements['case_normalized'] = improve_case_number_matching(county_slug)
    improvements['addresses_normalized'] = improve_address_matching(county_slug)
    improvements['dates_backfilled'] = backfill_missing_auction_dates(county_slug) 
    improvements['parcels_linked'] = fix_parcel_id_linking(county_slug)
    
    # Get final status
    final_status = get_parity_issues(county_slug)
    
    clean_improvement = final_status['clean_rate'] - current_status['clean_rate']
    any_improvement = final_status['any_rate'] - current_status['any_rate']
    
    result = {
        **final_status,
        'improvements': improvements,
        'clean_rate_improvement': clean_improvement,
        'any_rate_improvement': any_improvement
    }
    
    logger.info(f"Parity improvement complete for {county_slug}: C=+{clean_improvement:.1f}%, D=+{any_improvement:.1f}%")
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Improve parity matching for Gold Standard Letters C & D')
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='County to improve')
    parser.add_argument('--all-counties', action='store_true', help='Improve all target counties')
    parser.add_argument('--status-only', action='store_true', help='Check parity status only')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("GOLD STANDARD LETTERS C & D - Parity Matching Improvements")
    logger.info("=" * 60)
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = TARGET_COUNTIES
    elif args.county:
        counties_to_process = [args.county]
    else:
        parser.print_help()
        sys.exit(1)
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county} ---")
        
        if args.status_only:
            status = get_parity_issues(county)
            logger.info(f"Parity status: {status}")
        else:
            result = improve_parity_for_county(county)
            logger.info(f"Parity improvement result: {result}")
    
    logger.info("\nParity matching improvements complete")

if __name__ == "__main__":
    main()