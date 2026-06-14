#!/usr/bin/env python3
"""
SHARD-10 Lane Configuration (A-lane) Implementation
Configure foreclosure and tax deed lanes for dual-product coverage

A-lane failures: franklin (0/10), union (0/10) 
Target counties: manatee, collier, okeechobee, franklin, union

Based on issue briefing metrics:
- manatee: A=1487 ✓ (working)
- collier: A=559 ✓ (working) 
- okeechobee: A=164 ✓ (working)
- franklin: A=0 ❌ (needs setup)
- union: A=0 ❌ (needs setup)
"""

import os
import sys
import json
import httpx
import logging
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

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
    "Content-Type": "application/json"
}

# County configurations for SHARD-10 dual-product setup
COUNTY_LANE_CONFIGS = {
    'manatee': {
        'co_no': 51,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://manatee.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://manatee.realforeclose.com',
        'appraiser_url': 'https://mcpao.manatee.fl.us',
        'status': 'configured'  # A=1487 metric (PASS)
    },
    'collier': {
        'co_no': 21,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://collier.realforeclose.com',
        'tax_deed_platform': 'realforeclose', 
        'tax_deed_url': 'https://collier.realforeclose.com',
        'appraiser_url': 'https://www.collierappraiser.com',
        'status': 'configured'  # A=559 metric (PASS)
    },
    'okeechobee': {
        'co_no': 57,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://okeechobee.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://okeechobee.realforeclose.com',
        'appraiser_url': 'https://www.okeechobeeappraiser.com',
        'status': 'configured'  # A=164 metric (PASS)
    },
    'franklin': {
        'co_no': 29,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://franklin.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://franklin.realforeclose.com',
        'appraiser_url': 'https://www.franklincountyfl.com/property-appraiser',
        'status': 'needs_full_config'  # A=0 metric
    },
    'union': {
        'co_no': 73,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://union.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://union.realforeclose.com',
        'appraiser_url': 'https://www.unioncountyfl.gov/property-appraiser',
        'status': 'needs_full_config'  # A=0 metric
    }
}

client = httpx.AsyncClient(timeout=30)

