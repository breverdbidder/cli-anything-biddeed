#!/usr/bin/env python3
"""
SHARD 9 Letter E Fix: Parcel Linkage via County Property Appraiser ArcGIS
Links parcel_id via county property appraiser ArcGIS FeatureServer for assigned counties

Per issue briefing: "E: link parcel_id via the county property appraiser ArcGIS FeatureServer 
(Brevard/BCPAO pipeline is the reference implementation)"

This is high-leverage because: parcel linkage fixes (E) make parcels comps-eligible -> 
the valuations re-armer picks them up automatically -> J inputs flow.

Counties: leon, washington, marion, dixie, taylor

Usage:
  python scripts/shard9_parcel_linkage_fix.py --county leon
  python scripts/shard9_parcel_linkage_fix.py --all-counties
"""
import os
import sys
import argparse
import httpx
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import re
from urllib.parse import urljoin

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

# County property appraiser ArcGIS endpoints
# Discovered via standard Florida PA naming patterns
COUNTY_PA_ENDPOINTS = {
    'leon': {
        'name': 'Leon County Property Appraiser',
        'base_url': 'https://maps.leoncountyfl.gov/arcgis/rest/services/',
        'parcel_service': 'Property/PropertyAppraiser/MapServer/0',  # Common layer 0 for parcels
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'address_fields': ['SITE_ADDR', 'SITUS_ADDRESS', 'ADDRESS'],
        'backup_url': 'https://gis.leoncountyfl.gov/arcgis/rest/services/'
    },
    'washington': {
        'name': 'Washington County Property Appraiser', 
        'base_url': 'https://maps.washingtonfl.gov/arcgis/rest/services/',
        'parcel_service': 'Property/PropertyAppraiser/MapServer/0',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'address_fields': ['SITE_ADDR', 'SITUS_ADDRESS', 'ADDRESS'],
        'backup_url': 'https://gis.washingtonfl.gov/arcgis/rest/services/'
    },
    'marion': {
        'name': 'Marion County Property Appraiser',
        'base_url': 'https://maps.marioncountyfl.org/arcgis/rest/services/',
        'parcel_service': 'Property/PropertyAppraiser/MapServer/0', 
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'address_fields': ['SITE_ADDR', 'SITUS_ADDRESS', 'ADDRESS'],
        'backup_url': 'https://gis.marioncountyfl.org/arcgis/rest/services/'
    },
    'dixie': {
        'name': 'Dixie County Property Appraiser',
        'base_url': 'https://maps.dixiefl.gov/arcgis/rest/services/',
        'parcel_service': 'Property/PropertyAppraiser/MapServer/0',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'],
        'address_fields': ['SITE_ADDR', 'SITUS_ADDRESS', 'ADDRESS'],
        'backup_url': 'https://gis.dixiefl.gov/arcgis/rest/services/'
    },
    'taylor': {
        'name': 'Taylor County Property Appraiser',
        'base_url': 'https://maps.taylorfl.gov/arcgis/rest/services/',
        'parcel_service': 'Property/PropertyAppraiser/MapServer/0',
        'search_fields': ['PARCEL_ID', 'PARCELNO', 'PIN'], 
        'address_fields': ['SITE_ADDR', 'SITUS_ADDRESS', 'ADDRESS'],
        'backup_url': 'https://gis.taylorfl.gov/arcgis/rest/services/'
    }
}

