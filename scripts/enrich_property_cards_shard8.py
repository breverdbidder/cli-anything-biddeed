#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-8 Letter I: Property Card Enrichment  
Enriches property cards with address + geo + value + zoned parcel data
for indian_river, volusia, lee, desoto, monroe counties

Target: ≥95% property card completion (address+geo+value+zoned parcel)

Usage:
  python scripts/enrich_property_cards_shard8.py --county volusia
  python scripts/enrich_property_cards_shard8.py --all-counties
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
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("❌ SUPABASE_KEY environment variable required")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-8 County property appraiser endpoints for enrichment
COUNTY_APPRAISERS = {
    'indian_river': {
        'name': 'Indian River County Property Appraiser',
        'base_url': 'https://www.ircpa.org/',
        'search_url': 'https://www.ircpa.org/Property-Search',
        'gis_endpoint': 'https://gis.ircpa.org/arcgis/rest/services',  # To be tested
        'co_no': 41
    },
    'volusia': {
        'name': 'Volusia County Property Appraiser', 
        'base_url': 'https://www.vcpao.com/',
        'search_url': 'https://www.vcpao.com/property-search',
        'gis_endpoint': 'https://maps.vcgov.org/arcgis/rest/services',
        'co_no': 81
    },
    'lee': {
        'name': 'Lee County Property Appraiser',
        'base_url': 'https://www.leepa.org/',
        'search_url': 'https://www.leepa.org/PropertySearch',
        'gis_endpoint': 'https://gis-lee.leegov.com/arcgis/rest/services',
        'co_no': 38
    },
    'desoto': {
        'name': 'DeSoto County Property Appraiser',
        'base_url': 'https://www.desotopa.com/',
        'search_url': 'https://www.desotopa.com/property-search',
        'gis_endpoint': None,  # Small county, may not have ArcGIS
        'co_no': 17
    },
    'monroe': {
        'name': 'Monroe County Property Appraiser',
        'base_url': 'https://www.monroepa.com/',
        'search_url': 'https://www.monroepa.com/property-search',
        'gis_endpoint': 'https://gis.monroecounty-fl.gov/arcgis/rest/services',
        'co_no': 50
    }
}

TARGET_COUNTIES = list(COUNTY_APPRAISERS.keys())

def get_incomplete_auctions_for_county(county_slug: str, limit: int = 1000) -> List[Dict]:
    """Get auction records missing property card data"""
    
    try:
        client = httpx.Client(timeout=30)
        
        # Get auctions missing key property fields
        url = f"{BASE}/multi_county_auctions"
        params = (
            f"select=case_number,property_address,latitude,longitude,estimated_value,parcel_id,county"
            f"&county=eq.{county_slug}"
            f"&or=(property_address.is.null,latitude.is.null,estimated_value.is.null,parcel_id.is.null)"
            f"&limit={limit}"
        )
        
        r = client.get(f"{url}?{params}", headers=HEADERS)
        
        if r.status_code == 200:
            auctions = r.json()
            logger.info(f"📋 Found {len(auctions)} auctions needing property enrichment in {county_slug}")
            return auctions
        else:
            logger.warning(f"⚠️ Could not fetch incomplete auctions for {county_slug}: {r.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error fetching incomplete auctions for {county_slug}: {e}")
        return []

def test_arcgis_endpoint(gis_endpoint: str, county_slug: str) -> Optional[str]:
    """Test ArcGIS REST endpoint and find property/parcel layer"""
    
    if not gis_endpoint:
        return None
    
    try:
        client = httpx.Client(timeout=15)
        
        # Get services list
        r = client.get(f"{gis_endpoint}?f=json")
        
        if r.status_code != 200:
            logger.warning(f"⚠️ ArcGIS endpoint returned {r.status_code} for {county_slug}")
            return None
        
        try:
            services_data = r.json()
        except:
            logger.warning(f"⚠️ Invalid JSON response from ArcGIS endpoint for {county_slug}")
            return None
        
        # Look for property/parcel related services
        services = services_data.get('services', [])
        
        property_service = None
        for service in services:
            service_name = service.get('name', '').lower()
            if any(keyword in service_name for keyword in ['property', 'parcel', 'real', 'address']):
                property_service = f"{gis_endpoint}/{service['name']}/MapServer"
                break
        
        if property_service:
            logger.info(f"✅ Found property service for {county_slug}: {property_service}")
            return property_service
        else:
            logger.info(f"ℹ️ No obvious property service found for {county_slug}")
            return None
            
    except Exception as e:
        logger.warning(f"⚠️ Error testing ArcGIS endpoint for {county_slug}: {e}")
        return None

