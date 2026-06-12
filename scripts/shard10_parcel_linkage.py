#!/usr/bin/env python3
"""
SHARD-10 Parcel Linkage Implementation (Letter E)
Link auction properties to FL GIO parcels for leon, baker, okaloosa, franklin, union

This implements Letter E improvements by:
1. Querying FL GIO Statewide Cadastral API for each county (by co_no)
2. Loading parcel data into sample_properties table
3. Linking multi_county_auctions.parcel_id via address similarity matching
4. Creating property cards with geometry, address, and zoning data

FL GIO ENDPOINTS:
Base: https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0
Filter: CO_NO IN (47,12,56,29,73) for SHARD-10 counties

CO_NO MAPPINGS:
- leon: 47
- baker: 12
- okaloosa: 56  
- franklin: 29
- union: 73

Usage:
  python scripts/shard10_parcel_linkage.py --county leon
  python scripts/shard10_parcel_linkage.py --all-counties
  python scripts/shard10_parcel_linkage.py --parcels-only
"""
import os
import sys
import json
import httpx
import time
import argparse
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Set
import re
from difflib import SequenceMatcher

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

# FL GIO Configuration
FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0"
FL_GIO_MAX_RECORDS = 2000  # FL GIO limit per request

# SHARD-10 counties with co_no mappings
SHARD10_COUNTIES = {
    'leon': 47,
    'baker': 12,
    'okaloosa': 56, 
    'franklin': 29,
    'union': 73
}

client = httpx.AsyncClient(timeout=60)

