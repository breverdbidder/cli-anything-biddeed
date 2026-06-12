#!/usr/bin/env python3
"""
SHARD-6 Lane Configuration (A-lane) Implementation  
Configure foreclosure and tax deed lanes for dual-product coverage

A-lane failures: sumter, calhoun, liberty
Need to configure BOTH lanes per pipeline.counties
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

# County configurations for dual-product setup
COUNTY_LANE_CONFIGS = {
    'escambia': {
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://escambia.realforeclose.com',
        'tax_deed_platform': 'realforeclose', 
        'tax_deed_url': 'https://escambia.realforeclose.com',
        'appraiser_url': 'https://gis.myescambia.com',
        'status': 'partially_configured'  # Already has some coverage
    },
    'sumter': {
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://sumter.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://sumter.realforeclose.com', 
        'appraiser_url': 'https://www.sumtercountyfl.gov/223/Property-Appraiser',
        'status': 'needs_full_config'  # A=0 metric
    },
    'lake': {
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://lake.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://lake.realforeclose.com',
        'appraiser_url': 'https://gis.lakecountyfl.gov',
        'status': 'partially_configured'  # A=1113 metric
    },
    'calhoun': {
        'foreclosure_platform': 'custom_clerk',
        'foreclosure_url': 'https://www.calhounclerk.com/foreclosure',
        'tax_deed_platform': 'custom_clerk',
        'tax_deed_url': 'https://www.calhounclerk.com/foreclosure',
        'appraiser_url': 'https://www.calhounclerk.com',
        'status': 'needs_full_config'  # A=0 metric
    },
    'liberty': {
        'foreclosure_platform': 'unknown',  # Need to investigate
        'foreclosure_url': None,
        'tax_deed_platform': 'unknown',
        'tax_deed_url': None,
        'appraiser_url': 'https://www.libertycountyfl.com',
        'status': 'needs_investigation'  # No known online presence
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
            error_msg = f"Failed to configure {county}: {response.status_code}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
            
    except Exception as e:
        error_msg = f"Error configuring {county}: {e}"
        logger.error(error_msg)
        result['errors'].append(error_msg)
    
    return result

async def investigate_liberty_county() -> Dict:
    """Special investigation for Liberty County to find auction sources"""
    logger.info("Investigating Liberty County auction sources...")
    
    investigation_urls = [
        'https://www.libertycountyfl.com',
        'https://www.libertycountyclerk.com',
        'https://liberty.realforeclose.com',  # Test if this exists
        'https://www.floridaforeclosures.com/liberty',
        'https://liberty.bid4assets.com'  # Tax deed possibility
    ]
    
    results = {
        'county': 'liberty',
        'investigation_results': {},
        'recommended_action': None
    }
    
    for url in investigation_urls:
        logger.info(f"Testing {url}...")
        available = await test_endpoint_availability(url)
        results['investigation_results'][url] = available
        
        if available:
            logger.info(f"✅ Found potential source: {url}")
    
    # Determine recommendation
    available_sources = [url for url, avail in results['investigation_results'].items() if avail]
    
    if available_sources:
        results['recommended_action'] = f"Configure primary source: {available_sources[0]}"
    else:
        results['recommended_action'] = "Manual investigation required - no online sources found"
    
    return results

async def run_lane_configuration_campaign():
    """Run lane configuration for all SHARD-6 counties"""
    logger.info("Starting SHARD-6 lane configuration campaign (A-lane)...")
    
    # Priority counties based on A-lane failures
    target_counties = ['sumter', 'calhoun', 'liberty']  # A=0 or A=null
    
    all_results = {}
    
    # Special handling for Liberty County
    if 'liberty' in target_counties:
        logger.info(f"\n{'='*50}")
        logger.info("LIBERTY COUNTY INVESTIGATION")
        logger.info("="*50)
        
        liberty_investigation = await investigate_liberty_county()
        all_results['liberty'] = liberty_investigation
        
        print(f"\nLiberty Investigation:")
        print(f"  Available sources: {sum(liberty_investigation['investigation_results'].values())}")
        print(f"  Recommendation: {liberty_investigation['recommended_action']}")
        
        target_counties.remove('liberty')  # Process separately
    
    # Process other counties
    for county in target_counties:
        logger.info(f"\n{'='*50}")
        logger.info(f"CONFIGURING {county.upper()} - A-LANE DUAL-PRODUCT")
        logger.info("="*50)
        
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
    logger.info("SHARD-6 Lane Configuration (A-lane) Implementation")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        
        if county == 'liberty':
            # Special investigation
            result = asyncio.run(investigate_liberty_county())
        else:
            # Normal configuration
            result = asyncio.run(configure_county_lanes(county))
        
        print(json.dumps(result, indent=2))
    else:
        # Process all target counties
        results = asyncio.run(run_lane_configuration_campaign())
        print(f"\nA-Lane Configuration Campaign Complete!")
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()