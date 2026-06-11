#!/usr/bin/env python3
"""
SHARD-8 PARCEL LINKAGE FIX
Improve Letter E scores for counties close to 95% threshold

TARGETS:
- volusia: 65.8% (10,256/15,577) → need +4,321 links for 95%
- lee: 80.4% (14,229/17,701) → need +2,542 links for 95%  
- indian_river: 81.0% (1,176/1,452) → need +204 links for 95%

APPROACH:
1. Query auctions missing parcel_id by county
2. Use county property appraiser ArcGIS APIs to find parcel IDs
3. Bulk update multi_county_auctions with parcel links
4. Verify improvement in Letter E metrics

Based on Brevard BCPAO pipeline (proven approach).
"""
import os
import sys
import json
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

try:
    import httpx
    import requests
    from urllib.parse import quote, urlencode
except ImportError:
    print("ERROR: Required packages not available. Need: httpx, requests")
    sys.exit(1)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: No Supabase API key found")
    sys.exit(1)

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

# County-specific property appraiser configurations
COUNTY_CONFIGS = {
    'indian_river': {
        'priority': 'high',          # 81% → need +204 for 95%
        'appraiser_name': 'Indian River County Property Appraiser',
        'gis_base': 'https://maps.irpropapp.com',
        'arcgis_endpoint': 'DISCOVER',  # Need to find actual endpoint
        'search_fields': ['PARCELNO', 'ALTPARCELNO', 'PROPERTY_ADDRESS'],
        'batch_size': 50
    },
    'volusia': {
        'priority': 'high',          # 65.8% → need +4,321 for 95%
        'appraiser_name': 'Volusia County Property Appraiser', 
        'gis_base': 'https://vdp.vcpa.volusia.org',
        'arcgis_endpoint': 'DISCOVER',
        'search_fields': ['PARCEL_NO', 'ALT_PARCEL', 'PROP_ADDR'],
        'batch_size': 100
    },
    'lee': {
        'priority': 'medium',        # 80.4% → need +2,542 for 95%
        'appraiser_name': 'Lee County Property Appraiser',
        'gis_base': 'https://www.leepa.org', 
        'arcgis_endpoint': 'DISCOVER',
        'search_fields': ['PARCEL_ID', 'PARCEL_NUMBER', 'PROPERTY_ADDRESS'],
        'batch_size': 75
    }
}