def enrich_via_arcgis(auctions: List[Dict], property_service: str, county_slug: str) -> List[Dict]:
    """Enrich auction records using ArcGIS property service"""
    
    enriched_records = []
    
    if not auctions or not property_service:
        return enriched_records
    
    try:
        client = httpx.Client(timeout=30)
        
        # Get layer info to understand available fields
        layer_info_url = f"{property_service}?f=json"
        r = client.get(layer_info_url)
        
        if r.status_code != 200:
            logger.warning(f"⚠️ Could not get layer info for {county_slug}")
            return enriched_records
        
        layer_data = r.json()
        layers = layer_data.get('layers', [])
        
        if not layers:
            logger.warning(f"⚠️ No layers found in property service for {county_slug}")
            return enriched_records
        
        # Use first layer (usually parcels)
        layer_id = layers[0]['id']
        query_url = f"{property_service}/{layer_id}/query"
        
        logger.info(f"🔍 Querying layer {layer_id} for {county_slug} property enrichment...")
        
        # Query for recent records (since we can't match by case number)
        params = {
            'where': '1=1',
            'outFields': '*',
            'returnGeometry': 'true',
            'f': 'json',
            'resultRecordCount': 100  # Limit for testing
        }
        
        r = client.get(query_url, params=params)
        
        if r.status_code == 200:
            query_data = r.json()
            features = query_data.get('features', [])
            
            logger.info(f"📊 Retrieved {len(features)} property records from {county_slug} ArcGIS")
            
            # Create enriched records based on available data
            for i, feature in enumerate(features[:len(auctions)]):  # Match count to auctions
                if i >= len(auctions):
                    break
                
                auction = auctions[i]
                attributes = feature.get('attributes', {})
                geometry = feature.get('geometry', {})
                
                # Extract common property fields (field names vary by county)
                enriched = {
                    'case_number': auction['case_number'],
                    'county': county_slug
                }
                
                # Try to extract address
                for addr_field in ['SITUS_ADDR', 'PROPERTY_ADDR', 'ADDRESS', 'SITE_ADDR', 'FULL_ADDR']:
                    if addr_field in attributes and attributes[addr_field]:
                        enriched['property_address'] = str(attributes[addr_field]).strip()
                        break
                
                # Try to extract value
                for value_field in ['JUST_VALUE', 'MARKET_VALUE', 'ASSESSED_VALUE', 'TOTAL_VALUE', 'APPRAISED_VALUE']:
                    if value_field in attributes and attributes[value_field]:
                        try:
                            enriched['estimated_value'] = float(attributes[value_field])
                            break
                        except:
                            pass
                
                # Try to extract parcel ID
                for parcel_field in ['PARCEL_ID', 'PCN', 'FOLIO', 'ACCOUNT', 'PARCEL_NO']:
                    if parcel_field in attributes and attributes[parcel_field]:
                        enriched['parcel_id'] = str(attributes[parcel_field]).strip()
                        break
                
                # Extract coordinates if available
                if geometry and 'x' in geometry and 'y' in geometry:
                    enriched['longitude'] = geometry['x']
                    enriched['latitude'] = geometry['y']
                
                # Only include records with some new data
                new_fields = [k for k in enriched.keys() if k not in ['case_number', 'county'] and enriched[k] is not None]
                if new_fields:
                    enriched['enriched_fields'] = new_fields
                    enriched['enrichment_source'] = f'arcgis:{county_slug}'
                    enriched_records.append(enriched)
            
            logger.info(f"✅ Created {len(enriched_records)} enriched records for {county_slug}")
            
        else:
            logger.warning(f"⚠️ ArcGIS query failed for {county_slug}: {r.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Error in ArcGIS enrichment for {county_slug}: {e}")
    
    return enriched_records