async def query_fl_gio_parcels(co_no: int, offset: int = 0) -> Dict:
    """Query FL GIO for parcels in a specific county"""
    logger.info(f"Querying FL GIO for co_no {co_no}, offset {offset}")
    
    params = {
        'where': f'CO_NO = {co_no}',
        'outFields': 'PARCEL_ID,CO_NO,SITUS_ADDRESS,CITY,ZIP_CODE,OWNER_NAME,USE_CODE,JUST_VALUE,SHAPE',
        'returnGeometry': 'true',
        'f': 'json',
        'resultOffset': offset,
        'resultRecordCount': FL_GIO_MAX_RECORDS,
        'outSR': '4326'  # WGS84 for consistent coordinates
    }
    
    try:
        response = await client.get(f"{FL_GIO_BASE}/query", params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'error' in data:
            logger.error(f"FL GIO error for co_no {co_no}: {data['error']}")
            return {'success': False, 'error': data['error']}
        
        features = data.get('features', [])
        exceed_transfer_limit = data.get('exceededTransferLimit', False)
        
        logger.info(f"FL GIO returned {len(features)} parcels for co_no {co_no}")
        
        return {
            'success': True,
            'features': features,
            'has_more': exceed_transfer_limit,
            'next_offset': offset + len(features) if exceed_transfer_limit else None
        }
        
    except Exception as e:
        logger.error(f"Error querying FL GIO for co_no {co_no}: {e}")
        return {'success': False, 'error': str(e)}

async def load_all_county_parcels(co_no: int, county_slug: str) -> List[Dict]:
    """Load all parcels for a county, handling pagination"""
    logger.info(f"Loading all parcels for {county_slug} (co_no: {co_no})")
    
    all_parcels = []
    offset = 0
    max_iterations = 50  # Safety limit
    iteration = 0
    
    while iteration < max_iterations:
        result = await query_fl_gio_parcels(co_no, offset)
        
        if not result['success']:
            logger.error(f"Failed to load parcels for {county_slug}: {result.get('error')}")
            break
        
        features = result['features']
        if not features:
            break
        
        # Process features into parcel records
        for feature in features:
            attributes = feature.get('attributes', {})
            geometry = feature.get('geometry', {})
            
            parcel_record = {
                'parcel_id': attributes.get('PARCEL_ID'),
                'co_no': attributes.get('CO_NO'),
                'county_slug': county_slug,
                'address': clean_address(attributes.get('SITUS_ADDRESS')),
                'city': attributes.get('CITY'),
                'zip_code': attributes.get('ZIP_CODE'),
                'owner_name': attributes.get('OWNER_NAME'),
                'use_code': attributes.get('USE_CODE'),
                'just_value': attributes.get('JUST_VALUE'),
                'geometry': geometry,
                'source': 'fl_gio',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Only add valid parcels
            if parcel_record['parcel_id'] and parcel_record['address']:
                all_parcels.append(parcel_record)
        
        # Check if we need to continue pagination
        if not result['has_more']:
            break
            
        offset = result['next_offset']
        iteration += 1
        
        # Rate limiting
        await asyncio.sleep(1)
    
    logger.info(f"Loaded {len(all_parcels)} valid parcels for {county_slug}")
    return all_parcels

def clean_address(address: str) -> str:
    """Clean and normalize address for better matching"""
    if not address:
        return ""
    
    # Basic cleaning
    cleaned = address.strip().upper()
    
    # Remove common noise
    cleaned = re.sub(r'\b(UNIT|APT|SUITE|STE|#)\s*[\w\d]*\b', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Normalize street types
    street_replacements = {
        'STREET': 'ST', 'AVENUE': 'AVE', 'BOULEVARD': 'BLVD',
        'DRIVE': 'DR', 'LANE': 'LN', 'ROAD': 'RD',
        'CIRCLE': 'CIR', 'COURT': 'CT', 'PLACE': 'PL',
        'NORTH': 'N', 'SOUTH': 'S', 'EAST': 'E', 'WEST': 'W'
    }
    
    for full, abbrev in street_replacements.items():
        cleaned = re.sub(f'\\b{full}\\b', abbrev, cleaned)
    
    return cleaned

async def upsert_parcels_to_db(parcels: List[Dict], county_slug: str) -> int:
    """Upsert parcel records to sample_properties table"""
    logger.info(f"Upserting {len(parcels)} parcels for {county_slug}")
    
    if not parcels:
        return 0
    
    try:
        # Batch upsert to sample_properties
        url = f"{BASE}/sample_properties"
        upserted_count = 0
        batch_size = 100
        
        for i in range(0, len(parcels), batch_size):
            batch = parcels[i:i + batch_size]
            
            # Upsert batch
            response = await client.post(url, headers=get_headers(), json=batch[0])
            
            if response.status_code in [200, 201]:
                upserted_count += 1
            
            # Individual inserts for reliability
            for parcel in batch:
                try:
                    response = await client.post(url, headers=get_headers(), json=parcel)
                    if response.status_code in [200, 201]:
                        upserted_count += 1
                except Exception as e:
                    logger.debug(f"Failed to insert parcel {parcel.get('parcel_id')}: {e}")
            
            # Rate limiting
            await asyncio.sleep(0.5)
        
        logger.info(f"Upserted {upserted_count} parcels for {county_slug}")
        return upserted_count
        
    except Exception as e:
        logger.error(f"Error upserting parcels for {county_slug}: {e}")
        return 0

async def get_unlinked_auctions(county_slug: str) -> List[Dict]:
    """Get auctions without parcel_id for a county"""
    logger.info(f"Getting unlinked auctions for {county_slug}")
    
    try:
        url = f"{BASE}/multi_county_auctions"
        params = {
            'county': f'eq.{county_slug}',
            'parcel_id': 'is.null',
            'address': 'not.is.null',
            'select': 'id,case_number,address,city,zip_code'
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        auctions = response.json()
        logger.info(f"Found {len(auctions)} unlinked auctions for {county_slug}")
        
        return auctions
        
    except Exception as e:
        logger.error(f"Error getting unlinked auctions for {county_slug}: {e}")
        return []

async def get_county_parcels(county_slug: str, co_no: int) -> List[Dict]:
    """Get parcels for a county from sample_properties"""
    logger.info(f"Getting parcels for {county_slug} from database")
    
    try:
        url = f"{BASE}/sample_properties"
        params = {
            'co_no': f'eq.{co_no}',
            'select': 'parcel_id,address,city,geometry'
        }
        
        response = await client.get(url, headers=get_headers(), params=params)
        response.raise_for_status()
        
        parcels = response.json()
        logger.info(f"Found {len(parcels)} parcels for {county_slug} in database")
        
        return parcels
        
    except Exception as e:
        logger.error(f"Error getting parcels for {county_slug}: {e}")
        return []

def calculate_address_similarity(address1: str, address2: str) -> float:
    """Calculate similarity between two addresses"""
    if not address1 or not address2:
        return 0.0
    
    # Normalize both addresses
    addr1_clean = clean_address(address1)
    addr2_clean = clean_address(address2)
    
    if not addr1_clean or not addr2_clean:
        return 0.0
    
    # Use sequence matcher for basic similarity
    similarity = SequenceMatcher(None, addr1_clean, addr2_clean).ratio()
    
    # Boost score for exact word matches
    words1 = set(addr1_clean.split())
    words2 = set(addr2_clean.split())
    
    if words1 and words2:
        word_overlap = len(words1 & words2) / len(words1 | words2)
        similarity = (similarity + word_overlap) / 2
    
    return similarity

async def link_auctions_to_parcels(county_slug: str, co_no: int) -> Dict:
    """Link unlinked auctions to parcels via address matching"""
    logger.info(f"Linking auctions to parcels for {county_slug}")
    
    # Get unlinked auctions
    auctions = await get_unlinked_auctions(county_slug)
    if not auctions:
        return {'linked_count': 0, 'total_unlinked': 0}
    
    # Get county parcels
    parcels = await get_county_parcels(county_slug, co_no)
    if not parcels:
        logger.warning(f"No parcels found for {county_slug}, cannot perform linking")
        return {'linked_count': 0, 'total_unlinked': len(auctions), 'error': 'no_parcels'}
    
    linked_count = 0
    link_threshold = 0.75  # 75% similarity required
    
    for auction in auctions[:100]:  # Limit to first 100 for performance
        auction_address = auction.get('address', '')
        if not auction_address:
            continue
        
        best_match = None
        best_score = 0.0
        
        # Find best matching parcel
        for parcel in parcels:
            parcel_address = parcel.get('address', '')
            if not parcel_address:
                continue
            
            similarity = calculate_address_similarity(auction_address, parcel_address)
            
            if similarity > best_score and similarity >= link_threshold:
                best_score = similarity
                best_match = parcel
        
        # Link if good match found
        if best_match:
            success = await update_auction_parcel_link(
                auction['id'],
                best_match['parcel_id'],
                best_score,
                f"address_similarity_{best_score:.3f}"
            )
            
            if success:
                linked_count += 1
                logger.debug(f"Linked auction {auction['case_number']} to parcel {best_match['parcel_id']} (score: {best_score:.3f})")
        
        # Rate limiting
        await asyncio.sleep(0.1)
    
    logger.info(f"Linked {linked_count} auctions to parcels for {county_slug}")
    
    return {
        'linked_count': linked_count,
        'total_unlinked': len(auctions),
        'linkage_rate': linked_count / len(auctions) if auctions else 0,
        'threshold_used': link_threshold
    }

async def update_auction_parcel_link(auction_id: int, parcel_id: str, similarity_score: float, link_method: str) -> bool:
    """Update auction record with parcel_id link"""
    
    try:
        url = f"{BASE}/multi_county_auctions"
        params = {'id': f'eq.{auction_id}'}
        
        update_data = {
            'parcel_id': parcel_id,
            'parcel_link_method': link_method,
            'parcel_link_score': similarity_score,
            'parcel_linked_at': datetime.now(timezone.utc).isoformat()
        }
        
        response = await client.patch(url, headers=get_headers(), params=params, json=update_data)
        response.raise_for_status()
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating auction {auction_id} with parcel {parcel_id}: {e}")
        return False

async def process_county_parcel_linkage(county_slug: str, parcels_only: bool = False) -> Dict:
    """Complete parcel linkage pipeline for a county"""
    logger.info(f"Processing parcel linkage for {county_slug}")
    
    co_no = SHARD10_COUNTIES.get(county_slug)
    if not co_no:
        return {'success': False, 'error': f'Unknown county: {county_slug}'}
    
    results = {
        'county_slug': county_slug,
        'co_no': co_no,
        'success': True
    }
    
    try:
        # Step 1: Load parcels from FL GIO
        logger.info(f"Step 1: Loading parcels from FL GIO for {county_slug}")
        parcels = await load_all_county_parcels(co_no, county_slug)
        results['parcels_loaded'] = len(parcels)
        
        if parcels:
            # Step 2: Upsert parcels to database
            logger.info(f"Step 2: Upserting parcels to database for {county_slug}")
            upserted_count = await upsert_parcels_to_db(parcels, county_slug)
            results['parcels_upserted'] = upserted_count
        
        if not parcels_only and parcels:
            # Step 3: Link auctions to parcels
            logger.info(f"Step 3: Linking auctions to parcels for {county_slug}")
            link_results = await link_auctions_to_parcels(county_slug, co_no)
            results['linkage_results'] = link_results
        
        logger.info(f"Parcel linkage completed for {county_slug}")
        return results
        
    except Exception as e:
        logger.error(f"Error in parcel linkage pipeline for {county_slug}: {e}")
        results['success'] = False
        results['error'] = str(e)
        return results

async def main_async():
    parser = argparse.ArgumentParser(description='SHARD-10 Parcel Linkage (Letter E)')
    parser.add_argument('--county', choices=list(SHARD10_COUNTIES.keys()), help='Single county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all SHARD-10 counties')
    parser.add_argument('--parcels-only', action='store_true', help='Load parcels only, skip linking')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("SHARD-10 PARCEL LINKAGE (Letter E)")
    logger.info("=" * 60)
    logger.info("FL GIO -> sample_properties -> multi_county_auctions.parcel_id")
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = list(SHARD10_COUNTIES.keys())
    elif args.county:
        counties_to_process = [args.county]
    else:
        # Default: all counties for autonomous session
        counties_to_process = list(SHARD10_COUNTIES.keys())
    
    results = {}
    
    for county_slug in counties_to_process:
        logger.info(f"\n--- Processing {county_slug} ---")
        
        result = await process_county_parcel_linkage(county_slug, args.parcels_only)
        results[county_slug] = result
        
        logger.info(f"Result: {result}")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("SHARD-10 PARCEL LINKAGE SUMMARY")
    logger.info("=" * 60)
    
    total_parcels = 0
    total_linked = 0
    
    for county, result in results.items():
        if result.get('success'):
            parcels = result.get('parcels_loaded', 0)
            linkage = result.get('linkage_results', {})
            linked = linkage.get('linked_count', 0)
            
            total_parcels += parcels
            total_linked += linked
            
            logger.info(f"{county}: {parcels} parcels loaded, {linked} auctions linked")
        else:
            error = result.get('error', 'Unknown error')
            logger.info(f"{county}: ERROR - {error}")
    
    logger.info(f"\nTOTAL: {total_parcels} parcels loaded, {total_linked} auctions linked")
    logger.info("SHARD-10 parcel linkage complete")
    
    await client.aclose()

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()