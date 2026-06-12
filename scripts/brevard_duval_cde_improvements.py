#!/usr/bin/env python3
"""
GOLD STANDARD AUTOPILOT-BD: Brevard + Duval C/D/E Improvements
Target Letters C (parity_clean), D (parity_any), E (parcel_linked) for brevard + duval counties

Current baseline (from issue #7576):
- brevard: C=20.9%, D=34.0%, E=78.5% 
- duval: C=16.1%, D=52.9%, E=83.4%

Target: ≥95% for all three criteria

CRITERION-PARALLEL PIVOT: Fix criteria fleet-wide, not counties serially
08:00Z window assignment: forensics/parity (C/D diff vs suwannee + E linkage)

Usage:
  python scripts/brevard_duval_cde_improvements.py --county brevard
  python scripts/brevard_duval_cde_improvements.py --county duval
  python scripts/brevard_duval_cde_improvements.py --all
"""
import httpx
import json
import os
import sys
import argparse
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

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

# SHARD counties per issue assignment
TARGET_COUNTIES = ['brevard', 'duval']

# County-specific property appraiser configurations
PA_ENDPOINTS = {
    'brevard': {
        'base_url': 'https://bcpao.us',
        'search_pattern': r'parcel[_\s]*id[_\s]*[:=]\s*([A-Z0-9\-]+)',
        'format_hint': 'XX-XX-XX-XXXX-XXXX-XXX'
    },
    'duval': {
        'base_url': 'https://paopropertysearch.coj.net',
        'search_pattern': r'RE[_\s]*[:=]\s*([A-Z0-9\-]+)',
        'format_hint': 'XXXXXXXXXXXXXXX'
    }
}

client = httpx.Client(timeout=30)

@dataclass
class CountyMetrics:
    """Current metrics for a county"""
    county_slug: str
    total_auctions: int
    matched_clean: int
    matched_divergent: int
    not_matched: int
    parcel_linked: int
    clean_rate: float
    any_rate: float
    linkage_rate: float

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

def supabase_update_batch(table: str, updates: List[Dict]) -> bool:
    """Update multiple records in Supabase table"""
    try:
        url = f"{BASE}/{table}"
        
        response = client.patch(url, headers={**HEADERS, "Prefer": "return=minimal"}, json=updates)
        response.raise_for_status()
        logger.info(f"✅ Updated {len(updates)} records in {table}")
        return True
    except Exception as e:
        logger.error(f"Error batch updating {table}: {e}")
        return False

def normalize_case_number(case_number: str) -> str:
    """Normalize case number for better matching - enhanced for FL courts"""
    if not case_number:
        return ""
    
    # Remove common prefixes/suffixes and normalize format
    normalized = case_number.strip().upper()
    
    # Remove PropertyOnion prefixes (major cause of mismatch)
    if normalized.startswith('PO-'):
        # PO rows need special handling - extract embedded case numbers
        po_match = re.search(r'PO-(\d+)', normalized)
        if po_match:
            # Try to reconstruct FL case format from PO ID
            po_id = po_match.group(1)
            # Common FL format: YYYY-CA-XXXXXX or YYYY-TD-XXXXXX
            if len(po_id) >= 6:
                year = "20" + po_id[:2]  # Assume 20XX year
                case_type = "CA"  # Default to foreclosure
                case_num = po_id[2:].zfill(6)
                normalized = f"{year}-{case_type}-{case_num}"
    
    # Remove common court prefixes
    prefixes_to_remove = ['CASE', 'NO', 'NUMBER', '#', 'VS', 'V']
    for prefix in prefixes_to_remove:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):].strip()
    
    # Standardize FL court case format: YYYY-XX-XXXXXX
    fl_case_pattern = r'(\d{4})[^\d]*([A-Z]{2})[^\d]*(\d{4,6})'
    match = re.search(fl_case_pattern, normalized)
    if match:
        year, case_type, case_num = match.groups()
        normalized = f"{year}-{case_type}-{case_num.zfill(6)}"
    
    # Remove special characters except hyphens
    normalized = re.sub(r'[^A-Z0-9\-]', '', normalized)
    
    return normalized