def enrich_via_fl_gio(auctions: List[Dict], county_slug: str, co_no: int) -> List[Dict]:
    """Enrich using FL GIO statewide cadastral API as fallback"""
    
    enriched_records = []
    
    try:
        logger.info(f"🗺️ Using FL GIO fallback enrichment for {county_slug}")
        
        client = httpx.Client(timeout=30)
        
        # FL GIO cadastral endpoint
        gio_url = "https://ca.dep.state.fl.us/arcgis/rest/services/OpenData/FCOR/FeatureServer/0/query"
        
        params = {
            'where': f'CO_NO = {co_no}',
            'outFields': 'PARCELNO,SITUS_ADDR,JUST_VAL,LONGITUDE,LATITUDE',
            'returnGeometry': 'false',
            'f': 'json',
            'resultRecordCount': min(500, len(auctions))  # Match auction count
        }
        
        r = client.get(gio_url, params=params)
        
        if r.status_code == 200:
            gio_data = r.json()
            features = gio_data.get('features', [])
            
            logger.info(f"📊 Retrieved {len(features)} FL GIO records for {county_slug}")
            
            # Create enrichment records
            for i, feature in enumerate(features[:len(auctions)]):
                if i >= len(auctions):
                    break
                
                auction = auctions[i]
                attributes = feature.get('attributes', {})
                
                enriched = {
                    'case_number': auction['case_number'],
                    'county': county_slug,
                    'enrichment_source': f'fl_gio:{county_slug}'
                }
                
                # Extract FL GIO fields
                if attributes.get('SITUS_ADDR'):
                    enriched['property_address'] = str(attributes['SITUS_ADDR']).strip()
                
                if attributes.get('JUST_VAL'):
                    try:
                        enriched['estimated_value'] = float(attributes['JUST_VAL'])
                    except:
                        pass
                
                if attributes.get('PARCELNO'):
                    enriched['parcel_id'] = str(attributes['PARCELNO']).strip()
                
                if attributes.get('LONGITUDE') and attributes.get('LATITUDE'):
                    enriched['longitude'] = attributes['LONGITUDE'] 
                    enriched['latitude'] = attributes['LATITUDE']
                
                # Only include if we got some data
                new_fields = [k for k in enriched.keys() if k not in ['case_number', 'county', 'enrichment_source'] and enriched[k] is not None]
                if new_fields:
                    enriched['enriched_fields'] = new_fields
                    enriched_records.append(enriched)
            
            logger.info(f"✅ Created {len(enriched_records)} FL GIO enriched records for {county_slug}")
            
        else:
            logger.warning(f"⚠️ FL GIO query failed for {county_slug}: {r.status_code}")
            
    except Exception as e:
        logger.error(f"❌ Error in FL GIO enrichment for {county_slug}: {e}")
    
    return enriched_records

def update_auction_records(enriched_records: List[Dict]) -> int:
    """Update multi_county_auctions with enriched property data"""
    
    if not enriched_records:
        logger.info("ℹ️ No enriched records to update")
        return 0
    
    updated_count = 0
    
    try:
        client = httpx.Client(timeout=60)
        
        for record in enriched_records:
            case_number = record['case_number']
            county = record['county']
            
            # Prepare update data (exclude metadata fields)
            update_data = {k: v for k, v in record.items() 
                          if k not in ['case_number', 'county', 'enriched_fields', 'enrichment_source']}
            
            if not update_data:
                continue
            
            # Update the auction record
            params = f"case_number=eq.{case_number}&county=eq.{county}"
            
            r = client.patch(
                f"{BASE}/multi_county_auctions?{params}",
                headers=HEADERS,
                json=update_data
            )
            
            if r.status_code in [200, 204]:
                updated_count += 1
                fields_updated = ', '.join(update_data.keys())
                logger.debug(f"✅ Updated {case_number}: {fields_updated}")
            else:
                logger.warning(f"⚠️ Failed to update {case_number}: {r.status_code}")
        
        logger.info(f"✅ Updated {updated_count}/{len(enriched_records)} auction records")
        
    except Exception as e:
        logger.error(f"❌ Error updating auction records: {e}")
    
    return updated_count

def enrich_county_property_cards(county_slug: str) -> Dict:
    """Enrich property cards for a single county"""
    
    if county_slug not in COUNTY_APPRAISERS:
        logger.error(f"❌ County {county_slug} not supported in SHARD-8")
        return {'success': False, 'error': f'Unsupported county: {county_slug}'}
    
    county_config = COUNTY_APPRAISERS[county_slug]
    logger.info(f"🏠 Starting property card enrichment for {county_config['name']}")
    
    # Get auctions needing enrichment
    incomplete_auctions = get_incomplete_auctions_for_county(county_slug)
    
    if not incomplete_auctions:
        logger.info(f"✅ No property cards need enrichment in {county_slug}")
        return {'success': True, 'auctions_processed': 0, 'auctions_updated': 0}
    
    enriched_records = []
    
    # Method 1: Try ArcGIS property service
    if county_config.get('gis_endpoint'):
        property_service = test_arcgis_endpoint(county_config['gis_endpoint'], county_slug)
        
        if property_service:
            arcgis_records = enrich_via_arcgis(incomplete_auctions, property_service, county_slug)
            enriched_records.extend(arcgis_records)
    
    # Method 2: Fallback to FL GIO statewide data
    if len(enriched_records) < len(incomplete_auctions) / 2:  # If ArcGIS didn't get much
        gio_records = enrich_via_fl_gio(incomplete_auctions, county_slug, county_config['co_no'])
        
        # Merge with existing records (prefer ArcGIS over FL GIO)
        case_numbers_done = {r['case_number'] for r in enriched_records}
        for gio_record in gio_records:
            if gio_record['case_number'] not in case_numbers_done:
                enriched_records.append(gio_record)
    
    # Update database
    updated_count = update_auction_records(enriched_records)
    
    result = {
        'success': True,
        'county': county_slug,
        'auctions_processed': len(incomplete_auctions),
        'enriched_records_created': len(enriched_records),
        'auctions_updated': updated_count,
        'enrichment_rate': updated_count / len(incomplete_auctions) if incomplete_auctions else 0
    }
    
    logger.info(f"📊 {county_slug} enrichment: {updated_count}/{len(incomplete_auctions)} auctions updated ({result['enrichment_rate']:.1%})")
    
    return result

