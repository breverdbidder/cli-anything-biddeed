#!/usr/bin/env python3
"""
SHARD-6 Parcel Linkage (E-lane) Implementation
Link auction properties to parcels via county property appraiser APIs

Priority counties: escambia, lake (both have parcel linkage <95%)
Based on BCPAO bridge implementation pattern
"""

import os
import sys
import json
import httpx
import logging
import asyncio
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

# Property Appraiser API endpoints (discovered via discover_and_conquer.py)
APPRAISER_ENDPOINTS = {
    'escambia': {
        'arcgis_base': 'https://gis.myescambia.com/arcgis/rest/services',
        'property_layer': None,  # To be discovered
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN']
    },
    'lake': {
        'arcgis_base': 'https://gis.lakecountyfl.gov/arcgis/rest/services', 
        'property_layer': None,  # To be discovered
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN']
    },
    'calhoun': {
        'arcgis_base': None,  # Custom clerk - may need different approach
        'fallback_url': 'https://www.calhounclerk.com'
    }
}

client = httpx.AsyncClient(timeout=30)

async def discover_property_layer(county: str) -> Optional[str]:
    """Discover the property/parcel layer for a county's ArcGIS service"""
    config = APPRAISER_ENDPOINTS.get(county, {})
    base_url = config.get('arcgis_base')
    
    if not base_url:
        logger.warning(f"No ArcGIS base URL configured for {county}")
        return None
    
    try:
        # Get list of services
        services_url = f"{base_url}?f=json"
        response = await client.get(services_url)
        
        if response.status_code != 200:
            logger.error(f"Failed to get services for {county}: {response.status_code}")
            return None
            
        services_data = response.json()
        
        # Look for property/parcel related services
        property_keywords = ['property', 'parcel', 'cadastral', 'ownership', 'appraiser']
        
        for service in services_data.get('services', []):
            service_name = service.get('name', '').lower()
            service_type = service.get('type', '')
            
            if service_type == 'MapServer':
                for keyword in property_keywords:
                    if keyword in service_name:
                        service_url = f"{base_url}/{service['name']}/MapServer"
                        logger.info(f"Found potential property service for {county}: {service_url}")
                        
                        # Test the service
                        test_response = await client.get(f"{service_url}?f=json")
                        if test_response.status_code == 200:
                            return service_url
        
        logger.warning(f"No property layer found for {county}")
        return None
        
    except Exception as e:
        logger.error(f"Error discovering property layer for {county}: {e}")
        return None

async def get_unlinked_properties(county: str, limit: int = 1000) -> List[Dict]:
    """Get properties from multi_county_auctions that don't have parcel_id linked"""
    
    params = {
        'county': f'eq.{county}',
        'parcel_id': 'is.null',
        'limit': limit,
        'select': 'id,address,case_number,county,sale_date'
    }
    
    try:
        response = await client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            properties = response.json()
            logger.info(f"Found {len(properties)} unlinked properties in {county}")
            return properties
        else:
            logger.error(f"Failed to get unlinked properties for {county}: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error getting unlinked properties for {county}: {e}")
        return []

async def search_parcel_by_address(county: str, address: str, property_service_url: str) -> Optional[str]:
    """Search for parcel ID by address using county's ArcGIS service"""
    
    # Clean and normalize address for search
    clean_address = address.strip().upper()
    
    # Try different query formats
    query_variants = [
        clean_address,
        clean_address.replace(' AVE', ' AVENUE'),
        clean_address.replace(' ST', ' STREET'),
        clean_address.replace(' DR', ' DRIVE'),
        clean_address.replace(' RD', ' ROAD')
    ]
    
    for variant in query_variants:
        try:
            # Query the feature service
            query_url = f"{property_service_url}/query"
            
            params = {
                'where': f"UPPER(SITUS_ADDRESS) LIKE '%{variant}%' OR UPPER(PROPERTY_ADDRESS) LIKE '%{variant}%'",
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
                    # Return the first match's parcel ID
                    for field_name in ['PARCEL_ID', 'PARCELNO', 'PIN', 'PARCEL_NUMBER']:
                        attributes = features[0].get('attributes', {})
                        parcel_id = attributes.get(field_name)
                        if parcel_id:
                            logger.info(f"Found parcel {parcel_id} for address {variant}")
                            return str(parcel_id)
        
        except Exception as e:
            logger.debug(f"Search failed for {variant}: {e}")
            continue
    
    logger.debug(f"No parcel found for address: {address}")
    return None

async def update_property_parcel_link(property_id: int, parcel_id: str) -> bool:
    """Update multi_county_auctions with discovered parcel_id"""
    
    try:
        # Update the property with the parcel_id
        update_data = {'parcel_id': parcel_id}
        params = {'id': f'eq.{property_id}'}
        
        response = await client.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params=params,
            json=update_data
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ Updated property {property_id} with parcel {parcel_id}")
            return True
        else:
            logger.error(f"❌ Failed to update property {property_id}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error updating property {property_id}: {e}")
        return False

async def process_county_parcel_linkage(county: str, max_properties: int = 500) -> Dict:
    """Process parcel linkage for a county"""
    logger.info(f"Starting parcel linkage for {county}...")
    
    results = {
        'county': county,
        'processed': 0,
        'linked': 0,
        'failed': 0,
        'errors': []
    }
    
    # Discover the property layer
    property_service = await discover_property_layer(county)
    if not property_service:
        results['errors'].append(f"Could not discover property service for {county}")
        return results
    
    # Get unlinked properties
    unlinked_properties = await get_unlinked_properties(county, max_properties)
    if not unlinked_properties:
        logger.info(f"No unlinked properties found for {county}")
        return results
    
    results['processed'] = len(unlinked_properties)
    
    # Process each property
    for prop in unlinked_properties:
        address = prop.get('address', '')
        prop_id = prop.get('id')
        
        if not address or not prop_id:
            results['failed'] += 1
            continue
        
        # Search for parcel
        parcel_id = await search_parcel_by_address(county, address, property_service)
        
        if parcel_id:
            # Update the property
            success = await update_property_parcel_link(prop_id, parcel_id)
            if success:
                results['linked'] += 1
            else:
                results['failed'] += 1
        else:
            results['failed'] += 1
        
        # Rate limiting
        await asyncio.sleep(0.1)
    
    logger.info(f"Completed {county}: {results['linked']} linked, {results['failed']} failed")
    return results

async def run_parcel_linkage_campaign():
    """Run parcel linkage for all SHARD-6 counties that need it"""
    logger.info("Starting SHARD-6 parcel linkage campaign...")
    
    # Priority counties based on issue brief
    priority_counties = ['escambia', 'lake']  # Both have E-lane failures
    
    all_results = {}
    
    for county in priority_counties:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {county.upper()}")
        logger.info("="*50)
        
        results = await process_county_parcel_linkage(county)
        all_results[county] = results
        
        # Print results
        print(f"\n{county.upper()} Results:")
        print(f"  Processed: {results['processed']}")
        print(f"  Linked: {results['linked']}")
        print(f"  Failed: {results['failed']}")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-6 Parcel Linkage (E-lane) Implementation")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        # Process single county
        result = asyncio.run(process_county_parcel_linkage(county))
        print(json.dumps(result, indent=2))
    else:
        # Process all priority counties
        results = asyncio.run(run_parcel_linkage_campaign())
        print(f"\nCampaign Complete!")
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()