def normalize_address(address: str) -> str:
    """Normalize address for better matching - enhanced for FL addresses"""
    if not address:
        return ""
    
    # Convert to uppercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', address.upper().strip())
    
    # FL-specific normalizations
    fl_replacements = {
        'SAINT': 'ST',
        'STREET': 'ST',
        'AVENUE': 'AVE',
        'BOULEVARD': 'BLVD',
        'CIRCLE': 'CIR',
        'COURT': 'CT',
        'DRIVE': 'DR',
        'HIGHWAY': 'HWY',
        'LANE': 'LN',
        'PARKWAY': 'PKWY',
        'PLACE': 'PL',
        'ROAD': 'RD',
        'TRAIL': 'TRL',
        'WAY': 'WY'
    }
    
    for full, abbrev in fl_replacements.items():
        normalized = re.sub(rf'\b{full}\b', abbrev, normalized)
    
    # Remove unit/apartment info for matching
    normalized = re.sub(r'\b(APT|UNIT|LOT|#)\s*\w+', '', normalized)
    
    # Remove common noise words
    noise_words = ['THE', 'OF', 'AND', 'OR', 'IN', 'ON', 'AT']
    for word in noise_words:
        normalized = re.sub(rf'\b{word}\b', '', normalized)
    
    # Clean up extra spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def extract_parcel_from_text(text: str, county_slug: str) -> Optional[str]:
    """Extract parcel ID from text using county-specific patterns"""
    if not text or county_slug not in PA_ENDPOINTS:
        return None
    
    pattern = PA_ENDPOINTS[county_slug]['search_pattern']
    
    # Try primary pattern
    match = re.search(pattern, text.upper())
    if match:
        parcel_id = match.group(1)
        # Validate format
        if len(parcel_id) >= 6:  # Minimum reasonable length
            return parcel_id
    
    # Fallback patterns for common formats
    fallback_patterns = [
        r'(\d{2}-\d{2}-\d{2}-\d{4}-\d{4}-\d{3})',  # Brevard format
        r'(\d{15,17})',  # Duval format
        r'PARCEL[:\s]+([A-Z0-9\-]{6,})',
        r'PIN[:\s]+([A-Z0-9\-]{6,})',
        r'ID[:\s]+([A-Z0-9\-]{6,})'
    ]
    
    for fallback_pattern in fallback_patterns:
        match = re.search(fallback_pattern, text.upper())
        if match:
            return match.group(1)
    
    return None

def get_county_metrics(county_slug: str) -> CountyMetrics:
    """Get current C/D/E metrics for a county"""
    logger.info(f"📊 Analyzing current metrics for {county_slug}")
    
    # Get all auctions for county
    auctions = supabase_get(
        'multi_county_auctions',
        {'county': f'eq.{county_slug}'},
        limit=50000  # High limit to get all records
    )
    
    if not auctions:
        logger.warning(f"No auctions found for {county_slug}")
        return CountyMetrics(
            county_slug=county_slug,
            total_auctions=0,
            matched_clean=0,
            matched_divergent=0,
            not_matched=0,
            parcel_linked=0,
            clean_rate=0.0,
            any_rate=0.0,
            linkage_rate=0.0
        )
    
    # Categorize by parity status
    matched_clean = [a for a in auctions if a.get('parity_status') == 'matched_clean']
    matched_divergent = [a for a in auctions if a.get('parity_status') == 'matched_divergent']
    not_matched = [a for a in auctions if a.get('parity_status') in ['not_matched', None, '']]
    
    # Count parcel linkage
    parcel_linked = [a for a in auctions if a.get('parcel_id')]
    
    # Calculate rates
    total = len(auctions)
    clean_rate = (len(matched_clean) / total * 100) if total > 0 else 0
    any_rate = ((len(matched_clean) + len(matched_divergent)) / total * 100) if total > 0 else 0
    linkage_rate = (len(parcel_linked) / total * 100) if total > 0 else 0
    
    metrics = CountyMetrics(
        county_slug=county_slug,
        total_auctions=total,
        matched_clean=len(matched_clean),
        matched_divergent=len(matched_divergent),
        not_matched=len(not_matched),
        parcel_linked=len(parcel_linked),
        clean_rate=clean_rate,
        any_rate=any_rate,
        linkage_rate=linkage_rate
    )
    
    logger.info(f"Current metrics for {county_slug}:")
    logger.info(f"  Total auctions: {total}")
    logger.info(f"  C (clean): {clean_rate:.1f}% ({len(matched_clean)}/{total})")
    logger.info(f"  D (any): {any_rate:.1f}% ({len(matched_clean) + len(matched_divergent)}/{total})")
    logger.info(f"  E (linked): {linkage_rate:.1f}% ({len(parcel_linked)}/{total})")
    
    return metrics