class ParcelLinkageFixer:
    def __init__(self, dry_run=False, max_records=1000):
        self.dry_run = dry_run
        self.max_records = max_records
        self.results = {}
        self.session_stats = {
            'start_time': datetime.now(timezone.utc),
            'counties_processed': 0,
            'auctions_queried': 0,
            'parcels_found': 0,
            'updates_made': 0
        }
        
    def get_unlinked_auctions(self, county: str, limit: int = 1000) -> List[Dict]:
        """Get auctions missing parcel_id for county"""
        try:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            params = {
                'county': f'eq.{county}',
                'parcel_id': 'is.null',
                'select': 'id,case_number,property_address,plaintiff,defendant',
                'limit': limit,
                'order': 'id.desc'  # Get newest first
            }
            
            response = client.get(url, headers=BASE_HEADERS, params=params)
            
            if response.status_code == 200:
                auctions = response.json()
                print(f"  📊 Found {len(auctions)} unlinked auctions in {county}")
                return auctions
            else:
                print(f"  ❌ Failed to query unlinked auctions: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"  ❌ Unlinked auctions query error: {e}")
            return []
    
    def search_parcel_by_address(self, county: str, address: str) -> Optional[str]:
        """Search for parcel ID using property address"""
        if not address or len(address.strip()) < 5:
            return None
            
        config = COUNTY_CONFIGS[county]
        
        # This would integrate with county-specific property appraiser APIs
        # For now, return None to simulate API unavailable
        # In production, this would make actual API calls
        
        print(f"    🔍 Would search {config['appraiser_name']} for: {address}")
        return None
    
    def search_parcel_by_case_number(self, county: str, case_number: str) -> Optional[str]:
        """Search for parcel ID using case number (clerk records)"""
        if not case_number or len(case_number.strip()) < 4:
            return None
            
        # This would search clerk records or foreclosure databases
        # Many clerk systems have case → parcel mappings
        
        print(f"    🔍 Would search clerk records for case: {case_number}")
        return None
    
    def search_parcel_by_party_names(self, county: str, plaintiff: str, defendant: str) -> Optional[str]:
        """Search for parcel ID using party names (property records)"""
        if not defendant or len(defendant.strip()) < 3:
            return None
            
        # This would search property ownership records by defendant name
        # Property appraiser databases often have owner name search
        
        print(f"    🔍 Would search ownership records for: {defendant}")
        return None
    
    def find_parcel_id(self, county: str, auction: Dict) -> Optional[str]:
        """Try multiple methods to find parcel ID for auction"""
        auction_id = auction['id']
        case_number = auction.get('case_number', '')
        address = auction.get('property_address', '')
        plaintiff = auction.get('plaintiff', '')
        defendant = auction.get('defendant', '')
        
        print(f"    Finding parcel for auction {auction_id}...")
        
        # Method 1: Search by property address
        if address:
            parcel_id = self.search_parcel_by_address(county, address)
            if parcel_id:
                print(f"    ✅ Found via address: {parcel_id}")
                return parcel_id
        
        # Method 2: Search by case number
        if case_number:
            parcel_id = self.search_parcel_by_case_number(county, case_number)
            if parcel_id:
                print(f"    ✅ Found via case number: {parcel_id}")
                return parcel_id
        
        # Method 3: Search by party names
        if defendant:
            parcel_id = self.search_parcel_by_party_names(county, plaintiff, defendant)
            if parcel_id:
                print(f"    ✅ Found via ownership: {parcel_id}")
                return parcel_id
        
        print(f"    ❌ No parcel found for auction {auction_id}")
        return None
    
    def update_auction_parcel(self, auction_id: int, parcel_id: str) -> bool:
        """Update auction record with found parcel ID"""
        if self.dry_run:
            print(f"    🔧 Would update auction {auction_id} with parcel {parcel_id}")
            return True
            
        try:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            params = {'id': f'eq.{auction_id}'}
            payload = {
                'parcel_id': parcel_id,
                'parcel_linked_at': datetime.now(timezone.utc).isoformat(),
                'parcel_link_source': 'shard8_linkage_fix'
            }
            
            response = client.patch(url, headers=BASE_HEADERS, params=params, json=payload)
            
            if response.status_code in [200, 204]:
                print(f"    ✅ Updated auction {auction_id} with parcel {parcel_id}")
                return True
            else:
                print(f"    ❌ Failed to update auction {auction_id}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"    ❌ Update error for auction {auction_id}: {e}")
            return False
    
    def get_current_linkage_stats(self, county: str) -> Dict:
        """Get current parcel linkage statistics for county"""
        try:
            # Total auctions
            total_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=BASE_HEADERS,
                params={'county': f'eq.{county}', 'select': 'count'}
            )
            
            # Linked auctions
            linked_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions", 
                headers=BASE_HEADERS,
                params={
                    'county': f'eq.{county}',
                    'parcel_id': 'not.is.null',
                    'select': 'count'
                }
            )
            
            if total_response.status_code == 200 and linked_response.status_code == 200:
                total = len(total_response.json())
                linked = len(linked_response.json())
                pct = (linked * 100.0 / total) if total > 0 else 0
                
                return {
                    'total_auctions': total,
                    'linked_auctions': linked,
                    'linkage_pct': pct,
                    'unlinked_count': total - linked
                }
            else:
                print(f"  ⚠️  Stats query failed for {county}")
                return {}
                
        except Exception as e:
            print(f"  ❌ Stats error for {county}: {e}")
            return {}
    
    def fix_county_linkage(self, county: str, config: Dict) -> Dict:
        """Fix parcel linkage for a single county"""
        print(f"\n{'='*60}")
        print(f"FIXING LINKAGE: {county.upper()} (priority: {config['priority']})")
        print(f"{'='*60}")
        
        # Get baseline stats
        print(f"\n--- Baseline Assessment ---")
        before_stats = self.get_current_linkage_stats(county)
        if not before_stats:
            return {'error': 'Failed to get baseline stats'}
        
        print(f"  Total auctions: {before_stats['total_auctions']:,}")
        print(f"  Linked auctions: {before_stats['linked_auctions']:,}")
        print(f"  Linkage rate: {before_stats['linkage_pct']:.1f}%")
        print(f"  Unlinked count: {before_stats['unlinked_count']:,}")
        
        # Calculate gap to 95%
        target_linked = int(before_stats['total_auctions'] * 0.95)
        gap_to_target = max(0, target_linked - before_stats['linked_auctions'])
        print(f"  Gap to 95%: {gap_to_target:,} links needed")
        
        if gap_to_target == 0:
            print(f"  ✅ Already above 95% threshold!")
            return {
                'county': county,
                'before_stats': before_stats,
                'after_stats': before_stats,
                'parcels_found': 0,
                'updates_made': 0,
                'status': 'already_passing'
            }
        
        # Determine work batch size
        work_limit = min(self.max_records, config['batch_size'], gap_to_target * 2)
        print(f"  Work batch size: {work_limit:,} auctions")
        
        # Get unlinked auctions to process
        print(f"\n--- Querying Unlinked Auctions ---")
        unlinked_auctions = self.get_unlinked_auctions(county, work_limit)
        
        if not unlinked_auctions:
            print(f"  ⚠️  No unlinked auctions found to process")
            return {
                'county': county,
                'before_stats': before_stats,
                'error': 'No unlinked auctions available'
            }
        
        # Process auctions to find parcel IDs
        print(f"\n--- Processing {len(unlinked_auctions)} Auctions ---")
        parcels_found = 0
        updates_made = 0
        
        for i, auction in enumerate(unlinked_auctions):
            if i >= work_limit:
                break
                
            if i % 10 == 0:
                print(f"  Progress: {i}/{min(len(unlinked_auctions), work_limit)}")
            
            # Try to find parcel ID
            parcel_id = self.find_parcel_id(county, auction)
            
            if parcel_id:
                parcels_found += 1
                
                # Update auction record
                success = self.update_auction_parcel(auction['id'], parcel_id)
                if success:
                    updates_made += 1
                    
                # Rate limiting
                time.sleep(0.1)
        
        # Get final stats
        print(f"\n--- Final Assessment ---")
        after_stats = self.get_current_linkage_stats(county)
        
        if after_stats:
            print(f"  Total auctions: {after_stats['total_auctions']:,}")
            print(f"  Linked auctions: {after_stats['linked_auctions']:,} (+{after_stats['linked_auctions'] - before_stats['linked_auctions']:,})")
            print(f"  Linkage rate: {after_stats['linkage_pct']:.1f}% (+{after_stats['linkage_pct'] - before_stats['linkage_pct']:.1f}%)")
            
            improvement = after_stats['linkage_pct'] - before_stats['linkage_pct']
            if improvement > 0:
                print(f"  ✅ IMPROVED: Linkage rate increased by {improvement:.1f}%")
            else:
                print(f"  ⚠️  NO CHANGE: No effective improvement detected")
                
            gap_remaining = max(0, int(after_stats['total_auctions'] * 0.95) - after_stats['linked_auctions'])
            print(f"  Gap remaining to 95%: {gap_remaining:,}")
        else:
            after_stats = before_stats
        
        result = {
            'county': county,
            'before_stats': before_stats,
            'after_stats': after_stats,
            'auctions_processed': len(unlinked_auctions),
            'parcels_found': parcels_found,
            'updates_made': updates_made,
            'status': 'improved' if updates_made > 0 else 'no_change'
        }
        
        self.session_stats['auctions_queried'] += len(unlinked_auctions)
        self.session_stats['parcels_found'] += parcels_found
        self.session_stats['updates_made'] += updates_made
        
        return result
    
    def run_linkage_fixes(self):
        """Run parcel linkage fixes for all target counties"""
        print(f"SHARD-8 PARCEL LINKAGE FIX")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Max records per county: {self.max_records:,}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        
        # Process counties by priority
        high_priority = [k for k, v in COUNTY_CONFIGS.items() if v.get('priority') == 'high']
        medium_priority = [k for k, v in COUNTY_CONFIGS.items() if v.get('priority') == 'medium']
        
        print(f"\nHigh priority: {high_priority}")
        print(f"Medium priority: {medium_priority}")
        
        all_counties = high_priority + medium_priority
        
        for county in all_counties:
            config = COUNTY_CONFIGS[county]
            try:
                result = self.fix_county_linkage(county, config)
                self.results[county] = result
                self.session_stats['counties_processed'] += 1
                
                # Rate limiting between counties
                time.sleep(1)
                
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Linkage fix interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ FAILED to fix linkage for {county}: {e}")
                self.results[county] = {
                    'county': county,
                    'error': str(e),
                    'status': 'failed'
                }
        
        # Final summary
        self.print_summary()
    
    def print_summary(self):
        """Print linkage fix summary"""
        elapsed = datetime.now(timezone.utc) - self.session_stats['start_time']
        
        print(f"\n{'='*80}")
        print(f"LINKAGE FIX SUMMARY")
        print(f"{'='*80}")
        print(f"Session time: {elapsed.total_seconds()/60:.1f} minutes")
        print(f"Counties processed: {self.session_stats['counties_processed']}")
        print(f"Auctions queried: {self.session_stats['auctions_queried']:,}")
        print(f"Parcels found: {self.session_stats['parcels_found']:,}")
        print(f"Updates made: {self.session_stats['updates_made']:,}")
        
        for county, result in self.results.items():
            if result.get('error'):
                print(f"\n{county.upper()}: ❌ FAILED - {result['error']}")
                continue
            
            status = result.get('status', 'unknown')
            before = result.get('before_stats', {})
            after = result.get('after_stats', {})
            
            before_pct = before.get('linkage_pct', 0)
            after_pct = after.get('linkage_pct', 0)
            improvement = after_pct - before_pct
            
            updates = result.get('updates_made', 0)
            
            print(f"\n{county.upper()} ({status}):")
            print(f"  Before: {before_pct:.1f}% linked")
            print(f"  After:  {after_pct:.1f}% linked (+{improvement:.1f}%)")
            print(f"  Updates made: {updates:,}")
            
            if after_pct >= 95.0:
                print(f"  🎯 LETTER E: PASS (≥95% threshold)")
            else:
                remaining = 95.0 - after_pct
                print(f"  📊 LETTER E: FAIL (need +{remaining:.1f}%)")
        
        print(f"\n📋 NEXT ACTIONS:")
        print(f"1. Verify Letter E improvements via: SELECT public.pencil_dod_evaluate_county('<county>');")
        print(f"2. For counties still below 95%: Enhance parcel search methods")
        print(f"3. Consider alternative data sources (clerk records, title companies)")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Fix parcel linkage for SHARD-8 counties")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--county", help="Process single county only")
    parser.add_argument("--max-records", type=int, default=1000, help="Max records per county")
    args = parser.parse_args()
    
    # Filter to single county if specified
    configs = COUNTY_CONFIGS
    if args.county:
        if args.county in COUNTY_CONFIGS:
            configs = {args.county: COUNTY_CONFIGS[args.county]}
        else:
            print(f"ERROR: {args.county} not in target list: {list(COUNTY_CONFIGS.keys())}")
            sys.exit(1)
    
    fixer = ParcelLinkageFixer(dry_run=args.dry_run, max_records=args.max_records)
    
    # Temporarily override configs
    global COUNTY_CONFIGS
    COUNTY_CONFIGS = configs
    
    try:
        fixer.run_linkage_fixes()
    except KeyboardInterrupt:
        print(f"\nLinkage fix interrupted by user")
    finally:
        client.close()

if __name__ == "__main__":
    main()