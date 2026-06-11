#!/usr/bin/env python3
"""
SHARD-10 Parcel Linkage Improvements (Gold Standard Letter E)
Improve parcel_id linkage for target counties to achieve ≥95% threshold

Priority targets:
- manatee: 91.4% → 95%+ (4.6% gap = ~290 auctions) - HIGHEST PRIORITY
- alachua: 77.4% → 95%+ (17.6% gap = ~400 auctions)  
- martin: 34.8% → 95%+ (60.2% gap = ~1500 auctions)

Strategy:
1. Query county property appraiser ArcGIS REST APIs 
2. Match auction addresses/case numbers to parcel_id
3. Use existing BCPAO pipeline patterns (Brevard reference implementation)
4. Focus on high-success-rate matching first

Usage:
  python scripts/shard10_parcel_linkage.py --county manatee
  python scripts/shard10_parcel_linkage.py --all-priority
"""
import os
import sys
import httpx
import json
import re
from datetime import datetime
import argparse
import time
from typing import Dict, List, Optional, Tuple

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties with current Letter E metrics
TARGET_COUNTIES = {
    'manatee': {'co_no': 51, 'current_pct': 91.4, 'priority': 1},
    'alachua': {'co_no': 11, 'current_pct': 77.4, 'priority': 2}, 
    'martin': {'co_no': 53, 'current_pct': 34.8, 'priority': 3}
}

# County property appraiser endpoints (to be discovered)
APPRAISER_ENDPOINTS = {
    'manatee': {
        'base_url': 'https://www.manateepao.com',  # To be verified
        'search_type': 'address_search',
        'notes': 'Manatee County Property Appraiser - endpoint discovery needed'
    },
    'alachua': {
        'base_url': 'https://www.acpafl.org',  # To be verified  
        'search_type': 'address_search',
        'notes': 'Alachua County Property Appraiser - endpoint discovery needed'
    },
    'martin': {
        'base_url': 'https://www.pa.martin.fl.us',  # To be verified
        'search_type': 'address_search', 
        'notes': 'Martin County Property Appraiser - endpoint discovery needed'
    }
}

def log(msg):
    """Log with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def get_unlinked_auctions(county_slug: str, limit: int = 1000) -> List[Dict]:
    """Get auction records without parcel_id for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}&parcel_id=is.null"
            f"&select=id,case_number,property_address,city,state,zip_code,county"
            f"&limit={limit}",
            headers=sb_headers()
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            log(f"❌ Error fetching unlinked auctions: {response.text}")
            return []
            
    except Exception as e:
        log(f"❌ Error fetching unlinked auctions: {e}")
        return []

def get_current_linkage_stats(county_slug: str) -> Dict:
    """Get current parcel linkage statistics"""
    try:
        client = httpx.Client(timeout=30)
        
        # Total auctions
        response_total = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}&select=count",
            headers=sb_headers()
        )
        total_count = len(response_total.json()) if response_total.status_code == 200 else 0
        
        # Linked auctions
        response_linked = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            f"?county=eq.{county_slug}&parcel_id=not.is.null&select=count",
            headers=sb_headers()
        )
        linked_count = len(response_linked.json()) if response_linked.status_code == 200 else 0
        
        # Unlinked auctions
        unlinked_count = total_count - linked_count
        linkage_pct = (linked_count / total_count * 100) if total_count > 0 else 0
        
        return {
            'county': county_slug,
            'total_auctions': total_count,
            'linked_auctions': linked_count,
            'unlinked_auctions': unlinked_count,
            'linkage_percentage': linkage_pct,
            'gap_to_95': max(0, 95.0 - linkage_pct)
        }
        
    except Exception as e:
        log(f"❌ Error getting linkage stats: {e}")
        return {}

