#!/usr/bin/env python3
"""
SHARD-6 PARCEL LINKAGE FIXER
Fix parcel_id linkage for Letter E Gold Standard compliance

Target: Link ≥95% of auctions to parcel_id from sample_properties/fl_parcels
Strategy: Use property address matching + county property appraiser lookups

Counties: highlands, st_johns, hendry, calhoun, liberty
"""
import os
import sys
import time
import httpx
import json
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SHARD6_COUNTIES = {
    'highlands': {
        'co_no': 38,
        'appraiser_url': 'https://www.pa.highlands.fl.us',
        'appraiser_search': '/search?address={address}'
    },
    'st_johns': {
        'co_no': 65,
        'appraiser_url': 'https://www.sjcpa.us',
        'appraiser_search': '/property-search?addr={address}'
    },
    'hendry': {
        'co_no': 36,
        'appraiser_url': 'https://www.hendrysearch.org',
        'appraiser_search': '/search?q={address}'
    },
    'calhoun': {
        'co_no': 17,
        'appraiser_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=648&LayerID=8993&PageTypeID=1',
        'appraiser_search': '&searchType=address&searchValue={address}'
    },
    'liberty': {
        'co_no': 49,
        'appraiser_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=647&LayerID=8990&PageTypeID=1',
        'appraiser_search': '&searchType=address&searchValue={address}'
    }
}

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co") 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

client = httpx.AsyncClient(timeout=30, headers={
    "User-Agent": "BidDeed.AI Gold Standard Parcel Linkage (F.S. 119 Public Records)"
})

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

async def get_unlinked_auctions(county_slug: str, limit: int = 100) -> List[Dict]:
    """Get auctions without parcel_id that need linking"""
    headers = sb_headers()
    
    try:
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}"
            f"&parcel_id=is.null"
            f"&property_address=not.is.null"
            f"&select=case_number,property_address,property_city,property_zip"
            f"&limit={limit}",
            headers=headers
        )
        
        if response.status_code == 200:
            auctions = response.json()
            logger.info(f"📊 {county_slug}: Found {len(auctions)} unlinked auctions")
            return auctions
        else:
            logger.error(f"❌ {county_slug}: Failed to fetch unlinked auctions: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ {county_slug}: Error fetching unlinked auctions: {e}")
        return []

