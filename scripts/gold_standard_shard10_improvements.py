#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-10: manatee, alachua, martin, franklin, union
Multi-letter improvements for assigned counties in fleet parallel session

County Status (from issue brief):
- manatee: 2/10 (A✅, H✅, B/C/D/E/F/G/I/J❌)
- alachua: 1/10 (A✅, B/C/D/E/F/G/H/I/J❌) 
- martin: 1/10 (A✅, B/C/D/E/F/G/H/I/J❌)
- franklin: 0/10 (all❌) - NEEDS LETTER A INGESTION
- union: 0/10 (all❌) - NEEDS LETTER A INGESTION

Usage:
  python scripts/gold_standard_shard10_improvements.py --county manatee --letter B
  python scripts/gold_standard_shard10_improvements.py --county franklin --letter A  
  python scripts/gold_standard_shard10_improvements.py --verify-all
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

if not SUPABASE_KEY:
    logger.error("SUPABASE_KEY environment variable not set")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-10 assigned counties with CO_NO mapping
SHARD_10_COUNTIES = {
    'manatee': {'co_no': 51, 'status': '2/10', 'priority_letters': ['B', 'F', 'C', 'D', 'E']},
    'alachua': {'co_no': 11, 'status': '1/10', 'priority_letters': ['H', 'B', 'C', 'D', 'E']}, 
    'martin': {'co_no': 53, 'status': '1/10', 'priority_letters': ['H', 'B', 'C', 'D', 'E']},
    'franklin': {'co_no': 29, 'status': '0/10', 'priority_letters': ['A']},  # NEEDS INGESTION
    'union': {'co_no': 73, 'status': '0/10', 'priority_letters': ['A']}     # NEEDS INGESTION
}

client = httpx.Client(timeout=60)

def supabase_rpc(function_name: str, params: Dict = None) -> any:
    """Call Supabase RPC function"""
    try:
        response = client.post(f"{BASE}/rpc/{function_name}", headers=HEADERS, json=params or {})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error calling RPC {function_name}: {e}")
        return None

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

def supabase_upsert(table: str, data: List[Dict], batch_size: int = 500) -> int:
    """Upsert data to Supabase table in batches"""
    if not data:
        return 0
    
    total_upserted = 0
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        try:
            response = client.post(f"{BASE}/{table}", headers=HEADERS, json=batch)
            response.raise_for_status()
            total_upserted += len(batch)
            logger.info(f"Upserted batch {i//batch_size + 1}: {len(batch)} records to {table}")
        except Exception as e:
            logger.error(f"Error upserting batch to {table}: {e}")
            
    return total_upserted

def evaluate_county_letters(county_slug: str) -> Dict:
    """Get current letter grades for a county using pencil_dod_evaluate_county"""
    logger.info(f"Evaluating county: {county_slug}")
    
    result = supabase_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county_slug})
    
    if result:
        # Convert list of letter results to dict
        letters_dict = {}
        for letter_data in result:
            letter = letter_data.get('letter')
            letters_dict[letter] = {
                'metric': letter_data.get('metric'),
                'pass': letter_data.get('pass'),
                'status': '✅' if letter_data.get('pass') else '❌'
            }
        return letters_dict
    else:
        logger.error(f"Failed to evaluate county {county_slug}")
        return {}

def trigger_county_ingestion_a(county_slug: str) -> Dict:
    """Letter A: Trigger full parcel ingestion for 0/10 counties (Franklin, Union)"""
    county_info = SHARD_10_COUNTIES.get(county_slug)
    if not county_info:
        return {"error": f"County {county_slug} not in SHARD-10"}
    
    co_no = county_info['co_no']
    
    # NOTE: This requires the ingest_county.py script to run with credentials
    # Since we can't execute Python scripts directly in this environment,
    # we'll log the command needed and create the trigger script
    
    command = f"python scripts/ingest_county.py --county {co_no} --full"
    
    logger.info(f"Letter A improvement for {county_slug} (CO_NO {co_no})")
    logger.info(f"Command needed: {command}")
    logger.info(f"This will create multi_county_auctions records for dual-product coverage")
    
    # Check current auction count for this county
    current_auctions = supabase_get('multi_county_auctions', {
        'select': 'count',
        'county': f'eq.{county_slug}'
    })
    
    return {
        'county': county_slug,
        'co_no': co_no,
        'letter': 'A',
        'action': 'ingestion_required',
        'command': command,
        'current_auctions': len(current_auctions) if current_auctions else 0,
        'note': 'Must run ingest_county.py with Supabase credentials to populate multi_county_auctions'
    }

