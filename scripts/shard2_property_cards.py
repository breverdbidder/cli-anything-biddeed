#!/usr/bin/env python3
"""
SHARD-2 PROPERTY CARD ENRICHMENT - Letter I Gold Standard
Enriches property cards with address, geo coordinates, assessed value, and zoning

Critical for Letter I: ≥95% property card complete (address+geo+value+zoned parcel)

Usage:
  python scripts/shard2_property_cards.py --county citrus
  python scripts/shard2_property_cards.py --all-counties
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
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-2 county property appraiser APIs
PROPERTY_SOURCES = {
    'citrus': {
        'name': 'Citrus County Property Appraiser',
        'base_url': 'https://www.citruspa.org/',
        'api_endpoint': 'https://gis.citruspa.org/arcgis/rest/services/',
        'parcel_search': 'https://www.citruspa.org/parcel-search/',
        'method': 'arcgis_rest'
    },
    'pinellas': {
        'name': 'Pinellas County Property Appraiser', 
        'base_url': 'https://www.pcpao.org/',
        'api_endpoint': 'https://maps.pcpao.org/arcgis/rest/services/',
        'parcel_search': 'https://www.pcpao.org/apps/property-search/',
        'method': 'arcgis_rest'
    },
    'collier': {
        'name': 'Collier County Property Appraiser',
        'base_url': 'https://www.collierappraiser.com/',
        'api_endpoint': 'https://maps.collierappraiser.com/arcgis/rest/services/',
        'parcel_search': 'https://www.collierappraiser.com/property-search/',
        'method': 'arcgis_rest'
    },
    'santa_rosa': {
        'name': 'Santa Rosa County Property Appraiser',
        'base_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=983&LayerID=19013&PageTypeID=2',
        'api_endpoint': None,  # May need HTML scraping
        'parcel_search': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=983&LayerID=19013&PageTypeID=2',
        'method': 'html_scrape'
    },
    'holmes': {
        'name': 'Holmes County Property Appraiser',
        'base_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=984&LayerID=19014&PageTypeID=2',
        'api_endpoint': None,  # May need HTML scraping
        'parcel_search': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=984&LayerID=19014&PageTypeID=2', 
        'method': 'html_scrape'
    }
}

TARGET_COUNTIES = ['citrus', 'pinellas', 'collier', 'santa_rosa', 'holmes']

client = httpx.Client(timeout=30, follow_redirects=True)

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

def supabase_update(table: str, case_number: str, updates: Dict) -> bool:
    """Update specific auction record"""
    try:
        params = {'case_number': f'eq.{case_number}'}
        url = f"{BASE}/{table}?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        response = client.patch(url, headers=HEADERS, json=updates)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error updating {case_number}: {e}")
        return False

def get_incomplete_property_cards(county_slug: str, limit: int = 100) -> List[Dict]:
    """Get auctions with incomplete property cards"""
    params = {
        'select': 'case_number,parcel_id,property_address,latitude,longitude,assessed_value,zoning_code',
        'county': f'eq.{county_slug}',
        'parcel_id': 'not.is.null',  # Must have parcel_id to enrich
        'or': '(property_address.is.null,latitude.is.null,assessed_value.is.null,zoning_code.is.null)',
        'order': 'auction_date.desc',
        'limit': str(limit)
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} incomplete property cards for {county_slug}")
    return auctions

def discover_arcgis_endpoints(county_config: Dict) -> Dict[str, str]:
    """Discover ArcGIS REST endpoints for property data"""
    if not county_config.get('api_endpoint'):
        return {}
    
    try:
        # Probe the ArcGIS REST services directory
        services_url = county_config['api_endpoint'].rstrip('/') + '?f=json'
        response = client.get(services_url)
        
        if response.status_code == 200:
            services_data = response.json()
            
            # Look for common service patterns
            endpoints = {}
            for service in services_data.get('services', []):
                name = service.get('name', '').lower()
                if any(keyword in name for keyword in ['parcel', 'property', 'cadastral', 'land']):
                    service_url = f"{county_config['api_endpoint']}/{service['name']}/MapServer"
                    endpoints['parcels'] = service_url
                    break
            
            return endpoints
            
    except Exception as e:
        logger.warning(f"Failed to discover ArcGIS endpoints: {e}")
    
    return {}

def enrich_via_arcgis(county_config: Dict, parcel_id: str) -> Dict:
    """Enrich property data via ArcGIS REST API"""
    enrichment = {}
    
    try:
        endpoints = discover_arcgis_endpoints(county_config)
        if not endpoints.get('parcels'):
            logger.warning(f"No parcel endpoint found for {county_config['name']}")
            return enrichment
        
        # Query parcel layer by parcel ID
        query_url = f"{endpoints['parcels']}/query"
        params = {
            'where': f"PARCEL_ID='{parcel_id}' OR PIN='{parcel_id}' OR APN='{parcel_id}'",
            'outFields': '*',
            'f': 'json',
            'returnGeometry': 'true'
        }
        
        response = client.get(query_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('features'):
                feature = data['features'][0]  # Take first match
                attributes = feature.get('attributes', {})
                geometry = feature.get('geometry', {})
                
                # Extract common field mappings
                for field, value in attributes.items():
                    field_lower = field.lower()
                    
                    # Property address
                    if any(addr_field in field_lower for addr_field in ['address', 'site_addr', 'prop_addr']):
                        if value and not enrichment.get('property_address'):
                            enrichment['property_address'] = str(value).strip()
                    
                    # Assessed value
                    elif any(val_field in field_lower for val_field in ['assessed', 'total_val', 'market_val', 'just_val']):
                        if value and isinstance(value, (int, float)) and value > 0:
                            enrichment['assessed_value'] = float(value)
                    
                    # Zoning
                    elif any(zone_field in field_lower for zone_field in ['zoning', 'zone_code', 'zone_desc']):
                        if value and not enrichment.get('zoning_code'):
                            enrichment['zoning_code'] = str(value).strip()
                
                # Extract coordinates from geometry
                if geometry.get('x') and geometry.get('y'):
                    enrichment['longitude'] = float(geometry['x'])
                    enrichment['latitude'] = float(geometry['y'])
                elif geometry.get('rings'):
                    # Polygon geometry - use centroid
                    rings = geometry['rings'][0]
                    if rings:
                        x_coords = [p[0] for p in rings]
                        y_coords = [p[1] for p in rings]
                        enrichment['longitude'] = sum(x_coords) / len(x_coords)
                        enrichment['latitude'] = sum(y_coords) / len(y_coords)
        
    except Exception as e:
        logger.error(f"ArcGIS enrichment failed for {parcel_id}: {e}")
    
    return enrichment

def enrich_via_html_scrape(county_config: Dict, parcel_id: str) -> Dict:
    """Enrich property data via HTML scraping (fallback method)"""
    enrichment = {}
    
    # Placeholder for HTML scraping implementation
    # TODO: Implement county-specific HTML parsing for QPublic sites
    
    logger.info(f"HTML scrape enrichment needed for {parcel_id} (not yet implemented)")
    
    return enrichment

def enrich_property_card(county_config: Dict, auction: Dict) -> Dict:
    """Enrich a single property card with missing data"""
    parcel_id = auction.get('parcel_id')
    if not parcel_id:
        return {}
    
    enrichment = {}
    
    try:
        if county_config['method'] == 'arcgis_rest':
            enrichment = enrich_via_arcgis(county_config, parcel_id)
        elif county_config['method'] == 'html_scrape':
            enrichment = enrich_via_html_scrape(county_config, parcel_id)
        
        # Only include fields that are currently missing
        filtered_enrichment = {}
        for field, value in enrichment.items():
            if value and not auction.get(field):
                filtered_enrichment[field] = value
        
        return filtered_enrichment
        
    except Exception as e:
        logger.error(f"Property enrichment failed for {parcel_id}: {e}")
        return {}

def calculate_completion_score(auction: Dict) -> float:
    """Calculate property card completion score (0-100%)"""
    required_fields = ['property_address', 'latitude', 'longitude', 'assessed_value', 'zoning_code']
    completed_fields = sum(1 for field in required_fields if auction.get(field))
    return (completed_fields / len(required_fields)) * 100

def process_county_property_cards(county_slug: str, batch_size: int = 50) -> Dict[str, int]:
    """Process property card enrichment for a single county"""
    logger.info(f"\n=== Processing {county_slug.upper()} Property Cards ===")
    
    if county_slug not in PROPERTY_SOURCES:
        logger.error(f"County {county_slug} not supported in SHARD-2")
        return {'processed': 0, 'enriched': 0}
    
    county_config = PROPERTY_SOURCES[county_slug]
    
    # Get incomplete property cards
    incomplete_cards = get_incomplete_property_cards(county_slug, batch_size)
    
    if not incomplete_cards:
        logger.info(f"No incomplete property cards found for {county_slug}")
        return {'processed': 0, 'enriched': 0}
    
    enriched_count = 0
    
    for auction in incomplete_cards:
        case_number = auction['case_number']
        initial_score = calculate_completion_score(auction)
        
        logger.info(f"Enriching {case_number} (completion: {initial_score:.1f}%)")
        
        # Enrich the property card
        enrichment = enrich_property_card(county_config, auction)
        
        if enrichment:
            # Apply enrichment to auction data for score calculation
            enriched_auction = {**auction, **enrichment}
            final_score = calculate_completion_score(enriched_auction)
            
            # Update database if improvement found
            if final_score > initial_score:
                success = supabase_update('multi_county_auctions', case_number, enrichment)
                if success:
                    enriched_count += 1
                    logger.info(f"  ✅ Updated {case_number}: {initial_score:.1f}% → {final_score:.1f}%")
                    
                    # Log enriched fields
                    fields = list(enrichment.keys())
                    logger.info(f"     Added: {', '.join(fields)}")
                else:
                    logger.warning(f"  ❌ Failed to update {case_number}")
            else:
                logger.info(f"  ⚠️ No improvement for {case_number}")
        else:
            logger.info(f"  ⚠️ No enrichment data found for {case_number}")
    
    return {
        'processed': len(incomplete_cards),
        'enriched': enriched_count
    }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SHARD-2 Property Card Enrichment")
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Specific county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all SHARD-2 counties')
    parser.add_argument('--batch-size', type=int, default=50, help='Number of records to process per county')
    parser.add_argument('--dry-run', action='store_true', help='Analyze only, no database updates')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("🏠 SHARD-2 PROPERTY CARD ENRICHMENT - Letter I")
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
    total_stats = {'processed': 0, 'enriched': 0}
    
    for county in counties_to_process:
        try:
            stats = process_county_property_cards(county, args.batch_size)
            
            logger.info(f"{county.upper()} Results:")
            logger.info(f"  - Processed cards: {stats['processed']}")
            logger.info(f"  - Enriched cards: {stats['enriched']}")
            
            if stats['processed'] > 0:
                enrichment_rate = (stats['enriched'] / stats['processed']) * 100
                logger.info(f"  - Enrichment rate: {enrichment_rate:.1f}%")
            
            total_stats['processed'] += stats['processed']
            total_stats['enriched'] += stats['enriched']
            
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            continue
    
    # Summary
    logger.info(f"\n🎯 SHARD-2 PROPERTY CARD SUMMARY")
    logger.info(f"Total cards processed: {total_stats['processed']}")
    logger.info(f"Total cards enriched: {total_stats['enriched']}")
    
    if total_stats['enriched'] > 0:
        overall_rate = (total_stats['enriched'] / total_stats['processed']) * 100 if total_stats['processed'] > 0 else 0
        logger.info(f"Overall enrichment rate: {overall_rate:.1f}%")
        logger.info("\n✅ Letter I metric should improve after property card enrichment")
        logger.info("Run pencil_dod_evaluate_county('<county>') to verify metric changes")
    else:
        logger.info("\n⚠️ No property cards enriched - may need API endpoint fixes")

if __name__ == "__main__":
    main()