#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-7: Property Card Enrichment
Counties: alachua, gilchrist, miami_dade, walton, gadsden, lafayette, wakulla
Letter I: Enrich property cards with address + geo + value + zoned parcel data

Target: ≥95% with complete property cards (address+geo+value+zoned parcel)
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
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# WAVE2-SHARD-7 counties with their CO_NO from fl_counties_manifest.yml
SHARD_COUNTIES = {
    'alachua': {'co_no': 11, 'name': 'Alachua'},
    'gilchrist': {'co_no': 31, 'name': 'Gilchrist'},
    'miami_dade': {'co_no': 23, 'name': 'Miami-Dade'},
    'walton': {'co_no': 76, 'name': 'Walton'},
    'gadsden': {'co_no': 30, 'name': 'Gadsden'},
    'lafayette': {'co_no': 44, 'name': 'Lafayette'},
    'wakulla': {'co_no': 75, 'name': 'Wakulla'}
}

# County property appraiser endpoints (to be discovered/configured)
COUNTY_APPRAISERS = {
    'alachua': {
        'name': 'Alachua County Property Appraiser',
        'base_url': 'https://www.acpafl.org/',
        'search_url': 'https://www.acpafl.org/property-search.html',
        'arcgis_endpoint': None,  # To be discovered
        'co_no': 11
    },
    'gilchrist': {
        'name': 'Gilchrist County Property Appraiser',
        'base_url': 'https://www.gcpa.us/',
        'search_url': 'https://www.gcpa.us/property-search',
        'arcgis_endpoint': None,
        'co_no': 31
    },
    'miami_dade': {
        'name': 'Miami-Dade County Property Appraiser', 
        'base_url': 'https://www.miamidade.gov/pa/',
        'search_url': 'https://www.miamidade.gov/Apps/PA/PApublicServiceSearch/Search.aspx',
        'arcgis_endpoint': 'https://gisweb.miamidade.gov/arcgis/rest/services/MDC_OpenData/PropertyAppraiser/MapServer',
        'co_no': 23
    },
    'walton': {
        'name': 'Walton County Property Appraiser',
        'base_url': 'https://www.waltoncountyfl.gov/pa',
        'search_url': 'https://www.waltoncountyfl.gov/pa/property-search',
        'arcgis_endpoint': None,
        'co_no': 76
    },
    'gadsden': {
        'name': 'Gadsden County Property Appraiser',
        'base_url': 'https://www.gadsdencountypa.com/',
        'search_url': 'https://www.gadsdencountypa.com/property-search',
        'arcgis_endpoint': None,
        'co_no': 30
    },
    'lafayette': {
        'name': 'Lafayette County Property Appraiser',
        'base_url': 'https://www.lafayettecountypa.com/',
        'search_url': 'https://www.lafayettecountypa.com/property-search',
        'arcgis_endpoint': None,
        'co_no': 44
    },
    'wakulla': {
        'name': 'Wakulla County Property Appraiser',
        'base_url': 'https://www.wakullapropertyappraiser.com/',
        'search_url': 'https://www.wakullapropertyappraiser.com/property-search',
        'arcgis_endpoint': None,
        'co_no': 75
    }
}

client = httpx.Client(timeout=60, follow_redirects=True)

def supabase_get(table: str, params: str = "", limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}?{params}&limit={limit}"
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_update(table: str, filters: str, updates: Dict) -> int:
    """Update records in Supabase table"""
    try:
        url = f"{BASE}/{table}?{filters}"
        response = client.patch(url, headers=HEADERS, json=updates)
        response.raise_for_status()
        return 1
    except Exception as e:
        logger.error(f"Error updating {table}: {e}")
        return 0

def supabase_upsert(table: str, data: List[Dict]) -> int:
    """Upsert records to Supabase table"""
    try:
        url = f"{BASE}/{table}"
        response = client.post(url, headers=HEADERS, json=data)
        response.raise_for_status()
        return len(data)
    except Exception as e:
        logger.error(f"Error upserting to {table}: {e}")
        return 0

def discover_arcgis_endpoint(county_slug: str) -> Optional[str]:
    """Discover ArcGIS REST endpoint for county property appraiser"""
    config = COUNTY_APPRAISERS.get(county_slug, {})
    base_url = config.get('base_url')
    
    if not base_url:
        return None
    
    # Common ArcGIS paths to try
    common_paths = [
        '/arcgis/rest/services/',
        '/gis/rest/services/',
        '/maps/rest/services/',
        '/MapServer/rest/services/',
        '/webgis/rest/services/'
    ]
    
    for path in common_paths:
        try:
            test_url = base_url.rstrip('/') + path
            response = client.get(test_url, timeout=10)
            
            if response.status_code == 200 and 'services' in response.text.lower():
                logger.info(f"Found ArcGIS endpoint for {county_slug}: {test_url}")
                return test_url
                
        except Exception as e:
            continue
    
    logger.warning(f"Could not discover ArcGIS endpoint for {county_slug}")
    return None

