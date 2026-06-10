#!/usr/bin/env python3
"""
Letter I Property Card Enrichment - GOLD STANDARD SHARD-0
=========================================================

Enriches multi_county_auctions with complete property cards: address + geo + value + zoned parcel.
Target: ≥95% completion for charlotte, brevard, broward counties.

Key components:
- address: standardized property address
- geo: latitude/longitude coordinates  
- value: current assessed/market value from property appraiser
- zoned parcel: parcel_id linked to zoning data

Usage:
    python scripts/letter_i_property_enrichment.py --county charlotte
    python scripts/letter_i_property_enrichment.py --county broward  
    python scripts/letter_i_property_enrichment.py --county brevard
    python scripts/letter_i_property_enrichment.py --all-assigned    # all three counties
"""

import os
import sys
import json
import time
import httpx
import argparse
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from typing import Dict, List, Optional
import re

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

# Property appraiser configuration for each county
APPRAISER_CONFIG = {
    'charlotte': {
        'name': 'Charlotte County Property Appraiser',
        'base_url': 'https://www.ccappraiser.com',
        'search_pattern': '/search?parcel={parcel_id}',
        'gis_endpoint': None  # To be discovered
    },
    'broward': {
        'name': 'Broward County Property Appraiser', 
        'base_url': 'https://bcpa.broward.org',
        'search_pattern': '/Property-Search/Property-Detail?PINNO={parcel_id}',
        'gis_endpoint': None  # To be discovered
    },
    'brevard': {
        'name': 'Brevard County Property Appraiser (BCPAO)',
        'base_url': 'https://brevard.county-taxes.com',
        'search_pattern': '/public/real_estate/parcels/{parcel_id}',
        'gis_endpoint': 'https://gis.brevardcounty.us/arcgis/rest/services'
    }
}

client = httpx.Client(timeout=30, headers={"User-Agent": "BidDeed-GoldStandard-LetterI/1.0"})

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def sb_get(endpoint, params=""):
    r = client.get(f"{SUPABASE_URL}/rest/v1/{endpoint}?{params}", headers=sb_headers())
    if r.status_code == 200:
        return r.json()
    else:
        print(f"ERROR: GET {endpoint} -> {r.status_code}: {r.text[:200]}")
        return []

def sb_patch(endpoint, data):
    r = client.patch(f"{SUPABASE_URL}/rest/v1/{endpoint}", headers=sb_headers(), json=data)
    if r.status_code in (200, 204):
        return True
    else:
        print(f"ERROR: PATCH {endpoint} -> {r.status_code}: {r.text[:200]}")
        return False

def get_incomplete_auctions(county, limit=1000):
    """Get auctions that need property card enrichment."""
    # Query for auctions missing any of the four required components
    # This is a simplified query - in practice would need to check specific columns
    params = f"county=eq.{county}&select=id,case_number,address,parcel_id,lat,lng,assessed_value&limit={limit}"
    
    auctions = sb_get("multi_county_auctions", params)
    
    # Filter for incomplete property cards
    incomplete = []
    for auction in auctions:
        missing_components = []
        
        # Check address
        if not auction.get('address') or auction['address'].strip() == '':
            missing_components.append('address')
            
        # Check geo (lat/lng)
        if not auction.get('lat') or not auction.get('lng'):
            missing_components.append('geo')
            
        # Check value
        if not auction.get('assessed_value'):
            missing_components.append('value')
            
        # Check zoned parcel linkage
        if not auction.get('parcel_id'):
            missing_components.append('zoned_parcel')
            
        if missing_components:
            auction['missing_components'] = missing_components
            incomplete.append(auction)
    
    return incomplete

def normalize_address(raw_address):
    """Standardize address format for consistency."""
    if not raw_address:
        return None
        
    address = raw_address.strip().upper()
    
    # Basic normalization
    address = re.sub(r'\s+', ' ', address)  # Multiple spaces -> single
    address = re.sub(r'\.', '', address)    # Remove periods
    
    # Common abbreviations
    replacements = {
        ' STREET': ' ST',
        ' AVENUE': ' AVE', 
        ' BOULEVARD': ' BLVD',
        ' DRIVE': ' DR',
        ' LANE': ' LN',
        ' ROAD': ' RD',
        ' COURT': ' CT',
        ' PLACE': ' PL'
    }
    
    for old, new in replacements.items():
        address = address.replace(old, new)
    
    return address

def geocode_address(address, county):
    """Get lat/lng coordinates for an address."""
    # This would typically use a geocoding service
    # For now, return None to indicate needs implementation
    return None, None

def lookup_property_value(parcel_id, county):
    """Look up assessed value from county property appraiser."""
    config = APPRAISER_CONFIG.get(county)
    if not config:
        return None
        
    try:
        # This would scrape the property appraiser website
        # Implementation would be county-specific based on their site structure
        # For now, return None to indicate needs implementation
        return None
        
    except Exception as e:
        print(f"    Error looking up value for {parcel_id}: {e}")
        return None

def link_zoned_parcel(parcel_id, county):
    """Verify parcel_id exists in zoning data."""
    if not parcel_id:
        return False
        
    # Check if this parcel exists in zoning_assignments
    zoning_rows = sb_get("zoning_assignments", f"parcel_id=eq.{parcel_id}&county=eq.{county}")
    return len(zoning_rows) > 0

