#!/usr/bin/env python3
"""
SHARD-8 VERIFIED OUTCOMES PIPELINE
Build Letter B (verified independent outcomes >=95% of closed) for assigned counties

CRITICAL ISSUE: All counties show verified=0, pct_verified_outcomes=null
ROOT CAUSE: No INDEPENDENT data source - need clerk record pipelines

TARGETS:
- indian_river: 608 closed_sold, 0 verified (need 578+ verified for 95%)
- volusia: 5,481 closed_sold, 0 verified (need 5,207+ verified for 95%) 
- lee: 5,862 closed_sold, 0 verified (need 5,569+ verified for 95%)
- desoto: 0 closed_sold (bootstrap first)
- monroe: 0 closed_sold (bootstrap first)

APPROACH:
1. Extend Duval AcclaimWeb pattern to county clerk systems
2. Build county-specific outcome scrapers (Certificate of Title, sale results)
3. Match outcomes to multi_county_auctions by case_number
4. Write to foreclosure_outcomes/tax_deed_outcomes with data_source=clerk
"""
import os
import sys
import json
import re
import time
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging

try:
    import httpx
    import requests
except ImportError:
    print("ERROR: Required packages not available. Need: httpx, requests")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: No Supabase API key found")
    sys.exit(1)

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

# County clerk configurations for verified outcomes
COUNTY_CLERK_CONFIGS = {
    'indian_river': {
        'priority': 'high',      # 608 closed, need 578+ verified
        'clerk_name': 'Indian River County Clerk',
        'clerk_portal': 'https://officialrecords.indian-river.org/',
        'acclaim_endpoint': 'DISCOVER',  # Need to check if they use AcclaimWeb
        'alt_sources': [
            'https://www.indian-river.org/departments/tax-collector/tax-deed-sales',
            'https://www.clerk.indian-river.org/court-records'
        ],
        'sale_types': ['foreclosure', 'tax_deed'],
        'batch_size': 100
    },
    'volusia': {
        'priority': 'critical',  # 5,481 closed, need 5,207+ verified
        'clerk_name': 'Volusia County Clerk',
        'clerk_portal': 'https://vdp.vcpa.volusia.org/',
        'acclaim_endpoint': 'DISCOVER', 
        'alt_sources': [
            'https://www.volusia.org/services/community-services/property-tax/tax-deeds/',
            'https://www.clerk.org/public-records/'
        ],
        'sale_types': ['foreclosure', 'tax_deed'],
        'batch_size': 200
    },
    'lee': {
        'priority': 'critical',  # 5,862 closed, need 5,569+ verified  
        'clerk_name': 'Lee County Clerk',
        'clerk_portal': 'https://www2.leeclerk.org/',
        'acclaim_endpoint': 'DISCOVER',
        'alt_sources': [
            'https://www.leegov.com/taxcollector/taxdeeds',
            'https://www.leeclerk.org/public-records'
        ],
        'sale_types': ['foreclosure', 'tax_deed'],
        'batch_size': 200
    },
    'desoto': {
        'priority': 'future',    # 0 closed - bootstrap first
        'clerk_name': 'DeSoto County Clerk',
        'clerk_portal': 'https://www.desotoclerk.com/',
        'acclaim_endpoint': 'DISCOVER',
        'alt_sources': [],
        'sale_types': ['foreclosure', 'tax_deed'],
        'batch_size': 50
    },
    'monroe': {
        'priority': 'future',    # 0 closed - bootstrap first
        'clerk_name': 'Monroe County Clerk',
        'clerk_portal': 'https://www.clerk.co.monroe.fl.us/',
        'acclaim_endpoint': 'DISCOVER',
        'alt_sources': [],
        'sale_types': ['foreclosure', 'tax_deed'],
        'batch_size': 50
    }
}

