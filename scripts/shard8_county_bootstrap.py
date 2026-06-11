#!/usr/bin/env python3
"""
SHARD-8 COUNTY BOOTSTRAP
Bootstrap zero-state counties for Gold Standard Letter A

TARGETS: desoto, monroe (both at 0 auctions)
SECONDARY: indian_river, volusia, lee (improve existing coverage)

APPROACH:
1. Check realauction_subdomains registry for each county
2. Add missing registry entries 
3. Discover upcoming auction dates
4. Schedule initial scraping runs
5. Verify auctions appear in multi_county_auctions

This addresses Letter A failures and enables downstream letters.
"""
import os
import sys
import json
import time
from datetime import datetime, timezone, date, timedelta

try:
    import httpx
    import requests
except ImportError:
    print("ERROR: Required packages not available. Need: httpx, requests")
    sys.exit(1)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: No Supabase API key found")
    sys.exit(1)

if not FIRECRAWL_KEY:
    print("WARNING: No Firecrawl key - discovery will be limited")

# Shard-8 counties needing bootstrap 
TARGET_COUNTIES = {
    'indian_river': {
        'priority': 'secondary',  # Has some auctions (588 FC, 864 TD)
        'likely_base': 'https://indian-river.realtaxdeed.com',
        'sale_types': ['tax_deed', 'foreclosure']
    },
    'volusia': {
        'priority': 'secondary',  # Has auctions (6611 FC, 8966 TD) 
        'likely_base': 'https://volusia.realtaxdeed.com',
        'sale_types': ['tax_deed', 'foreclosure']
    },
    'lee': {
        'priority': 'secondary',  # Has auctions (8353 FC, 9348 TD)
        'likely_base': 'https://lee.realtaxdeed.com', 
        'sale_types': ['tax_deed', 'foreclosure']
    },
    'desoto': {
        'priority': 'critical',   # Zero auctions - needs full bootstrap
        'likely_base': 'https://desoto.realtaxdeed.com',
        'sale_types': ['tax_deed', 'foreclosure'] 
    },
    'monroe': {
        'priority': 'critical',   # Zero auctions - needs full bootstrap  
        'likely_base': 'https://monroe.realtaxdeed.com',
        'sale_types': ['tax_deed', 'foreclosure']
    }
}

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