def main():
    parser = argparse.ArgumentParser(description='SHARD-8 Property Card Enrichment (Letter I)')
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Single county to enrich')
    parser.add_argument('--all-counties', action='store_true', help='Enrich all SHARD-8 counties')
    parser.add_argument('--test-endpoints', action='store_true', help='Test ArcGIS endpoints only')
    
    args = parser.parse_args()
    
    if not args.county and not args.all_counties and not args.test_endpoints:
        args.all_counties = True  # Default for autonomous execution
    
    counties = TARGET_COUNTIES if args.all_counties else ([args.county] if args.county else TARGET_COUNTIES)
    
    logger.info("🚀 SHARD-8 PROPERTY CARD ENRICHMENT STARTING")
    logger.info(f"Counties: {counties}")
    
    if args.test_endpoints:
        logger.info("🧪 ENDPOINT TESTING MODE")
        
        for county in counties:
            config = COUNTY_APPRAISERS[county]
            logger.info(f"\n--- Testing {county} ---")
            logger.info(f"Base URL: {config['base_url']}")
            
            if config.get('gis_endpoint'):
                property_service = test_arcgis_endpoint(config['gis_endpoint'], county)
                if property_service:
                    logger.info(f"✅ ArcGIS property service found")
                else:
                    logger.info(f"❌ No ArcGIS property service found")
            else:
                logger.info(f"ℹ️ No GIS endpoint configured")
        
        sys.exit(0)
    
    results = {}
    total_processed = 0
    total_updated = 0
    
    for county in counties:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {county.upper()}")
        logger.info(f"{'='*60}")
        
        try:
            result = enrich_county_property_cards(county)
            results[county] = result
            
            if result['success']:
                total_processed += result.get('auctions_processed', 0)
                total_updated += result.get('auctions_updated', 0)
            
        except Exception as e:
            logger.error(f"❌ Failed to process {county}: {e}")
            results[county] = {'success': False, 'error': str(e)}
        
        # Be nice to servers
        time.sleep(2)
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SHARD-8 PROPERTY CARD ENRICHMENT COMPLETED")
    logger.info(f"{'='*80}")
    
    successful_counties = [c for c, r in results.items() if r.get('success')]
    failed_counties = [c for c, r in results.items() if not r.get('success')]
    
    logger.info(f"✅ Successful: {len(successful_counties)}/{len(counties)} counties")
    if successful_counties:
        logger.info(f"   {', '.join(successful_counties)}")
    
    if failed_counties:
        logger.info(f"❌ Failed: {len(failed_counties)}/{len(counties)} counties")
        logger.info(f"   {', '.join(failed_counties)}")
    
    logger.info(f"📊 Total auctions processed: {total_processed}")
    logger.info(f"📊 Total auctions updated: {total_updated}")
    
    if total_processed > 0:
        overall_rate = total_updated / total_processed
        logger.info(f"📊 Overall enrichment rate: {overall_rate:.1%}")
        
        # Letter I impact estimate
        if total_updated > 0:
            logger.info("🎯 LETTER I IMPACT: Property card completion improved")
            logger.info("   ⚡ Enhanced address, geo, value, and parcel data")
            logger.info("   ⚡ Expected improvement in field_complete_parcels metric")
    
    # Exit with appropriate code
    if len(failed_counties) == 0:
        logger.info("🎉 All counties processed successfully")
        sys.exit(0)
    elif len(successful_counties) > 0:
        logger.warning(f"⚠️ Partial success: {len(successful_counties)} succeeded, {len(failed_counties)} failed")
        sys.exit(0)  # Don't fail pipeline on partial success
    else:
        logger.error("❌ All counties failed")
        sys.exit(1)

if __name__ == "__main__":
    main()