def improve_verified_outcomes_b(county_slug: str) -> Dict:
    """Letter B: Improve verified outcomes for counties with auction data"""
    
    # Get closed auctions that need verified outcomes
    closed_auctions = supabase_get('multi_county_auctions', {
        'select': 'case_number,parcel_id,auction_date,sale_type,auction_status,winning_bid',
        'county': f'eq.{county_slug}',
        'auction_status': 'in.(sold,no_sale,canceled)',
        'limit': '5000'
    })
    
    # Check existing verified outcomes
    existing_outcomes = supabase_get('tax_deed_outcomes', {
        'select': 'case_number',
        'county_slug': f'eq.{county_slug}'
    }) + supabase_get('foreclosure_outcomes', {
        'select': 'case_number', 
        'county_slug': f'eq.{county_slug}'
    })
    
    existing_cases = {o['case_number'] for o in existing_outcomes}
    missing_outcomes = [a for a in closed_auctions if a['case_number'] not in existing_cases]
    
    verification_rate = (len(existing_outcomes) / len(closed_auctions) * 100) if closed_auctions else 0
    
    logger.info(f"Letter B analysis for {county_slug}:")
    logger.info(f"  Closed auctions: {len(closed_auctions)}")
    logger.info(f"  Verified outcomes: {len(existing_outcomes)}")
    logger.info(f"  Missing outcomes: {len(missing_outcomes)}")
    logger.info(f"  Current rate: {verification_rate:.1f}%")
    
    return {
        'county': county_slug,
        'letter': 'B',
        'closed_auctions': len(closed_auctions),
        'verified_outcomes': len(existing_outcomes),
        'missing_outcomes': len(missing_outcomes),
        'verification_rate': verification_rate,
        'target_rate': 95.0,
        'pass_status': verification_rate >= 95.0,
        'action_needed': 'Scrape county clerk verified outcomes' if verification_rate < 95.0 else 'None'
    }

def improve_parity_matching_cd(county_slug: str) -> Dict:
    """Letters C&D: Improve parity matching rates"""
    
    # Get parity status records for this county
    parity_records = supabase_get('parity_status', {
        'select': '*',
        'county': f'eq.{county_slug}',
        'limit': '10000'
    })
    
    if not parity_records:
        return {
            'county': county_slug,
            'letters': ['C', 'D'],
            'error': 'No parity_status records found',
            'action_needed': 'Run parity comparison first'
        }
    
    # Calculate current rates
    total_records = len(parity_records)
    matched_clean = len([r for r in parity_records if r.get('matched_clean')])
    matched_any = len([r for r in parity_records if r.get('matched_any')])
    
    clean_rate = (matched_clean / total_records * 100) if total_records else 0
    any_rate = (matched_any / total_records * 100) if total_records else 0
    
    logger.info(f"Letters C&D analysis for {county_slug}:")
    logger.info(f"  Total parity records: {total_records}")
    logger.info(f"  Clean matches (C): {matched_clean} ({clean_rate:.1f}%)")
    logger.info(f"  Any matches (D): {matched_any} ({any_rate:.1f}%)")
    
    # Find improvement opportunities
    unmatched_records = [r for r in parity_records if not r.get('matched_any')]
    improvement_candidates = len(unmatched_records)
    
    return {
        'county': county_slug,
        'letters': ['C', 'D'],
        'total_records': total_records,
        'matched_clean': matched_clean,
        'matched_any': matched_any,
        'clean_rate': clean_rate,
        'any_rate': any_rate,
        'c_pass': clean_rate >= 95.0,
        'd_pass': any_rate >= 95.0,
        'improvement_candidates': improvement_candidates,
        'action_needed': 'Improve case number/address normalization' if any_rate < 95.0 else 'None'
    }