client = httpx.Client(timeout=60, follow_redirects=True, headers={
    'User-Agent': 'BidDeed-SHARD9-ParcelLinkage/1.0 (contact: ariel@everestcapitalusa.com)'
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

def supabase_update(table: str, data: List[Dict], match_cols: List[str]) -> int:
    """Update records in Supabase table"""
    if not data:
        return 0
    
    updated_count = 0
    for record in data:
        try:
            # Build where clause for matching
            where_params = {col: f"eq.{record[col]}" for col in match_cols if col in record}
            update_data = {k: v for k, v in record.items() if k not in match_cols}
            
            # Construct URL with where params
            where_str = "&".join(f"{k}={v}" for k, v in where_params.items())
            url = f"{BASE}/{table}?{where_str}"
            
            response = client.patch(url, json=update_data, headers=HEADERS)
            if response.status_code in [200, 204]:
                updated_count += 1
            else:
                logger.warning(f"Failed to update record: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error updating record: {e}")
    
    logger.info(f"Updated {updated_count} records in {table}")
    return updated_count

def discover_arcgis_endpoint(county_slug: str) -> Optional[str]:
    """Discover the working ArcGIS REST endpoint for a county"""
    pa_info = COUNTY_PA_ENDPOINTS.get(county_slug)
    if not pa_info:
        logger.error(f"No PA endpoint config for {county_slug}")
        return None
    
    # Try primary and backup URLs
    urls_to_try = [
        pa_info['base_url'],
        pa_info.get('backup_url', ''),
        # Generic patterns
        f"https://gis.{county_slug}countyfl.gov/arcgis/rest/services/",
        f"https://maps.{county_slug}pa.org/arcgis/rest/services/",
        f"https://{county_slug}pa.org/arcgis/rest/services/"
    ]
    
    for base_url in urls_to_try:
        if not base_url:
            continue
            
        try:
            logger.info(f"Testing {base_url}")
            response = client.get(base_url + "?f=json", timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'services' in data or 'folders' in data:
                    logger.info(f"✅ Found working ArcGIS endpoint: {base_url}")
                    return base_url
                    
        except Exception as e:
            logger.debug(f"Failed {base_url}: {e}")
    
    logger.warning(f"❌ No working ArcGIS endpoint found for {county_slug}")
    return None

def find_parcel_layer(base_url: str, county_slug: str) -> Optional[str]:
    """Find the parcel layer in the ArcGIS service"""
    pa_info = COUNTY_PA_ENDPOINTS.get(county_slug)
    
    # Try common parcel service paths
    potential_services = [
        pa_info['parcel_service'],
        'Property/MapServer/0',
        'Parcels/MapServer/0', 
        'PropertyAppraiser/MapServer/0',
        'Public/MapServer/0'
    ]
    
    for service_path in potential_services:
        try:
            full_url = urljoin(base_url, service_path)
            logger.info(f"Testing parcel layer: {full_url}")
            
            response = client.get(full_url + "?f=json", timeout=15)
            if response.status_code == 200:
                data = response.json()
                
                # Check if this looks like a parcel layer
                if 'fields' in data:
                    fields = [f['name'].upper() for f in data['fields']]
                    parcel_indicators = ['PARCEL', 'PIN', 'PROPERTY', 'OWNER']
                    
                    if any(indicator in field for indicator in parcel_indicators for field in fields):
                        logger.info(f"✅ Found parcel layer: {full_url}")
                        return full_url
                        
        except Exception as e:
            logger.debug(f"Failed {full_url}: {e}")
    
    logger.warning(f"❌ No parcel layer found for {county_slug}")
    return None

def get_unlinked_auctions(county_slug: str) -> List[Dict]:
    """Get auctions without parcel_id that need linking"""
    params = {
        "county": f"eq.{county_slug}",
        "parcel_id": "is.null",
        "select": "id,case_number,property_address,county",
        "limit": "1000"  # Process in batches
    }
    
    auctions = supabase_get("multi_county_auctions", params)
    logger.info(f"Found {len(auctions)} unlinked auctions for {county_slug}")
    return auctions

def query_parcel_by_address(parcel_layer_url: str, address: str, county_slug: str) -> Optional[str]:
    """Query parcel layer by property address to get parcel_id"""
    if not address:
        return None
        
    pa_info = COUNTY_PA_ENDPOINTS.get(county_slug)
    
    try:
        # Clean up address for querying
        clean_address = address.strip().upper()
        clean_address = re.sub(r'\s+', ' ', clean_address)  # Normalize spaces
        
        # Try different where clause formats
        where_clauses = [
            f"UPPER(SITE_ADDR) LIKE '%{clean_address}%'",
            f"UPPER(SITUS_ADDRESS) LIKE '%{clean_address}%'",
            f"UPPER(ADDRESS) LIKE '%{clean_address}%'",
            # Try just street number and name
            f"UPPER(SITE_ADDR) LIKE '%{clean_address.split()[0]}%'"
        ]
        
        for where_clause in where_clauses:
            query_params = {
                'where': where_clause,
                'outFields': '*',
                'f': 'json',
                'resultRecordCount': 5
            }
            
            # Build query string manually to handle spaces properly
            query_string = "&".join(f"{k}={v}" for k, v in query_params.items())
            query_url = f"{parcel_layer_url}/query?{query_string}"
            
            response = client.get(query_url, timeout=20)
            if response.status_code == 200:
                data = response.json()
                
                if 'features' in data and data['features']:
                    feature = data['features'][0]  # Take first match
                    attributes = feature.get('attributes', {})
                    
                    # Try to find parcel ID in different field names
                    for field_name in pa_info['search_fields']:
                        if field_name in attributes and attributes[field_name]:
                            parcel_id = str(attributes[field_name]).strip()
                            logger.info(f"✅ Found parcel {parcel_id} for {address}")
                            return parcel_id
            
            time.sleep(0.5)  # Rate limiting between queries
            
    except Exception as e:
        logger.error(f"Error querying parcel for {address}: {e}")
    
    return None

def process_county_parcel_linkage(county_slug: str) -> Dict:
    """Process parcel linkage for a single county"""
    logger.info(f"Processing parcel linkage for {county_slug}")
    
    # Discover ArcGIS endpoint
    base_url = discover_arcgis_endpoint(county_slug)
    if not base_url:
        return {'county': county_slug, 'linked': 0, 'error': 'No ArcGIS endpoint found'}
    
    # Find parcel layer
    parcel_layer_url = find_parcel_layer(base_url, county_slug)
    if not parcel_layer_url:
        return {'county': county_slug, 'linked': 0, 'error': 'No parcel layer found'}
    
    # Get unlinked auctions
    unlinked_auctions = get_unlinked_auctions(county_slug)
    if not unlinked_auctions:
        logger.info(f"No unlinked auctions for {county_slug}")
        return {'county': county_slug, 'linked': 0, 'checked': 0}
    
    # Process each auction to find parcel_id
    linked_count = 0
    updates = []
    
    for auction in unlinked_auctions[:100]:  # Limit to 100 per run to avoid timeouts
        address = auction.get('property_address')
        if not address:
            continue
            
        parcel_id = query_parcel_by_address(parcel_layer_url, address, county_slug)
        if parcel_id:
            updates.append({
                'id': auction['id'],
                'parcel_id': parcel_id,
                'parcel_linked_at': datetime.now().isoformat(),
                'parcel_source': f"{county_slug}_pa_arcgis"
            })
            linked_count += 1
            
        time.sleep(1)  # Rate limiting
    
    # Apply updates
    if updates:
        updated_count = supabase_update('multi_county_auctions', updates, ['id'])
        logger.info(f"Updated {updated_count} auction records with parcel_id")
    
    return {
        'county': county_slug,
        'checked': len(unlinked_auctions[:100]),
        'linked': linked_count,
        'parcel_layer_url': parcel_layer_url
    }

def main():
    parser = argparse.ArgumentParser(description='SHARD 9 Parcel Linkage Fix (Letter E)')
    parser.add_argument('--county', choices=['leon', 'washington', 'marion', 'dixie', 'taylor'],
                      help='County to process')
    parser.add_argument('--all-counties', action='store_true',
                      help='Process all assigned counties')
    parser.add_argument('--discover-only', action='store_true',
                      help='Only discover and test ArcGIS endpoints')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    target_counties = ['leon', 'washington', 'marion', 'dixie', 'taylor'] if args.all_counties else [args.county]
    
    if not target_counties or target_counties == [None]:
        logger.error("Must specify --county or --all-counties")
        sys.exit(1)
    
    results = []
    
    for county in target_counties:
        if county:
            if args.discover_only:
                # Just test endpoint discovery
                logger.info(f"\n=== Testing {county} endpoints ===")
                base_url = discover_arcgis_endpoint(county)
                if base_url:
                    parcel_layer = find_parcel_layer(base_url, county)
                    print(f"{county}: {base_url} -> {parcel_layer}")
            else:
                # Full parcel linkage process
                time.sleep(2)  # Rate limiting between counties
                result = process_county_parcel_linkage(county)
                results.append(result)
    
    if not args.discover_only and results:
        # Summary
        total_linked = sum(r['linked'] for r in results)
        total_checked = sum(r['checked'] for r in results)
        logger.info(f"Session complete: {total_linked} parcels linked from {total_checked} checked across {len(results)} counties")
        
        for result in results:
            county = result['county']
            if 'error' in result:
                logger.info(f"{county}: ERROR - {result['error']}")
            else:
                logger.info(f"{county}: {result['linked']}/{result['checked']} parcels linked")

if __name__ == "__main__":
    main()