async def get_sample_properties(county_slug: str) -> Dict[str, str]:
    """Get sample_properties for address matching"""
    headers = sb_headers()
    
    try:
        # Get co_no for this county
        county_config = SHARD6_COUNTIES.get(county_slug, {})
        co_no = county_config.get('co_no')
        
        if not co_no:
            logger.error(f"❌ {county_slug}: No co_no found in configuration")
            return {}
        
        response = await client.get(
            f"{SUPABASE_URL}/rest/v1/sample_properties"
            f"?co_no=eq.{co_no}"
            f"&address=not.is.null"
            f"&select=parcel_id,address,city,zip_code",
            headers=headers
        )
        
        if response.status_code == 200:
            properties = response.json()
            
            # Build address lookup dictionary
            address_lookup = {}
            for prop in properties:
                address = prop.get('address', '').strip().upper()
                city = prop.get('city', '').strip().upper()
                parcel_id = prop.get('parcel_id', '').strip()
                
                if address and parcel_id:
                    # Create searchable address keys
                    full_address = f"{address}, {city}".strip(', ')
                    address_lookup[full_address] = parcel_id
                    address_lookup[address] = parcel_id  # Also index by address alone
            
            logger.info(f"📚 {county_slug}: Loaded {len(address_lookup)} address-to-parcel mappings")
            return address_lookup
        else:
            logger.error(f"❌ {county_slug}: Failed to fetch sample properties: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"❌ {county_slug}: Error fetching sample properties: {e}")
        return {}

def normalize_address(address: str) -> str:
    """Normalize address for better matching"""
    if not address:
        return ""
    
    # Convert to uppercase and remove extra whitespace
    normalized = re.sub(r'\s+', ' ', address.strip().upper())
    
    # Common address normalizations
    replacements = {
        ' STREET': ' ST',
        ' AVENUE': ' AVE', 
        ' ROAD': ' RD',
        ' DRIVE': ' DR',
        ' LANE': ' LN',
        ' CIRCLE': ' CIR',
        ' COURT': ' CT',
        ' BOULEVARD': ' BLVD',
        ' PLACE': ' PL',
        ' NORTH ': ' N ',
        ' SOUTH ': ' S ',
        ' EAST ': ' E ',
        ' WEST ': ' W ',
        '#': 'APT',
        'UNIT ': 'APT '
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Remove common noise
    normalized = re.sub(r'\b(APT|UNIT|STE|SUITE)\s*\w*\b', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    return normalized

def find_best_address_match(target_address: str, address_lookup: Dict[str, str]) -> Optional[str]:
    """Find the best matching parcel_id for a target address"""
    if not target_address or not address_lookup:
        return None
    
    normalized_target = normalize_address(target_address)
    
    # Try exact match first
    if normalized_target in address_lookup:
        return address_lookup[normalized_target]
    
    # Try fuzzy matching
    best_match = None
    best_score = 0.8  # Minimum similarity threshold
    
    for lookup_address, parcel_id in address_lookup.items():
        normalized_lookup = normalize_address(lookup_address)
        
        # Calculate similarity
        similarity = SequenceMatcher(None, normalized_target, normalized_lookup).ratio()
        
        if similarity > best_score:
            best_score = similarity
            best_match = parcel_id
    
    return best_match

async def link_auction_parcels(county_slug: str, auctions: List[Dict], 
                             address_lookup: Dict[str, str]) -> List[Dict]:
    """Link auctions to parcel_ids and return update records"""
    logger.info(f"🔗 {county_slug}: Linking {len(auctions)} auctions to parcels...")
    
    updates = []
    
    for i, auction in enumerate(auctions):
        case_number = auction.get('case_number', '')
        property_address = auction.get('property_address', '')
        property_city = auction.get('property_city', '')
        
        if not property_address:
            continue
        
        # Build full address for matching
        full_address = f"{property_address}"
        if property_city:
            full_address += f", {property_city}"
        
        # Find best matching parcel
        parcel_id = find_best_address_match(full_address, address_lookup)
        
        if parcel_id:
            updates.append({
                'case_number': case_number,
                'parcel_id': parcel_id,
                'address_used': full_address,
                'linkage_method': 'address_fuzzy_match'
            })
        
        # Log progress
        if (i + 1) % 25 == 0:
            linked_so_far = len(updates)
            logger.info(f"  Progress: {i + 1}/{len(auctions)} processed, {linked_so_far} linked")
    
    logger.info(f"✅ {county_slug}: Successfully linked {len(updates)} auctions to parcels")
    return updates

async def update_auction_parcels(county_slug: str, updates: List[Dict]) -> int:
    """Update multi_county_auctions with parcel_ids"""
    if not updates:
        return 0
    
    headers = sb_headers()
    updated_count = 0
    
    # Update auctions one by one (could be batched for better performance)
    for update in updates:
        try:
            response = await client.patch(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
                f"?case_number=eq.{update['case_number']}"
                f"&county=eq.{county_slug}",
                headers=headers,
                json={
                    'parcel_id': update['parcel_id'],
                    'updated_at': datetime.now(timezone.utc).isoformat()
                }
            )
            
            if response.status_code in (200, 204):
                updated_count += 1
            else:
                logger.warning(f"⚠️ Failed to update {update['case_number']}: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"⚠️ Error updating {update['case_number']}: {e}")
            continue
    
    logger.info(f"💾 {county_slug}: Updated {updated_count} auction records with parcel_ids")
    return updated_count

async def calculate_letter_e_improvement(county_slug: str) -> Dict:
    """Calculate Letter E improvement after parcel linking"""
    headers = sb_headers()
    
    try:
        # Get total auctions
        total_response = await client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}"
            f"&select=count",
            headers=headers
        )
        
        total_auctions = len(total_response.json()) if total_response.status_code == 200 else 0
        
        # Get linked auctions  
        linked_response = await client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}"
            f"&parcel_id=not.is.null"
            f"&select=count",
            headers=headers
        )
        
        linked_auctions = len(linked_response.json()) if linked_response.status_code == 200 else 0
        
        linkage_pct = (linked_auctions / total_auctions * 100) if total_auctions > 0 else 0
        letter_e_pass = linkage_pct >= 95.0
        
        result = {
            'county': county_slug,
            'total_auctions': total_auctions,
            'linked_auctions': linked_auctions,
            'linkage_pct': linkage_pct,
            'letter_e_pass': letter_e_pass,
            'target_threshold': 95.0
        }
        
        status = "PASS ✅" if letter_e_pass else "FAIL ❌"
        logger.info(f"📈 {county_slug} Letter E: {status} ({linkage_pct:.1f}% linked, {linked_auctions}/{total_auctions})")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error calculating Letter E for {county_slug}: {e}")
        return {'county': county_slug, 'error': str(e)}

