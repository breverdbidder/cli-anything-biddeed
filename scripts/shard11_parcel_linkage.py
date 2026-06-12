#!/usr/bin/env python3
"""
SHARD-11 Letter E: Parcel Linkage via County GIS
Fix parcel linking for manatee, bay, okeechobee counties via property appraiser ArcGIS

Current metrics:
- manatee: E FAIL metric=87.9 [parcel_linked=3961 of 4504]  
- bay: E FAIL metric=81.3 [parcel_linked=2396 of 2947]
- okeechobee: E FAIL metric=85.6 [parcel_linked=385 of 450]

Strategy: Use county property appraiser ArcGIS FeatureServer to match addresses → parcel_ids
Based on successful Brevard/BCPAO pattern

Usage:
  python scripts/shard11_parcel_linkage.py --county manatee
  python scripts/shard11_parcel_linkage.py --all-counties
"""
import os
import sys
import json
import httpx
import time
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import re
from urllib.parse import urlencode

# Setup logging  
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# County Property Appraiser ArcGIS endpoints
COUNTY_GIS_CONFIG = {
    'manatee': {
        'name': 'Manatee County Property Appraiser',
        'arcgis_url': 'https://gis.manateegov.com/arcgis/rest/services/Public/Property_Information/MapServer/0',
        'query_field': 'SITUS_ADDRESS',
        'parcel_field': 'PARCEL_ID',
        'backup_url': 'https://gis.manateegov.com/arcgis/rest/services',
        'co_no': 49
    },
    'bay': {
        'name': 'Bay County Property Appraiser', 
        'arcgis_url': 'https://gis.baycountyfl.gov/arcgis/rest/services/Property/PropertyInfo/MapServer/0',
        'query_field': 'SITE_ADDR',
        'parcel_field': 'PARCEL_ID',
        'backup_url': 'https://gis.baycountyfl.gov/arcgis/rest/services',
        'co_no': 4
    },
    'okeechobee': {
        'name': 'Okeechobee County Property Appraiser',
        'arcgis_url': 'https://gis.okeechobee.org/arcgis/rest/services/Property/PropertySearch/MapServer/0', 
        'query_field': 'PROPERTY_ADDRESS',
        'parcel_field': 'PARCEL_NUMBER',
        'backup_url': 'https://gis.okeechobee.org/arcgis/rest/services',
        'co_no': 58
    }
}

TARGET_COUNTIES = ['manatee', 'bay', 'okeechobee']

