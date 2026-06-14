#!/usr/bin/env python3
"""
SHARD-7 Parcel Linkage (Letter E) Implementation
Link auction properties to parcels via county property appraiser APIs

Priority counties: highlands, baker, miami_dade (have A✓, need E fix)
Columbia/Madison need A-letter first before E-letter work
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

# Property Appraiser API endpoints for SHARD-7 counties
SHARD7_APPRAISER_ENDPOINTS = {
    'highlands': {
        'arcgis_base': 'https://gis.highlandscounty.org/arcgis/rest/services',
        'appraiser_url': 'https://www.hcpao.org/',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN', 'STRAP'],
        'notes': '2/10 - A✓, H✓'
    },
    'baker': {
        'arcgis_base': 'https://maps.bakercountyfl.org/arcgis/rest/services', 
        'appraiser_url': 'https://www.bcpao.us/',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'notes': '1/10 - A✓'
    },
    'miami_dade': {
        'arcgis_base': 'https://gisws.miamidade.gov/arcgis/rest/services',
        'appraiser_url': 'https://www.miamidade.gov/pa/',
        'search_fields': ['FOLIO', 'PARCEL_ID', 'PARCELNO', 'PIN'],
        'notes': '1/10 - A✓, massive volume'
    },
    # Columbia and Madison commented out - need A-letter first
    # 'columbia': {
    #     'arcgis_base': 'https://gis.columbiacountyfla.com/arcgis/rest/services',
    #     'appraiser_url': 'https://www.ccpao.com/',
    #     'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
    #     'notes': '0/10 - ALL FAIL, need A-letter first'
    # },
    # 'madison': {
    #     'arcgis_base': 'https://gis.madisoncountyfl.com/arcgis/rest/services',
    #     'appraiser_url': 'https://www.madisonpao.com/',
    #     'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
    #     'notes': '0/10 - ALL FAIL, need A-letter first'
    # }
}

client = httpx.AsyncClient(timeout=30)

async def discover_property_layer(county: str) -> Optional[str]:
    """Discover the property/parcel layer for a county's ArcGIS service"""
    config = SHARD7_APPRAISER_ENDPOINTS.get(county, {})
    base_url = config.get('arcgis_base')
    
    if not base_url:
        logger.warning(f"No ArcGIS base URL configured for {county}")
        return None
    
    try:
        logger.info(f"Discovering property layer for {county} at {base_url}")
        
        # Get list of services
        services_url = f"{base_url}?f=json"
        response = await client.get(services_url)
        
        if response.status_code != 200:
            logger.error(f"Failed to get services for {county}: {response.status_code}")
            return None
            
        services_data = response.json()
        
        # Look for property/parcel related services
        property_keywords = ['property', 'parcel', 'cadastral', 'ownership', 'appraiser', 'assessor', 'land']
        
        for service in services_data.get('services', []):
            service_name = service.get('name', '').lower()
            service_type = service.get('type', '')
            
            if service_type == 'MapServer':
                for keyword in property_keywords:
                    if keyword in service_name:
                        service_url = f"{base_url}/{service['name']}/MapServer"
                        logger.info(f"Found potential property service for {county}: {service_url}")
                        
                        # Test the service and get layer info
                        test_response = await client.get(f"{service_url}?f=json")
                        if test_response.status_code == 200:
                            service_info = test_response.json()
                            layers = service_info.get('layers', [])
                            
                            # Find the layer with parcel data
                            for layer in layers:
                                layer_name = layer.get('name', '').lower()
                                if any(kw in layer_name for kw in property_keywords):
                                    layer_url = f"{service_url}/{layer['id']}"
                                    logger.info(f"Found property layer for {county}: {layer_url}")
                                    return layer_url
                            
                            # If no specific layer found, use the service root
                            return service_url
        
        logger.warning(f"No property layer found for {county}")
        return None
        
    except Exception as e:
        logger.error(f"Error discovering property layer for {county}: {e}")
        return None

