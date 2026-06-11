#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-6 Letters E + I: Parcel Linkage + Property Card Enrichment
Links auctions to parcels and enriches with address + geo + value + zoned parcel data
for highlands, sumter, jackson, calhoun, liberty counties

Usage:
  python scripts/shard6_property_enrichment.py --county highlands
  python scripts/shard6_property_enrichment.py --all-counties
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

# SHARD-6 County property appraiser endpoints for enrichment
COUNTY_APPRAISERS = {
    'highlands': {
        'name': 'Highlands County Property Appraiser',
        'base_url': 'https://www.hcpao.org/',
        'search_url': 'https://www.hcpao.org/Property-Search',
        'gis_endpoint': None,  # To be discovered
        'co_no': 38
    },
    'sumter': {
        'name': 'Sumter County Property Appraiser',
        'base_url': 'https://www.sumtercountypao.com/',
        'search_url': 'https://www.sumtercountypao.com/PropertySearch',
        'gis_endpoint': None,
        'co_no': 70
    },
    'jackson': {
        'name': 'Jackson County Property Appraiser', 
        'base_url': 'https://www.jacksoncountypao.com/',
        'search_url': 'https://www.jacksoncountypao.com/PropertySearch',
        'gis_endpoint': None,
        'co_no': 42
    },
    'calhoun': {
        'name': 'Calhoun County Property Appraiser',
        'base_url': 'https://www.calhouncountypao.com/',
        'search_url': 'https://www.calhouncountypao.com/PropertySearch',
        'gis_endpoint': None,
        'co_no': 17
    },
    'liberty': {
        'name': 'Liberty County Property Appraiser',
        'base_url': 'https://www.libertycountypao.com/',
        'search_url': 'https://www.libertycountypao.com/PropertySearch', 
        'gis_endpoint': None,
        'co_no': 49
    }
}

client = httpx.Client(timeout=30, follow_redirects=True)

