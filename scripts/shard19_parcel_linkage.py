#!/usr/bin/env python3
"""
SHARD-19 PARCEL LINKAGE ENHANCER - Letter E Gold Standard
Links parcel_id via county property appraiser ArcGIS FeatureServer for charlotte, citrus, broward

Critical for Letter E: ≥95% parcel linkage via county property appraiser

Current status from issue:
- charlotte: E=43.8% (needs improvement)
- citrus: E=95.3% (already passing)
- broward: E=20.6% (needs major improvement)

Usage:
  python scripts/shard19_parcel_linkage.py --county charlotte
  python scripts/shard19_parcel_linkage.py --all-counties
"""
import httpx
import json
import os
import sys
import argparse
import re
from datetime import datetime
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
    "Content-Type": "application/json"
}

# SHARD-19 county property appraiser ArcGIS endpoints
COUNTY_APPRAISER_SOURCES = {
    'charlotte': {
        'name': 'Charlotte County Property Appraiser',
        'arcgis_base': 'https://gis.charlottecountyfl.gov/arcgis/rest/services',
        'parcel_service': 'https://gis.charlottecountyfl.gov/arcgis/rest/services/Public/Parcels/MapServer/0',
        'query_fields': ['PARCELID', 'PARCEL_ID', 'PARCEL_NO', 'FOLIO'],
        'address_fields': ['ADDRESS', 'FULL_ADDR', 'SITE_ADDR'],
        'owner_fields': ['OWNER', 'OWNER_NAME', 'OWNER1']
    },
    'citrus': {
        'name': 'Citrus County Property Appraiser',
        'arcgis_base': 'https://services1.arcgis.com/BNlYOK5ORl18uFCo/arcgis/rest/services',
        'parcel_service': 'https://services1.arcgis.com/BNlYOK5ORl18uFCo/arcgis/rest/services/Citrus_Parcels/FeatureServer/0',
        'query_fields': ['PARCEL_ID', 'PARCELID', 'FOLIO', 'PARCEL_NO'],
        'address_fields': ['SITUS_ADDR', 'ADDRESS', 'SITE_ADDRESS'],
        'owner_fields': ['OWNER_NAME', 'OWNER', 'PROP_OWNER']
    },
    'broward': {
        'name': 'Broward County Property Appraiser',
        'arcgis_base': 'https://gis.broward.org/arcgis/rest/services',
        'parcel_service': 'https://gis.broward.org/arcgis/rest/services/OpenData/Property_Information/MapServer/0',
        'query_fields': ['FOLIO', 'PARCEL_ID', 'PARCELID', 'PCN'],
        'address_fields': ['SITE_ADDRESS', 'PHY_ADDR1', 'SITUS_ADDR'],
        'owner_fields': ['OWNER_NAME', 'OWNER1', 'PROP_OWNER']
    }
}

# SHARD-19 target counties
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

client = httpx.Client(timeout=60, follow_redirects=True)

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

def supabase_update(table: str, updates: Dict, filters: Dict) -> int:
    """Update records in Supabase table"""
    try:
        url = f"{BASE}/{table}"
        filter_params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        if filter_params:
            url += f"?{filter_params}"
        
        response = client.patch(url, headers=HEADERS, json=updates)
        response.raise_for_status()
        return 1  # Assuming single record update
    except Exception as e:
        logger.error(f"Error updating {table}: {e}")
        return 0

def get_unlinked_auctions(county_slug: str, limit: int = 500) -> List[Dict]:
    """Get auctions that don't have parcel_id linked"""
    params = {
        'select': 'id,case_number,property_address,defendant_name,county',
        'county': f'eq.{county_slug}',
        'parcel_id': 'is.null',  # Only unlinked records
        'order': 'auction_date.desc',
        'limit': str(limit)
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} unlinked auctions for {county_slug}")
    return auctions

def discover_arcgis_endpoints(county_slug: str) -> Dict:
    """Discover available ArcGIS FeatureServer endpoints for the county"""
    if county_slug not in COUNTY_APPRAISER_SOURCES:
        return {}
    
    config = COUNTY_APPRAISER_SOURCES[county_slug]
    arcgis_base = config['arcgis_base']
    
    logger.info(f"Discovering ArcGIS endpoints for {config['name']}: {arcgis_base}")
    
    try:
        # Query the base services directory
        response = client.get(f"{arcgis_base}?f=json")
        if response.status_code == 200:
            services_data = response.json()
            services = services_data.get('services', [])
            
            # Look for parcel-related services
            parcel_services = []
            for service in services:
                service_name = service.get('name', '').lower()
                if any(keyword in service_name for keyword in ['parcel', 'property', 'cadastral', 'tax']):
                    service_url = f"{arcgis_base}/{service['name']}/{service['type']}"
                    parcel_services.append(service_url)
            
            logger.info(f"Found {len(parcel_services)} potential parcel services")
            return {
                'services': parcel_services,
                'primary': config['parcel_service']
            }
    except Exception as e:
        logger.warning(f"Failed to discover services for {county_slug}: {e}")
    
    # Fallback to configured service
    return {'primary': config['parcel_service']}