def enrich_property_card(auction, county):
    """Enrich a single auction record with complete property data."""
    enrichments = {}
    enriched_components = []
    
    # Address standardization
    if 'address' in auction['missing_components']:
        if auction.get('address'):
            normalized = normalize_address(auction['address'])
            if normalized and normalized != auction['address']:
                enrichments['address'] = normalized
                enriched_components.append('address')
    
    # Geocoding
    if 'geo' in auction['missing_components']:
        address_to_geocode = enrichments.get('address') or auction.get('address')
        if address_to_geocode:
            lat, lng = geocode_address(address_to_geocode, county)
            if lat and lng:
                enrichments['lat'] = lat
                enrichments['lng'] = lng
                enriched_components.append('geo')
    
    # Property value lookup
    if 'value' in auction['missing_components']:
        parcel_id = auction.get('parcel_id')
        if parcel_id:
            assessed_value = lookup_property_value(parcel_id, county)
            if assessed_value:
                enrichments['assessed_value'] = assessed_value
                enriched_components.append('value')
    
    # Zoned parcel verification
    if 'zoned_parcel' in auction['missing_components']:
        parcel_id = auction.get('parcel_id')
        if parcel_id and link_zoned_parcel(parcel_id, county):
            # Mark as having valid zoned parcel linkage
            enrichments['zoned_parcel_linked'] = True
            enriched_components.append('zoned_parcel')
    
    return enrichments, enriched_components

def process_county_enrichment(county):
    """Main function to enrich property cards for a county."""
    print(f"Processing property card enrichment for {county} county...")
    
    incomplete_auctions = get_incomplete_auctions(county)
    if not incomplete_auctions:
        print(f"  All auctions in {county} have complete property cards!")
        return 0
    
    print(f"  Found {len(incomplete_auctions)} auctions needing enrichment")
    
    enriched_count = 0
    
    for auction in incomplete_auctions:
        auction_id = auction['id']
        case_number = auction['case_number']
        missing = auction['missing_components']
        
        print(f"    Enriching {case_number} (missing: {', '.join(missing)})")
        
        try:
            enrichments, enriched_components = enrich_property_card(auction, county)
            
            if enrichments:
                # Update the auction record with enrichments
                success = sb_patch(f"multi_county_auctions?id=eq.{auction_id}", enrichments)
                if success:
                    enriched_count += 1
                    print(f"      ✓ Enriched: {', '.join(enriched_components)}")
                else:
                    print(f"      ✗ Failed to update database")
            else:
                print(f"      → No enrichments possible (need implementation)")
                
        except Exception as e:
            print(f"      ✗ Error enriching {case_number}: {e}")
            continue
            
        # Rate limiting
        time.sleep(0.2)
    
    return enriched_count

def calculate_completion_rate(county):
    """Calculate current property card completion rate for a county."""
    # Get all auctions for the county
    all_auctions = sb_get("multi_county_auctions", f"county=eq.{county}&select=id,address,lat,lng,assessed_value,parcel_id")
    
    if not all_auctions:
        return 0.0, 0, 0
        
    total_count = len(all_auctions)
    complete_count = 0
    
    for auction in all_auctions:
        # Check if all four components are present
        has_address = bool(auction.get('address') and auction['address'].strip())
        has_geo = bool(auction.get('lat') and auction.get('lng'))
        has_value = bool(auction.get('assessed_value'))
        has_zoned_parcel = bool(auction.get('parcel_id'))
        
        if has_address and has_geo and has_value and has_zoned_parcel:
            complete_count += 1
    
    completion_rate = (complete_count / total_count * 100) if total_count > 0 else 0.0
    return completion_rate, complete_count, total_count

def main():
    parser = argparse.ArgumentParser(description='Letter I Property Card Enrichment')
    parser.add_argument('--county', choices=['charlotte', 'brevard', 'broward'],
                       help='County to enrich property cards for')
    parser.add_argument('--all-assigned', action='store_true',
                       help='Enrich all assigned counties (charlotte, brevard, broward)')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        print("ERROR: No SUPABASE_KEY found in environment")
        sys.exit(1)
    
    if args.all_assigned:
        counties = ['charlotte', 'brevard', 'broward']
    elif args.county:
        counties = [args.county]
    else:
        print("ERROR: Specify --county or --all-assigned")
        sys.exit(1)
    
    total_enriched = 0
    
    for county in counties:
        try:
            print(f"\n=== {county.upper()} COUNTY ===")
            
            # Show current completion rate
            completion_rate, complete, total = calculate_completion_rate(county)
            print(f"  Current completion: {completion_rate:.1f}% ({complete}/{total})")
            
            # Process enrichment
            enriched = process_county_enrichment(county)
            total_enriched += enriched
            
            # Show updated completion rate
            completion_rate_after, complete_after, total_after = calculate_completion_rate(county)
            print(f"  Updated completion: {completion_rate_after:.1f}% ({complete_after}/{total_after})")
            
        except Exception as e:
            print(f"ERROR processing {county}: {e}")
    
    print(f"\nCOMPLETED: {total_enriched} total property cards enriched")
    
    # Final status report
    print("\nFinal Letter I completion rates:")
    for county in counties:
        completion_rate, complete, total = calculate_completion_rate(county)
        status = "✓ PASS" if completion_rate >= 95.0 else "✗ FAIL"
        print(f"  {county}: {completion_rate:.1f}% ({complete}/{total}) {status}")

if __name__ == "__main__":
    main()