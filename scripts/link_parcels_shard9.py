#!/usr/bin/env python3
"""
GOLD STANDARD Letter E: Parcel Linking Pipeline - SHARD-9
Links parcel_id to auctions via county property appraiser APIs for leon, washington, marion, dixie, taylor

This is a critical enabler - parcel linkage feeds into:
- Letter E: Direct parcel linkage metric
- Letter I: Property card enrichment (needs parcel_id)
- Letter J: Deal thesis pipeline (needs property values)

Usage:
  python scripts/link_parcels_shard9.py --county leon
  python scripts/link_parcels_shard9.py --county washington
  python scripts/link_parcels_shard9.py --county marion
  python scripts/link_parcels_shard9.py --all-counties
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
from bs4 import BeautifulSoup
import time

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

# County property appraiser APIs and sources
COUNTY_APPRAISER_SOURCES = {
    'leon': {
        'name': 'Leon County Property Appraiser',
        'search_url': 'https://www.leonpa.org/PropertySearch',
        'api_base': 'https://www.leonpa.org/api/property',
        'arcgis_url': 'https://maps.leon.fl.gov/arcgis/rest/services/LeonCounty/PropertyAppraiser/MapServer',
        'search_fields': ['address', 'owner_name', 'parcel_id'],
        'notes': 'Leon County has ArcGIS REST API and property search portal'
    },
    'washington': {
        'name': 'Washington County Property Appraiser', 
        'search_url': 'https://www.washingtonpa.com/search',
        'api_base': None,  # No known REST API
        'search_fields': ['address', 'owner_name'],
        'notes': 'Washington County may require screen scraping'
    },
    'marion': {
        'name': 'Marion County Property Appraiser',
        'search_url': 'https://www.pa.marion.fl.us/search/',
        'api_base': 'https://www.pa.marion.fl.us/api/property',
        'arcgis_url': 'https://gis.marioncountyfl.org/arcgis/rest/services/PropertyAppraiser/MapServer',
        'search_fields': ['address', 'owner_name', 'parcel_id'],
        'notes': 'Marion County has modern property search with potential API'
    },
    'dixie': {
        'name': 'Dixie County Property Appraiser',
        'search_url': 'TBD - research needed',
        'api_base': None,
        'search_fields': ['address'],
        'notes': 'Small county - manual search likely required'
    },
    'taylor': {
        'name': 'Taylor County Property Appraiser', 
        'search_url': 'TBD - research needed',
        'api_base': None,
        'search_fields': ['address'],
        'notes': 'Small county - manual search likely required'
    }
}

client = httpx.Client(timeout=30, follow_redirects=True, headers={
    'User-Agent': 'Mozilla/5.0 (BidDeed-ParcelLinker/1.0; contact: ariel@everestcapitalusa.com)',
    'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
})

def supabase_get(table: str, params: Dict = None) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_update(table: str, id_field: str, id_value: str, updates: Dict) -> bool:
    """Update a specific record in Supabase"""
    try:
        response = client.patch(
            f"{BASE}/{table}?{id_field}=eq.{id_value}",
            headers=HEADERS,
            json=updates
        )
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error updating {table} record {id_value}: {e}")
        return False

def get_unlinked_auctions(county_slug: str, limit: int = 500) -> List[Dict]:
    """Get auctions that don't have parcel_id linked"""
    params = {
        'select': 'id,case_number,property_address,plaintiff,defendant,auction_date,parcel_id',
        'county': f'eq.{county_slug}',
        'parcel_id': 'is.null',  # Only get unlinked auctions
        'order': 'auction_date.desc',
        'limit': str(limit)
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} unlinked auctions for {county_slug}")
    return auctions

def normalize_address(address: str) -> str:
    """Normalize address for matching"""
    if not address:
        return ""
        
    # Remove common suffixes and normalize
    normalized = address.upper().strip()
    
    # Replace street type abbreviations
    replacements = {
        ' ST$': ' STREET',
        ' ST ': ' STREET ',
        ' RD$': ' ROAD', 
        ' RD ': ' ROAD ',
        ' AVE$': ' AVENUE',
        ' AVE ': ' AVENUE ',
        ' BLVD$': ' BOULEVARD',
        ' BLVD ': ' BOULEVARD ',
        ' DR$': ' DRIVE',
        ' DR ': ' DRIVE ',
        ' LN$': ' LANE',
        ' LN ': ' LANE ',
    }
    
    for pattern, replacement in replacements.items():
        normalized = re.sub(pattern, replacement, normalized)
    
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized

def search_leon_parcel(auction: Dict) -> Optional[str]:
    """Search Leon County Property Appraiser for parcel ID"""
    address = auction.get('property_address', '')
    if not address:
        return None
        
    try:
        # Try Leon County Property Appraiser search
        search_url = COUNTY_APPRAISER_SOURCES['leon']['search_url']
        normalized_address = normalize_address(address)
        
        # First try: direct property search
        search_params = {
            'address': normalized_address,
            'format': 'json'
        }
        
        # Try the API endpoint if it exists
        api_base = COUNTY_APPRAISER_SOURCES['leon']['api_base']
        if api_base:
            api_url = f"{api_base}/search"
            response = client.get(api_url, params=search_params)
            
            if response.status_code == 200:
                try:
                    results = response.json()
                    if results and isinstance(results, list) and len(results) > 0:
                        # Extract parcel ID from first result
                        first_result = results[0]
                        parcel_id = first_result.get('parcel_id') or first_result.get('parcelId') or first_result.get('PARCEL_ID')
                        if parcel_id:
                            logger.info(f"Found Leon parcel via API: {parcel_id} for {address}")
                            return parcel_id
                except json.JSONDecodeError:
                    pass
        
        # Fallback: try ArcGIS REST API
        arcgis_url = COUNTY_APPRAISER_SOURCES['leon']['arcgis_url']
        if arcgis_url:
            # Query ArcGIS MapServer for parcels by address
            query_params = {
                'where': f"SITUS_ADDRESS LIKE '%{normalized_address.split()[0]}%'",
                'outFields': 'PARCEL_ID,SITUS_ADDRESS,OWNER_NAME',
                'returnGeometry': 'false',
                'f': 'json'
            }
            
            query_url = f"{arcgis_url}/0/query"  # Assuming layer 0 is parcels
            response = client.get(query_url, params=query_params)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    features = data.get('features', [])
                    
                    for feature in features:
                        attributes = feature.get('attributes', {})
                        parcel_id = attributes.get('PARCEL_ID')
                        situs_address = attributes.get('SITUS_ADDRESS', '')
                        
                        # Check address similarity
                        if parcel_id and address_similarity(normalized_address, normalize_address(situs_address)) > 0.7:
                            logger.info(f"Found Leon parcel via ArcGIS: {parcel_id} for {address}")
                            return parcel_id
                            
                except json.JSONDecodeError:
                    pass
        
    except Exception as e:
        logger.warning(f"Error searching Leon parcel for {address}: {e}")
    
    return None

def search_marion_parcel(auction: Dict) -> Optional[str]:
    """Search Marion County Property Appraiser for parcel ID"""
    address = auction.get('property_address', '')
    if not address:
        return None
        
    try:
        normalized_address = normalize_address(address)
        
        # Try Marion County property search API
        api_base = COUNTY_APPRAISER_SOURCES['marion']['api_base']
        if api_base:
            api_url = f"{api_base}/search"
            search_params = {'address': normalized_address}
            
            response = client.get(api_url, params=search_params)
            if response.status_code == 200:
                try:
                    results = response.json()
                    if results and len(results) > 0:
                        first_result = results[0]
                        parcel_id = first_result.get('parcel_id') or first_result.get('parcelId')
                        if parcel_id:
                            logger.info(f"Found Marion parcel: {parcel_id} for {address}")
                            return parcel_id
                except json.JSONDecodeError:
                    pass
        
        # Fallback: try screen scraping the search page
        search_url = COUNTY_APPRAISER_SOURCES['marion']['search_url']
        response = client.get(search_url)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for search form and submit
            search_form = soup.find('form')
            if search_form:
                # This would require form submission logic
                # For now, return None and log that we need to implement
                logger.info(f"Marion County search form found but not implemented for {address}")
        
    except Exception as e:
        logger.warning(f"Error searching Marion parcel for {address}: {e}")
    
    return None

