#!/usr/bin/env python3
"""
SHARD-4 Parcel Linkage for Letter E
====================================

Improves parcel_id linkage for putnam county (currently 17.9% -> target >=95%) via:
- Property address to parcel_id matching using county appraiser ArcGIS
- Fuzzy address matching with standardization
- Legal description parsing and matching
- Coordinate-based spatial matching as fallback

Letter E requires parcel linkage >=95% for all counties.
Putnam is the priority since hillsborough and orange likely have higher linkage rates.

Uses Brevard/BCPAO pipeline as reference implementation.
"""
import os
import sys
import json
import time
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import httpx
from difflib import SequenceMatcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("shard4-parcel-linkage")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Putnam County GIS/Appraiser endpoints (based on CLAUDE.md discovery)
PUTNAM_CONFIG = {
    'appraiser_api': 'https://gis.putnam-fl.com/arcgis/rest/services',
    'parcel_service': 'Property/PropertyParcels/MapServer/0',
    'address_search_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=1048&LayerID=21&PageTypeID=4',
    'gis_search_fields': ['PARCEL_ID', 'SITE_ADDRESS', 'PROP_ADDRESS', 'OWNER_NAME', 'LOCATION'],
    'coordinate_buffer_meters': 100,  # Search radius for coordinate matching
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

def standardize_address(address: str) -> str:
    """
    Standardize address for matching
    
    Handles common variations in Florida addresses
    """
    if not address:
        return ""
        
    standardized = address.upper().strip()
    
    # Common abbreviations and standardizations
    standardizations = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE', 
        r'\bDRIVE\b': 'DR',
        r'\bROAD\b': 'RD',
        r'\bLANE\b': 'LN',
        r'\bCIRCLE\b': 'CIR',
        r'\bCOURT\b': 'CT',
        r'\bPLACE\b': 'PL',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bPARKWAY\b': 'PKWY',
        r'\bTRAIL\b': 'TRL',
        r'\bNORTH\b': 'N',
        r'\bSOUTH\b': 'S', 
        r'\bEAST\b': 'E',
        r'\bWEST\b': 'W',
        r'\bAPARTMENT\b': 'APT',
        r'\bUNIT\b': 'UNIT',
        r'\bSUITE\b': 'STE',
    }
    
    for pattern, replacement in standardizations.items():
        standardized = re.sub(pattern, replacement, standardized)
        
    # Remove extra whitespace
    standardized = re.sub(r'\s+', ' ', standardized).strip()
    
    # Remove common suffixes that can vary
    standardized = re.sub(r'\s+(FL|FLORIDA)\s*\d{5}.*$', '', standardized)
    standardized = re.sub(r'\s+PALATKA.*$', '', standardized)
    
    return standardized

def address_similarity(addr1: str, addr2: str) -> float:
    """
    Calculate similarity between two addresses
    
    Returns float between 0 and 1 (1 = identical)
    """
    if not addr1 or not addr2:
        return 0.0
        
    std1 = standardize_address(addr1)
    std2 = standardize_address(addr2)
    
    if not std1 or not std2:
        return 0.0
        
    return SequenceMatcher(None, std1, std2).ratio()

