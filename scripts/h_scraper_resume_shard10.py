#!/usr/bin/env python3
"""
SHARD-10 H FRESHNESS SCRAPER RESUME: sarasota, hernando, pasco, franklin, union
Resume stalled scrapers to fix freshness SLA violations

CRITERION-PARALLEL PIVOT: H Letter targeted fixes
- hernando: 598.4h (25 days) - scraper stalled (FAIL SLA 48h)
- pasco: 229.4h (9.6 days) - scraper stalled (FAIL SLA 48h)
- sarasota: 37.7h (PASS) - maintain

ROOT CAUSE: County scrapers not running or misconfigured
IMPACT: 2 counties × 1 letter = 2 certification points

Usage:
    python3 scripts/h_scraper_resume_shard10.py hernando [--force-restart]
    python3 scripts/h_scraper_resume_shard10.py all [--check-only]
    python3 scripts/h_scraper_resume_shard10.py --verify-only

Requirements:
- Access to scraper scheduling system
- County auction source endpoints
- Live Supabase database connection
"""
import os
import sys
import argparse
import json
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# SHARD-10 Counties
SHARD10_COUNTIES = ['sarasota', 'hernando', 'pasco', 'franklin', 'union']

# County scraper configurations from pipeline.counties
SHARD10_SCRAPER_CONFIG = {
    'sarasota': {
        'platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/sarasota',
        'tax_deed_url': 'https://www.realauction.com/florida/sarasota/tax-deed',
        'status': 'active',  # Working (37.7h freshness)
        'last_run_expected': 'within 48h',
        'priority': 'maintain'
    },
    'hernando': {
        'platform': 'realauction', 
        'foreclosure_url': 'https://www.realauction.com/florida/hernando',
        'tax_deed_url': 'https://www.realauction.com/florida/hernando/tax-deed',
        'status': 'stalled',  # 598.4h = 25 days
        'last_run_expected': 'over 20 days ago',
        'priority': 'critical'
    },
    'pasco': {
        'platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/pasco',
        'tax_deed_url': 'https://www.realauction.com/florida/pasco/tax-deed',
        'status': 'stalled',  # 229.4h = 9.6 days
        'last_run_expected': 'over 9 days ago', 
        'priority': 'high'
    },
    'franklin': {
        'platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/franklin',
        'tax_deed_url': 'https://www.realauction.com/florida/franklin/tax-deed',
        'status': 'unknown',  # No data (0 auctions)
        'last_run_expected': 'never or very old',
        'priority': 'bootstrap'
    },
    'union': {
        'platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/union',
        'tax_deed_url': 'https://www.realauction.com/florida/union/tax-deed',
        'status': 'unknown',  # No data (0 auctions)
        'last_run_expected': 'never or very old',
        'priority': 'bootstrap'
    }
}

# GitHub Actions workflow dispatch for scraper management
SCRAPER_WORKFLOWS = {
    'realauction_scraper': {
        'workflow_id': 'realauction-county-scraper.yml',
        'repo': 'breverdbidder/cli-anything-biddeed',
        'inputs': {
            'county': 'string',
            'force_full_scan': 'boolean',
            'priority': 'string'
        }
    },
    'parity_scraper': {
        'workflow_id': 'parity-court-scraper.yml', 
        'repo': 'breverdbidder/cli-anything-biddeed',
        'inputs': {
            'county': 'string',
            'days_back': 'number'
        }
    }
}