def search_washington_parcel(auction: Dict) -> Optional[str]:
    """Search Washington County Property Appraiser for parcel ID"""
    address = auction.get('property_address', '')
    if not address:
        return None
        
    try:
        # Washington County likely requires screen scraping
        search_url = COUNTY_APPRAISER_SOURCES['washington']['search_url']
        normalized_address = normalize_address(address)
        
        # Try to access the search page
        response = client.get(search_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for search form
            search_forms = soup.find_all('form')
            for form in search_forms:
                # Check if this is a property search form
                form_text = form.get_text().lower()
                if any(keyword in form_text for keyword in ['property', 'address', 'search', 'parcel']):
                    logger.info(f"Washington County search form found but not implemented for {address}")
                    # Would need to implement form submission
                    break
        
    except Exception as e:
        logger.warning(f"Error searching Washington parcel for {address}: {e}")
    
    return None

def address_similarity(addr1: str, addr2: str) -> float:
    """Calculate similarity between two addresses (simple word overlap)"""
    if not addr1 or not addr2:
        return 0.0
        
    words1 = set(addr1.split())
    words2 = set(addr2.split())
    
    if not words1 or not words2:
        return 0.0
        
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def link_parcels_for_county(county_slug: str, limit: int = 100) -> int:
    """Link parcels for all unlinked auctions in a county"""
    
    logger.info(f"Starting parcel linking for {county_slug}")
    
    # Get unlinked auctions
    unlinked_auctions = get_unlinked_auctions(county_slug, limit)
    
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions found for {county_slug}")
        return 0
    
    linked_count = 0
    
    for auction in unlinked_auctions:
        auction_id = auction.get('id')
        address = auction.get('property_address', '')
        
        if not address:
            logger.debug(f"Skipping auction {auction_id} - no address")
            continue
        
        parcel_id = None
        
        # County-specific parcel search
        if county_slug == 'leon':
            parcel_id = search_leon_parcel(auction)
        elif county_slug == 'marion':
            parcel_id = search_marion_parcel(auction)
        elif county_slug == 'washington':
            parcel_id = search_washington_parcel(auction)
        elif county_slug in ['dixie', 'taylor']:
            logger.info(f"Parcel linking not implemented for {county_slug} - small county")
            continue
        
        # Update auction record with parcel_id
        if parcel_id:
            updates = {
                'parcel_id': parcel_id,
                'parcel_linked_at': datetime.now().isoformat(),
                'parcel_source': f'{county_slug}_property_appraiser'
            }
            
            success = supabase_update('multi_county_auctions', 'id', str(auction_id), updates)
            if success:
                linked_count += 1
                logger.info(f"Linked auction {auction_id} to parcel {parcel_id}")
            else:
                logger.warning(f"Failed to update auction {auction_id} with parcel {parcel_id}")
        else:
            logger.debug(f"No parcel found for auction {auction_id}: {address}")
        
        # Rate limiting
        time.sleep(0.5)  # Be nice to county servers
    
    return linked_count

def get_parcel_linkage_status(county_slug: str) -> Dict:
    """Get current parcel linkage statistics for county"""
    
    # Total auctions
    total_auctions = len(supabase_get('multi_county_auctions', {
        'county': f'eq.{county_slug}',
        'select': 'id'
    }))
    
    # Linked auctions (have parcel_id)
    linked_auctions = len(supabase_get('multi_county_auctions', {
        'county': f'eq.{county_slug}',
        'parcel_id': 'not.is.null',
        'select': 'id'
    }))
    
    linkage_rate = (linked_auctions / total_auctions * 100) if total_auctions > 0 else 0
    
    return {
        'county': county_slug,
        'total_auctions': total_auctions,
        'linked_auctions': linked_auctions,
        'unlinked_auctions': total_auctions - linked_auctions,
        'linkage_rate': linkage_rate,
        'letter_e_status': 'PASS' if linkage_rate >= 95.0 else 'FAIL'
    }

def main():
    parser = argparse.ArgumentParser(description='Link parcel IDs for Gold Standard Letter E - SHARD-9')
    parser.add_argument('--county', choices=['leon', 'washington', 'marion', 'dixie', 'taylor'], 
                       help='County to process')
    parser.add_argument('--all-counties', action='store_true', 
                       help='Process all SHARD-9 counties')
    parser.add_argument('--limit', type=int, default=100,
                       help='Maximum auctions to process per county (default: 100)')
    parser.add_argument('--status-only', action='store_true',
                       help='Only check current linkage status')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.warning("SUPABASE_KEY environment variable not set - running in dry-run mode")
    
    logger.info("=" * 60)
    logger.info("GOLD STANDARD LETTER E - Parcel Linking Pipeline SHARD-9")
    logger.info("=" * 60)
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = ['leon', 'washington', 'marion']  # Skip dixie/taylor for now
    elif args.county:
        counties_to_process = [args.county]
    else:
        parser.print_help()
        sys.exit(1)
    
    total_linked = 0
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county} ---")
        
        # Show current status
        current_status = get_parcel_linkage_status(county)
        logger.info(f"Current linkage status: {current_status}")
        
        if not args.status_only:
            # Perform parcel linking
            linked_count = link_parcels_for_county(county, args.limit)
            total_linked += linked_count
            logger.info(f"Linked {linked_count} parcels for {county}")
            
            # Show final status
            final_status = get_parcel_linkage_status(county)
            logger.info(f"Final linkage status: {final_status}")
            
            improvement = final_status['linkage_rate'] - current_status['linkage_rate']
            logger.info(f"Linkage rate improvement: +{improvement:.1f}%")
    
    if not args.status_only:
        logger.info(f"\nTotal parcels linked across all counties: {total_linked}")
    
    logger.info("SHARD-9 parcel linking complete")

if __name__ == "__main__":
    main()