async def get_unlinked_properties(county: str, limit: int = 500) -> List[Dict]:
    """Get properties from multi_county_auctions that don't have parcel_id linked"""
    
    params = {
        'county': f'eq.{county}',
        'parcel_id': 'is.null',
        'limit': limit,
        'select': 'id,address,case_number,county,auction_date,sale_type',
        'order': 'auction_date.desc'
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
    
    if not address or len(address.strip()) < 5:
        return None
    
    # Clean and normalize address for search
    clean_address = address.strip().upper()
    
    # Remove common noise words
    clean_address = clean_address.replace('UNPLATTED', '').replace('UNKNOWN', '').strip()
    
    # Try different query formats
    query_variants = [
        clean_address,
        clean_address.replace(' AVE', ' AVENUE'),
        clean_address.replace(' ST', ' STREET'),
        clean_address.replace(' DR', ' DRIVE'),
        clean_address.replace(' RD', ' ROAD'),
        clean_address.replace(' BLVD', ' BOULEVARD'),
        clean_address.replace(' CT', ' COURT'),
        clean_address.replace(' CIR', ' CIRCLE')
    ]
    
    # County-specific search field variations
    search_fields = SHARD7_APPRAISER_ENDPOINTS.get(county, {}).get('search_fields', ['PARCEL_ID'])
    
    for variant in query_variants:
        if len(variant.strip()) < 5:
            continue
            
        try:
            # Query the feature service
            query_url = f"{property_service_url}/query"
            
            # Try different address field names
            address_conditions = []
            for addr_field in ['SITUS_ADDRESS', 'PROPERTY_ADDRESS', 'SITE_ADDRESS', 'PHYSADDR', 'ADDRESS']:
                address_conditions.append(f"UPPER({addr_field}) LIKE '%{variant.split()[0]}%'")
            
            where_clause = " OR ".join(address_conditions)
            
            params = {
                'where': where_clause,
                'outFields': ','.join(search_fields + ['SITUS_ADDRESS', 'PROPERTY_ADDRESS', 'SITE_ADDRESS']),
                'returnGeometry': 'false',
                'f': 'json',
                'resultRecordCount': 10
            }
            
            response = await client.get(query_url, params=params)
            
            if response.status_code == 200:
                result = response.json()
                features = result.get('features', [])
                
                if features:
                    # Find best match by address similarity
                    best_match = None
                    best_score = 0
                    
                    for feature in features:
                        attributes = feature.get('attributes', {})
                        
                        # Get the parcel ID from available fields
                        parcel_id = None
                        for field_name in search_fields:
                            if attributes.get(field_name):
                                parcel_id = str(attributes[field_name]).strip()
                                break
                        
                        if not parcel_id:
                            continue
                        
                        # Score the address match
                        feature_address = ''
                        for addr_field in ['SITUS_ADDRESS', 'PROPERTY_ADDRESS', 'SITE_ADDRESS']:
                            if attributes.get(addr_field):
                                feature_address = str(attributes[addr_field]).upper()
                                break
                        
                        if feature_address:
                            # Simple scoring based on word overlap
                            variant_words = set(variant.split())
                            feature_words = set(feature_address.split())
                            overlap = len(variant_words & feature_words)
                            score = overlap / max(len(variant_words), 1)
                            
                            if score > best_score and score > 0.3:  # Minimum 30% match
                                best_score = score
                                best_match = parcel_id
                    
                    if best_match:
                        logger.info(f"Found parcel {best_match} for address '{variant}' (score: {best_score:.2f})")
                        return best_match
        
        except Exception as e:
            logger.debug(f"Search failed for {variant}: {e}")
            continue
    
    logger.debug(f"No parcel found for address: {address}")
    return None

async def update_property_parcel_link(property_id: int, parcel_id: str) -> bool:
    """Update multi_county_auctions with discovered parcel_id"""
    
    try:
        # Update the property with the parcel_id
        update_data = {
            'parcel_id': parcel_id,
            'parcel_linked_at': datetime.now(timezone.utc).isoformat()
        }
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

async def process_county_parcel_linkage(county: str, max_properties: int = 300) -> Dict:
    """Process parcel linkage for a county"""
    logger.info(f"Starting parcel linkage for {county}...")
    
    results = {
        'county': county,
        'notes': SHARD7_APPRAISER_ENDPOINTS.get(county, {}).get('notes', ''),
        'processed': 0,
        'linked': 0,
        'failed': 0,
        'errors': [],
        'service_url': None
    }
    
    # Check if county is ready for E-letter work
    if county in ['columbia', 'madison']:
        results['errors'].append(f"{county} is 0/10 - needs A-letter before E-letter work")
        return results
    
    # Discover the property layer
    property_service = await discover_property_layer(county)
    if not property_service:
        results['errors'].append(f"Could not discover property service for {county}")
        return results
    
    results['service_url'] = property_service
    
    # Get unlinked properties
    unlinked_properties = await get_unlinked_properties(county, max_properties)
    if not unlinked_properties:
        logger.info(f"No unlinked properties found for {county}")
        return results
    
    results['processed'] = len(unlinked_properties)
    logger.info(f"Processing {len(unlinked_properties)} unlinked properties for {county}")
    
    # Process each property
    for i, prop in enumerate(unlinked_properties):
        address = prop.get('address', '')
        prop_id = prop.get('id')
        case_number = prop.get('case_number', '')
        
        if i % 50 == 0:
            logger.info(f"Progress: {i}/{len(unlinked_properties)} ({i/len(unlinked_properties)*100:.1f}%)")
        
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
                logger.debug(f"Linked {case_number} → {parcel_id}")
            else:
                results['failed'] += 1
        else:
            results['failed'] += 1
        
        # Rate limiting - be gentle with county systems
        await asyncio.sleep(0.2)
    
    linkage_rate = (results['linked'] / results['processed'] * 100) if results['processed'] > 0 else 0
    logger.info(f"Completed {county}: {results['linked']}/{results['processed']} linked ({linkage_rate:.1f}%)")
    
    return results

async def run_shard7_parcel_linkage():
    """Run parcel linkage for SHARD-7 counties ready for E-letter work"""
    logger.info("Starting SHARD-7 parcel linkage campaign...")
    
    # Only counties with A✓ are ready for E-letter work
    ready_counties = ['highlands', 'baker', 'miami_dade']  
    
    logger.info(f"Counties ready for E-letter: {ready_counties}")
    logger.info("Columbia/Madison skipped - need A-letter first")
    
    all_results = {}
    
    for county in ready_counties:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {county.upper()} - Letter E (Parcel Linkage)")
        logger.info("="*60)
        
        results = await process_county_parcel_linkage(county)
        all_results[county] = results
        
        # Print results
        print(f"\n{county.upper()} Results:")
        print(f"  Status: {results['notes']}")
        print(f"  Service: {results['service_url']}")
        print(f"  Processed: {results['processed']}")
        print(f"  Linked: {results['linked']}")
        print(f"  Failed: {results['failed']}")
        
        if results['processed'] > 0:
            rate = results['linked'] / results['processed'] * 100
            print(f"  Success Rate: {rate:.1f}%")
            
            if rate >= 95.0:
                print(f"  ✅ Letter E: PASS (≥95% linkage)")
            else:
                print(f"  ❌ Letter E: FAIL (need ≥95% linkage)")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    return all_results

def main():
    """Main function"""
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    logger.info("SHARD-7 Parcel Linkage (Letter E) Implementation")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        if county not in SHARD7_APPRAISER_ENDPOINTS:
            logger.error(f"County {county} not supported. Available: {list(SHARD7_APPRAISER_ENDPOINTS.keys())}")
            sys.exit(1)
        
        # Process single county
        result = asyncio.run(process_county_parcel_linkage(county))
        print(json.dumps(result, indent=2))
    else:
        # Process all ready counties
        results = asyncio.run(run_shard7_parcel_linkage())
        
        print(f"\n{'='*60}")
        print("SHARD-7 PARCEL LINKAGE CAMPAIGN COMPLETE")
        print("="*60)
        
        total_processed = sum(r['processed'] for r in results.values())
        total_linked = sum(r['linked'] for r in results.values())
        
        if total_processed > 0:
            overall_rate = total_linked / total_processed * 100
            print(f"Overall: {total_linked}/{total_processed} linked ({overall_rate:.1f}%)")
        
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()