def query_parcel_by_address(service_url: str, address: str, config: Dict) -> List[Dict]:
    """Query ArcGIS FeatureServer for parcels matching an address"""
    try:
        # Clean address for better matching
        clean_address = re.sub(r'[^\w\s]', '', address.upper().strip())
        
        # Build query parameters for ArcGIS REST API
        query_params = {
            'where': f"UPPER({config['address_fields'][0]}) LIKE '%{clean_address}%'",
            'outFields': ','.join(config['query_fields'] + config['address_fields'] + config['owner_fields']),
            'returnGeometry': 'false',
            'f': 'json',
            'resultRecordCount': '10'  # Limit results
        }
        
        response = client.get(f"{service_url}/query", params=query_params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            features = data.get('features', [])
            
            # Extract attributes from features
            results = []
            for feature in features:
                attributes = feature.get('attributes', {})
                # Find the parcel ID field
                parcel_id = None
                for field in config['query_fields']:
                    if attributes.get(field):
                        parcel_id = str(attributes[field])
                        break
                
                if parcel_id:
                    results.append({
                        'parcel_id': parcel_id,
                        'address': attributes.get(config['address_fields'][0], ''),
                        'owner': attributes.get(config['owner_fields'][0], ''),
                        'raw_attributes': attributes
                    })
            
            return results
            
    except Exception as e:
        logger.warning(f"Failed to query {service_url} for address '{address}': {e}")
    
    return []

def match_parcel_by_owner(service_url: str, owner_name: str, config: Dict) -> List[Dict]:
    """Query ArcGIS FeatureServer for parcels matching an owner name"""
    try:
        # Clean owner name for better matching
        clean_owner = re.sub(r'[^\w\s]', '', owner_name.upper().strip())
        # Take first few words to avoid overly specific queries
        owner_words = clean_owner.split()[:3]
        owner_query = ' '.join(owner_words)
        
        # Build query parameters
        query_params = {
            'where': f"UPPER({config['owner_fields'][0]}) LIKE '%{owner_query}%'",
            'outFields': ','.join(config['query_fields'] + config['address_fields'] + config['owner_fields']),
            'returnGeometry': 'false',
            'f': 'json',
            'resultRecordCount': '5'  # Fewer results for owner search
        }
        
        response = client.get(f"{service_url}/query", params=query_params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            features = data.get('features', [])
            
            results = []
            for feature in features:
                attributes = feature.get('attributes', {})
                parcel_id = None
                for field in config['query_fields']:
                    if attributes.get(field):
                        parcel_id = str(attributes[field])
                        break
                
                if parcel_id:
                    results.append({
                        'parcel_id': parcel_id,
                        'address': attributes.get(config['address_fields'][0], ''),
                        'owner': attributes.get(config['owner_fields'][0], ''),
                        'raw_attributes': attributes
                    })
            
            return results
            
    except Exception as e:
        logger.warning(f"Failed to query {service_url} for owner '{owner_name}': {e}")
    
    return []

def link_auction_parcel(auction: Dict, county_slug: str, dry_run: bool = False) -> Optional[str]:
    """Attempt to link a parcel_id to an auction record"""
    if county_slug not in COUNTY_APPRAISER_SOURCES:
        return None
    
    config = COUNTY_APPRAISER_SOURCES[county_slug]
    service_url = config['parcel_service']
    
    # Try address-based matching first
    if auction.get('property_address'):
        address_results = query_parcel_by_address(service_url, auction['property_address'], config)
        if address_results:
            # Take the first/best match
            match = address_results[0]
            parcel_id = match['parcel_id']
            
            if not dry_run:
                # Update the auction record
                updates = {'parcel_id': parcel_id}
                filters = {'id': auction['id']}
                if supabase_update('multi_county_auctions', updates, filters):
                    logger.info(f"Linked {auction['case_number']} to parcel {parcel_id} via address")
                    return parcel_id
            else:
                logger.info(f"DRY RUN: Would link {auction['case_number']} to parcel {parcel_id}")
                return parcel_id
    
    # Try owner-based matching as fallback
    if auction.get('defendant_name'):
        owner_results = match_parcel_by_owner(service_url, auction['defendant_name'], config)
        if owner_results:
            match = owner_results[0]
            parcel_id = match['parcel_id']
            
            if not dry_run:
                updates = {'parcel_id': parcel_id}
                filters = {'id': auction['id']}
                if supabase_update('multi_county_auctions', updates, filters):
                    logger.info(f"Linked {auction['case_number']} to parcel {parcel_id} via owner")
                    return parcel_id
            else:
                logger.info(f"DRY RUN: Would link {auction['case_number']} to parcel {parcel_id} via owner")
                return parcel_id
    
    return None

def process_county_parcel_linkage(county_slug: str, dry_run: bool = False, limit: int = 100) -> Dict[str, int]:
    """Process parcel linkage for a single county"""
    logger.info(f"\n=== Processing {county_slug.upper()} Parcel Linkage ===")
    
    # Check if county has already passing grade (citrus = 95.3%)
    if county_slug == 'citrus':
        logger.info("Citrus already passing Letter E (95.3%) - skipping")
        return {'processed': 0, 'linked': 0}
    
    # Get unlinked auctions
    unlinked_auctions = get_unlinked_auctions(county_slug, limit)
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions found for {county_slug}")
        return {'processed': 0, 'linked': 0}
    
    # Discover/verify ArcGIS endpoints
    endpoints = discover_arcgis_endpoints(county_slug)
    if not endpoints.get('primary'):
        logger.error(f"No parcel service endpoint found for {county_slug}")
        return {'processed': 0, 'linked': 0}
    
    logger.info(f"Using parcel service: {endpoints['primary']}")
    
    # Process each unlinked auction
    linked_count = 0
    for auction in unlinked_auctions:
        try:
            parcel_id = link_auction_parcel(auction, county_slug, dry_run)
            if parcel_id:
                linked_count += 1
        except Exception as e:
            logger.warning(f"Error linking {auction['case_number']}: {e}")
    
    return {
        'processed': len(unlinked_auctions),
        'linked': linked_count,
        'success_rate': round(linked_count / len(unlinked_auctions) * 100, 1) if unlinked_auctions else 0
    }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SHARD-19 Parcel Linkage Enhancer")
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Specific county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all SHARD-19 counties')
    parser.add_argument('--dry-run', action='store_true', help='Analyze only, no database writes')
    parser.add_argument('--limit', type=int, default=100, help='Max auctions to process per county')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        logger.info("This script requires database access to update parcel linkages")
        sys.exit(1)
    
    logger.info("🔗 SHARD-19 PARCEL LINKAGE ENHANCER - Letter E")
    logger.info(f"Target counties: charlotte (43.8%), citrus (95.3% ✓), broward (20.6%)")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    elif args.all_counties:
        counties_to_process = TARGET_COUNTIES
    else:
        logger.error("Must specify --county or --all-counties")
        sys.exit(1)
    
    logger.info(f"Processing counties: {', '.join(counties_to_process)}")
    
    # Process each county
    total_stats = {'processed': 0, 'linked': 0}
    
    for county in counties_to_process:
        try:
            stats = process_county_parcel_linkage(county, dry_run=args.dry_run, limit=args.limit)
            
            logger.info(f"{county.upper()} Results:")
            logger.info(f"  - Processed auctions: {stats['processed']}")
            logger.info(f"  - Successfully linked: {stats['linked']}")
            logger.info(f"  - Success rate: {stats.get('success_rate', 0)}%")
            
            total_stats['processed'] += stats['processed']
            total_stats['linked'] += stats['linked']
            
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            continue
    
    # Summary
    overall_rate = round(total_stats['linked'] / total_stats['processed'] * 100, 1) if total_stats['processed'] else 0
    
    logger.info(f"\n🎯 SHARD-19 PARCEL LINKAGE SUMMARY")
    logger.info(f"Total auctions processed: {total_stats['processed']}")
    logger.info(f"Total successfully linked: {total_stats['linked']}")
    logger.info(f"Overall success rate: {overall_rate}%")
    
    if total_stats['linked'] > 0:
        logger.info("\n✅ Letter E metric should improve after these parcel linkages")
        logger.info("Run pencil_dod_evaluate_county('<county>') to verify metric changes")
        logger.info("\nTo verify improvements:")
        for county in counties_to_process:
            logger.info(f"  SELECT public.pencil_dod_evaluate_county('{county}');")
    else:
        logger.info("\n⚠️ No new parcel linkages created")
        if not args.dry_run:
            logger.info("This may indicate:")
            logger.info("- All recent auctions already have parcel_id")
            logger.info("- ArcGIS endpoints may need adjustment")
            logger.info("- Address/owner matching logic needs improvement")
            logger.info("- County property appraiser data structure changed")

if __name__ == "__main__":
    main()