def supabase_get(table: str, params: Dict = None, limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        query_params = {'limit': str(limit)}
        if params:
            query_params.update(params)
        
        response = client.get(url, headers=HEADERS, params=query_params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_upsert(table: str, data: List[Dict]) -> int:
    """Upsert data to Supabase table"""
    if not data:
        return 0
        
    try:
        response = client.post(f"{BASE}/{table}", headers=HEADERS, json=data)
        response.raise_for_status()
        logger.info(f"Successfully upserted {len(data)} records to {table}")
        return len(data)
    except Exception as e:
        logger.error(f"Error upserting to {table}: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Response: {e.response.text}")
        return 0

def get_auctions_needing_parcel_linkage(county_slug: str) -> List[Dict]:
    """Get auctions missing parcel_id (Letter E)"""
    
    params = {
        'select': 'case_number,address,auction_date,sale_type,auction_status,winning_bid,parcel_id',
        'county': f'eq.{county_slug}',
        'parcel_id': 'is.null',  # Missing parcel linkage
        'limit': '1000'
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} auctions needing parcel linkage for {county_slug}")
    return auctions

def get_incomplete_property_cards(county_slug: str) -> List[Dict]:
    """Get auction properties missing address, geo, value, or zoned parcel data (Letter I)"""
    
    co_no = COUNTY_APPRAISERS[county_slug]['co_no']
    
    # Get auctions that need property enrichment
    params = {
        'select': 'case_number,parcel_id,address,winning_bid,auction_status,sale_type',
        'county': f'eq.{county_slug}',
        'limit': '1000'
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    
    # Check which ones need enrichment (missing address, geo, value, or zoning)
    incomplete = []
    for auction in auctions:
        needs_enrichment = False
        missing_fields = []
        
        if not auction.get('address') or auction['address'].strip() == '':
            needs_enrichment = True
            missing_fields.append('address')
            
        if not auction.get('parcel_id'):
            needs_enrichment = True 
            missing_fields.append('parcel_id')
        
        # Check if we have corresponding sample_properties record with geo/value
        if auction.get('parcel_id'):
            sample_props = supabase_get('sample_properties', {
                'parcel_id': f'eq.{auction["parcel_id"]}',
                'select': 'lat,lng,just_value,assessed_value'
            }, limit=1)
            
            if not sample_props or not sample_props[0].get('lat'):
                needs_enrichment = True
                missing_fields.append('geo')
                
            if not sample_props or not sample_props[0].get('just_value'):
                needs_enrichment = True
                missing_fields.append('value')
        
        # Check zoning assignment
        if auction.get('parcel_id'):
            zoning = supabase_get('zoning_assignments', {
                'parcel_id': f'eq.{auction["parcel_id"]}',
                'co_no': f'eq.{co_no}',
                'select': 'zone_code'
            }, limit=1)
            
            if not zoning or not zoning[0].get('zone_code'):
                needs_enrichment = True
                missing_fields.append('zoning')
        
        if needs_enrichment:
            auction['missing_fields'] = missing_fields
            incomplete.append(auction)
    
    logger.info(f"Found {len(incomplete)} properties needing enrichment for {county_slug}")
    return incomplete

def enrich_from_fl_gio_parcels(parcel_id: str, co_no: int) -> Optional[Dict]:
    """Enrich property data from FL GIO Statewide Cadastral"""
    
    try:
        # FL GIO API endpoint
        base_url = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
        
        params = {
            'where': f"PARCEL_ID = '{parcel_id}' AND CO_NO = {co_no}",
            'outFields': 'PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,NCONST_VAL,TOT_LVG_AR,DOR_UC,NO_RES_UNT,ACT_YR_BLT',
            'returnGeometry': 'true',
            'geometryType': 'esriGeometryPoint',
            'spatialRel': 'esriSpatialRelIntersects',
            'outSR': '4326',
            'f': 'json'
        }
        
        response = client.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        features = data.get('features', [])
        
        if not features:
            logger.warning(f"No FL GIO data found for parcel {parcel_id}")
            return None
            
        feature = features[0]
        attributes = feature['attributes']
        geometry = feature.get('geometry', {})
        
        # Extract enrichment data
        enriched = {
            'parcel_id': parcel_id,
            'address': f"{attributes.get('PHY_ADDR1', '')}, {attributes.get('PHY_CITY', '')}, FL {attributes.get('PHY_ZIPCD', '')}".strip(),
            'latitude': geometry.get('y'),
            'longitude': geometry.get('x'), 
            'just_value': attributes.get('JV'),
            'land_value': attributes.get('LND_VAL'),
            'improvement_value': attributes.get('NCONST_VAL'),
            'total_living_area': attributes.get('TOT_LVG_AR'),
            'dor_use_code': attributes.get('DOR_UC'),
            'residential_units': attributes.get('NO_RES_UNT'),
            'year_built': attributes.get('ACT_YR_BLT'),
            'data_source': 'fl_gio_statewide'
        }
        
        # Clean up address
        if enriched['address'].startswith(', '):
            enriched['address'] = enriched['address'][2:]
        
        return enriched
        
    except Exception as e:
        logger.error(f"Error enriching from FL GIO for parcel {parcel_id}: {e}")
        return None

def search_parcel_by_address(address: str, co_no: int) -> Optional[str]:
    """Search for parcel_id using address via FL GIO"""
    
    if not address or address.strip() == '':
        return None
    
    try:
        # Clean address for search
        clean_address = address.strip().upper()
        
        # FL GIO API endpoint for address search
        base_url = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query"
        
        params = {
            'where': f"CO_NO = {co_no} AND UPPER(PHY_ADDR1) LIKE '%{clean_address[:20]}%'",
            'outFields': 'PARCEL_ID,PHY_ADDR1',
            'returnGeometry': 'false',
            'f': 'json'
        }
        
        response = client.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        features = data.get('features', [])
        
        if features:
            # Return the first matching parcel
            return features[0]['attributes']['PARCEL_ID']
        
        return None
        
    except Exception as e:
        logger.error(f"Error searching parcel for address {address}: {e}")
        return None

def link_parcels_to_auctions(county_slug: str) -> int:
    """Link parcels to auctions that are missing parcel_id (Letter E)"""
    
    co_no = COUNTY_APPRAISERS[county_slug]['co_no']
    auctions_needing_linkage = get_auctions_needing_parcel_linkage(county_slug)
    
    if not auctions_needing_linkage:
        logger.info(f"No auctions need parcel linkage for {county_slug}")
        return 0
    
    logger.info(f"Linking parcels for {len(auctions_needing_linkage)} auctions in {county_slug}")
    
    linked_count = 0
    for auction in auctions_needing_linkage:
        if auction.get('address'):
            parcel_id = search_parcel_by_address(auction['address'], co_no)
            if parcel_id:
                # Update the auction with parcel_id
                try:
                    response = client.patch(
                        f"{BASE}/multi_county_auctions?case_number=eq.{auction['case_number']}",
                        headers={**HEADERS, "Prefer": "return=minimal"},
                        json={'parcel_id': parcel_id}
                    )
                    if response.status_code in [200, 204]:
                        linked_count += 1
                        logger.debug(f"Linked parcel {parcel_id} to case {auction['case_number']}")
                except Exception as e:
                    logger.error(f"Error linking parcel to {auction['case_number']}: {e}")
    
    logger.info(f"Successfully linked {linked_count} parcels for {county_slug}")
    return linked_count

def update_multi_county_auctions(enriched_data: List[Dict]) -> int:
    """Update multi_county_auctions with enriched address data"""
    
    if not enriched_data:
        return 0
    
    updates = []
    for data in enriched_data:
        if data.get('address') and data.get('case_number'):
            updates.append({
                'case_number': data['case_number'],
                'address': data['address'],
                'parcel_id': data['parcel_id']
            })
    
    if updates:
        updated_count = 0
        for update in updates:
            try:
                response = client.patch(
                    f"{BASE}/multi_county_auctions?case_number=eq.{update['case_number']}",
                    headers={**HEADERS, "Prefer": "return=minimal"},
                    json={
                        'address': update['address'],
                        'parcel_id': update['parcel_id']
                    }
                )
                if response.status_code in [200, 204]:
                    updated_count += 1
            except Exception as e:
                logger.error(f"Error updating auction {update['case_number']}: {e}")
        
        logger.info(f"Updated {updated_count} auction records with enriched addresses")
        return updated_count
    
    return 0

def update_sample_properties(enriched_data: List[Dict]) -> int:
    """Update sample_properties with enriched geo and value data"""
    
    if not enriched_data:
        return 0
    
    updates = []
    for data in enriched_data:
        if data.get('parcel_id'):
            update = {
                'parcel_id': data['parcel_id'],
                'lat': data.get('latitude'),
                'lng': data.get('longitude'),
                'just_value': data.get('just_value'),
                'land_value': data.get('land_value'),
                'improvement_value': data.get('improvement_value'),
                'total_living_area': data.get('total_living_area'),
                'year_built': data.get('year_built'),
                'enriched_at': datetime.now().isoformat()
            }
            
            # Remove None values
            update = {k: v for k, v in update.items() if v is not None}
            
            if len(update) > 2:  # More than just parcel_id and enriched_at
                updates.append(update)
    
    if updates:
        updated_count = supabase_upsert('sample_properties', updates)
        logger.info(f"Updated {updated_count} sample_properties records")
        return updated_count
    
    return 0

def create_zoning_assignments(enriched_data: List[Dict], county_slug: str) -> int:
    """Create zoning assignments from enriched DOR use code data"""
    
    if not enriched_data:
        return 0
    
    co_no = COUNTY_APPRAISERS[county_slug]['co_no']
    
    # DOR use code to zone code mapping (from ingest_county.py)
    DOR_UC_MAP = {
        "000": "VAC-RES",   "001": "SFR",       "002": "MH",        "003": "MFR-10",
        "004": "MFR-CONDO", "005": "COOP",      "006": "RETIRE",    "007": "MISC-RES",
        "008": "MFR",       "009": "RES-COMMON", "010": "VAC-COM",   "011": "RETAIL",
        "012": "MIXED-USE", "013": "DEPT-STORE", "014": "SUPER",     "015": "REGIONAL",
        "016": "COMM-PARK", "017": "OFFICE",     "018": "PROF-SVC",  "019": "HOTEL",
        "020": "VAC-IND",   "021": "LIGHT-IND",  "022": "HEAVY-IND", "023": "LUMBER",
        "024": "PACKING",   "025": "MINING",     "026": "UTIL",      "027": "AUTO-SVC",
        "028": "PARKING",   "029": "WHOLESALE",  "030": "VAC-AG",    "031": "CROP",
        "032": "PASTURE",   "033": "TIMBER",     "034": "DAIRY",     "035": "BEE",
        "036": "NURSERY",   "037": "ORCHARD",    "038": "POULTRY",   "039": "AG-OTHER",
    }
    
    zoning_assignments = []
    for data in enriched_data:
        if data.get('parcel_id') and data.get('dor_use_code'):
            dor_uc = str(data['dor_use_code']).zfill(3)
            zone_code = DOR_UC_MAP.get(dor_uc, f"UC-{dor_uc}")
            
            assignment = {
                'parcel_id': data['parcel_id'],
                'zone_code': zone_code,
                'co_no': co_no,
                'zone_source': 'dor_use_code_enriched',
                'zone_confidence': 'baseline',
                'dor_uc': dor_uc
            }
            
            zoning_assignments.append(assignment)
    
    if zoning_assignments:
        created_count = supabase_upsert('zoning_assignments', zoning_assignments)
        logger.info(f"Created {created_count} zoning assignments for {county_slug}")
        return created_count
    
    return 0

def calculate_parcel_linkage_rate(county_slug: str) -> Dict:
    """Calculate Letter E completion rate for a county"""
    
    try:
        # Get all auctions for this county
        auctions = supabase_get('multi_county_auctions', {
            'county': f'eq.{county_slug}',
            'select': 'case_number,parcel_id'
        })
        
        total_auctions = len(auctions)
        linked_auctions = len([a for a in auctions if a.get('parcel_id')])
        
        linkage_rate = (linked_auctions / total_auctions * 100) if total_auctions > 0 else 0
        
        return {
            'county_slug': county_slug,
            'total_auctions': total_auctions,
            'linked_auctions': linked_auctions,
            'linkage_rate': linkage_rate,
            'letter_e_status': 'PASS' if linkage_rate >= 95.0 else 'FAIL',
            'missing_count': total_auctions - linked_auctions
        }
        
    except Exception as e:
        logger.error(f"Error calculating linkage rate for {county_slug}: {e}")
        return {'error': str(e)}

def calculate_property_card_completion_rate(county_slug: str) -> Dict:
    """Calculate Letter I completion rate for a county"""
    
    try:
        co_no = COUNTY_APPRAISERS[county_slug]['co_no']
        
        # Get all auctions for this county
        auctions = supabase_get('multi_county_auctions', {
            'county': f'eq.{county_slug}',
            'select': 'case_number,parcel_id,address'
        })
        
        total_auctions = len(auctions)
        complete_cards = 0
        
        for auction in auctions:
            has_address = bool(auction.get('address') and auction['address'].strip())
            has_parcel = bool(auction.get('parcel_id'))
            has_geo = False
            has_value = False  
            has_zoning = False
            
            if has_parcel:
                # Check geo and value from sample_properties
                sample_props = supabase_get('sample_properties', {
                    'parcel_id': f'eq.{auction["parcel_id"]}',
                    'select': 'lat,lng,just_value'
                }, limit=1)
                
                if sample_props:
                    has_geo = bool(sample_props[0].get('lat') and sample_props[0].get('lng'))
                    has_value = bool(sample_props[0].get('just_value'))
                
                # Check zoning assignment
                zoning = supabase_get('zoning_assignments', {
                    'parcel_id': f'eq.{auction["parcel_id"]}',
                    'co_no': f'eq.{co_no}',
                    'select': 'zone_code'
                }, limit=1)
                
                has_zoning = bool(zoning and zoning[0].get('zone_code'))
            
            # Letter I requires: address + geo + value + zoned parcel
            if has_address and has_geo and has_value and has_zoning:
                complete_cards += 1
        
        completion_rate = (complete_cards / total_auctions * 100) if total_auctions > 0 else 0
        
        return {
            'county_slug': county_slug,
            'total_auctions': total_auctions,
            'complete_property_cards': complete_cards,
            'completion_rate': completion_rate,
            'letter_i_status': 'PASS' if completion_rate >= 95.0 else 'FAIL',
            'missing_count': total_auctions - complete_cards
        }
        
    except Exception as e:
        logger.error(f"Error calculating completion rate for {county_slug}: {e}")
        return {'error': str(e)}

def enrich_county_properties(county_slug: str) -> Dict:
    """Enrich property cards for a specific county (Letters E + I)"""
    
    logger.info(f"Starting property enrichment for {county_slug}")
    
    # Check current completion rates
    linkage_status = calculate_parcel_linkage_rate(county_slug)
    card_status = calculate_property_card_completion_rate(county_slug)
    
    logger.info(f"Current Letter E status: {linkage_status}")
    logger.info(f"Current Letter I status: {card_status}")
    
    # Step 1: Link parcels to auctions (Letter E)
    linked_count = link_parcels_to_auctions(county_slug)
    
    # Step 2: Get properties needing enrichment
    incomplete_properties = get_incomplete_property_cards(county_slug)
    
    if not incomplete_properties:
        logger.info(f"No properties need enrichment for {county_slug}")
        final_linkage = calculate_parcel_linkage_rate(county_slug)
        final_card = calculate_property_card_completion_rate(county_slug)
        
        return {
            **final_linkage,
            **final_card,
            'linked_count': linked_count,
            'enriched_count': 0
        }
    
    logger.info(f"Enriching {len(incomplete_properties)} properties for {county_slug}")
    
    # Step 3: Enrich properties using FL GIO data
    enriched_data = []
    co_no = COUNTY_APPRAISERS[county_slug]['co_no']
    
    for prop in incomplete_properties[:100]:  # Limit to first 100 for this session
        if prop.get('parcel_id'):
            enriched = enrich_from_fl_gio_parcels(prop['parcel_id'], co_no)
            if enriched:
                enriched['case_number'] = prop['case_number']  # Link back to auction
                enriched_data.append(enriched)
    
    logger.info(f"Successfully enriched {len(enriched_data)} properties from FL GIO")
    
    # Step 4: Update database tables
    updated_auctions = update_multi_county_auctions(enriched_data)
    updated_properties = update_sample_properties(enriched_data)
    created_zoning = create_zoning_assignments(enriched_data, county_slug)
    
    # Step 5: Calculate improvements
    final_linkage = calculate_parcel_linkage_rate(county_slug)
    final_card = calculate_property_card_completion_rate(county_slug)
    
    linkage_improvement = final_linkage['linkage_rate'] - linkage_status['linkage_rate']
    card_improvement = final_card['completion_rate'] - card_status['completion_rate']
    
    result = {
        **final_linkage,
        **final_card,
        'linked_count': linked_count,
        'enriched_count': len(enriched_data),
        'updated_auctions': updated_auctions,
        'updated_properties': updated_properties,
        'created_zoning': created_zoning,
        'linkage_improvement': linkage_improvement,
        'card_improvement': card_improvement
    }
    
    logger.info(f"Property enrichment complete for {county_slug}: Letter E +{linkage_improvement:.1f}%, Letter I +{card_improvement:.1f}%")
    
    return result

def main():
    parser = argparse.ArgumentParser(description='Enrich properties for SHARD-6 Gold Standard Letters E + I')
    parser.add_argument('--county', choices=['highlands', 'sumter', 'jackson', 'calhoun', 'liberty'], 
                       help='County to enrich')
    parser.add_argument('--all-counties', action='store_true',
                       help='Enrich all SHARD-6 counties')
    parser.add_argument('--status-only', action='store_true',
                       help='Check completion status only')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("GOLD STANDARD SHARD-6 LETTERS E + I - Property Enrichment") 
    logger.info("=" * 60)
    
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = ['highlands', 'sumter', 'jackson', 'calhoun', 'liberty']
    elif args.county:
        counties_to_process = [args.county]
    else:
        parser.print_help()
        sys.exit(1)
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county} ---")
        
        if args.status_only:
            linkage_status = calculate_parcel_linkage_rate(county)
            card_status = calculate_property_card_completion_rate(county)
            logger.info(f"Letter E (parcel linkage): {linkage_status}")
            logger.info(f"Letter I (property cards): {card_status}")
        else:
            result = enrich_county_properties(county)
            logger.info(f"Property enrichment result: {result}")
    
    logger.info("\nProperty enrichment complete")

if __name__ == "__main__":
    main()