async def check_existing_county_config(county: str) -> Dict:
    """Check if county already exists in pipeline.counties table"""
    
    try:
        params = {'county_slug': f'eq.{county}'}
        response = await client.get(f"{BASE}/counties", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            results = response.json()
            if results:
                logger.info(f"Found existing config for {county}")
                return results[0]
            else:
                logger.info(f"No existing config for {county}")
                return {}
        else:
            logger.error(f"Failed to check config for {county}: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"Error checking config for {county}: {e}")
        return {}

async def test_endpoint_availability(url: str) -> bool:
    """Test if an endpoint is available and returns reasonable content"""
    
    try:
        response = await client.get(url, timeout=10)
        
        if response.status_code == 200:
            content = response.text.lower()
            
            # Check for foreclosure/auction related content
            keywords = ['foreclosure', 'auction', 'sale', 'property', 'deed']
            has_content = any(keyword in content for keyword in keywords)
            
            logger.info(f"✅ {url} - Status {response.status_code}, Has content: {has_content}")
            return has_content
        else:
            logger.warning(f"⚠️ {url} - Status {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ {url} - Error: {e}")
        return False

async def configure_county_lanes(county: str) -> Dict:
    """Configure dual-product lanes for a county"""
    logger.info(f"Configuring lanes for {county}...")
    
    result = {
        'county': county,
        'foreclosure_configured': False,
        'tax_deed_configured': False,
        'endpoints_tested': {},
        'errors': []
    }
    
    config = COUNTY_LANE_CONFIGS.get(county)
    if not config:
        result['errors'].append(f"No configuration defined for {county}")
        return result
    
    # Test endpoint availability
    for endpoint_type, url in [
        ('foreclosure', config.get('foreclosure_url')),
        ('tax_deed', config.get('tax_deed_url')),
        ('appraiser', config.get('appraiser_url'))
    ]:
        if url:
            available = await test_endpoint_availability(url)
            result['endpoints_tested'][endpoint_type] = {
                'url': url,
                'available': available
            }
    
    # Check existing configuration
    existing_config = await check_existing_county_config(county)
    
    # Prepare county configuration for database
    county_config = {
        'county_slug': county,
        'county_name': county.title(),
        'state': 'FL',
        'co_no': config.get('co_no'),  # Add FL county number
        'foreclosure_platform': config.get('foreclosure_platform'),
        'foreclosure_url': config.get('foreclosure_url'),
        'tax_deed_platform': config.get('tax_deed_platform'), 
        'tax_deed_url': config.get('tax_deed_url'),
        'appraiser_url': config.get('appraiser_url'),
        'status': 'configured',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        if existing_config:
            # Update existing configuration
            params = {'county_slug': f'eq.{county}'}
            response = await client.patch(
                f"{BASE}/counties",
                headers=HEADERS,
                params=params,
                json=county_config
            )
        else:
            # Insert new configuration
            response = await client.post(
                f"{BASE}/counties",
                headers=HEADERS,
                json=county_config
            )
        
        if response.status_code in [200, 201]:
            logger.info(f"✅ Successfully configured lanes for {county}")
            result['foreclosure_configured'] = bool(config.get('foreclosure_url'))
            result['tax_deed_configured'] = bool(config.get('tax_deed_url'))
        else:
            error_msg = f"Failed to configure {county}: {response.status_code} - {response.text}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            
    except Exception as e:
        error_msg = f"Error configuring {county}: {e}"
        logger.error(error_msg)
        result['errors'].append(error_msg)
    
    return result

async def investigate_franklin_union() -> Dict:
    """Special investigation for Franklin and Union counties to find auction sources"""
    logger.info("Investigating Franklin and Union County auction sources...")
    
    investigation_targets = {
        'franklin': [
            'https://franklin.realforeclose.com',
            'https://www.franklincountyfl.com',
            'https://www.franklinclerk.com',
            'https://www.floridaforeclosures.com/franklin',
            'https://franklin.bid4assets.com'
        ],
        'union': [
            'https://union.realforeclose.com',
            'https://www.unioncountyfl.gov',
            'https://www.unioncountyclerk.com',
            'https://www.floridaforeclosures.com/union',
            'https://union.bid4assets.com'
        ]
    }
    
    results = {
        'franklin': {'investigation_results': {}, 'recommended_action': None},
        'union': {'investigation_results': {}, 'recommended_action': None}
    }
    
    for county, urls in investigation_targets.items():
        logger.info(f"\n--- Investigating {county.upper()} ---")
        
        for url in urls:
            logger.info(f"Testing {url}...")
            available = await test_endpoint_availability(url)
            results[county]['investigation_results'][url] = available
            
            if available:
                logger.info(f"✅ Found potential source for {county}: {url}")
        
        # Determine recommendation
        available_sources = [url for url, avail in results[county]['investigation_results'].items() if avail]
        
        if available_sources:
            results[county]['recommended_action'] = f"Configure primary source: {available_sources[0]}"
        else:
            results[county]['recommended_action'] = "Manual investigation required - no online sources found"
    
    return results

async def run_shard10_lane_configuration():
    """Run lane configuration for all SHARD-10 counties"""
    logger.info("Starting SHARD-10 lane configuration campaign (A-lane)...")
    
    # Priority: franklin and union (0 metrics) need immediate setup
    priority_counties = ['franklin', 'union']  # A=0 
    working_counties = ['manatee', 'collier', 'okeechobee']  # A>0 but may need config updates
    
    all_results = {}
    
    # Special investigation for zero-metric counties
    logger.info(f"\n{'='*60}")
    logger.info("FRANKLIN & UNION INVESTIGATION (A=0 COUNTIES)")
    logger.info("="*60)
    
    investigation = await investigate_franklin_union()
    all_results['investigation'] = investigation
    
    print(f"\nFranklin Investigation:")
    franklin_available = sum(investigation['franklin']['investigation_results'].values())
    print(f"  Available sources: {franklin_available}")
    print(f"  Recommendation: {investigation['franklin']['recommended_action']}")
    
    print(f"\nUnion Investigation:")
    union_available = sum(investigation['union']['investigation_results'].values())
    print(f"  Available sources: {union_available}")
    print(f"  Recommendation: {investigation['union']['recommended_action']}")
    
    # Configure all counties (including working ones for completeness)
    all_counties = priority_counties + working_counties
    
    for county in all_counties:
        logger.info(f"\n{'='*60}")
        logger.info(f"CONFIGURING {county.upper()} - A-LANE DUAL-PRODUCT")
        logger.info("="*60)
        
        results = await configure_county_lanes(county)
        all_results[county] = results
        
        # Print results
        print(f"\n{county.upper()} A-Lane Configuration:")
        print(f"  Foreclosure configured: {results['foreclosure_configured']}")
        print(f"  Tax deed configured: {results['tax_deed_configured']}")
        print(f"  Endpoints tested: {len(results['endpoints_tested'])}")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-10 Lane Configuration (A-lane) Implementation")
    print("Target counties: manatee, collier, okeechobee, franklin, union")
    print("Priority: franklin & union (A=0 metrics)")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        
        if county in ['franklin', 'union']:
            # Special investigation for zero-metric counties
            if county == 'franklin':
                result = asyncio.run(investigate_franklin_union())
                print(json.dumps(result['franklin'], indent=2))
            else:
                result = asyncio.run(investigate_franklin_union())
                print(json.dumps(result['union'], indent=2))
        else:
            # Normal configuration
            result = asyncio.run(configure_county_lanes(county))
            print(json.dumps(result, indent=2))
    else:
        # Process all SHARD-10 counties
        results = asyncio.run(run_shard10_lane_configuration())
        print(f"\nSHARD-10 A-Lane Configuration Campaign Complete!")
        print(f"Summary:")
        print(f"- Counties configured: {len([k for k in results.keys() if k not in ['investigation']])}")
        print(f"- Zero-metric counties investigated: franklin, union")

if __name__ == "__main__":
    main()