def discover_appraiser_endpoint(county_slug: str) -> Optional[str]:
    """Attempt to discover the county property appraiser ArcGIS endpoint"""
    log(f"🔍 Discovering property appraiser endpoint for {county_slug}")
    
    appraiser_info = APPRAISER_ENDPOINTS.get(county_slug, {})
    base_url = appraiser_info.get('base_url')
    
    if not base_url:
        log(f"❌ No base URL configured for {county_slug}")
        return None
    
    # Common ArcGIS REST patterns to try
    arcgis_patterns = [
        '/arcgis/rest/services',
        '/gis/arcgis/rest/services',
        '/maps/arcgis/rest/services',
        '/services/arcgis/rest/services'
    ]
    
    try:
        client = httpx.Client(timeout=30)
        
        for pattern in arcgis_patterns:
            test_url = f"{base_url}{pattern}"
            log(f"  Testing: {test_url}")
            
            try:
                response = client.get(test_url, timeout=10)
                if response.status_code == 200 and 'services' in response.text.lower():
                    log(f"✅ Found ArcGIS endpoint: {test_url}")
                    
                    # Look for parcel-related services
                    if 'parcel' in response.text.lower() or 'property' in response.text.lower():
                        log(f"✅ Parcel services detected at {test_url}")
                        return test_url
                    
                    # Return the base services endpoint even if no parcel service found
                    return test_url
                    
            except Exception as e:
                log(f"    ❌ Failed: {e}")
                continue
        
        log(f"❌ No ArcGIS endpoint found for {county_slug}")
        return None
        
    except Exception as e:
        log(f"❌ Endpoint discovery error: {e}")
        return None

def match_parcels_by_address(county_slug: str, unlinked_auctions: List[Dict]) -> int:
    """Match parcels by property address using various strategies"""
    log(f"🔗 Matching parcels by address for {county_slug}")
    
    co_no = TARGET_COUNTIES[county_slug]['co_no']
    matched_count = 0
    
    try:
        client = httpx.Client(timeout=30)
        
        # Strategy 1: Exact address match from sample_properties
        log(f"  Strategy 1: Exact address matching...")
        
        for auction in unlinked_auctions[:100]:  # Limit to first 100 for testing
            auction_id = auction['id']
            address = auction.get('property_address', '').strip()
            city = auction.get('city', '').strip()
            
            if not address:
                continue
            
            # Clean address for matching
            clean_address = re.sub(r'[^\w\s]', '', address).upper()
            
            # Query sample_properties for parcel_id with matching address
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/sample_properties"
                f"?co_no=eq.{co_no}"
                f"&situs_address=ilike.*{clean_address[:20]}*"  # Partial match
                f"&select=parcel_id,situs_address,situs_city",
                headers=sb_headers()
            )
            
            if response.status_code == 200:
                properties = response.json()
                if len(properties) == 1:  # Unique match
                    parcel_id = properties[0]['parcel_id']
                    
                    # Update auction with parcel_id
                    update_response = client.patch(
                        f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{auction_id}",
                        headers=sb_headers(),
                        json={'parcel_id': parcel_id, 'parcel_link_method': 'address_match'}
                    )
                    
                    if update_response.status_code in [200, 204]:
                        matched_count += 1
                        log(f"    ✅ Matched: {address} → {parcel_id}")
                    
                elif len(properties) > 1:
                    log(f"    ⚠️ Multiple matches for: {address}")
                
            time.sleep(0.1)  # Rate limiting
    
        log(f"  Address matching results: {matched_count} matched")
        return matched_count
        
    except Exception as e:
        log(f"❌ Address matching error: {e}")
        return 0

def match_parcels_by_case_number(county_slug: str, unlinked_auctions: List[Dict]) -> int:
    """Match parcels by case number patterns (if available)"""
    log(f"🔗 Matching parcels by case number for {county_slug}")
    
    # This would involve county-specific case number to parcel_id mapping
    # For now, return 0 - this is a TODO for future implementation
    
    log(f"  Case number matching: TODO - county-specific implementation needed")
    return 0

def update_linkage_batch(matches: List[Tuple[int, str]]) -> int:
    """Update multiple auction records with parcel_id in batch"""
    if not matches:
        return 0
    
    try:
        client = httpx.Client(timeout=30)
        
        # Batch update using multiple PATCH requests
        updated_count = 0
        
        for auction_id, parcel_id in matches:
            response = client.patch(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?id=eq.{auction_id}",
                headers=sb_headers(),
                json={
                    'parcel_id': parcel_id,
                    'parcel_link_method': 'shard10_batch',
                    'updated_at': datetime.now().isoformat()
                }
            )
            
            if response.status_code in [200, 204]:
                updated_count += 1
            
            time.sleep(0.05)  # Rate limiting
        
        log(f"✅ Batch updated {updated_count} parcel linkages")
        return updated_count
        
    except Exception as e:
        log(f"❌ Batch update error: {e}")
        return 0