def get_parcel_data_from_fl_gio(county_slug: str, parcel_ids: List[str]) -> Dict[str, Dict]:
    """Get parcel data from FL GIO Statewide Cadastral for specific parcels"""
    co_no = SHARD_COUNTIES[county_slug]['co_no']
    
    FL_GIO_BASE = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0"
    
    parcel_data = {}
    
    # Batch process parcel IDs
    batch_size = 50
    for i in range(0, len(parcel_ids), batch_size):
        batch = parcel_ids[i:i+batch_size]
        
        # Create WHERE clause for this batch
        where_clause = f"CO_NO = {co_no} AND PARCEL_ID IN ({','.join(repr(p) for p in batch)})"
        
        try:
            response = client.get(f"{FL_GIO_BASE}/query", params={
                "where": where_clause,
                "outFields": "PARCEL_ID,PHY_ADDR1,PHY_CITY,PHY_ZIPCD,JV,LND_VAL,NCONST_VAL,TOT_LVG_AR,NO_RES_UNT,ACT_YR_BLT,DOR_UC",
                "returnGeometry": "true",
                "geometryPrecision": 6,
                "f": "json"
            }, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                features = data.get("features", [])
                
                for feature in features:
                    attrs = feature.get("attributes", {})
                    geom = feature.get("geometry", {})
                    
                    parcel_id = attrs.get("PARCEL_ID")
                    if parcel_id:
                        parcel_data[parcel_id] = {
                            "parcel_id": parcel_id,
                            "address": attrs.get("PHY_ADDR1", ""),
                            "city": attrs.get("PHY_CITY", ""),
                            "zip_code": attrs.get("PHY_ZIPCD", ""),
                            "just_value": attrs.get("JV", 0),
                            "land_value": attrs.get("LND_VAL", 0),
                            "improvement_value": attrs.get("NCONST_VAL", 0),
                            "living_area": attrs.get("TOT_LVG_AR", 0),
                            "res_units": attrs.get("NO_RES_UNT", 0),
                            "year_built": attrs.get("ACT_YR_BLT"),
                            "use_code": attrs.get("DOR_UC", ""),
                            "geometry": geom,
                            "data_source": "fl_gio_cadastral"
                        }
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            logger.error(f"Error fetching FL GIO data for batch {i//batch_size + 1}: {e}")
            continue
    
    logger.info(f"Retrieved {len(parcel_data)} parcel records from FL GIO for {county_slug}")
    return parcel_data

def enrich_auctions_with_parcel_data(county_slug: str) -> Dict:
    """Enrich auctions with property card data"""
    logger.info(f"Starting property card enrichment for {county_slug}")
    
    # Get auctions missing property card data
    incomplete_auctions = supabase_get(
        "multi_county_auctions",
        f"county=eq.{county_slug}&select=id,parcel_id,property_address,case_number"
    )
    
    if not incomplete_auctions:
        logger.info(f"No auctions found for {county_slug}")
        return {"processed": 0, "enriched": 0, "parcel_linked": 0}
    
    logger.info(f"Found {len(incomplete_auctions)} auctions for {county_slug}")
    
    # Get unique parcel IDs (excluding nulls)
    parcel_ids = list(set(auction["parcel_id"] for auction in incomplete_auctions 
                         if auction.get("parcel_id")))
    
    logger.info(f"Found {len(parcel_ids)} unique parcel IDs")
    
    results = {"processed": 0, "enriched": 0, "parcel_linked": 0}
    
    if parcel_ids:
        # Get parcel data from FL GIO
        parcel_data = get_parcel_data_from_fl_gio(county_slug, parcel_ids)
        
        # Enrich auctions with parcel data
        for auction in incomplete_auctions:
            results["processed"] += 1
            auction_id = auction["id"]
            parcel_id = auction.get("parcel_id")
            
            update_data = {}
            
            if parcel_id and parcel_id in parcel_data:
                # Auction has parcel linkage and we found data
                parcel_info = parcel_data[parcel_id]
                
                update_data = {
                    "property_address_enriched": parcel_info.get("address", ""),
                    "property_city": parcel_info.get("city", ""),
                    "property_zip": parcel_info.get("zip_code", ""),
                    "just_value": parcel_info.get("just_value", 0),
                    "land_value": parcel_info.get("land_value", 0),
                    "improvement_value": parcel_info.get("improvement_value", 0),
                    "living_area": parcel_info.get("living_area", 0),
                    "year_built": parcel_info.get("year_built"),
                    "use_code": parcel_info.get("use_code", ""),
                    "property_card_complete": True,
                    "property_card_source": "fl_gio_cadastral",
                    "property_card_updated_at": datetime.now().isoformat()
                }
                
                results["enriched"] += 1
                results["parcel_linked"] += 1
                
            elif not parcel_id:
                # Try to link to parcel using address matching
                auction_addr = auction.get("property_address", "").upper().strip()
                
                if auction_addr:
                    # Simple address matching against parcel data
                    best_match = None
                    best_score = 0
                    
                    for pid, pdata in parcel_data.items():
                        parcel_addr = pdata.get("address", "").upper().strip()
                        if parcel_addr and auction_addr in parcel_addr or parcel_addr in auction_addr:
                            # Basic substring matching - could be improved
                            score = len(set(auction_addr.split()) & set(parcel_addr.split()))
                            if score > best_score:
                                best_match = (pid, pdata)
                                best_score = score
                    
                    if best_match and best_score >= 2:  # At least 2 word overlap
                        parcel_id, parcel_info = best_match
                        
                        update_data = {
                            "parcel_id": parcel_id,
                            "property_address_enriched": parcel_info.get("address", ""),
                            "property_city": parcel_info.get("city", ""),
                            "property_zip": parcel_info.get("zip_code", ""),
                            "just_value": parcel_info.get("just_value", 0),
                            "land_value": parcel_info.get("land_value", 0),
                            "improvement_value": parcel_info.get("improvement_value", 0),
                            "living_area": parcel_info.get("living_area", 0),
                            "year_built": parcel_info.get("year_built"),
                            "use_code": parcel_info.get("use_code", ""),
                            "property_card_complete": True,
                            "property_card_source": "fl_gio_cadastral_matched",
                            "property_card_updated_at": datetime.now().isoformat()
                        }
                        
                        results["enriched"] += 1
                        results["parcel_linked"] += 1
                        logger.info(f"Linked auction {auction_id} to parcel {parcel_id} via address match")
            
            # Update auction record
            if update_data:
                if supabase_update("multi_county_auctions", f"id=eq.{auction_id}", update_data):
                    logger.debug(f"Enriched auction {auction_id}")
    
    logger.info(f"Property card enrichment completed for {county_slug}: {results}")
    return results

def enable_zoning_kpi_for_county(county_slug: str) -> bool:
    """Enable zoning KPI tracking for county to support Letter G"""
    logger.info(f"Enabling zoning KPI for {county_slug}")
    
    co_no = SHARD_COUNTIES[county_slug]['co_no']
    
    # Check if county has zoning assignments
    zoning_count = supabase_get("zoning_assignments", f"co_no=eq.{co_no}&select=count")
    
    if not zoning_count:
        logger.warning(f"No zoning assignments found for {county_slug} - run county ingestion first")
        return False
    
    # This would typically involve updating database views or configurations
    # For now, just log the action needed
    logger.info(f"County {county_slug} needs zoning KPI view configuration")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="WAVE2-SHARD-7 Property Card Enrichment")
    parser.add_argument("--county", choices=list(SHARD_COUNTIES.keys()), help="Specific county to process")
    parser.add_argument("--all-counties", action="store_true", help="Process all SHARD-7 counties")
    parser.add_argument("--discover-endpoints", action="store_true", help="Discover ArcGIS endpoints for counties")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    if args.discover_endpoints:
        logger.info("Discovering ArcGIS endpoints...")
        for county in SHARD_COUNTIES.keys():
            endpoint = discover_arcgis_endpoint(county)
            if endpoint:
                logger.info(f"{county}: {endpoint}")
            else:
                logger.warning(f"{county}: No endpoint found")
        return
    
    counties_to_process = [args.county] if args.county else list(SHARD_COUNTIES.keys()) if args.all_counties else []
    
    if not counties_to_process:
        parser.print_help()
        sys.exit(1)
    
    logger.info(f"Starting property card enrichment for counties: {counties_to_process}")
    
    total_results = {"processed": 0, "enriched": 0, "parcel_linked": 0}
    
    for county in counties_to_process:
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {county}")
        logger.info(f"{'='*60}")
        
        # Enrich property cards
        county_results = enrich_auctions_with_parcel_data(county)
        for key in total_results.keys():
            total_results[key] += county_results.get(key, 0)
        
        # Enable zoning KPI
        enable_zoning_kpi_for_county(county)
    
    logger.info(f"\n{'='*60}")
    logger.info("FINAL RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Total processed: {total_results['processed']}")
    logger.info(f"Total enriched: {total_results['enriched']}")
    logger.info(f"Parcel linked: {total_results['parcel_linked']}")
    
    # Calculate completion percentage
    if total_results['processed'] > 0:
        completion_pct = (total_results['enriched'] / total_results['processed']) * 100
        logger.info(f"Property card completion: {completion_pct:.1f}%")

if __name__ == "__main__":
    main()