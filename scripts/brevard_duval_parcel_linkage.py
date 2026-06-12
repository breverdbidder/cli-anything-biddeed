#!/usr/bin/env python3
"""
BREVARD & DUVAL Parcel Linkage (E-lane) Implementation
Fix Letter E failures: brevard 78.5% -> 95%, duval 83.4% -> 95%

Strategy:
- Brevard: Use BCPAO pipeline + ArcGIS discovery
- Duval: Use maps.coj.net ArcGIS FeatureServer + address matching
- Batch processing with rate limiting for API protection
"""

import os
import sys
import json
import httpx
import logging
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# County-specific endpoints from CLAUDE.md 
APPRAISER_ENDPOINTS = {
    'brevard': {
        'arcgis_base': 'https://maps.brevardcounty.us/arcgis/rest/services',
        'bcpao_api': 'https://www.bcpao.us/api/v1/account',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN', 'ACCOUNT_NO'],
        'property_service': None  # To be discovered
    },
    'duval': {
        'arcgis_base': 'https://maps.coj.net/arcgis/rest/services',
        'property_search': 'https://paopropertysearch.coj.net',
        'search_fields': ['PARCEL_ID', 'RE_PARCEL_ID', 'PIN'],
        'property_service': None  # To be discovered
    }
}

# Rate limiting
RATE_LIMIT_DELAY = 0.5  # Seconds between requests

client = httpx.AsyncClient(timeout=30)

async def discover_property_layer(county: str) -> Optional[str]:
    """Discover the property/parcel layer for county's ArcGIS service"""
    config = APPRAISER_ENDPOINTS.get(county, {})
    base_url = config.get('arcgis_base')
    
    if not base_url:
        logger.warning(f"No ArcGIS base URL configured for {county}")
        return None
    
    try:
        logger.info(f"Discovering property layer for {county}...")
        
        # Get list of services
        services_url = f"{base_url}?f=json"
        response = await client.get(services_url)
        
        if response.status_code != 200:
            logger.error(f"Failed to get services for {county}: {response.status_code}")
            return None
            
        services_data = response.json()
        
        # Look for property/parcel related services
        property_keywords = ['property', 'parcel', 'cadastral', 'ownership', 'appraiser', 'tax']
        
        candidates = []
        
        for service in services_data.get('services', []):
            service_name = service.get('name', '').lower()
            service_type = service.get('type', '')
            
            if service_type == 'MapServer':
                for keyword in property_keywords:
                    if keyword in service_name:
                        service_url = f"{base_url}/{service['name']}/MapServer"
                        candidates.append((service_url, service_name))
                        break
        
        # Test candidates
        for service_url, service_name in candidates:
            try:
                test_response = await client.get(f"{service_url}?f=json")
                if test_response.status_code == 200:
                    service_info = test_response.json()
                    
                    # Check if it has layers
                    layers = service_info.get('layers', [])
                    if layers:
                        logger.info(f"✅ Found property service for {county}: {service_name}")
                        
                        # Save the configuration
                        config['property_service'] = service_url
                        return service_url
                        
            except Exception as e:
                logger.debug(f"Service test failed for {service_name}: {e}")
                continue
        
        logger.warning(f"No working property layer found for {county}")
        return None
        
    except Exception as e:
        logger.error(f"Error discovering property layer for {county}: {e}")
        return None

async def get_unlinked_auctions(county: str, limit: int = 1000) -> List[Dict]:
    """Get auction properties that need parcel_id linking"""
    
    params = {
        'county_slug': f'eq.{county}',
        'parcel_id': 'is.null',
        'limit': limit,
        'select': 'id,address,case_number,county_slug,sale_date,property_address'
    }
    
    try:
        response = await client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            properties = response.json()
            logger.info(f"Found {len(properties)} unlinked auctions in {county}")
            return properties
        else:
            logger.error(f"Failed to get unlinked auctions for {county}: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting unlinked auctions for {county}: {e}")
        return []