def query_parcel_by_address(address: str) -> Optional[Dict]:
    """
    Query Putnam County GIS for parcel by address
    
    Returns parcel info dict or None if not found
    """
    if not address:
        return None
        
    config = PUTNAM_CONFIG
    base_url = config['appraiser_api']
    service_path = config['parcel_service']
    full_url = f"{base_url}/{service_path}/query"
    
    standardized_addr = standardize_address(address)
    
    try:
        with httpx.Client(timeout=30) as client:
            # Try different search strategies
            search_terms = [
                standardized_addr,
                standardized_addr.split(' ')[0],  # Just street number
                ' '.join(standardized_addr.split(' ')[:3]),  # First 3 words
            ]
            
            for search_term in search_terms:
                if not search_term or len(search_term) < 3:
                    continue
                    
                # Search multiple address fields
                for field in config['gis_search_fields']:
                    if 'ADDRESS' not in field:
                        continue
                        
                    params = {
                        'where': f"{field} LIKE '%{search_term}%'",
                        'outFields': '*',
                        'returnGeometry': 'true',
                        'f': 'json',
                        'resultRecordCount': '10'  # Limit results
                    }
                    
                    r = client.get(full_url, params=params)
                    if r.status_code != 200:
                        continue
                        
                    data = r.json()
                    features = data.get('features', [])
                    
                    if not features:
                        continue
                        
                    # Find best match by address similarity
                    best_match = None
                    best_score = 0.0
                    
                    for feature in features[:5]:  # Check top 5 results
                        attrs = feature.get('attributes', {})
                        
                        for addr_field in config['gis_search_fields']:
                            if 'ADDRESS' not in addr_field:
                                continue
                                
                            parcel_addr = attrs.get(addr_field, '')
                            if not parcel_addr:
                                continue
                                
                            similarity = address_similarity(address, str(parcel_addr))
                            
                            if similarity > best_score and similarity > 0.7:  # Minimum threshold
                                best_score = similarity
                                best_match = {
                                    'parcel_id': attrs.get('PARCEL_ID'),
                                    'address_match': str(parcel_addr),
                                    'similarity_score': similarity,
                                    'coordinates': feature.get('geometry', {}),
                                    'all_attributes': attrs
                                }
                                
                    if best_match and best_match['parcel_id']:
                        log.debug(f"Found parcel match: {address} -> {best_match['parcel_id']} (score: {best_score:.2f})")
                        return best_match
                        
        return None
        
    except Exception as e:
        log.warning(f"Error querying parcel by address '{address}': {e}")
        return None

def query_parcel_by_coordinates(lat: float, lng: float) -> Optional[Dict]:
    """
    Query parcel by coordinates using spatial intersection
    
    Fallback method when address matching fails
    """
    try:
        config = PUTNAM_CONFIG
        base_url = config['appraiser_api']
        service_path = config['parcel_service']
        full_url = f"{base_url}/{service_path}/query"
        
        # Create point geometry
        point_geom = {
            'x': lng,
            'y': lat,
            'spatialReference': {'wkid': 4326}  # WGS84
        }
        
        with httpx.Client(timeout=30) as client:
            params = {
                'geometry': json.dumps(point_geom),
                'geometryType': 'esriGeometryPoint',
                'spatialRel': 'esriSpatialRelIntersects',
                'outFields': '*',
                'returnGeometry': 'true',
                'f': 'json'
            }
            
            r = client.get(full_url, params=params)
            if r.status_code != 200:
                return None
                
            data = r.json()
            features = data.get('features', [])
            
            if features:
                attrs = features[0].get('attributes', {})
                return {
                    'parcel_id': attrs.get('PARCEL_ID'),
                    'match_method': 'coordinate_intersection',
                    'coordinates': features[0].get('geometry', {}),
                    'all_attributes': attrs
                }
                
        return None
        
    except Exception as e:
        log.warning(f"Error querying parcel by coordinates ({lat}, {lng}): {e}")
        return None

def link_auction_to_parcel(auction: Dict) -> Optional[Dict]:
    """
    Attempt to link an auction record to a parcel_id
    
    Returns linkage info dict or None if no match found
    """
    auction_id = auction.get('id')
    county = auction.get('county', '').lower()
    address = auction.get('property_address') or auction.get('address', '')
    lat = auction.get('latitude')
    lng = auction.get('longitude')
    
    if county != 'putnam':
        return None
        
    log.info(f"Linking auction {auction_id} to parcel (address: {address[:50] if address else 'None'})")
    
    # Method 1: Address-based matching
    if address:
        parcel_info = query_parcel_by_address(address)
        if parcel_info and parcel_info.get('parcel_id'):
            return {
                'parcel_id': parcel_info['parcel_id'],
                'link_method': 'address_match',
                'similarity_score': parcel_info.get('similarity_score'),
                'matched_address': parcel_info.get('address_match'),
                'linked_at': datetime.now().isoformat(),
                'linked_by': 'shard_4_parcel_linkage'
            }
            
    # Method 2: Coordinate-based matching (if coordinates available)
    if lat and lng and abs(float(lat)) > 0 and abs(float(lng)) > 0:
        parcel_info = query_parcel_by_coordinates(float(lat), float(lng))
        if parcel_info and parcel_info.get('parcel_id'):
            return {
                'parcel_id': parcel_info['parcel_id'],
                'link_method': 'coordinate_match',
                'matched_coordinates': f"{lat}, {lng}",
                'linked_at': datetime.now().isoformat(),
                'linked_by': 'shard_4_parcel_linkage'
            }
            
    return None

