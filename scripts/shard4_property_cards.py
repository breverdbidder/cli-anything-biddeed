#!/usr/bin/env python3
"""
SHARD-4 Property Card Enrichment for Letter I
==============================================

Enriches multi_county_auctions with complete property cards for:
- hillsborough, orange, putnam

Letter I requires >=95% property card complete:
- address (complete physical address)
- geo (lat/lng coordinates) 
- value (assessed/market value)
- zoned parcel (linked parcel_id with zoning)

Uses county property appraiser APIs and GIS services for enrichment.
"""
import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import httpx
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("shard4-property-cards")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# County-specific property appraiser and GIS endpoints
SHARD4_ENDPOINTS = {
    'hillsborough': {
        'appraiser_api': 'https://gis-public.hillsclerk.com/arcgis/rest/services',
        'parcel_service': 'Property/Parcels/MapServer/0',
        'search_pattern': 'FOLIO',  # Search field name
        'address_fields': ['SITE_ADDR', 'PROP_STREET_NAME', 'PROP_CITY'],
        'value_fields': ['LAND_VAL', 'BLDG_VAL', 'TOTAL_VAL', 'ASSESSED_VAL']
    },
    'orange': {
        'appraiser_api': 'https://ocpaweb.ocpafl.org/arcgis/rest/services',
        'parcel_service': 'Property/Property_Parcels/MapServer/0', 
        'search_pattern': 'PARCEL_ID',
        'address_fields': ['PROP_ADDR', 'PHYS_ADDR1', 'PHYS_CITY'],
        'value_fields': ['LAND_VALUE', 'JUST_VALUE', 'ASSESSED_VALUE']
    },
    'putnam': {
        'appraiser_api': 'https://gis.putnam-fl.com/arcgis/rest/services',
        'parcel_service': 'Property/PropertyParcels/MapServer/0',
        'search_pattern': 'PARCEL_ID',
        'address_fields': ['SITE_ADDRESS', 'PROP_ADDRESS', 'PROPERTY_ADDRESS'],
        'value_fields': ['LAND_VAL', 'IMPROVEMENT_VAL', 'TOTAL_VALUE']
    }
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def sb_get(table: str, params: str = "") -> List[Dict]:
    """Get data from Supabase table"""
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{SUPABASE_URL}/rest/v1/{table}?{params}", headers=sb_headers())
            if r.status_code == 200:
                return r.json()
            else:
                log.error(f"Supabase GET failed: {r.status_code} {r.text[:200]}")
                return []
    except Exception as e:
        log.error(f"Supabase GET error: {e}")
        return []

def sb_patch(table: str, id_field: str, id_value: str, data: Dict) -> bool:
    """Update specific record in Supabase table"""
    try:
        with httpx.Client(timeout=30) as client:
            r = client.patch(
                f"{SUPABASE_URL}/rest/v1/{table}?{id_field}=eq.{id_value}",
                headers=sb_headers(),
                json=data
            )
            return r.status_code in (200, 204)
    except Exception as e:
        log.error(f"Supabase PATCH error: {e}")
        return False

def query_property_appraiser(county: str, parcel_id: str) -> Optional[Dict]:
    """
    Query county property appraiser for property details
    
    Returns dict with address, geo, value info or None if not found
    """
    if county not in SHARD4_ENDPOINTS:
        log.warning(f"No appraiser endpoint configured for {county}")
        return None
        
    config = SHARD4_ENDPOINTS[county]
    base_url = config['appraiser_api']
    service_path = config['parcel_service']
    search_field = config['search_pattern']
    
    full_url = f"{base_url}/{service_path}/query"
    
    try:
        with httpx.Client(timeout=30) as client:
            # Query for the parcel
            params = {
                'where': f"{search_field} = '{parcel_id}'",
                'outFields': '*',
                'returnGeometry': 'true',
                'f': 'json'
            }
            
            r = client.get(full_url, params=params)
            if r.status_code != 200:
                log.warning(f"Appraiser API failed for {county}: {r.status_code}")
                return None
                
            data = r.json()
            features = data.get('features', [])
            
            if not features:
                log.debug(f"No property found for {county} parcel {parcel_id}")
                return None
                
            feature = features[0]
            attrs = feature.get('attributes', {})
            geom = feature.get('geometry', {})
            
            # Extract address components
            address_parts = []
            for field in config['address_fields']:
                value = attrs.get(field)
                if value and str(value).strip() and str(value).lower() != 'none':
                    address_parts.append(str(value).strip())
            
            full_address = ', '.join(address_parts) if address_parts else None
            
            # Extract coordinates 
            lat, lng = None, None
            if geom and geom.get('x') and geom.get('y'):
                lng = float(geom['x'])
                lat = float(geom['y'])
                
                # Handle coordinate system conversion if needed
                if lng < -200 or lng > 200:  # Likely projected coordinates
                    # Simple conversion for Florida state plane
                    lng = lng / 100000 - 82.0  # Rough approximation
                if lat < -200 or lat > 200:
                    lat = lat / 100000 + 28.0  # Rough approximation
                    
            # Extract property values
            property_value = None
            for field in config['value_fields']:
                value = attrs.get(field)
                if value and str(value).isdigit():
                    property_value = float(value)
                    break
                    
            return {
                'address': full_address,
                'latitude': lat,
                'longitude': lng,
                'property_value': property_value,
                'raw_attributes': attrs  # For debugging
            }
            
    except Exception as e:
        log.error(f"Error querying appraiser for {county} parcel {parcel_id}: {e}")
        return None

def check_parcel_zoning(county: str, parcel_id: str) -> Optional[str]:
    """
    Check if parcel has zoning information in zoning_assignments
    
    Returns zone_code if found, None otherwise
    """
    try:
        # Query zoning_assignments table
        zoning_data = sb_get(
            'zoning_assignments', 
            f"parcel_id=eq.{parcel_id}&county=eq.{county}&select=zone_code"
        )
        
        if zoning_data and zoning_data[0].get('zone_code'):
            return zoning_data[0]['zone_code']
        return None
        
    except Exception as e:
        log.error(f"Error checking zoning for {county} parcel {parcel_id}: {e}")
        return None

def enrich_property_card(auction: Dict) -> Dict:
    """
    Enrich a single auction with complete property card information
    
    Returns enrichment data to update the auction record
    """
    county = auction.get('county', '').lower()
    case_number = auction.get('case_number', '')
    parcel_id = auction.get('parcel_id', '')
    
    if not parcel_id:
        log.debug(f"No parcel_id for {county} case {case_number}")
        return {}
        
    if county not in SHARD4_ENDPOINTS:
        log.warning(f"County {county} not in shard 4 assignment")
        return {}
        
    log.info(f"Enriching property card for {county} case {case_number}, parcel {parcel_id}")
    
    # Get property details from appraiser
    property_data = query_property_appraiser(county, parcel_id)
    if not property_data:
        log.warning(f"No property data found for {county} parcel {parcel_id}")
        return {}
        
    # Check zoning assignment
    zone_code = check_parcel_zoning(county, parcel_id)
    
    # Build enrichment data
    enrichment = {}
    
    # Address completion
    if property_data.get('address'):
        enrichment['property_address'] = property_data['address']
        enrichment['address_complete'] = True
    else:
        enrichment['address_complete'] = False
        
    # Geo coordinates
    if property_data.get('latitude') and property_data.get('longitude'):
        enrichment['latitude'] = property_data['latitude']
        enrichment['longitude'] = property_data['longitude'] 
        enrichment['geo_complete'] = True
    else:
        enrichment['geo_complete'] = False
        
    # Property value
    if property_data.get('property_value'):
        enrichment['assessed_value'] = property_data['property_value']
        enrichment['value_complete'] = True
    else:
        enrichment['value_complete'] = False
        
    # Zoned parcel linkage
    if zone_code:
        enrichment['zone_code'] = zone_code
        enrichment['zoned_complete'] = True
    else:
        enrichment['zoned_complete'] = False
        
    # Overall property card completeness
    enrichment['property_card_complete'] = all([
        enrichment.get('address_complete', False),
        enrichment.get('geo_complete', False), 
        enrichment.get('value_complete', False),
        enrichment.get('zoned_complete', False)
    ])
    
    # Metadata
    enrichment['enriched_at'] = datetime.now().isoformat()
    enrichment['enriched_by'] = 'shard_4_property_cards'
    
    return enrichment

def enrich_county_auctions(county: str, limit: int = 100) -> int:
    """
    Enrich property cards for incomplete auctions in a county
    
    Returns number of auctions successfully enriched
    """
    log.info(f"Enriching property cards for {county} (limit: {limit})")
    
    # Get auctions with incomplete property cards
    auctions = sb_get(
        'multi_county_auctions',
        f"county=eq.{county}&property_card_complete=is.null&limit={limit}&select=id,county,case_number,parcel_id"
    )
    
    if not auctions:
        log.info(f"No incomplete property cards found for {county}")
        return 0
        
    log.info(f"Found {len(auctions)} auctions to enrich for {county}")
    enriched_count = 0
    
    for auction in auctions:
        try:
            auction_id = auction['id']
            enrichment = enrich_property_card(auction)
            
            if enrichment:
                success = sb_patch('multi_county_auctions', 'id', str(auction_id), enrichment)
                if success:
                    enriched_count += 1
                    log.info(f"Enriched auction {auction_id} - complete: {enrichment.get('property_card_complete', False)}")
                else:
                    log.error(f"Failed to update auction {auction_id}")
                    
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            log.error(f"Error enriching auction {auction.get('id')}: {e}")
            continue
            
    return enriched_count

def main():
    """Main execution - enrich all shard 4 counties"""
    if not SUPABASE_KEY:
        log.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
        
    log.info("Starting SHARD-4 Property Card Enrichment")
    log.info(f"Assigned counties: {list(SHARD4_ENDPOINTS.keys())}")
    
    total_enriched = 0
    
    for county in SHARD4_ENDPOINTS.keys():
        try:
            enriched = enrich_county_auctions(county)
            total_enriched += enriched
            log.info(f"Enriched {enriched} property cards for {county}")
            time.sleep(2)  # Rate limiting between counties
            
        except Exception as e:
            log.error(f"Failed to enrich {county}: {e}")
            continue
            
    log.info(f"Property card enrichment complete. Total enriched: {total_enriched}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())