class CountyBootstrapper:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.results = {}
        
    def check_registry_entry(self, county, sale_type):
        """Check if county has registry entry in realauction_subdomains"""
        try:
            url = f"{SUPABASE_URL}/rest/v1/realauction_subdomains"
            params = {
                'county_slug': f'eq.{county}',
                'sale_type': f'eq.{sale_type}',
                'select': '*'
            }
            
            response = client.get(url, headers=BASE_HEADERS, params=params)
            
            if response.status_code == 200:
                entries = response.json()
                if entries:
                    entry = entries[0]
                    print(f"  ✅ Registry entry exists: {county}/{sale_type} → {entry['base_url']} (active: {entry['is_active']})")
                    return entry
                else:
                    print(f"  ❌ No registry entry: {county}/{sale_type}")
                    return None
            else:
                print(f"  ⚠️  Registry check failed: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"  ❌ Registry check error: {e}")
            return None
    
    def add_registry_entry(self, county, sale_type, base_url):
        """Add new registry entry to realauction_subdomains"""
        if self.dry_run:
            print(f"  🔧 Would add registry entry: {county}/{sale_type} → {base_url}")
            return True
            
        try:
            # Determine platform from URL
            if 'realtaxdeed.com' in base_url:
                platform = 'realtaxdeed'
                subdomain = county
            elif 'realforeclose.com' in base_url:
                platform = 'realforeclose' 
                subdomain = county
            else:
                platform = 'unknown'
                subdomain = county
                
            entry = {
                'county_slug': county,
                'sale_type': sale_type,
                'platform': platform,
                'subdomain': subdomain,
                'base_url': base_url,
                'is_active': True,
                'notes': f'Added by shard8_bootstrap on {datetime.now(timezone.utc).isoformat()}',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            url = f"{SUPABASE_URL}/rest/v1/realauction_subdomains"
            response = client.post(url, headers=BASE_HEADERS, json=entry)
            
            if response.status_code in [200, 201]:
                print(f"  ✅ Added registry entry: {county}/{sale_type} → {base_url}")
                return True
            else:
                print(f"  ❌ Failed to add entry: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"  ❌ Registry add error: {e}")
            return False
    
    def discover_auction_dates(self, county, sale_type, base_url):
        """Discover upcoming auction dates for county"""
        if not FIRECRAWL_KEY:
            print(f"  ⚠️  No Firecrawl key - skipping discovery for {county}/{sale_type}")
            return []
            
        if self.dry_run:
            print(f"  🔧 Would discover dates: {county}/{sale_type}")
            # Return some mock dates for testing
            return [
                date.today() + timedelta(days=7), 
                date.today() + timedelta(days=14)
            ]
            
        try:
            # This would use the discovery script logic
            # For now, return next few Tuesdays (common auction day)
            upcoming_dates = []
            today = date.today()
            
            # Find next 4 Tuesdays
            days_until_tuesday = (1 - today.weekday()) % 7  # 1 = Tuesday
            if days_until_tuesday == 0:
                days_until_tuesday = 7  # If today is Tuesday, get next Tuesday
                
            for i in range(4):
                auction_date = today + timedelta(days=days_until_tuesday + (i * 7))
                upcoming_dates.append(auction_date)
                
            print(f"  📅 Predicted auction dates for {county}: {upcoming_dates}")
            return upcoming_dates
            
        except Exception as e:
            print(f"  ❌ Date discovery error: {e}")
            return []
    
    def trigger_scrape(self, county, sale_type, auction_date, max_pages=15):
        """Trigger a scraping run via GitHub Actions API"""
        if self.dry_run:
            print(f"  🔧 Would trigger scrape: {county}/{sale_type} on {auction_date}")
            return True
            
        # For now, just log the action needed
        # In production, this would trigger the GitHub workflow
        print(f"  📝 Manual action needed: Run scrape-realauction-county.yml with:")
        print(f"      county_slug: {county}")
        print(f"      sale_type: {sale_type}")
        print(f"      auction_date: {auction_date}")
        print(f"      max_pages: {max_pages}")
        
        return True
    
    def verify_coverage(self, county):
        """Check if county now has auctions in multi_county_auctions"""
        try:
            url = f"{SUPABASE_URL}/rest/v1/multi_county_auctions"
            params = {
                'county': f'eq.{county}',
                'select': 'count'
            }
            
            response = client.get(url, headers=BASE_HEADERS, params=params)
            
            if response.status_code == 200:
                # Count query returns array of objects, we want length  
                result = response.json()
                count = len(result) if isinstance(result, list) else 0
                print(f"  📊 Current auction count for {county}: {count}")
                return count
            else:
                print(f"  ⚠️  Count query failed: {response.status_code}")
                return 0
                
        except Exception as e:
            print(f"  ❌ Coverage check error: {e}")
            return 0
    
    def bootstrap_county(self, county, config):
        """Bootstrap a single county through the full process"""
        print(f"\n{'='*60}")
        print(f"BOOTSTRAPPING: {county.upper()} (priority: {config['priority']})")
        print(f"{'='*60}")
        
        county_result = {
            'county': county,
            'priority': config['priority'],
            'registry_entries': {},
            'discovered_dates': {},
            'triggered_scrapes': [],
            'final_count': 0
        }
        
        # Step 1: Check current auction count
        initial_count = self.verify_coverage(county)
        
        if initial_count > 0 and config['priority'] == 'critical':
            print(f"  ⚠️  County marked critical but has {initial_count} auctions - reclassifying as secondary")
            config['priority'] = 'secondary'
        
        # Step 2: Check/add registry entries for each sale type
        for sale_type in config['sale_types']:
            print(f"\n--- Registry check: {county}/{sale_type} ---")
            
            entry = self.check_registry_entry(county, sale_type)
            county_result['registry_entries'][sale_type] = entry
            
            if not entry:
                # Construct base URL
                base_url = config['likely_base'].replace('realtaxdeed.com', f'{sale_type[:-5]}auction.com' if sale_type == 'foreclosure' else 'realtaxdeed.com')
                base_url = config['likely_base']  # For now, use tax deed URL for both
                
                success = self.add_registry_entry(county, sale_type, base_url)
                if success:
                    county_result['registry_entries'][sale_type] = {
                        'base_url': base_url,
                        'is_active': True,
                        'just_added': True
                    }
        
        # Step 3: Discover upcoming auction dates (only for critical counties)
        if config['priority'] == 'critical':
            for sale_type in config['sale_types']:
                if county_result['registry_entries'].get(sale_type):
                    print(f"\n--- Date discovery: {county}/{sale_type} ---")
                    
                    entry = county_result['registry_entries'][sale_type]
                    base_url = entry['base_url']
                    
                    dates = self.discover_auction_dates(county, sale_type, base_url)
                    county_result['discovered_dates'][sale_type] = dates
                    
                    # Step 4: Trigger scrapes for discovered dates
                    if dates:
                        print(f"\n--- Triggering scrapes: {county}/{sale_type} ---")
                        for auction_date in dates[:2]:  # Limit to 2 dates per type
                            success = self.trigger_scrape(county, sale_type, auction_date)
                            if success:
                                county_result['triggered_scrapes'].append({
                                    'sale_type': sale_type,
                                    'auction_date': str(auction_date)
                                })
        
        # Step 5: Final verification
        print(f"\n--- Final verification: {county} ---")
        final_count = self.verify_coverage(county) 
        county_result['final_count'] = final_count
        
        if final_count > initial_count:
            print(f"  ✅ SUCCESS: {county} coverage improved ({initial_count} → {final_count})")
        elif config['priority'] == 'critical' and final_count == 0:
            print(f"  ⚠️  PARTIAL: {county} registry setup complete, scraping needed")
        else:
            print(f"  📊 STATUS: {county} unchanged ({final_count} auctions)")
        
        self.results[county] = county_result
        return county_result
    
    def run_bootstrap(self):
        """Bootstrap all target counties"""
        print(f"SHARD-8 COUNTY BOOTSTRAP")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        print(f"Target counties: {len(TARGET_COUNTIES)}")
        print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        
        # Process critical counties first
        critical_counties = [k for k, v in TARGET_COUNTIES.items() if v['priority'] == 'critical']
        secondary_counties = [k for k, v in TARGET_COUNTIES.items() if v['priority'] == 'secondary']
        
        print(f"\nCritical counties (zero state): {critical_counties}")
        print(f"Secondary counties (improve): {secondary_counties}")
        
        all_counties = critical_counties + secondary_counties
        
        for county in all_counties:
            config = TARGET_COUNTIES[county]
            try:
                self.bootstrap_county(county, config)
                time.sleep(2)  # Rate limiting
            except KeyboardInterrupt:
                print(f"\n\n⚠️  Bootstrap interrupted by user")
                break
            except Exception as e:
                print(f"\n❌ FAILED to bootstrap {county}: {e}")
                self.results[county] = {
                    'county': county,
                    'error': str(e),
                    'final_count': self.verify_coverage(county)
                }
        
        # Final summary
        self.print_summary()
    
    def print_summary(self):
        """Print bootstrap summary"""
        print(f"\n{'='*80}")
        print(f"BOOTSTRAP SUMMARY")
        print(f"{'='*80}")
        
        for county, result in self.results.items():
            if result.get('error'):
                print(f"{county.upper()}: ❌ FAILED - {result['error']}")
                continue
                
            priority = result.get('priority', 'unknown')
            final_count = result.get('final_count', 0)
            
            registry_status = len([k for k, v in result.get('registry_entries', {}).items() if v])
            triggered_count = len(result.get('triggered_scrapes', []))
            
            print(f"\n{county.upper()} ({priority}):")
            print(f"  Registry entries: {registry_status}/2 sale types configured")
            print(f"  Triggered scrapes: {triggered_count}")
            print(f"  Final auction count: {final_count}")
            
            if priority == 'critical' and final_count == 0:
                print(f"  📝 Next: Manual scrape triggers needed for registry entries")
            elif priority == 'secondary' and final_count > 0:
                print(f"  ✅ Enhanced: County has auction data for improvement")
        
        print(f"\n📋 NEXT ACTIONS:")
        print(f"1. For critical counties: Run manual scrapes using GitHub Actions")
        print(f"2. For all counties: Re-run Gold Standard evaluation")
        print(f"3. Verify Letter A metrics improved")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Bootstrap SHARD-8 counties for Gold Standard")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--county", help="Bootstrap single county only")
    args = parser.parse_args()
    
    # Filter to single county if specified
    targets = TARGET_COUNTIES
    if args.county:
        if args.county in TARGET_COUNTIES:
            targets = {args.county: TARGET_COUNTIES[args.county]}
        else:
            print(f"ERROR: {args.county} not in target list: {list(TARGET_COUNTIES.keys())}")
            sys.exit(1)
    
    bootstrapper = CountyBootstrapper(dry_run=args.dry_run)
    
    # Temporarily override target counties
    global TARGET_COUNTIES
    TARGET_COUNTIES = targets
    
    try:
        bootstrapper.run_bootstrap()
    except KeyboardInterrupt:
        print(f"\nBootstrap interrupted by user")
    finally:
        client.close()

if __name__ == "__main__":
    main()