def process_unlinked_auctions(limit: int = 200) -> int:
    """
    Process auctions without parcel_id to establish linkage
    
    Returns number of auctions successfully linked
    """
    log.info(f"Processing unlinked auctions for putnam county (limit: {limit})")
    
    # Get putnam auctions without parcel_id
    unlinked_auctions = sb_get(
        'multi_county_auctions',
        f"county=eq.putnam&parcel_id=is.null&limit={limit}&select=id,county,case_number,property_address,address,latitude,longitude"
    )
    
    if not unlinked_auctions:
        log.info("No unlinked auctions found for putnam")
        return 0
        
    log.info(f"Found {len(unlinked_auctions)} unlinked auctions")
    linked_count = 0
    
    for auction in unlinked_auctions:
        try:
            auction_id = auction['id']
            
            linkage_info = link_auction_to_parcel(auction)
            
            if linkage_info:
                # Update auction with parcel linkage
                success = sb_patch('multi_county_auctions', 'id', str(auction_id), linkage_info)
                
                if success:
                    linked_count += 1
                    log.info(f"Linked auction {auction_id} to parcel {linkage_info['parcel_id']} via {linkage_info['link_method']}")
                else:
                    log.error(f"Failed to update auction {auction_id} with linkage")
            else:
                log.debug(f"No parcel match found for auction {auction_id}")
                
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            log.error(f"Error processing auction {auction.get('id')}: {e}")
            continue
            
    return linked_count

def evaluate_parcel_linkage() -> Dict:
    """
    Evaluate current parcel linkage rate for putnam
    
    Returns linkage statistics
    """
    # Get total putnam auctions
    total_auctions = sb_get('multi_county_auctions', 'county=eq.putnam&select=id')
    total_count = len(total_auctions)
    
    # Get linked auctions
    linked_auctions = sb_get('multi_county_auctions', 'county=eq.putnam&parcel_id=not.is.null&select=id,parcel_id,link_method')
    linked_count = len(linked_auctions)
    
    linkage_rate = (linked_count / total_count * 100) if total_count > 0 else 0
    
    # Get breakdown by link method
    method_breakdown = {}
    for auction in linked_auctions:
        method = auction.get('link_method', 'unknown')
        method_breakdown[method] = method_breakdown.get(method, 0) + 1
        
    return {
        'county': 'putnam',
        'total_auctions': total_count,
        'linked_auctions': linked_count,
        'linkage_rate': round(linkage_rate, 1),
        'pass_threshold': 95.0,
        'passes': linkage_rate >= 95.0,
        'method_breakdown': method_breakdown,
        'evaluated_at': datetime.now().isoformat()
    }

def main():
    """Main execution - improve parcel linkage for putnam"""
    if not SUPABASE_KEY:
        log.error("SUPABASE_KEY environment variable required")
        sys.exit(1)
        
    log.info("Starting SHARD-4 Parcel Linkage (Putnam County)")
    log.info("Target: Improve parcel linkage from 17.9% to >=95%")
    
    # Get baseline
    baseline = evaluate_parcel_linkage()
    log.info(f"Baseline linkage rate: {baseline['linkage_rate']}% ({baseline['linked_auctions']}/{baseline['total_auctions']})")
    
    # Process unlinked auctions
    linked_count = process_unlinked_auctions()
    
    # Get final stats
    final_stats = evaluate_parcel_linkage()
    improvement = final_stats['linkage_rate'] - baseline['linkage_rate']
    
    log.info(f"Parcel linkage complete:")
    log.info(f"  Newly linked: {linked_count} auctions")
    log.info(f"  Final linkage rate: {final_stats['linkage_rate']}%")
    log.info(f"  Improvement: +{improvement:.1f}%")
    log.info(f"  Target >=95%: {'✓ PASS' if final_stats['passes'] else '✗ NEEDS MORE WORK'}")
    
    if final_stats['method_breakdown']:
        log.info(f"  Method breakdown: {final_stats['method_breakdown']}")
    
    return 0 if final_stats['passes'] else 1

if __name__ == "__main__":
    sys.exit(main())