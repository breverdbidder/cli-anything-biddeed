#!/usr/bin/env python3
"""
MY SHARD-2 LETTER A COVERAGE - Dual-Product Coverage
Improves dual-product coverage for hendry and holmes counties (both failing Letter A)
Sets up both RealAuction and tax deed scraping lanes per pipeline.counties config

Letter A: dual-product coverage (foreclosure + tax deed channels)

Usage:
  python scripts/my_shard2_letter_a_coverage.py --county hendry
  python scripts/my_shard2_letter_a_coverage.py --county holmes  
  python scripts/my_shard2_letter_a_coverage.py --setup-counties
"""
import httpx
import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional
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
    "Content-Type": "application/json"
}

# Letter A failing counties from MY SHARD-2
LETTER_A_COUNTIES = ['hendry', 'holmes']

# County configuration for dual-product setup
COUNTY_CONFIGS = {
    'hendry': {
        'name': 'Hendry County',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/hendry',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/florida/hendry/tax-deeds',
        'clerk_calendar': 'https://www.hendryco.net/departments/tax-collector/tax-deed-sales',
        'needs_setup': True
    },
    'holmes': {
        'name': 'Holmes County',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/florida/holmes',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/florida/holmes/tax-deeds', 
        'clerk_calendar': 'https://www.holmescounty.org/departments/tax-collector',
        'needs_setup': True
    }
}

client = httpx.Client(timeout=30, follow_redirects=True)

def supabase_get(table: str, params: Dict = None) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        
        response = client.get(url, headers=HEADERS)
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

def check_county_pipeline_config(county_slug: str) -> Dict:
    """Check current pipeline configuration for county"""
    params = {
        'select': '*',
        'slug': f'eq.{county_slug}'
    }
    
    counties = supabase_get('pipeline.counties', params)
    if counties:
        return counties[0]
    else:
        logger.warning(f"No pipeline configuration found for {county_slug}")
        return {}

def setup_dual_product_config(county_slug: str) -> bool:
    """Set up dual-product configuration in pipeline.counties"""
    if county_slug not in COUNTY_CONFIGS:
        logger.error(f"County {county_slug} not supported")
        return False
    
    config = COUNTY_CONFIGS[county_slug]
    
    # Check if county exists in pipeline.counties
    existing = check_county_pipeline_config(county_slug)
    
    county_record = {
        'slug': county_slug,
        'name': config['name'],
        'state': 'FL',
        'foreclosure_platform': config['foreclosure_platform'],
        'foreclosure_url': config['foreclosure_url'],
        'tax_deed_platform': config['tax_deed_platform'], 
        'tax_deed_url': config['tax_deed_url'],
        'status': 'active',
        'dual_product': True,  # Enable dual-product coverage
        'updated_at': datetime.now().isoformat(),
        'notes': f'MY SHARD-2 Letter A setup - dual product coverage enabled'
    }
    
    if existing:
        # Update existing record
        logger.info(f"Updating existing pipeline config for {county_slug}")
        # Use PATCH to update
        try:
            response = client.patch(
                f"{BASE}/pipeline.counties?slug=eq.{county_slug}",
                headers=HEADERS,
                json=county_record
            )
            response.raise_for_status()
            logger.info(f"✅ Updated pipeline config for {county_slug}")
            return True
        except Exception as e:
            logger.error(f"Failed to update pipeline config: {e}")
            return False
    else:
        # Create new record
        logger.info(f"Creating new pipeline config for {county_slug}")
        success = supabase_upsert('pipeline.counties', [county_record])
        return success > 0