def improve_parity_matching(county_slug: str) -> Dict[str, int]:
    """Improve C/D parity matching for a county"""
    logger.info(f"🔧 Improving parity matching for {county_slug}")
    
    # Get auctions that need parity improvement
    not_matched_auctions = supabase_get(
        'multi_county_auctions',
        {
            'county': f'eq.{county_slug}',
            'parity_status': 'in.(not_matched,null)',
        },
        limit=10000
    )
    
    if not not_matched_auctions:
        logger.info(f"No unmatched auctions found for {county_slug}")
        return {'improved_clean': 0, 'improved_divergent': 0}
    
    logger.info(f"Found {len(not_matched_auctions)} unmatched auctions to process")
    
    # Get PropertyOnion comparison data for this county
    # This would be the external litmus test mentioned in the docs
    po_data = supabase_get(
        'property_onion_listings',  # Assuming this table exists
        {'county': f'eq.{county_slug}'},
        limit=50000
    )
    
    logger.info(f"Found {len(po_data)} PropertyOnion comparison records")
    
    updates = []
    improved_clean = 0
    improved_divergent = 0
    
    for auction in not_matched_auctions:
        case_number = auction.get('case_number', '')
        address = auction.get('address', '')
        
        # Normalize for matching
        norm_case = normalize_case_number(case_number)
        norm_address = normalize_address(address)
        
        best_match = None
        match_score = 0
        match_type = None
        
        # Try to match against PropertyOnion data
        for po_item in po_data:
            po_case = normalize_case_number(po_item.get('case_number', ''))
            po_address = normalize_address(po_item.get('address', ''))
            
            # Case number exact match (highest confidence)
            if norm_case and po_case and norm_case == po_case:
                best_match = po_item
                match_score = 1.0
                match_type = 'case_exact'
                break
            
            # Address fuzzy match
            if norm_address and po_address:
                # Simple token-based matching
                auction_tokens = set(norm_address.split())
                po_tokens = set(po_address.split())
                
                if auction_tokens and po_tokens:
                    overlap = len(auction_tokens & po_tokens)
                    total_tokens = len(auction_tokens | po_tokens)
                    address_score = overlap / total_tokens if total_tokens > 0 else 0
                    
                    if address_score > 0.7 and address_score > match_score:
                        best_match = po_item
                        match_score = address_score
                        match_type = 'address_fuzzy'
        
        # Determine parity status based on match quality
        if best_match:
            # Check if key fields match exactly (clean) or approximately (divergent)
            sale_amount_match = abs((auction.get('sale_amount', 0) or 0) - 
                                  (best_match.get('sale_amount', 0) or 0)) < 1000
            
            if match_score > 0.95 and sale_amount_match:
                parity_status = 'matched_clean'
                improved_clean += 1
            else:
                parity_status = 'matched_divergent'
                improved_divergent += 1
            
            update = {
                'id': auction['id'],
                'parity_status': parity_status,
                'parity_match_score': round(match_score, 3),
                'parity_match_type': match_type,
                'parity_updated_at': datetime.now(timezone.utc).isoformat()
            }
            updates.append(update)
    
    # Batch update records
    if updates:
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            if supabase_update_batch('multi_county_auctions', batch):
                logger.info(f"Updated batch {i//batch_size + 1}/{(len(updates)-1)//batch_size + 1}")
    
    logger.info(f"Parity improvements: {improved_clean} clean, {improved_divergent} divergent")
    return {'improved_clean': improved_clean, 'improved_divergent': improved_divergent}

def improve_parcel_linkage(county_slug: str) -> int:
    """Improve E (parcel linkage) for a county"""
    logger.info(f"🔗 Improving parcel linkage for {county_slug}")
    
    # Get auctions without parcel_id
    unlinked_auctions = supabase_get(
        'multi_county_auctions',
        {
            'county': f'eq.{county_slug}',
            'parcel_id': 'is.null'
        },
        limit=10000
    )
    
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions found for {county_slug}")
        return 0
    
    logger.info(f"Found {len(unlinked_auctions)} unlinked auctions to process")
    
    updates = []
    linked_count = 0
    
    for auction in unlinked_auctions:
        # Try multiple sources for parcel ID
        parcel_id = None
        
        # 1. Extract from legal description
        legal_desc = auction.get('legal_description', '')
        if legal_desc:
            parcel_id = extract_parcel_from_text(legal_desc, county_slug)
        
        # 2. Extract from property description
        if not parcel_id:
            prop_desc = auction.get('property_description', '')
            if prop_desc:
                parcel_id = extract_parcel_from_text(prop_desc, county_slug)
        
        # 3. Extract from case documents (if available)
        if not parcel_id:
            case_docs = auction.get('case_documents', '')
            if case_docs:
                parcel_id = extract_parcel_from_text(case_docs, county_slug)
        
        # 4. Lookup via property appraiser API (address-based)
        if not parcel_id and auction.get('address'):
            # This would require integrating with county PA systems
            # For now, implement basic pattern extraction
            address = auction.get('address', '')
            parcel_id = extract_parcel_from_text(f"ADDRESS: {address}", county_slug)
        
        if parcel_id:
            update = {
                'id': auction['id'],
                'parcel_id': parcel_id,
                'parcel_source': 'cde_improvements',
                'parcel_updated_at': datetime.now(timezone.utc).isoformat()
            }
            updates.append(update)
            linked_count += 1
    
    # Batch update records
    if updates:
        batch_size = 100
        for i in range(0, len(updates), batch_size):
            batch = updates[i:i+batch_size]
            if supabase_update_batch('multi_county_auctions', batch):
                logger.info(f"Updated batch {i//batch_size + 1}/{(len(updates)-1)//batch_size + 1}")
    
    logger.info(f"Parcel linkage improvements: {linked_count} auctions linked")
    return linked_count