class VerifiedOutcomesScraper:
    def __init__(self, dry_run=False, max_records=1000):
        self.dry_run = dry_run
        self.max_records = max_records
        self.results = {}
        self.session_stats = {
            'start_time': datetime.now(timezone.utc),
            'counties_processed': 0,
            'outcomes_scraped': 0,
            'outcomes_matched': 0,
            'verification_rate_improvements': {}
        }
        
    def get_current_verification_status(self, county: str) -> Dict:
        """Get current Letter B verification metrics"""
        try:
            # Get closed auctions
            closed_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=BASE_HEADERS,
                params={
                    'county': f'eq.{county}',
                    'auction_status': 'in.(sold,no_sale,canceled)',
                    'select': 'id,case_number,sale_type'
                }
            )
            
            if closed_response.status_code != 200:
                logger.error(f"Failed to get closed auctions for {county}")
                return {}
            
            closed_auctions = closed_response.json()
            
            # Get verified outcomes for foreclosures
            fc_outcomes_response = client.get(
                f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes",
                headers=BASE_HEADERS,
                params={
                    'county_slug': f'eq.{county}',
                    'data_source': 'not.ilike.*propertyonion*',  # Independent sources only
                    'select': 'id,case_number'
                }
            )
            
            # Get verified outcomes for tax deeds
            td_outcomes_response = client.get(
                f"{SUPABASE_URL}/rest/v1/tax_deed_outcomes",
                headers=BASE_HEADERS,
                params={
                    'county_slug': f'eq.{county}',
                    'data_source': 'not.ilike.*propertyonion*',  # Independent sources only
                    'select': 'id,case_number'
                }
            )
            
            fc_outcomes = fc_outcomes_response.json() if fc_outcomes_response.status_code == 200 else []
            td_outcomes = td_outcomes_response.json() if td_outcomes_response.status_code == 200 else []
            
            total_closed = len(closed_auctions)
            total_verified = len(fc_outcomes) + len(td_outcomes)
            verification_pct = (total_verified / total_closed * 100) if total_closed > 0 else 0
            
            return {
                'county': county,
                'total_closed': total_closed,
                'foreclosure_outcomes': len(fc_outcomes),
                'tax_deed_outcomes': len(td_outcomes),
                'total_verified': total_verified,
                'verification_pct': verification_pct,
                'target_verified': int(total_closed * 0.95),
                'gap_to_95pct': max(0, int(total_closed * 0.95) - total_verified),
                'letter_b_status': 'PASS' if verification_pct >= 95.0 else 'FAIL'
            }
            
        except Exception as e:
            logger.error(f"Error getting verification status for {county}: {e}")
            return {}
    
    def discover_acclaim_endpoint(self, county: str, config: Dict) -> Optional[str]:
        """Discover if county uses AcclaimWeb system like Duval"""
        clerk_portal = config['clerk_portal']
        
        # Common AcclaimWeb URL patterns
        acclaim_patterns = [
            f"https://vaclmweb1.{county}clerk.us/AcclaimWeb/",
            f"https://vaclmweb.{county}clerk.us/AcclaimWeb/",
            f"https://acclaim.{county}clerk.org/",
            f"https://records.{county}clerk.org/AcclaimWeb/"
        ]
        
        logger.info(f"  Testing AcclaimWeb endpoints for {county}...")
        
        for pattern in acclaim_patterns:
            try:
                if self.dry_run:
                    logger.info(f"    Would test: {pattern}")
                    continue
                    
                response = client.head(pattern, timeout=10)
                if response.status_code == 200:
                    logger.info(f"    ✅ Found AcclaimWeb: {pattern}")
                    return pattern
                else:
                    logger.debug(f"    ❌ {pattern} returned {response.status_code}")
                    
            except Exception as e:
                logger.debug(f"    ❌ {pattern} failed: {e}")
                continue
        
        logger.info(f"  ⚠️  No AcclaimWeb endpoint found for {county}")
        return None
    
    def scrape_acclaim_certificates(self, county: str, acclaim_url: str, months_back: int = 6) -> List[Dict]:
        """Scrape Certificate of Title records from AcclaimWeb (Duval pattern)"""
        outcomes = []
        
        if not FIRECRAWL_KEY:
            logger.warning(f"  No Firecrawl key - skipping AcclaimWeb scrape")
            return outcomes
            
        try:
            # Build search query for Certificate of Title documents
            end_date = date.today()
            start_date = end_date - timedelta(days=months_back * 30)
            
            search_params = {
                'doc_type': 'CT',  # Certificate of Title
                'recorded_from': start_date.strftime('%m/%d/%Y'),
                'recorded_to': end_date.strftime('%m/%d/%Y')
            }
            
            logger.info(f"  Searching AcclaimWeb for CT records: {start_date} to {end_date}")
            
            if self.dry_run:
                logger.info(f"    Would search AcclaimWeb at {acclaim_url} with params: {search_params}")
                
                # Return mock data for testing
                return [{
                    'county_slug': county,
                    'case_number': f'MOCK-{county}-001',
                    'certificate_number': f'CT{county}123',
                    'sale_date': end_date.isoformat(),
                    'sale_amount': 50000.00,
                    'buyer_name': 'Mock Buyer LLC',
                    'data_source': f'acclaim_ct:{county.upper()}-FC-V1',
                    'confidence_level': 'high'
                }]
            
            # Use Firecrawl to scrape AcclaimWeb search results
            # This would implement the actual scraping logic
            logger.info(f"  Would implement AcclaimWeb scraping for {county}")
            
        except Exception as e:
            logger.error(f"  Error scraping AcclaimWeb for {county}: {e}")
        
        return outcomes
    
    def scrape_clerk_portal(self, county: str, config: Dict) -> List[Dict]:
        """Scrape outcome records from county clerk portal"""
        outcomes = []
        clerk_portal = config['clerk_portal']
        
        logger.info(f"  Scraping clerk portal: {clerk_portal}")
        
        try:
            if self.dry_run:
                logger.info(f"    Would scrape {config['clerk_name']} portal")
                # Return mock outcomes for testing
                return [{
                    'county_slug': county,
                    'case_number': f'MOCK-{county}-PORTAL-001',
                    'sale_date': date.today().isoformat(),
                    'sale_amount': 75000.00,
                    'sale_status': 'sold',
                    'buyer_name': 'Mock Portal Buyer',
                    'data_source': f'clerk_portal:{county}',
                    'confidence_level': 'medium'
                }]
            
            # Implement portal-specific scraping logic
            # Each county may have different portal structures
            
        except Exception as e:
            logger.error(f"  Error scraping clerk portal for {county}: {e}")
        
        return outcomes
    
    def match_outcomes_to_auctions(self, county: str, scraped_outcomes: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """Match scraped outcomes to existing auctions in multi_county_auctions"""
        matched_outcomes = []
        unmatched_outcomes = []
        
        if not scraped_outcomes:
            return matched_outcomes, unmatched_outcomes
        
        logger.info(f"  Matching {len(scraped_outcomes)} outcomes to auction records...")
        
        try:
            # Get all auction case numbers for the county
            auctions_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
                headers=BASE_HEADERS,
                params={
                    'county': f'eq.{county}',
                    'select': 'id,case_number,sale_type,auction_date',
                    'limit': '10000'
                }
            )
            
            if auctions_response.status_code != 200:
                logger.error(f"  Failed to get auctions for matching")
                return matched_outcomes, scraped_outcomes
            
            auctions = auctions_response.json()
            auction_lookup = {a['case_number']: a for a in auctions if a.get('case_number')}
            
            for outcome in scraped_outcomes:
                case_number = outcome.get('case_number', '').strip()
                
                if not case_number:
                    unmatched_outcomes.append(outcome)
                    continue
                
                # Try exact match first
                if case_number in auction_lookup:
                    auction = auction_lookup[case_number]
                    matched_outcome = {
                        **outcome,
                        'auction_id': auction['id'],
                        'matched_auction_date': auction['auction_date'],
                        'match_method': 'exact_case_number'
                    }
                    matched_outcomes.append(matched_outcome)
                    continue
                
                # Try fuzzy matching (remove common prefixes/suffixes)
                normalized_case = re.sub(r'^(FC|TD|CA)-?', '', case_number, flags=re.IGNORECASE)
                normalized_case = re.sub(r'-?(FC|TD|CA)$', '', normalized_case, flags=re.IGNORECASE)
                
                fuzzy_matches = [
                    a for a in auctions 
                    if a.get('case_number') and normalized_case in a['case_number']
                ]
                
                if len(fuzzy_matches) == 1:
                    auction = fuzzy_matches[0]
                    matched_outcome = {
                        **outcome,
                        'auction_id': auction['id'],
                        'matched_auction_date': auction['auction_date'],
                        'match_method': 'fuzzy_case_number'
                    }
                    matched_outcomes.append(matched_outcome)
                    continue
                
                # No match found
                outcome['match_status'] = 'no_auction_found'
                unmatched_outcomes.append(outcome)
            
            logger.info(f"  Matched: {len(matched_outcomes)}, Unmatched: {len(unmatched_outcomes)}")
            
        except Exception as e:
            logger.error(f"  Error matching outcomes: {e}")
            return matched_outcomes, scraped_outcomes
        
        return matched_outcomes, unmatched_outcomes
    
    def upsert_verified_outcomes(self, county: str, matched_outcomes: List[Dict]) -> int:
        """Insert verified outcomes into appropriate tables"""
        if not matched_outcomes:
            return 0
        
        foreclosure_outcomes = []
        tax_deed_outcomes = []
        
        for outcome in matched_outcomes:
            case_number = outcome.get('case_number', '')
            
            # Determine table based on case number or sale type
            if (any(prefix in case_number.upper() for prefix in ['FC', 'FORECL']) or 
                outcome.get('sale_type') == 'foreclosure'):
                table = 'foreclosure_outcomes'
                foreclosure_outcomes.append(outcome)
            else:
                table = 'tax_deed_outcomes'
                tax_deed_outcomes.append(outcome)
        
        upserted_count = 0
        
        # Upsert foreclosure outcomes
        if foreclosure_outcomes:
            if self.dry_run:
                logger.info(f"  Would upsert {len(foreclosure_outcomes)} foreclosure outcomes")
                upserted_count += len(foreclosure_outcomes)
            else:
                try:
                    response = client.post(
                        f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes",
                        headers={**BASE_HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=foreclosure_outcomes
                    )
                    
                    if response.status_code in [200, 201]:
                        logger.info(f"  ✅ Upserted {len(foreclosure_outcomes)} foreclosure outcomes")
                        upserted_count += len(foreclosure_outcomes)
                    else:
                        logger.error(f"  ❌ Foreclosure upsert failed: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"  ❌ Foreclosure upsert error: {e}")
        
        # Upsert tax deed outcomes
        if tax_deed_outcomes:
            if self.dry_run:
                logger.info(f"  Would upsert {len(tax_deed_outcomes)} tax deed outcomes")
                upserted_count += len(tax_deed_outcomes)
            else:
                try:
                    response = client.post(
                        f"{SUPABASE_URL}/rest/v1/tax_deed_outcomes",
                        headers={**BASE_HEADERS, "Prefer": "resolution=merge-duplicates"},
                        json=tax_deed_outcomes
                    )
                    
                    if response.status_code in [200, 201]:
                        logger.info(f"  ✅ Upserted {len(tax_deed_outcomes)} tax deed outcomes")
                        upserted_count += len(tax_deed_outcomes)
                    else:
                        logger.error(f"  ❌ Tax deed upsert failed: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"  ❌ Tax deed upsert error: {e}")
        
        return upserted_count
    
    def process_county_outcomes(self, county: str, config: Dict) -> Dict:
        """Process verified outcomes for a single county"""
        logger.info(f"\n{'='*60}")
        logger.info(f"PROCESSING OUTCOMES: {county.upper()} (priority: {config['priority']})")
        logger.info(f"{'='*60}")
        
        # Check current status
        before_status = self.get_current_verification_status(county)
        if not before_status:
            return {'error': 'Failed to get baseline status'}
            
        logger.info(f"  Current status:")
        logger.info(f"    Closed auctions: {before_status['total_closed']:,}")
        logger.info(f"    Verified outcomes: {before_status['total_verified']:,}")
        logger.info(f"    Verification rate: {before_status['verification_pct']:.1f}%")
        logger.info(f"    Gap to 95%: {before_status['gap_to_95pct']:,} outcomes needed")
        
        if before_status['verification_pct'] >= 95.0:
            logger.info(f"  ✅ Already above 95% threshold!")
            return {
                'county': county,
                'status': 'already_passing',
                'before_status': before_status,
                'after_status': before_status
            }
        
        if before_status['total_closed'] == 0:
            logger.info(f"  ⚠️  No closed auctions - county needs bootstrap first")
            return {
                'county': county,
                'status': 'needs_bootstrap',
                'before_status': before_status
            }
        
        all_outcomes = []
        
        # Method 1: Try AcclaimWeb if available
        acclaim_url = self.discover_acclaim_endpoint(county, config)
        if acclaim_url:
            logger.info(f"  📜 Scraping AcclaimWeb certificates...")
            acclaim_outcomes = self.scrape_acclaim_certificates(county, acclaim_url)
            all_outcomes.extend(acclaim_outcomes)
            logger.info(f"    Found {len(acclaim_outcomes)} AcclaimWeb records")
        
        # Method 2: Clerk portal scraping
        logger.info(f"  🏛️  Scraping clerk portal...")
        portal_outcomes = self.scrape_clerk_portal(county, config)
        all_outcomes.extend(portal_outcomes)
        logger.info(f"    Found {len(portal_outcomes)} portal records")
        
        # Match outcomes to auction records
        logger.info(f"  🔗 Matching outcomes to auctions...")
        matched_outcomes, unmatched_outcomes = self.match_outcomes_to_auctions(county, all_outcomes)
        
        # Insert verified outcomes
        logger.info(f"  💾 Upserting verified outcomes...")
        upserted_count = self.upsert_verified_outcomes(county, matched_outcomes)
        
        # Check final status
        after_status = self.get_current_verification_status(county)
        
        if after_status:
            improvement = after_status['verification_pct'] - before_status['verification_pct']
            logger.info(f"  📊 Final status:")
            logger.info(f"    Verified outcomes: {after_status['total_verified']:,} (+{after_status['total_verified'] - before_status['total_verified']:,})")
            logger.info(f"    Verification rate: {after_status['verification_pct']:.1f}% (+{improvement:.1f}%)")
            
            if after_status['verification_pct'] >= 95.0:
                logger.info(f"  🎯 LETTER B: PASS (≥95% threshold)")
                status = 'pass_achieved'
            else:
                remaining_gap = after_status['gap_to_95pct']
                logger.info(f"  📈 LETTER B: IMPROVED (need {remaining_gap:,} more)")
                status = 'improved'
        else:
            after_status = before_status
            status = 'no_change'
        
        result = {
            'county': county,
            'status': status,
            'before_status': before_status,
            'after_status': after_status,
            'outcomes_scraped': len(all_outcomes),
            'outcomes_matched': len(matched_outcomes),
            'outcomes_upserted': upserted_count,
            'unmatched_count': len(unmatched_outcomes)
        }
        
        self.session_stats['outcomes_scraped'] += len(all_outcomes)
        self.session_stats['outcomes_matched'] += len(matched_outcomes)
        if improvement := after_status['verification_pct'] - before_status['verification_pct']:
            self.session_stats['verification_rate_improvements'][county] = improvement
        
        return result
    
    def run_outcomes_pipeline(self):
        """Run verified outcomes pipeline for all counties"""
        logger.info(f"SHARD-8 VERIFIED OUTCOMES PIPELINE")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"Max records per county: {self.max_records:,}")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        
        # Process counties by priority (skip future ones if no auctions)
        critical_counties = [k for k, v in COUNTY_CLERK_CONFIGS.items() if v.get('priority') == 'critical']
        high_counties = [k for k, v in COUNTY_CLERK_CONFIGS.items() if v.get('priority') == 'high']
        future_counties = [k for k, v in COUNTY_CLERK_CONFIGS.items() if v.get('priority') == 'future']
        
        logger.info(f"\nCritical priority: {critical_counties}")
        logger.info(f"High priority: {high_counties}")
        logger.info(f"Future (bootstrap first): {future_counties}")
        
        counties_to_process = critical_counties + high_counties
        
        for county in counties_to_process:
            config = COUNTY_CLERK_CONFIGS[county]
            
            try:
                result = self.process_county_outcomes(county, config)
                self.results[county] = result
                self.session_stats['counties_processed'] += 1
                
                # Rate limiting
                time.sleep(2)
                
            except KeyboardInterrupt:
                logger.info(f"\n\n⚠️  Pipeline interrupted by user")
                break
            except Exception as e:
                logger.error(f"\n❌ FAILED to process {county}: {e}")
                self.results[county] = {
                    'county': county,
                    'status': 'failed',
                    'error': str(e)
                }
        
        # Final summary
        self.print_summary()
    
    def print_summary(self):
        """Print pipeline summary"""
        elapsed = datetime.now(timezone.utc) - self.session_stats['start_time']
        
        logger.info(f"\n{'='*80}")
        logger.info(f"VERIFIED OUTCOMES PIPELINE SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Session time: {elapsed.total_seconds()/60:.1f} minutes")
        logger.info(f"Counties processed: {self.session_stats['counties_processed']}")
        logger.info(f"Outcomes scraped: {self.session_stats['outcomes_scraped']:,}")
        logger.info(f"Outcomes matched: {self.session_stats['outcomes_matched']:,}")
        
        for county, result in self.results.items():
            if result.get('error'):
                logger.info(f"\n{county.upper()}: ❌ FAILED - {result['error']}")
                continue
            
            status = result.get('status', 'unknown')
            before = result.get('before_status', {})
            after = result.get('after_status', {})
            
            before_pct = before.get('verification_pct', 0)
            after_pct = after.get('verification_pct', 0)
            improvement = after_pct - before_pct
            
            logger.info(f"\n{county.upper()} ({status}):")
            logger.info(f"  Before: {before_pct:.1f}% verified ({before.get('total_verified', 0):,} of {before.get('total_closed', 0):,})")
            logger.info(f"  After:  {after_pct:.1f}% verified ({after.get('total_verified', 0):,} of {after.get('total_closed', 0):,})")
            logger.info(f"  Improvement: +{improvement:.1f}%")
            logger.info(f"  Outcomes upserted: {result.get('outcomes_upserted', 0):,}")
            
            if after_pct >= 95.0:
                logger.info(f"  🎯 LETTER B: PASS (≥95% threshold)")
            else:
                remaining = 95.0 - after_pct
                gap = after.get('gap_to_95pct', 0)
                logger.info(f"  📊 LETTER B: FAIL (need +{remaining:.1f}%, {gap:,} more outcomes)")
        
        logger.info(f"\n📋 NEXT ACTIONS:")
        logger.info(f"1. For counties still failing: Expand scraper coverage (more document types)")
        logger.info(f"2. Verify Letter B improvements: SELECT public.pencil_dod_evaluate_county('<county>');")
        logger.info(f"3. For high-volume counties: Build automated daily collection pipelines")
        logger.info(f"4. Consider additional data sources: title companies, foreclosure services")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build verified outcomes pipeline for SHARD-8 Letter B")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--county", help="Process single county only")
    parser.add_argument("--max-records", type=int, default=1000, help="Max records per county")
    args = parser.parse_args()
    
    # Filter to single county if specified
    configs = COUNTY_CLERK_CONFIGS
    if args.county:
        if args.county in COUNTY_CLERK_CONFIGS:
            configs = {args.county: COUNTY_CLERK_CONFIGS[args.county]}
        else:
            print(f"ERROR: {args.county} not in target list: {list(COUNTY_CLERK_CONFIGS.keys())}")
            sys.exit(1)
    
    scraper = VerifiedOutcomesScraper(dry_run=args.dry_run, max_records=args.max_records)
    
    # Temporarily override configs
    global COUNTY_CLERK_CONFIGS
    COUNTY_CLERK_CONFIGS = configs
    
    try:
        scraper.run_outcomes_pipeline()
    except KeyboardInterrupt:
        logger.info(f"\nOutcomes pipeline interrupted by user")
    finally:
        client.close()

if __name__ == "__main__":
    main()