async def process_county_parcel_linkage(county_slug: str, limit: int = 100) -> Dict:
    """Process parcel linkage for a single county"""
    logger.info(f"🏔️ PROCESSING PARCEL LINKAGE: {county_slug.upper()}")
    
    start_time = time.time()
    
    # Get unlinked auctions and sample properties in parallel
    unlinked_auctions_task = get_unlinked_auctions(county_slug, limit)
    sample_properties_task = get_sample_properties(county_slug)
    
    unlinked_auctions, address_lookup = await asyncio.gather(
        unlinked_auctions_task, sample_properties_task
    )
    
    if not unlinked_auctions:
        logger.info(f"✅ {county_slug}: No unlinked auctions found")
        return {'county': county_slug, 'status': 'no_work_needed'}
    
    if not address_lookup:
        logger.error(f"❌ {county_slug}: No address lookup data available")
        return {'county': county_slug, 'error': 'no_address_data'}
    
    # Link auctions to parcels
    updates = await link_auction_parcels(county_slug, unlinked_auctions, address_lookup)
    
    # Update database
    updated_count = await update_auction_parcels(county_slug, updates)
    
    elapsed = time.time() - start_time
    
    result = {
        'county': county_slug,
        'unlinked_found': len(unlinked_auctions),
        'parcels_linked': updated_count,
        'elapsed_time': elapsed,
        'status': 'success'
    }
    
    logger.info(f"✅ {county_slug}: Linked {updated_count} parcels in {elapsed:.1f}s")
    return result

async def main():
    """Execute SHARD-6 parcel linkage fixing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SHARD-6 Parcel Linkage Fixer")
    parser.add_argument("--county", type=str, help="Single county to process",
                       choices=list(SHARD6_COUNTIES.keys()))
    parser.add_argument("--limit", type=int, default=100, help="Limit auctions per county")
    parser.add_argument("--dry-run", action="store_true", help="Don't update database")
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    logger.info("🚀 SHARD-6 PARCEL LINKAGE FIXER")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # Determine counties to process
    counties_to_process = [args.county] if args.county else list(SHARD6_COUNTIES.keys())
    
    logger.info(f"🎯 Target counties: {', '.join(counties_to_process)}")
    logger.info(f"📊 Mode: {'DRY RUN' if args.dry_run else 'LIVE LINKING'}")
    
    # Process counties
    results = []
    for county_slug in counties_to_process:
        if not args.dry_run:
            result = await process_county_parcel_linkage(county_slug, limit=args.limit)
            results.append(result)
            
            # Calculate Letter E improvement
            letter_e_result = await calculate_letter_e_improvement(county_slug)
            result['letter_e_metrics'] = letter_e_result
        else:
            logger.info(f"🔍 {county_slug}: DRY RUN - would process up to {args.limit} unlinked auctions")
    
    # Summary
    elapsed_total = time.time() - start_time
    
    logger.info("=" * 60)
    logger.info("SHARD-6 PARCEL LINKAGE COMPLETION REPORT")
    logger.info("=" * 60)
    logger.info(f"⏱️ Total time: {elapsed_total:.1f} seconds")
    
    if not args.dry_run and results:
        total_linked = sum(r.get('parcels_linked', 0) for r in results)
        counties_with_e_pass = sum(1 for r in results 
                                 if r.get('letter_e_metrics', {}).get('letter_e_pass'))
        
        logger.info(f"📊 Counties processed: {len(results)}")
        logger.info(f"🔗 Total parcels linked: {total_linked}")
        logger.info(f"🏆 Counties with Letter E pass: {counties_with_e_pass}/{len(results)}")
        
        # Detail per county
        for result in results:
            county = result['county']
            letter_e = result.get('letter_e_metrics', {})
            pct = letter_e.get('linkage_pct', 0)
            status = "PASS" if letter_e.get('letter_e_pass') else "FAIL"
            linked = result.get('parcels_linked', 0)
            logger.info(f"  {county:12s}: Letter E {status:4s} ({pct:5.1f}%, +{linked} linked)")
    
    await client.aclose()
    logger.info("✅ SHARD-6 parcel linkage fixer completed")

if __name__ == "__main__":
    asyncio.run(main())