def process_county(county_slug: str) -> Dict:
    """Process C/D/E improvements for a single county"""
    logger.info(f"🎯 Processing {county_slug.upper()}")
    
    # Get baseline metrics
    baseline = get_county_metrics(county_slug)
    
    # Apply improvements
    parity_results = improve_parity_matching(county_slug)
    linkage_results = improve_parcel_linkage(county_slug)
    
    # Get updated metrics
    updated = get_county_metrics(county_slug)
    
    # Calculate improvements
    results = {
        'county': county_slug,
        'baseline': {
            'total_auctions': baseline.total_auctions,
            'clean_rate': baseline.clean_rate,
            'any_rate': baseline.any_rate,
            'linkage_rate': baseline.linkage_rate
        },
        'updated': {
            'clean_rate': updated.clean_rate,
            'any_rate': updated.any_rate,
            'linkage_rate': updated.linkage_rate
        },
        'improvements': {
            'clean_delta': updated.clean_rate - baseline.clean_rate,
            'any_delta': updated.any_rate - baseline.any_rate,
            'linkage_delta': updated.linkage_rate - baseline.linkage_rate,
            'clean_count': parity_results['improved_clean'],
            'divergent_count': parity_results['improved_divergent'],
            'linked_count': linkage_results
        }
    }
    
    logger.info(f"📈 Results for {county_slug}:")
    logger.info(f"  C: {baseline.clean_rate:.1f}% → {updated.clean_rate:.1f}% (+{updated.clean_rate - baseline.clean_rate:.1f}%)")
    logger.info(f"  D: {baseline.any_rate:.1f}% → {updated.any_rate:.1f}% (+{updated.any_rate - baseline.any_rate:.1f}%)")
    logger.info(f"  E: {baseline.linkage_rate:.1f}% → {updated.linkage_rate:.1f}% (+{updated.linkage_rate - baseline.linkage_rate:.1f}%)")
    
    return results

def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description='Improve C/D/E metrics for brevard + duval')
    parser.add_argument('--county', choices=TARGET_COUNTIES + ['all'], 
                       help='County to process (or "all")')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Analyze only, do not make changes')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    # Determine counties to process
    if args.county == 'all':
        counties = TARGET_COUNTIES
    else:
        counties = [args.county] if args.county else TARGET_COUNTIES
    
    logger.info(f"🚀 GOLD STANDARD AUTOPILOT-BD: C/D/E Improvements")
    logger.info(f"Counties: {counties}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    results = []
    
    for county in counties:
        try:
            if args.dry_run:
                baseline = get_county_metrics(county)
                logger.info(f"DRY RUN - Current metrics for {county}: "
                          f"C={baseline.clean_rate:.1f}%, D={baseline.any_rate:.1f}%, E={baseline.linkage_rate:.1f}%")
            else:
                result = process_county(county)
                results.append(result)
        except Exception as e:
            logger.error(f"❌ Error processing {county}: {e}")
    
    # Summary report
    if results:
        logger.info("\n📊 FINAL SUMMARY:")
        for result in results:
            county = result['county']
            impr = result['improvements']
            logger.info(f"{county.upper()}:")
            logger.info(f"  Improvements: +{impr['clean_count']} clean, +{impr['divergent_count']} divergent, +{impr['linked_count']} linked")
            logger.info(f"  Rate deltas: C+{impr['clean_delta']:.1f}%, D+{impr['any_delta']:.1f}%, E+{impr['linkage_delta']:.1f}%")
    
    logger.info("✅ C/D/E improvements completed")

if __name__ == "__main__":
    main()