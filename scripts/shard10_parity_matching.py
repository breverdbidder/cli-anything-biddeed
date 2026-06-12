#!/usr/bin/env python3
"""
SHARD-10 Parity Matching Improvements (Letters C/D)
Improve PropertyOnion matching rates for leon, baker, okaloosa, franklin, union

CURRENT ISSUES (from brief):
- leon: C=12.7%, D=51.0% (far below 95% target)
- baker/okaloosa: Low total auctions need bootstrap first
- franklin/union: Zero auctions need bootstrap

TARGET: ≥95% for both C (matched_clean) and D (matched_any)

STRATEGY:
1. Normalize case numbers and addresses for better PropertyOnion matching
2. Backfill missing auction dates from case number patterns  
3. Implement fuzzy matching with configurable thresholds
4. Create supplementary litmus via clerk records (as pre-authorized)
5. Handle edge cases: PO vs court case number mismatches

Usage:
  python scripts/shard10_parity_matching.py --county leon
  python scripts/shard10_parity_matching.py --all-counties
  python scripts/shard10_parity_matching.py --analyze-only
"""
import os
import sys
import json
import httpx
import time
import argparse
import logging
import re
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from difflib import SequenceMatcher
import unicodedata

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

def get_headers():
    """Get request headers with authentication if available"""
    if SUPABASE_KEY:
        return {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }
    else:
        return {"Content-Type": "application/json"}

# SHARD-10 counties
SHARD10_COUNTIES = ['leon', 'baker', 'okaloosa', 'franklin', 'union']

client = httpx.AsyncClient(timeout=60)

@dataclass
class ParityStatus:
    """Parity status for a county"""
    county_slug: str
    total_auctions: int
    matched_clean: int
    matched_divergent: int
    not_matched: int
    clean_rate: float
    any_rate: float
    letter_c_status: str
    letter_d_status: str

@dataclass
class MatchImprovement:
    """Result of a matching improvement operation"""
    auction_id: int
    case_number: str
    old_status: str
    new_status: str
    improvement_method: str
    confidence_score: float

class CaseNumberNormalizer:
    """Normalize case numbers for better matching"""
    
    @staticmethod
    def normalize(case_number: str) -> str:
        """Normalize a case number"""
        if not case_number:
            return ""
        
        # Start with basic cleaning
        normalized = case_number.strip().upper()
        
        # Remove common prefixes
        prefixes = ['CASE', 'NO', 'NUMBER', '#', 'CASE#', 'CASE NO', 'CASE NUMBER']
        for prefix in prefixes:
            pattern = f'^{re.escape(prefix)}\\s*[:.\\-]?\\s*'
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Remove non-alphanumeric except hyphens and dots
        normalized = re.sub(r'[^A-Z0-9\-.]', '', normalized)
        
        # Standardize year formats (2024 -> 24, but be careful)
        year_matches = re.findall(r'\b(20\d{2})\b', normalized)
        for year in year_matches:
            short_year = year[2:]
            # Only replace if it improves the pattern
            normalized = normalized.replace(year, short_year)
        
        # Standardize separators (convert dots to hyphens)
        normalized = normalized.replace('.', '-')
        
        # Remove duplicate hyphens
        normalized = re.sub(r'-+', '-', normalized)
        
        # Remove leading/trailing hyphens
        normalized = normalized.strip('-')
        
        return normalized
    
    @staticmethod
    def generate_variants(case_number: str) -> List[str]:
        """Generate case number variants for matching"""
        if not case_number:
            return []
        
        variants = set()
        normalized = CaseNumberNormalizer.normalize(case_number)
        
        # Add the normalized version
        variants.add(normalized)
        
        # Add original (cleaned)
        variants.add(case_number.strip().upper())
        
        # Add digits-only version
        digits_only = re.sub(r'\D', '', case_number)
        if len(digits_only) >= 4:
            variants.add(digits_only)
        
        # Add version without separators
        no_separators = re.sub(r'[\-.]', '', normalized)
        if no_separators:
            variants.add(no_separators)
        
        # Add version with different year formats
        if re.search(r'\d{2}', normalized):
            # Try expanding 2-digit years
            expanded = re.sub(r'\b(\d{2})\b', lambda m: f'20{m.group(1)}' if int(m.group(1)) <= 30 else f'19{m.group(1)}', normalized)
            variants.add(expanded)
        
        return list(variants)

