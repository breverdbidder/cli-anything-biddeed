#!/usr/bin/env python3
"""
SHARD-7 A-Lane Setup - Columbia & Madison Counties
Configure dual-product lanes for counties with zero auctions

Based on issue metrics:
- columbia (0/10): Zero auctions, needs full A-lane setup
- madison (0/10): Zero auctions, needs full A-lane setup

CO_NO mapping from fl_counties_manifest.yml:
- columbia: 22
- madison: 50
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

# Supabase configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# County configurations for SHARD-7 A-lane setup
SHARD7_COUNTY_CONFIGS = {
    'columbia': {
        'co_no': 22,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://columbia.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://columbia.realforeclose.com',
        'appraiser_url': 'https://www.columbiacountyclerk.com',
        'clerk_url': 'https://or.columbiacountyclerk.com',
        'status': 'needs_a_lane_setup'
    },
    'madison': {
        'co_no': 50,
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://madison.realforeclose.com',
        'tax_deed_platform': 'realforeclose', 
        'tax_deed_url': 'https://madison.realforeclose.com',
        'appraiser_url': 'https://www.madisoncountyclerk.com',
        'clerk_url': 'https://or.madisoncountyclerk.com',
        'status': 'needs_a_lane_setup'
    }
}

client = httpx.AsyncClient(timeout=30)

async def test_endpoint_availability(url: str) -> Dict:
    """Test if an endpoint is available and returns auction-related content"""
    
    try:
        response = await client.get(url, timeout=10, follow_redirects=True)
        
        result = {
            'url': url,
            'status_code': response.status_code,
            'available': False,
            'has_auction_content': False,
            'redirect_url': str(response.url) if response.url != url else None
        }
        
        if response.status_code == 200:
            content = response.text.lower()
            
            # Check for foreclosure/auction related content
            auction_keywords = ['foreclosure', 'auction', 'sale', 'property', 'deed', 'bid']
            has_content = any(keyword in content for keyword in auction_keywords)
            
            result['available'] = True
            result['has_auction_content'] = has_content
            
            logger.info(f"✅ {url} - Status {response.status_code}, Auction content: {has_content}")
        else:
            logger.warning(f"⚠️ {url} - Status {response.status_code}")
            
        return result
            
    except Exception as e:
        logger.error(f"❌ {url} - Error: {e}")
        return {
            'url': url,
            'status_code': None,
            'available': False,
            'has_auction_content': False,
            'error': str(e)
        }

async def check_existing_pipeline_config(county: str) -> Dict:
    """Check if county exists in pipeline.counties table"""
    
    try:
        # Try different possible table names based on patterns seen
        table_names = ['counties', 'pipeline_counties', 'county_configs']
        
        for table_name in table_names:
            try:
                params = {'county_slug': f'eq.{county}'}
                response = await client.get(f"{BASE}/{table_name}", headers=HEADERS, params=params)
                
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        logger.info(f"Found existing config for {county} in {table_name}")
                        return {'found': True, 'table': table_name, 'config': results[0]}
            except Exception:
                continue
        
        logger.info(f"No existing pipeline config found for {county}")
        return {'found': False}
        
    except Exception as e:
        logger.error(f"Error checking pipeline config for {county}: {e}")
        return {'found': False, 'error': str(e)}

async def discover_county_auction_sources(county: str) -> Dict:
    """Discover available auction sources for a county"""
    logger.info(f"Discovering auction sources for {county}...")
    
    config = SHARD7_COUNTY_CONFIGS.get(county)
    if not config:
        return {'county': county, 'error': 'No configuration defined'}
    
    # Test multiple possible endpoints
    test_urls = [
        config.get('foreclosure_url'),
        config.get('tax_deed_url'), 
        config.get('appraiser_url'),
        config.get('clerk_url'),
        f"https://{county}.realauction.com",  # Alternative platform
        f"https://www.{county}countyclerk.com/foreclosure",  # Clerk foreclosure page
        f"https://gis.{county}county.com",  # GIS portal
    ]
    
    # Remove None values and duplicates
    test_urls = list(set([url for url in test_urls if url]))
    
    results = {
        'county': county,
        'co_no': config.get('co_no'),
        'sources_tested': {},
        'available_sources': [],
        'recommended_primary': None
    }
    
    for url in test_urls:
        logger.info(f"Testing {url}...")
        test_result = await test_endpoint_availability(url)
        results['sources_tested'][url] = test_result
        
        if test_result['available'] and test_result['has_auction_content']:
            results['available_sources'].append(url)
            
            # Prioritize realforeclose.com as primary
            if not results['recommended_primary'] or 'realforeclose.com' in url:
                results['recommended_primary'] = url
    
    return results

async def configure_pipeline_lanes(county: str, source_discovery: Dict) -> Dict:
    """Configure pipeline lanes based on source discovery"""
    logger.info(f"Configuring pipeline lanes for {county}...")
    
    config = SHARD7_COUNTY_CONFIGS.get(county)
    if not config:
        return {'county': county, 'error': 'No configuration defined'}
    
    # Check existing configuration
    existing_config = await check_existing_pipeline_config(county)
    
    # Prepare county configuration
    lane_config = {
        'county_slug': county,
        'county_name': county.title(),
        'co_no': config.get('co_no'),
        'state': 'FL',
        'foreclosure_platform': 'realforeclose' if source_discovery.get('recommended_primary') else 'custom_clerk',
        'foreclosure_url': source_discovery.get('recommended_primary') or config.get('clerk_url'),
        'tax_deed_platform': 'realforeclose' if source_discovery.get('recommended_primary') else 'custom_clerk',
        'tax_deed_url': source_discovery.get('recommended_primary') or config.get('clerk_url'),
        'appraiser_url': config.get('appraiser_url'),
        'status': 'configured',
        'shard7_configured_at': datetime.now(timezone.utc).isoformat(),
        'source_discovery': source_discovery
    }
    
    # Try to insert/update configuration
    result = {
        'county': county,
        'config_created': False,
        'config_updated': False,
        'config': lane_config,
        'errors': []
    }
    
    # Since we don't know the exact table name, try multiple approaches
    table_attempts = ['counties', 'pipeline_counties', 'county_pipeline_configs']
    
    for table_name in table_attempts:
        try:
            if existing_config.get('found'):
                # Update existing
                params = {'county_slug': f'eq.{county}'}
                response = await client.patch(
                    f"{BASE}/{table_name}",
                    headers=HEADERS,
                    params=params,
                    json=lane_config
                )
            else:
                # Insert new
                response = await client.post(
                    f"{BASE}/{table_name}",
                    headers=HEADERS,
                    json=lane_config
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Successfully configured {county} in {table_name}")
                result['config_created'] = not existing_config.get('found')
                result['config_updated'] = existing_config.get('found')
                result['table_name'] = table_name
                return result
            else:
                error_msg = f"Failed to configure {table_name}: {response.status_code} - {response.text}"
                logger.warning(error_msg)
                result['errors'].append(error_msg)
                
        except Exception as e:
            error_msg = f"Error with {table_name}: {e}"
            logger.warning(error_msg)
            result['errors'].append(error_msg)
    
    return result

async def setup_county_a_lane(county: str) -> Dict:
    """Complete A-lane setup for a county"""
    logger.info(f"\n{'='*50}")
    logger.info(f"A-LANE SETUP: {county.upper()}")
    logger.info("="*50)
    
    # Step 1: Discover auction sources
    source_discovery = await discover_county_auction_sources(county)
    
    # Step 2: Configure pipeline lanes
    pipeline_config = await configure_pipeline_lanes(county, source_discovery)
    
    # Step 3: Summary
    result = {
        'county': county,
        'a_lane_configured': len(source_discovery.get('available_sources', [])) > 0,
        'primary_source': source_discovery.get('recommended_primary'),
        'available_sources_count': len(source_discovery.get('available_sources', [])),
        'pipeline_configured': pipeline_config.get('config_created') or pipeline_config.get('config_updated'),
        'source_discovery': source_discovery,
        'pipeline_config': pipeline_config,
        'next_steps': []
    }
    
    # Add next steps based on results
    if result['a_lane_configured']:
        result['next_steps'].append("✅ A-lane configured - auction sources found")
        if result['pipeline_configured']:
            result['next_steps'].append("✅ Pipeline configuration saved")
        else:
            result['next_steps'].append("⚠️ Pipeline configuration needs manual review")
        result['next_steps'].append("🔄 Run scraper to populate multi_county_auctions")
        result['next_steps'].append("🔄 Verify A-lane metric > 0 after first scrape")
    else:
        result['next_steps'].append("❌ No auction sources found - manual investigation needed")
        result['next_steps'].append("📞 Contact county clerk for auction process")
        result['next_steps'].append("🔍 Check alternative platforms (bid4assets, etc.)")
    
    return result

async def run_shard7_a_lane_setup():
    """Run A-lane setup for SHARD-7 counties"""
    logger.info("Starting SHARD-7 A-lane setup for Columbia & Madison...")
    
    target_counties = ['columbia', 'madison']
    all_results = {}
    
    for county in target_counties:
        results = await setup_county_a_lane(county)
        all_results[county] = results
        
        # Print summary
        print(f"\n{county.upper()} A-Lane Setup Results:")
        print(f"  ✅ A-lane configured: {results['a_lane_configured']}")
        print(f"  📡 Primary source: {results.get('primary_source', 'None found'})")
        print(f"  🔍 Available sources: {results['available_sources_count']}")
        print(f"  ⚙️ Pipeline configured: {results['pipeline_configured']}")
        print(f"  📋 Next steps: {len(results['next_steps'])}")
        for step in results['next_steps']:
            print(f"    • {step}")
    
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-7 A-Lane Setup (Columbia & Madison)")
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in SHARD7_COUNTY_CONFIGS:
            result = asyncio.run(setup_county_a_lane(county))
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Error: County '{county}' not in SHARD-7 configuration")
            print(f"Available counties: {list(SHARD7_COUNTY_CONFIGS.keys())}")
    else:
        # Process all SHARD-7 zero-auction counties
        results = asyncio.run(run_shard7_a_lane_setup())
        print(f"\nSHARD-7 A-Lane Setup Campaign Complete!")
        
        # Summary
        total_configured = sum(1 for r in results.values() if r.get('a_lane_configured'))
        print(f"Counties with A-lane configured: {total_configured}/2")
        
        # JSON output for verification
        print("\nDetailed Results:")
        print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()