def improve_county_linkage(county_slug: str) -> Dict:
    """Main function to improve parcel linkage for a county"""
    log(f"\n{'='*60}")
    log(f"IMPROVING PARCEL LINKAGE: {county_slug.upper()}")
    log(f"{'='*60}")
    
    # Get current statistics
    initial_stats = get_current_linkage_stats(county_slug)
    if not initial_stats:
        return {'success': False, 'error': 'Could not get current stats'}
    
    log(f"📊 Initial statistics for {county_slug}:")
    log(f"   Total auctions: {initial_stats['total_auctions']}")
    log(f"   Linked: {initial_stats['linked_auctions']} ({initial_stats['linkage_percentage']:.1f}%)")
    log(f"   Unlinked: {initial_stats['unlinked_auctions']}")
    log(f"   Gap to 95%: {initial_stats['gap_to_95']:.1f}%")
    
    # Get unlinked auctions
    unlinked_auctions = get_unlinked_auctions(county_slug, 500)
    log(f"📋 Retrieved {len(unlinked_auctions)} unlinked auctions")
    
    if not unlinked_auctions:
        log(f"✅ No unlinked auctions found for {county_slug}")
        return {'success': True, 'matched_count': 0, 'initial_stats': initial_stats}
    
    # Discover appraiser endpoint
    endpoint = discover_appraiser_endpoint(county_slug)
    if endpoint:
        log(f"✅ Found appraiser endpoint: {endpoint}")
    else:
        log(f"⚠️ No ArcGIS endpoint found - using fallback methods")
    
    # Apply matching strategies
    total_matched = 0
    
    # Strategy 1: Address matching
    matched_address = match_parcels_by_address(county_slug, unlinked_auctions)
    total_matched += matched_address
    
    # Strategy 2: Case number matching (if available)
    matched_case = match_parcels_by_case_number(county_slug, unlinked_auctions)
    total_matched += matched_case
    
    # Get final statistics
    final_stats = get_current_linkage_stats(county_slug)
    improvement = final_stats['linkage_percentage'] - initial_stats['linkage_percentage']
    
    log(f"\n📈 LINKAGE IMPROVEMENT RESULTS:")
    log(f"   Before: {initial_stats['linkage_percentage']:.1f}%")
    log(f"   After: {final_stats['linkage_percentage']:.1f}%")
    log(f"   Improvement: +{improvement:.1f}%")
    log(f"   Auctions matched: {total_matched}")
    log(f"   Gold Standard Letter E: {'✅ PASS' if final_stats['linkage_percentage'] >= 95 else '❌ FAIL'}")
    
    return {
        'success': True,
        'county': county_slug,
        'matched_count': total_matched,
        'initial_stats': initial_stats,
        'final_stats': final_stats,
        'improvement': improvement,
        'passes_threshold': final_stats['linkage_percentage'] >= 95
    }

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 Parcel Linkage Improvements')
    parser.add_argument('--county', choices=['manatee', 'alachua', 'martin'],
                        help='Improve specific county only')
    parser.add_argument('--all-priority', action='store_true',
                        help='Process all counties in priority order')
    args = parser.parse_args()
    
    log("🎯 SHARD-10 PARCEL LINKAGE IMPROVEMENTS")
    log(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    results = {}
    
    if args.county:
        # Single county
        counties_to_process = [args.county]
    elif args.all_priority:
        # All counties in priority order
        counties_to_process = sorted(TARGET_COUNTIES.keys(), 
                                   key=lambda x: TARGET_COUNTIES[x]['priority'])
    else:
        log("❌ Must specify either --county or --all-priority")
        sys.exit(1)
    
    # Process counties
    for county_slug in counties_to_process:
        results[county_slug] = improve_county_linkage(county_slug)
        time.sleep(2)  # Pause between counties
    
    # Final summary
    log(f"\n{'='*60}")
    log("PARCEL LINKAGE IMPROVEMENT SUMMARY")
    log(f"{'='*60}")
    
    total_matched = 0
    counties_passing = 0
    
    for county, result in results.items():
        if result.get('success'):
            matched = result['matched_count']
            improvement = result.get('improvement', 0)
            passes = result.get('passes_threshold', False)
            
            total_matched += matched
            if passes:
                counties_passing += 1
            
            status = "✅ PASS" if passes else "❌ FAIL"
            log(f"  {county}: {matched} matched, +{improvement:.1f}% → {status}")
        else:
            log(f"  {county}: ❌ FAILED - {result.get('error', 'Unknown error')}")
    
    log(f"\nTotal auctions matched: {total_matched}")
    log(f"Counties now passing Letter E: {counties_passing}/{len(results)}")

if __name__ == "__main__":
    main()