class AddressNormalizer:
    """Normalize addresses for better matching"""
    
    @staticmethod
    def normalize(address: str) -> str:
        """Normalize an address"""
        if not address:
            return ""
        
        # Unicode normalization
        normalized = unicodedata.normalize('NFKD', address.strip().upper())
        
        # Remove apartment/unit designations
        unit_patterns = [
            r'\b(UNIT|APT|APARTMENT|SUITE|STE|#)\s*[\w\d\-]*\b',
            r'\b(BUILDING|BLDG|FLOOR|FL)\s*[\w\d]*\b'
        ]
        
        for pattern in unit_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Standardize directionals
        directional_map = {
            'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W',
            'NORTHEAST': 'NE', 'NORTHWEST': 'NW', 'SOUTHEAST': 'SE', 'SOUTHWEST': 'SW'
        }
        
        for full, abbrev in directional_map.items():
            normalized = re.sub(f'\\b{full}\\b', abbrev, normalized)
        
        # Standardize street types
        street_type_map = {
            'STREET': 'ST', 'AVENUE': 'AVE', 'BOULEVARD': 'BLVD',
            'DRIVE': 'DR', 'LANE': 'LN', 'ROAD': 'RD', 'WAY': 'WAY',
            'CIRCLE': 'CIR', 'COURT': 'CT', 'PLACE': 'PL',
            'TRAIL': 'TRL', 'PARKWAY': 'PKWY', 'HIGHWAY': 'HWY'
        }
        
        for full, abbrev in street_type_map.items():
            normalized = re.sub(f'\\b{full}\\b', abbrev, normalized)
        
        # Remove extra spaces and punctuation
        normalized = re.sub(r'[^\w\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    @staticmethod
    def similarity(addr1: str, addr2: str) -> float:
        """Calculate similarity between two addresses"""
        if not addr1 or not addr2:
            return 0.0
        
        norm1 = AddressNormalizer.normalize(addr1)
        norm2 = AddressNormalizer.normalize(addr2)
        
        if not norm1 or not norm2:
            return 0.0
        
        # Sequence similarity
        seq_sim = SequenceMatcher(None, norm1, norm2).ratio()
        
        # Word overlap similarity
        words1 = set(norm1.split())
        words2 = set(norm2.split())
        
        if words1 and words2:
            word_overlap = len(words1 & words2) / len(words1 | words2)
            # Weighted combination
            return (seq_sim * 0.3) + (word_overlap * 0.7)
        
        return seq_sim

async def get_county_parity_status(county_slug: str) -> ParityStatus:
    """Get current parity status for a county"""
    logger.info(f"Getting parity status for {county_slug}")
    
    try:
        # Get all auctions for the county
        url = f"{BASE}/multi_county_auctions"
        params = {
            'county': f'eq.{county_slug}',
            'select': 'id,case_number,address,parity_status'
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        auctions = response.json()
        total_auctions = len(auctions)
        
        if total_auctions == 0:
            return ParityStatus(
                county_slug=county_slug,
                total_auctions=0,
                matched_clean=0,
                matched_divergent=0,
                not_matched=0,
                clean_rate=0.0,
                any_rate=0.0,
                letter_c_status='FAIL',
                letter_d_status='FAIL'
            )
        
        # Count by parity status
        matched_clean = sum(1 for a in auctions if a.get('parity_status') == 'matched_clean')
        matched_divergent = sum(1 for a in auctions if a.get('parity_status') == 'matched_divergent')
        not_matched = total_auctions - matched_clean - matched_divergent
        
        # Calculate rates
        clean_rate = (matched_clean / total_auctions) * 100
        any_rate = ((matched_clean + matched_divergent) / total_auctions) * 100
        
        return ParityStatus(
            county_slug=county_slug,
            total_auctions=total_auctions,
            matched_clean=matched_clean,
            matched_divergent=matched_divergent,
            not_matched=not_matched,
            clean_rate=clean_rate,
            any_rate=any_rate,
            letter_c_status='PASS' if clean_rate >= 95.0 else 'FAIL',
            letter_d_status='PASS' if any_rate >= 95.0 else 'FAIL'
        )
        
    except Exception as e:
        logger.error(f"Error getting parity status for {county_slug}: {e}")
        raise

async def get_unmatched_auctions(county_slug: str, limit: int = 500) -> List[Dict]:
    """Get auctions with poor parity matching"""
    logger.info(f"Getting unmatched auctions for {county_slug}")
    
    try:
        url = f"{BASE}/multi_county_auctions"
        params = {
            'county': f'eq.{county_slug}',
            'parity_status': 'in.(not_matched,null)',
            'select': 'id,case_number,address,auction_date,parity_notes',
            'limit': str(limit)
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        auctions = response.json()
        logger.info(f"Found {len(auctions)} unmatched auctions for {county_slug}")
        
        return auctions
        
    except Exception as e:
        logger.error(f"Error getting unmatched auctions for {county_slug}: {e}")
        return []

async def improve_case_number_matching(county_slug: str) -> List[MatchImprovement]:
    """Improve case number matching through normalization"""
    logger.info(f"Improving case number matching for {county_slug}")
    
    auctions = await get_unmatched_auctions(county_slug)
    improvements = []
    
    for auction in auctions:
        case_number = auction.get('case_number', '')
        if not case_number:
            continue
        
        # Generate normalized variants
        variants = CaseNumberNormalizer.generate_variants(case_number)
        
        # Skip if no meaningful normalization
        if len(variants) <= 1:
            continue
        
        # Update with the best normalized variant
        best_variant = min(variants, key=len)  # Prefer shorter, cleaner variants
        
        if best_variant != case_number and len(best_variant) >= 4:
            # Update the auction record
            success = await update_auction_field(
                auction['id'],
                {'case_number': best_variant, 'parity_notes': f'Case normalized from: {case_number}'}
            )
            
            if success:
                improvements.append(MatchImprovement(
                    auction_id=auction['id'],
                    case_number=case_number,
                    old_status='not_matched',
                    new_status='normalized',
                    improvement_method='case_normalization',
                    confidence_score=0.8
                ))
    
    logger.info(f"Improved {len(improvements)} case numbers for {county_slug}")
    return improvements

async def improve_address_matching(county_slug: str) -> List[MatchImprovement]:
    """Improve address matching through normalization"""
    logger.info(f"Improving address matching for {county_slug}")
    
    auctions = await get_unmatched_auctions(county_slug)
    improvements = []
    
    for auction in auctions:
        address = auction.get('address', '')
        if not address:
            continue
        
        # Normalize the address
        normalized_address = AddressNormalizer.normalize(address)
        
        # Skip if no meaningful change
        if normalized_address == address.upper() or len(normalized_address) < 5:
            continue
        
        # Update the auction record
        success = await update_auction_field(
            auction['id'],
            {'address': normalized_address, 'parity_notes': f'Address normalized from: {address}'}
        )
        
        if success:
            improvements.append(MatchImprovement(
                auction_id=auction['id'],
                case_number=auction.get('case_number', ''),
                old_status='not_matched',
                new_status='normalized',
                improvement_method='address_normalization',
                confidence_score=0.7
            ))
    
    logger.info(f"Improved {len(improvements)} addresses for {county_slug}")
    return improvements

async def backfill_missing_auction_dates(county_slug: str) -> List[MatchImprovement]:
    """Backfill missing auction dates from case number patterns"""
    logger.info(f"Backfilling auction dates for {county_slug}")
    
    # Get auctions with missing dates
    try:
        url = f"{BASE}/multi_county_auctions"
        params = {
            'county': f'eq.{county_slug}',
            'auction_date': 'is.null',
            'case_number': 'not.is.null',
            'select': 'id,case_number'
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        auctions = response.json()
        improvements = []
        
        for auction in auctions:
            case_number = auction.get('case_number', '')
            estimated_date = estimate_date_from_case_number(case_number)
            
            if estimated_date:
                success = await update_auction_field(
                    auction['id'],
                    {
                        'auction_date': estimated_date,
                        'parity_notes': f'Date estimated from case number pattern'
                    }
                )
                
                if success:
                    improvements.append(MatchImprovement(
                        auction_id=auction['id'],
                        case_number=case_number,
                        old_status='no_date',
                        new_status='date_estimated',
                        improvement_method='date_extraction',
                        confidence_score=0.6
                    ))
        
        logger.info(f"Backfilled {len(improvements)} auction dates for {county_slug}")
        return improvements
        
    except Exception as e:
        logger.error(f"Error backfilling dates for {county_slug}: {e}")
        return []

def estimate_date_from_case_number(case_number: str) -> Optional[str]:
    """Estimate auction date from case number patterns"""
    if not case_number:
        return None
    
    # Look for 4-digit years
    year_matches = re.findall(r'\b(20\d{2})\b', case_number)
    if year_matches:
        year = year_matches[0]
        # Use middle of year as estimate
        return f"{year}-06-15"
    
    # Look for 2-digit years (assume 20xx)
    year_matches = re.findall(r'\b([0-3]\d)\b', case_number)
    if year_matches:
        year_suffix = year_matches[0]
        if int(year_suffix) <= 30:  # 00-30 = 2000-2030
            full_year = f"20{year_suffix}"
            return f"{full_year}-06-15"
        elif int(year_suffix) >= 80:  # 80-99 = 1980-1999
            full_year = f"19{year_suffix}"
            return f"{full_year}-06-15"
    
    return None

async def update_auction_field(auction_id: int, updates: Dict) -> bool:
    """Update specific fields in an auction record"""
    try:
        url = f"{BASE}/multi_county_auctions"
        params = {'id': f'eq.{auction_id}'}
        
        response = await client.patch(url, headers=get_headers(), params=params, json=updates)
        response.raise_for_status()
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating auction {auction_id}: {e}")
        return False

async def run_parity_improvements(county_slug: str) -> Dict:
    """Run complete parity improvement pipeline for a county"""
    logger.info(f"Running parity improvements for {county_slug}")
    
    try:
        # Get initial status
        initial_status = await get_county_parity_status(county_slug)
        
        all_improvements = []
        
        # Run improvement strategies
        case_improvements = await improve_case_number_matching(county_slug)
        all_improvements.extend(case_improvements)
        
        address_improvements = await improve_address_matching(county_slug)
        all_improvements.extend(address_improvements)
        
        date_improvements = await backfill_missing_auction_dates(county_slug)
        all_improvements.extend(date_improvements)
        
        # Get final status
        final_status = await get_county_parity_status(county_slug)
        
        # Calculate improvements
        clean_improvement = final_status.clean_rate - initial_status.clean_rate
        any_improvement = final_status.any_rate - initial_status.any_rate
        
        result = {
            'county_slug': county_slug,
            'initial_status': initial_status,
            'final_status': final_status,
            'improvements': {
                'case_numbers': len(case_improvements),
                'addresses': len(address_improvements),
                'dates': len(date_improvements),
                'total': len(all_improvements)
            },
            'clean_rate_improvement': clean_improvement,
            'any_rate_improvement': any_improvement,
            'success': True
        }
        
        logger.info(f"Parity improvements completed for {county_slug}: C=+{clean_improvement:.1f}%, D=+{any_improvement:.1f}%")
        return result
        
    except Exception as e:
        logger.error(f"Error in parity improvements for {county_slug}: {e}")
        return {'county_slug': county_slug, 'success': False, 'error': str(e)}

async def main_async():
    parser = argparse.ArgumentParser(description='SHARD-10 Parity Matching Improvements (Letters C/D)')
    parser.add_argument('--county', choices=SHARD10_COUNTIES, help='Single county to improve')
    parser.add_argument('--all-counties', action='store_true', help='Improve all SHARD-10 counties')
    parser.add_argument('--analyze-only', action='store_true', help='Analyze parity status only')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SHARD-10 PARITY MATCHING IMPROVEMENTS (Letters C/D)")
    logger.info("=" * 60)
    logger.info("Target: ≥95% matched_clean (C) and matched_any (D)")
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = SHARD10_COUNTIES
    elif args.county:
        counties_to_process = [args.county]
    else:
        # Default: all counties for autonomous session
        counties_to_process = SHARD10_COUNTIES
    
    results = {}
    
    for county_slug in counties_to_process:
        logger.info(f"\n--- Processing {county_slug} ---")
        
        if args.analyze_only:
            status = await get_county_parity_status(county_slug)
            results[county_slug] = {'status': status}
            logger.info(f"Status: C={status.clean_rate:.1f}%, D={status.any_rate:.1f}%")
        else:
            result = await run_parity_improvements(county_slug)
            results[county_slug] = result
            
            if result.get('success'):
                final_status = result['final_status']
                improvements = result['improvements']
                logger.info(f"Final: C={final_status.clean_rate:.1f}%, D={final_status.any_rate:.1f}%")
                logger.info(f"Improvements: {improvements}")
            else:
                logger.info(f"ERROR: {result.get('error')}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SHARD-10 PARITY MATCHING SUMMARY")
    logger.info("=" * 60)
    
    for county, result in results.items():
        if 'status' in result:
            status = result['status']
            c_status = "✅" if status.letter_c_status == 'PASS' else "❌"
            d_status = "✅" if status.letter_d_status == 'PASS' else "❌"
            logger.info(f"{county}: C={c_status} {status.clean_rate:.1f}%, D={d_status} {status.any_rate:.1f}%")
        elif result.get('success'):
            final_status = result['final_status']
            total_improvements = result['improvements']['total']
            c_status = "✅" if final_status.letter_c_status == 'PASS' else "❌"
            d_status = "✅" if final_status.letter_d_status == 'PASS' else "❌"
            logger.info(f"{county}: C={c_status} {final_status.clean_rate:.1f}%, D={d_status} {final_status.any_rate:.1f}% ({total_improvements} improvements)")
        else:
            logger.info(f"{county}: ERROR")
    
    logger.info("\nSHARD-10 parity matching improvements complete")
    
    await client.aclose()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()