def check_parcel_linkage_e(county_slug: str) -> Dict:
    """Letter E: Check parcel linkage rates"""
    
    # Get auction records for this county
    auctions = supabase_get('multi_county_auctions', {
        'select': 'parcel_id,county',
        'county': f'eq.{county_slug}',
        'limit': '10000'
    })
    
    # Count non-null parcel IDs
    linked_parcels = len([a for a in auctions if a.get('parcel_id')])
    total_auctions = len(auctions)
    linkage_rate = (linked_parcels / total_auctions * 100) if total_auctions else 0
    
    logger.info(f"Letter E analysis for {county_slug}:")
    logger.info(f"  Total auctions: {total_auctions}")
    logger.info(f"  Linked parcels: {linked_parcels}")
    logger.info(f"  Linkage rate: {linkage_rate:.1f}%")
    
    return {
        'county': county_slug,
        'letter': 'E',
        'total_auctions': total_auctions,
        'linked_parcels': linked_parcels,
        'linkage_rate': linkage_rate,
        'target_rate': 95.0,
        'pass_status': linkage_rate >= 95.0,
        'action_needed': 'Run county property appraiser linkage' if linkage_rate < 95.0 else 'None'
    }

def verify_all_shard10_counties() -> Dict:
    """Verify current status of all SHARD-10 assigned counties"""
    results = {}
    
    logger.info("=" * 60)
    logger.info("SHARD-10 VERIFICATION: manatee, alachua, martin, franklin, union")
    logger.info("=" * 60)
    
    for county_slug, county_info in SHARD_10_COUNTIES.items():
        logger.info(f"\n--- {county_slug.upper()} (CO_NO {county_info['co_no']}) ---")
        
        # Get fresh letter evaluations
        letters = evaluate_county_letters(county_slug)
        
        # Store results
        results[county_slug] = {
            'co_no': county_info['co_no'],
            'current_status': county_info['status'],
            'priority_letters': county_info['priority_letters'],
            'letter_evaluations': letters,
            'pass_count': len([l for l in letters.values() if l.get('pass')]) if letters else 0
        }
        
        # Log current status
        if letters:
            for letter, data in letters.items():
                status = data['status']
                metric = data['metric']
                logger.info(f"  {letter}: {status} {metric}")
        else:
            logger.warning(f"  Could not evaluate letters for {county_slug}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='GOLD STANDARD SHARD-10 Multi-Letter Improvements')
    parser.add_argument('--county', choices=list(SHARD_10_COUNTIES.keys()), 
                       help='Specific county to improve')
    parser.add_argument('--letter', choices=['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                       help='Specific letter to improve')
    parser.add_argument('--verify-all', action='store_true',
                       help='Verify current status of all SHARD-10 counties')
    parser.add_argument('--priority-only', action='store_true',
                       help='Only work on priority letters for each county')
    
    args = parser.parse_args()
    
    if args.verify_all:
        results = verify_all_shard10_counties()
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("SHARD-10 SUMMARY")
        logger.info("=" * 60)
        for county, data in results.items():
            pass_count = data['pass_count']
            logger.info(f"{county:12s}: {pass_count}/10 - Priority: {', '.join(data['priority_letters'])}")
        
        return
    
    if not args.county:
        parser.print_help()
        return
    
    county_slug = args.county
    county_info = SHARD_10_COUNTIES[county_slug]
    
    logger.info(f"Improving {county_slug} (CO_NO {county_info['co_no']})")
    logger.info(f"Current status: {county_info['status']}")
    logger.info(f"Priority letters: {', '.join(county_info['priority_letters'])}")
    
    # Target specific letter or priority letters
    letters_to_improve = [args.letter] if args.letter else county_info['priority_letters']
    
    for letter in letters_to_improve:
        logger.info(f"\n--- Improving Letter {letter} for {county_slug} ---")
        
        if letter == 'A':
            result = trigger_county_ingestion_a(county_slug)
        elif letter == 'B':
            result = improve_verified_outcomes_b(county_slug)
        elif letter in ['C', 'D']:
            result = improve_parity_matching_cd(county_slug)
        elif letter == 'E':
            result = check_parcel_linkage_e(county_slug)
        else:
            logger.warning(f"Letter {letter} improvement not yet implemented")
            continue
        
        logger.info(f"Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    main()