class ParcelLinkageProcessor:
    """Fix parcel linkage using county GIS services"""
    
    def __init__(self):
        self.client = httpx.Client(
            timeout=60,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; ZoneWise Research)'},
            follow_redirects=True
        )
    
    def query_supabase(self, table: str, params: Dict = None) -> List[Dict]:
        """Query Supabase table"""
        try:
            url = f"{BASE}/{table}"
            response = self.client.get(url, headers=HEADERS, params=params)
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"Query error {table}: {e}")
            return []
    
    def upsert_supabase(self, table: str, data: List[Dict]) -> int:
        """Upsert to Supabase table"""
        if not data:
            return 0
        try:
            response = self.client.patch(
                f"{BASE}/{table}",
                headers=HEADERS,
                json=data
            )
            if response.status_code in [200, 201, 204]:
                logger.info(f"✅ Updated {len(data)} records in {table}")
                return len(data)
            else:
                logger.error(f"❌ Update failed {table}: {response.status_code}")
                return 0
        except Exception as e:
            logger.error(f"❌ Update error {table}: {e}")
            return 0
    
    def discover_arcgis_endpoint(self, county: str) -> Optional[str]:
        """Discover working ArcGIS endpoint for county"""
        config = COUNTY_GIS_CONFIG[county]
        
        # Try primary endpoint first
        primary_url = config['arcgis_url']
        try:
            response = self.client.get(f"{primary_url}?f=json", timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'fields' in data:
                    logger.info(f"✅ Primary endpoint working for {county}: {primary_url}")
                    return primary_url
        except Exception as e:
            logger.warning(f"Primary endpoint failed for {county}: {e}")
        
        # Try backup discovery
        backup_url = config['backup_url']
        try:
            response = self.client.get(f"{backup_url}?f=json", timeout=30)
            if response.status_code == 200:
                data = response.json()
                # Look for property/parcel services
                for service in data.get('services', []):
                    service_name = service.get('name', '').lower()
                    if 'property' in service_name or 'parcel' in service_name:
                        discovered_url = f"{backup_url}/{service['name']}/MapServer/0"
                        logger.info(f"✅ Discovered endpoint for {county}: {discovered_url}")
                        return discovered_url
        except Exception as e:
            logger.error(f"Discovery failed for {county}: {e}")
        
        return None
    
    def query_parcel_by_address(self, endpoint_url: str, address: str, config: Dict) -> Optional[str]:
        """Query parcel ID by address using ArcGIS REST"""
        query_field = config['query_field']
        parcel_field = config['parcel_field']
        
        # Clean and format address for query
        clean_address = address.strip().upper()
        
        # Build ArcGIS query
        query_params = {
            'where': f"{query_field} LIKE '%{clean_address}%'",
            'outFields': f"{parcel_field},{query_field}",
            'returnGeometry': 'false',
            'f': 'json',
            'resultRecordCount': '5'
        }
        
        query_url = f"{endpoint_url}/query"
        
        try:
            response = self.client.get(query_url, params=query_params, timeout=30)
            time.sleep(1)  # Rate limiting
            
            if response.status_code == 200:
                data = response.json()
                features = data.get('features', [])
                
                if features:
                    # Return best match parcel ID
                    best_match = features[0]['attributes']
                    parcel_id = best_match.get(parcel_field)
                    matched_address = best_match.get(query_field)
                    
                    logger.debug(f"Match: {address} → {parcel_id} ({matched_address})")
                    return parcel_id
            
        except Exception as e:
            logger.error(f"Query error for '{address}': {e}")
        
        return None
    
    def get_unlinked_auctions(self, county: str, limit: int = 500) -> List[Dict]:
        """Get auctions without parcel_id linkage"""
        params = {
            'select': 'id,case_number,property_address,city,state,zip_code,parcel_id',
            'county': f'eq.{county}',
            'parcel_id': 'is.null',
            'property_address': 'not.is.null',
            'limit': str(limit),
            'order': 'auction_date.desc'
        }
        
        unlinked = self.query_supabase('multi_county_auctions', params)
        logger.info(f"{county}: {len(unlinked)} auctions need parcel linking")
        return unlinked
    
    def process_county_linkage(self, county: str) -> Dict:
        """Process parcel linkage for a county"""
        logger.info(f"🔗 Processing parcel linkage for {county}")
        
        if county not in COUNTY_GIS_CONFIG:
            return {'error': f'County {county} not supported'}
        
        config = COUNTY_GIS_CONFIG[county]
        
        # Discover working ArcGIS endpoint
        endpoint = self.discover_arcgis_endpoint(county)
        if not endpoint:
            return {'error': f'No working ArcGIS endpoint found for {county}'}
        
        # Get unlinked auctions
        unlinked_auctions = self.get_unlinked_auctions(county)
        if not unlinked_auctions:
            return {'county': county, 'linked': 0, 'message': 'No auctions need linking'}
        
        linked_updates = []
        successful_links = 0
        
        for auction in unlinked_auctions:
            address = auction.get('property_address')
            auction_id = auction.get('id')
            
            if not address or not auction_id:
                continue
            
            # Query parcel ID from county GIS
            parcel_id = self.query_parcel_by_address(endpoint, address, config)
            
            if parcel_id:
                # Prepare update record
                update_record = {
                    'id': auction_id,
                    'parcel_id': parcel_id,
                    'parcel_source': f'{county}_gis',
                    'parcel_linked_at': datetime.now().isoformat()
                }
                
                linked_updates.append(update_record)
                successful_links += 1
                
                logger.info(f"✅ Linked: {address} → {parcel_id}")
            
            # Rate limiting and batch processing
            if len(linked_updates) >= 50:
                self.upsert_supabase('multi_county_auctions', linked_updates)
                linked_updates = []
                time.sleep(2)
        
        # Final batch update
        if linked_updates:
            self.upsert_supabase('multi_county_auctions', linked_updates)
        
        logger.info(f"✅ {county}: Linked {successful_links} parcels")
        
        return {
            'county': county,
            'linked': successful_links,
            'total_processed': len(unlinked_auctions),
            'link_rate': round(successful_links / len(unlinked_auctions) * 100, 1) if unlinked_auctions else 0
        }

def get_current_linkage_metrics(counties: List[str]) -> Dict:
    """Get current Letter E metrics"""
    client = httpx.Client(timeout=30)
    current_metrics = {}
    
    for county in counties:
        try:
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={'county_name': county},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                current_metrics[county] = {
                    'grade_e': result.get('grade_e'),
                    'metric_e': result.get('metric_e'),
                    'linkage_pct': result.get('metric_e')
                }
            else:
                current_metrics[county] = {'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            current_metrics[county] = {'error': str(e)}
    
    return current_metrics

def main():
    parser = argparse.ArgumentParser(description="SHARD-11 Parcel Linkage Fix (Letter E)")
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='Process single county')
    parser.add_argument('--all-counties', action='store_true', help='Process all counties')  
    parser.add_argument('--limit', type=int, default=200, help='Limit auctions per county')
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    print("=" * 60)
    print("SHARD-11 PARCEL LINKAGE FIX (Letter E)")
    print("Strategy: County GIS → parcel_id matching")
    if args.county:
        print(f"Target County: {args.county}")
    else:
        print(f"Target Counties: {', '.join(TARGET_COUNTIES)}")
    print("=" * 60)
    
    counties_to_process = [args.county] if args.county else TARGET_COUNTIES
    
    # Check current metrics before fix
    print(f"\n📊 Current linkage metrics...")
    current_metrics = get_current_linkage_metrics(counties_to_process)
    
    for county in counties_to_process:
        metrics = current_metrics.get(county, {})
        if 'error' in metrics:
            print(f"{county}: Error - {metrics['error']}")
        else:
            pct = metrics.get('linkage_pct', 'Unknown')
            grade = metrics.get('grade_e', 'Unknown')
            print(f"{county}: {pct}% linked (Grade: {grade})")
    
    # Process linkage fixes
    processor = ParcelLinkageProcessor()
    results = []
    
    for county in counties_to_process:
        print(f"\n🎯 Processing {county}...")
        
        try:
            result = processor.process_county_linkage(county)
            results.append(result)
            
            if 'error' in result:
                print(f"❌ {county}: {result['error']}")
            else:
                linked = result.get('linked', 0)
                rate = result.get('link_rate', 0)
                print(f"✅ {county}: {linked} parcels linked ({rate}% success)")
        
        except Exception as e:
            logger.error(f"❌ Error processing {county}: {e}")
            results.append({'county': county, 'error': str(e)})
    
    # Check metrics after fix
    print(f"\n📊 Checking linkage after fix...")
    time.sleep(10)  # Give updates time to propagate
    
    updated_metrics = get_current_linkage_metrics(counties_to_process)
    
    print(f"\n{'='*60}")
    print("PARCEL LINKAGE FIX SUMMARY")
    print(f"{'='*60}")
    
    total_linked = sum(r.get('linked', 0) for r in results if 'error' not in r)
    
    for county in counties_to_process:
        before = current_metrics.get(county, {}).get('linkage_pct', 'Unknown')
        after = updated_metrics.get(county, {}).get('linkage_pct', 'Unknown')
        
        improvement = "✅ IMPROVED" if (
            isinstance(before, (int, float)) and 
            isinstance(after, (int, float)) and 
            after > before
        ) else "🔄 CHECK AGAIN"
        
        print(f"{county}: {before}% → {after}% {improvement}")
    
    print(f"\nTotal parcels linked: {total_linked}")
    print("Next steps:")
    print("1. Wait 15-30min for Letter E metrics to update")
    print("2. Run scripts/verify_shard11_status.py to confirm improvement")
    print("3. Consider running again with higher --limit for more coverage")

if __name__ == "__main__":
    main()