async def search_parcel_brevard(address: str, case_number: str) -> Optional[str]:
    """Search for Brevard parcel using BCPAO pipeline and ArcGIS"""
    
    # Strategy 1: Try BCPAO if we have an account number from case_number
    account_pattern = re.compile(r'\b\d{7,10}\b')  # Account numbers are typically 7-10 digits
    account_match = account_pattern.search(case_number or '')
    
    if account_match:
        account_number = account_match.group()
        try:
            # Note: In production this would use Firecrawl due to Cloudflare challenges
            # For now, we'll skip BCPAO API and go directly to ArcGIS
            logger.debug(f"Found potential account number: {account_number}")
        except Exception as e:
            logger.debug(f"BCPAO lookup failed: {e}")
    
    # Strategy 2: ArcGIS address search
    config = APPRAISER_ENDPOINTS['brevard']
    property_service = config.get('property_service')
    
    if not property_service:
        logger.warning("No property service URL available for Brevard")
        return None
    
    try:
        # Clean address for search
        clean_address = re.sub(r'[^\w\s]', '', address).strip().upper()
        
        # Try multiple query patterns
        query_variants = [
            f"UPPER(PROPERTY_ADDRESS) LIKE '%{clean_address}%'",
            f"UPPER(SITUS_ADDRESS) LIKE '%{clean_address}%'",
        ]
        
        for variant in query_variants:
            query_url = f"{property_service}/0/query"  # Layer 0 is typically parcels
            
            params = {
                'where': variant,
                'outFields': '*', 
                'returnGeometry': 'false',
                'f': 'json',
                'resultRecordCount': 5
            }
            
            response = await client.get(query_url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                features = result.get('features', [])
                
                if features:
                    # Extract parcel ID from first match
                    attributes = features[0].get('attributes', {})
                    
                    for field_name in config['search_fields']:
                        parcel_id = attributes.get(field_name)
                        if parcel_id:
                            logger.info(f"✅ Found Brevard parcel {parcel_id} for address {address}")
                            return str(parcel_id)
            
            await asyncio.sleep(RATE_LIMIT_DELAY)
    
    except Exception as e:
        logger.debug(f"Brevard parcel search failed for {address}: {e}")
    
    return None

async def search_parcel_duval(address: str, case_number: str) -> Optional[str]:
    """Search for Duval parcel using maps.coj.net ArcGIS services"""
    
    config = APPRAISER_ENDPOINTS['duval']
    property_service = config.get('property_service')
    
    if not property_service:
        logger.warning("No property service URL available for Duval")
        return None
    
    try:
        # Clean address for search
        clean_address = re.sub(r'[^\w\s]', '', address).strip().upper()
        
        # Duval-specific address normalization
        clean_address = clean_address.replace(' JACKSONVILLE', '').replace(' JAX', '').strip()
        
        # Try different field patterns for Duval
        query_variants = [
            f"UPPER(PROPERTY_ADDRESS) LIKE '%{clean_address}%'",
            f"UPPER(SITE_ADDRESS) LIKE '%{clean_address}%'",
            f"UPPER(SITUS_ADDR) LIKE '%{clean_address}%'",
        ]
        
        for variant in query_variants:
            query_url = f"{property_service}/0/query"  # Assuming layer 0
            
            params = {
                'where': variant,
                'outFields': '*',
                'returnGeometry': 'false', 
                'f': 'json',
                'resultRecordCount': 5
            }
            
            response = await client.get(query_url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                features = result.get('features', [])
                
                if features:
                    # Extract parcel ID from first match
                    attributes = features[0].get('attributes', {})
                    
                    for field_name in config['search_fields']:
                        parcel_id = attributes.get(field_name)
                        if parcel_id:
                            logger.info(f"✅ Found Duval parcel {parcel_id} for address {address}")
                            return str(parcel_id)
            
            await asyncio.sleep(RATE_LIMIT_DELAY)
    
    except Exception as e:
        logger.debug(f"Duval parcel search failed for {address}: {e}")
    
    return None

async def update_auction_parcel_link(auction_id: int, parcel_id: str) -> bool:
    """Update multi_county_auctions with discovered parcel_id"""
    
    try:
        # Update the auction with the parcel_id
        update_data = {'parcel_id': parcel_id}
        params = {'id': f'eq.{auction_id}'}
        
        response = await client.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params=params,
            json=update_data
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ Linked auction {auction_id} to parcel {parcel_id}")
            return True
        else:
            logger.error(f"❌ Failed to link auction {auction_id}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error linking auction {auction_id}: {e}")
        return False

async def process_county_linkage(county: str, max_auctions: int = 500) -> Dict:
    """Process parcel linkage for a specific county"""
    logger.info(f"Starting parcel linkage for {county}...")
    
    results = {
        'county': county,
        'processed': 0,
        'linked': 0,
        'failed': 0,
        'errors': [],
        'start_time': datetime.now(timezone.utc).isoformat()
    }
    
    # Discover the property layer first
    property_service = await discover_property_layer(county)
    if not property_service:
        results['errors'].append(f"Could not discover property service for {county}")
        return results
    
    # Get unlinked auctions
    unlinked_auctions = await get_unlinked_auctions(county, max_auctions)
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions found for {county}")
        return results
    
    results['processed'] = len(unlinked_auctions)
    
    # Choose search function based on county
    search_function = search_parcel_brevard if county == 'brevard' else search_parcel_duval
    
    # Process each auction
    for auction in unlinked_auctions:
        address = auction.get('address') or auction.get('property_address', '')
        case_number = auction.get('case_number', '')
        auction_id = auction.get('id')
        
        if not address or not auction_id:
            results['failed'] += 1
            continue
        
        # Search for parcel
        parcel_id = await search_function(address, case_number)
        
        if parcel_id:
            # Update the auction
            success = await update_auction_parcel_link(auction_id, parcel_id)
            if success:
                results['linked'] += 1
            else:
                results['failed'] += 1
        else:
            results['failed'] += 1
        
        # Rate limiting between auctions
        await asyncio.sleep(RATE_LIMIT_DELAY)
    
    results['end_time'] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"✅ Completed {county}: {results['linked']} linked, {results['failed']} failed")
    return results

async def run_brevard_duval_linkage():
    """Run parcel linkage for both assigned counties"""
    logger.info("Starting BREVARD & DUVAL parcel linkage campaign...")
    
    target_counties = ['brevard', 'duval']
    all_results = {}
    
    for county in target_counties:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {county.upper()} County")
        logger.info("="*60)
        
        results = await process_county_linkage(county, max_auctions=1000)
        all_results[county] = results
        
        # Print immediate results
        print(f"\n{county.upper()} Results:")
        print(f"  Processed: {results['processed']}")
        print(f"  Linked: {results['linked']} ({results['linked']/max(1,results['processed'])*100:.1f}%)")
        print(f"  Failed: {results['failed']}")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    return all_results

def main():
    """Main function with command line support"""
    logger.info("BREVARD & DUVAL Parcel Linkage (E-lane) Implementation")
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in ['brevard', 'duval']:
            # Process single county
            result = asyncio.run(process_county_linkage(county))
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: County '{county}' not supported. Use 'brevard' or 'duval'.")
            sys.exit(1)
    else:
        # Process both counties
        results = asyncio.run(run_brevard_duval_linkage())
        
        print(f"\n{'='*60}")
        print("CAMPAIGN COMPLETE - E-LANE IMPROVEMENT SUMMARY")
        print("="*60)
        
        total_processed = sum(r['processed'] for r in results.values())
        total_linked = sum(r['linked'] for r in results.values())
        
        print(f"Total auctions processed: {total_processed}")
        print(f"Total parcel links created: {total_linked}")
        print(f"Overall success rate: {total_linked/max(1,total_processed)*100:.1f}%")
        
        print(f"\nDetailed results:")
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()