def test_foreclosure_lane(county_slug: str) -> Dict:
    """Test foreclosure lane connectivity"""
    if county_slug not in COUNTY_CONFIGS:
        return {'success': False, 'error': 'County not configured'}
    
    config = COUNTY_CONFIGS[county_slug]
    foreclosure_url = config['foreclosure_url']
    
    try:
        response = client.get(foreclosure_url, timeout=10)
        
        success = response.status_code == 200
        logger.info(f"Foreclosure lane test for {county_slug}: {response.status_code}")
        
        # Look for auction indicators
        content = response.text.lower()
        has_auctions = any(keyword in content for keyword in ['auction', 'foreclosure', 'sale', 'bid'])
        
        return {
            'success': success,
            'url': foreclosure_url,
            'status_code': response.status_code,
            'has_auction_content': has_auctions,
            'test_timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error testing foreclosure lane for {county_slug}: {e}")
        return {
            'success': False,
            'error': str(e),
            'url': foreclosure_url
        }

def test_tax_deed_lane(county_slug: str) -> Dict:
    """Test tax deed lane connectivity"""
    if county_slug not in COUNTY_CONFIGS:
        return {'success': False, 'error': 'County not configured'}
    
    config = COUNTY_CONFIGS[county_slug]
    tax_deed_url = config['tax_deed_url']
    
    try:
        response = client.get(tax_deed_url, timeout=10)
        
        success = response.status_code == 200
        logger.info(f"Tax deed lane test for {county_slug}: {response.status_code}")
        
        # Look for tax deed indicators
        content = response.text.lower()
        has_tax_deeds = any(keyword in content for keyword in ['tax deed', 'tax sale', 'delinquent', 'certificate'])
        
        return {
            'success': success,
            'url': tax_deed_url,
            'status_code': response.status_code,
            'has_tax_deed_content': has_tax_deeds,
            'test_timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error testing tax deed lane for {county_slug}: {e}")
        return {
            'success': False,
            'error': str(e),
            'url': tax_deed_url
        }

def evaluate_letter_a_improvement(county_slug: str) -> Dict:
    """Evaluate potential Letter A improvement after setup"""
    logger.info(f"Evaluating Letter A improvement potential for {county_slug}")
    
    # Test both lanes
    foreclosure_test = test_foreclosure_lane(county_slug)
    tax_deed_test = test_tax_deed_lane(county_slug)
    
    # Count current auctions 
    current_auctions = len(supabase_get('multi_county_auctions', {'county': f'eq.{county_slug}', 'limit': '1000'}))
    
    # Estimate improvement potential
    dual_product_working = foreclosure_test['success'] and tax_deed_test['success']
    
    improvement_score = 0
    if foreclosure_test['success']:
        improvement_score += 0.5
    if tax_deed_test['success']:
        improvement_score += 0.5
    
    return {
        'county': county_slug,
        'current_auctions': current_auctions,
        'foreclosure_lane': foreclosure_test,
        'tax_deed_lane': tax_deed_test,
        'dual_product_ready': dual_product_working,
        'improvement_potential': improvement_score,
        'letter_a_prognosis': 'PASS' if dual_product_working else 'NEEDS_WORK',
        'evaluation_timestamp': datetime.now().isoformat()
    }

def process_letter_a_county(county_slug: str) -> Dict:
    """Process Letter A setup for a single county"""
    logger.info(f"\n=== Processing Letter A for {county_slug.upper()} ===")
    
    # Set up dual-product configuration
    setup_success = setup_dual_product_config(county_slug)
    
    if not setup_success:
        logger.error(f"Failed to set up pipeline configuration for {county_slug}")
        return {'success': False, 'county': county_slug}
    
    # Evaluate improvement potential
    evaluation = evaluate_letter_a_improvement(county_slug)
    
    return {
        'success': setup_success,
        'county': county_slug,
        'setup_completed': setup_success,
        'evaluation': evaluation
    }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MY SHARD-2 Letter A Coverage Setup")
    parser.add_argument('--county', choices=LETTER_A_COUNTIES, help='Specific county to setup')
    parser.add_argument('--setup-counties', action='store_true', help='Setup all Letter A failing counties')
    parser.add_argument('--test-lanes', action='store_true', help='Test lane connectivity only')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("📋 MY SHARD-2 LETTER A COVERAGE SETUP")
    logger.info(f"Target counties: {', '.join(LETTER_A_COUNTIES)}")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    elif args.setup_counties:
        counties_to_process = LETTER_A_COUNTIES
    else:
        logger.error("Must specify --county or --setup-counties")
        sys.exit(1)
    
    logger.info(f"Processing counties: {', '.join(counties_to_process)}")
    
    # Process each county
    results = []
    
    for county in counties_to_process:
        try:
            if args.test_lanes:
                # Just test connectivity
                evaluation = evaluate_letter_a_improvement(county)
                logger.info(f"{county.upper()} Lane Test Results:")
                logger.info(f"  Foreclosure: {'✅' if evaluation['foreclosure_lane']['success'] else '❌'}")
                logger.info(f"  Tax Deed: {'✅' if evaluation['tax_deed_lane']['success'] else '❌'}")
                logger.info(f"  Dual Product Ready: {'✅' if evaluation['dual_product_ready'] else '❌'}")
                continue
            
            result = process_letter_a_county(county)
            results.append(result)
            
            if result['success']:
                evaluation = result['evaluation']
                logger.info(f"{county.upper()} Setup Results:")
                logger.info(f"  Pipeline Config: ✅")
                logger.info(f"  Current Auctions: {evaluation['current_auctions']}")
                logger.info(f"  Letter A Prognosis: {evaluation['letter_a_prognosis']}")
            else:
                logger.error(f"{county.upper()} setup failed")
                
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            continue
    
    # Summary
    if results:
        successful = sum(1 for r in results if r['success'])
        logger.info(f"\n🎯 LETTER A SETUP SUMMARY")
        logger.info(f"Counties processed: {successful}/{len(results)}")
        
        for result in results:
            county = result['county']
            if result['success']:
                prognosis = result['evaluation']['letter_a_prognosis']
                logger.info(f"  {county}: ✅ {prognosis}")
            else:
                logger.info(f"  {county}: ❌ FAILED")
    
    logger.info("\n🔍 NEXT STEPS:")
    logger.info("1. Run scrapers for both foreclosure and tax deed lanes")
    logger.info("2. Verify dual-product coverage in multi_county_auctions")
    logger.info("3. Check Letter A metric improvement via pencil_dod_evaluate_county")

if __name__ == "__main__":
    main()