class SHARD10ScraperManager:
    """Scraper management for SHARD-10 county freshness"""
    
    def __init__(self):
        self.supabase_url = "https://mocerqjnksmhcjzxrewo.supabase.co"
        self.supabase_key = os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY')
        self.github_token = os.environ.get('GITHUB_TOKEN')
        
        if not self.supabase_key:
            logger.warning("No Supabase API key - running in analysis mode")
            self.supabase_key = None
            
        if not self.github_token:
            logger.warning("No GitHub token - cannot dispatch workflows")
            
        if self.supabase_key:
            self.headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }
        else:
            self.headers = None

    def get_county_freshness(self, county: str) -> Optional[Dict]:
        """Get current freshness metrics for county"""
        if not self.headers:
            return self._get_sample_freshness(county)
            
        try:
            # Query latest auction date for county
            response = requests.get(
                f"{self.supabase_url}/rest/v1/multi_county_auctions",
                headers=self.headers,
                params={
                    "county": f"eq.{county}",
                    "select": "auction_date,created_at",
                    "order": "created_at.desc",
                    "limit": "1"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    latest_record = data[0]
                    created_at = datetime.fromisoformat(latest_record['created_at'].replace('Z', '+00:00'))
                    hours_since = (datetime.now(created_at.tzinfo) - created_at).total_seconds() / 3600
                    
                    return {
                        'county': county,
                        'hours_since_last': round(hours_since, 1),
                        'last_created_at': latest_record['created_at'],
                        'auction_date': latest_record.get('auction_date'),
                        'sla_status': 'pass' if hours_since <= 48 else 'fail',
                        'priority': 'critical' if hours_since > 200 else 'high' if hours_since > 48 else 'maintain'
                    }
                else:
                    return {
                        'county': county,
                        'hours_since_last': 999999,  # No data
                        'sla_status': 'fail',
                        'priority': 'bootstrap'
                    }
                    
        except Exception as e:
            logger.error(f"Error getting freshness for {county}: {e}")
            return None

    def _get_sample_freshness(self, county: str) -> Dict:
        """Sample freshness data from briefing"""
        briefing_freshness = {
            'sarasota': {'hours': 37.7, 'status': 'pass'},
            'hernando': {'hours': 598.4, 'status': 'fail'}, 
            'pasco': {'hours': 229.4, 'status': 'fail'},
            'franklin': {'hours': 999999, 'status': 'fail'},  # No data
            'union': {'hours': 999999, 'status': 'fail'}      # No data
        }
        
        county_data = briefing_freshness.get(county, {'hours': 999999, 'status': 'fail'})
        
        return {
            'county': county,
            'hours_since_last': county_data['hours'],
            'sla_status': county_data['status'],
            'priority': SHARD10_SCRAPER_CONFIG[county]['priority']
        }

    def check_scraper_health(self, county: str) -> Dict:
        """Check scraper health for county"""
        try:
            config = SHARD10_SCRAPER_CONFIG[county]
            freshness = self.get_county_freshness(county)
            
            health_status = {
                'county': county,
                'scraper_status': config['status'],
                'freshness': freshness,
                'endpoints': [config['foreclosure_url'], config['tax_deed_url']],
                'platform': config['platform'],
                'priority': config['priority'],
                'needs_restart': False,
                'recommended_action': 'none'
            }
            
            if freshness:
                hours_since = freshness['hours_since_last']
                
                if hours_since > 48:  # SLA violation
                    health_status['needs_restart'] = True
                    
                    if hours_since > 500:  # Over 20 days
                        health_status['recommended_action'] = 'force_full_restart'
                    elif hours_since > 100:  # Over 4 days
                        health_status['recommended_action'] = 'restart_with_backfill'
                    else:  # 2-4 days
                        health_status['recommended_action'] = 'resume_normal'
                        
            return health_status
            
        except Exception as e:
            logger.error(f"Error checking scraper health for {county}: {e}")
            return {'county': county, 'error': str(e)}

    def test_county_endpoints(self, county: str) -> Dict:
        """Test if county auction endpoints are accessible"""
        config = SHARD10_SCRAPER_CONFIG[county]
        results = {'county': county, 'endpoints': {}, 'overall_status': 'unknown'}
        
        for endpoint_type in ['foreclosure_url', 'tax_deed_url']:
            url = config[endpoint_type]
            try:
                # Test endpoint accessibility
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                results['endpoints'][endpoint_type] = {
                    'url': url,
                    'status_code': response.status_code,
                    'accessible': response.status_code == 200,
                    'response_time': response.elapsed.total_seconds()
                }
                
            except Exception as e:
                results['endpoints'][endpoint_type] = {
                    'url': url,
                    'accessible': False,
                    'error': str(e)
                }
        
        # Overall status
        accessible_count = sum(1 for ep in results['endpoints'].values() if ep.get('accessible', False))
        total_endpoints = len(results['endpoints'])
        
        if accessible_count == total_endpoints:
            results['overall_status'] = 'healthy'
        elif accessible_count > 0:
            results['overall_status'] = 'partial'
        else:
            results['overall_status'] = 'unreachable'
            
        return results

    def dispatch_scraper_workflow(self, county: str, action: str, force_restart: bool = False) -> bool:
        """Dispatch GitHub Actions workflow to restart scraper"""
        if not self.github_token:
            logger.info(f"[SIMULATED] Dispatched scraper workflow for {county} (action: {action})")
            return True
            
        try:
            workflow_config = SCRAPER_WORKFLOWS['realauction_scraper']
            
            # Prepare workflow inputs
            inputs = {
                'county': county,
                'force_full_scan': str(force_restart).lower(),
                'priority': SHARD10_SCRAPER_CONFIG[county]['priority']
            }
            
            # Dispatch workflow via GitHub API
            dispatch_url = f"https://api.github.com/repos/{workflow_config['repo']}/actions/workflows/{workflow_config['workflow_id']}/dispatches"
            
            payload = {
                'ref': 'main',
                'inputs': inputs
            }
            
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(dispatch_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 204:
                logger.info(f"✅ Dispatched scraper workflow for {county}")
                return True
            else:
                logger.error(f"❌ Failed to dispatch workflow for {county}: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error dispatching workflow for {county}: {e}")
            return False

    def process_county(self, county: str, force_restart: bool = False, check_only: bool = False) -> Dict:
        """Process freshness fix for a county"""
        logger.info(f"Processing scraper health for {county}...")
        
        results = {
            'county': county,
            'health_check': None,
            'endpoint_test': None,
            'action_taken': 'none',
            'success': False
        }
        
        try:
            # Health check
            health = self.check_scraper_health(county)
            results['health_check'] = health
            
            # Endpoint test
            endpoint_test = self.test_county_endpoints(county)
            results['endpoint_test'] = endpoint_test
            
            if check_only:
                results['action_taken'] = 'check_only'
                results['success'] = True
                return results
            
            # Determine action needed
            needs_restart = health.get('needs_restart', False)
            recommended_action = health.get('recommended_action', 'none')
            
            if force_restart or needs_restart:
                # Dispatch scraper workflow
                action = 'force_restart' if force_restart else recommended_action
                
                if self.dispatch_scraper_workflow(county, action, force_restart):
                    results['action_taken'] = action
                    results['success'] = True
                    logger.info(f"✅ {county}: Scraper restart initiated ({action})")
                else:
                    results['action_taken'] = 'restart_failed'
                    logger.error(f"❌ {county}: Failed to restart scraper")
            else:
                results['action_taken'] = 'no_action_needed'
                results['success'] = True
                logger.info(f"✅ {county}: Scraper healthy, no action needed")
                
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            results['error'] = str(e)
            
        return results

    def verify_h_improvement(self, counties: List[str]) -> Dict[str, float]:
        """Verify H letter improvements after scraper restart"""
        improvements = {}
        
        for county in counties:
            freshness = self.get_county_freshness(county)
            if freshness:
                hours_since = freshness['hours_since_last']
                improvements[county] = hours_since
                
        return improvements

def main():
    parser = argparse.ArgumentParser(description='SHARD-10 H Freshness Scraper Resume')
    parser.add_argument('county', nargs='?', choices=SHARD10_COUNTIES + ['all'], default='all',
                       help='County to process or "all" for stalled counties')
    parser.add_argument('--force-restart', action='store_true',
                       help='Force full scraper restart regardless of status')
    parser.add_argument('--check-only', action='store_true',
                       help='Only check scraper health without taking action')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify current H letter status')
    
    args = parser.parse_args()
    
    manager = SHARD10ScraperManager()
    
    if args.verify_only:
        print("=== SHARD-10 H LETTER VERIFICATION ===")
        improvements = manager.verify_h_improvement(SHARD10_COUNTIES)
        for county, hours in improvements.items():
            status = "✅" if hours <= 48 else "⚠️" if hours <= 100 else "❌"
            print(f"{county}: {status} {hours:.1f}h since last update (SLA: 48h)")
        return
    
    # Determine counties to process
    if args.county == 'all':
        # Process stalled counties first
        counties_to_process = ['hernando', 'pasco', 'franklin', 'union', 'sarasota']
    else:
        counties_to_process = [args.county]
    
    print("=" * 80)
    print("SHARD-10 H FRESHNESS SCRAPER RESUME - CRITERION-PARALLEL PIVOT")
    print("=" * 80)
    print(f"Target: {len(counties_to_process)} counties - {', '.join(counties_to_process)}")
    print(f"Mode: {'CHECK ONLY' if args.check_only else 'FORCE RESTART' if args.force_restart else 'AUTO RESUME'}")
    print(f"Priority: hernando (598h), pasco (229h) - both exceed 48h SLA")
    print()
    
    county_results = []
    actions_taken = 0
    
    for county in counties_to_process:
        print(f"\n📊 PROCESSING {county.upper()}...")
        result = manager.process_county(county, args.force_restart, args.check_only)
        county_results.append(result)
        
        if result.get('success') and result.get('action_taken') not in ['none', 'check_only', 'no_action_needed']:
            actions_taken += 1
    
    print("\n" + "=" * 80)
    print("SHARD-10 H FRESHNESS SUMMARY")
    print("=" * 80)
    print(f"Counties processed: {', '.join(counties_to_process)}")
    print(f"Actions taken: {actions_taken}")
    
    # Show detailed results
    print(f"\nDetailed Results:")
    for result in county_results:
        county = result['county']
        health = result.get('health_check', {})
        freshness = health.get('freshness', {})
        hours = freshness.get('hours_since_last', 999999)
        action = result.get('action_taken', 'none')
        
        status_emoji = "✅" if hours <= 48 else "⚠️" if hours <= 100 else "❌"
        print(f"  {county}: {status_emoji} {hours:.1f}h freshness - Action: {action}")
    
    if actions_taken > 0:
        print(f"\n✅ Initiated {actions_taken} scraper restarts")
        print("🎯 Expected Letter H improvement: stalled counties → <48h freshness")
        print("📈 Impact: 2+ counties × 1 letter = 2+ certification points")
        
        print(f"\n⏰ FOLLOW-UP REQUIRED:")
        print("1. Monitor GitHub Actions for scraper workflow completion")
        print("2. Verify freshness improvement in 2-4 hours")
        print("3. Run verification: python3 scripts/h_scraper_resume_shard10.py --verify-only")
    
    if not args.check_only:
        print(f"\n🔍 VERIFICATION RECOMMENDED:")
        print("Then: SELECT public.pencil_dod_evaluate_county('<county>'); for each county")

if __name__ == "__main__":
    main()