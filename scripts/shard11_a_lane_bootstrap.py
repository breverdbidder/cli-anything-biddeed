#!/usr/bin/env python3
"""
SHARD-11 A-Lane Bootstrap - Session 24
Configure gadsden & wakulla counties for dual-product coverage (A-lane)

Current status:
- gadsden: A=0 (fc=0 td=0) - needs complete configuration  
- wakulla: A=0 (fc=0 td=0) - needs complete configuration

This implements A-lane dual-product setup per pipeline.counties schema.
"""
import os
import sys
import json
import httpx
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if SUPABASE_KEY:
    BASE = f"{SUPABASE_URL}/rest/v1"
    HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
else:
    logger.warning("No SUPABASE_KEY found - will run in dry-run mode")
    BASE = None
    HEADERS = None

# SHARD-11 A-lane configurations
SHARD11_COUNTY_CONFIGS = {
    'gadsden': {
        'county_name': 'Gadsden',
        'state': 'FL',
        'foreclosure_platform': 'realforeclose', 
        'foreclosure_url': 'https://gadsden.realforeclose.com',
        'tax_deed_platform': 'realforeclose',
        'tax_deed_url': 'https://gadsden.realforeclose.com',
        'appraiser_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=962&LayerID=20736&PageTypeID=2',
        'status': 'new_configuration'
    },
    'wakulla': {
        'county_name': 'Wakulla', 
        'state': 'FL',
        'foreclosure_platform': 'realforeclose',
        'foreclosure_url': 'https://wakulla.realforeclose.com',
        'tax_deed_platform': 'realforeclose', 
        'tax_deed_url': 'https://wakulla.realforeclose.com',
        'appraiser_url': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=875&LayerID=19123&PageTypeID=2',
        'status': 'new_configuration'
    }
}

client = httpx.AsyncClient(timeout=30) if SUPABASE_KEY else None

async def test_endpoint_availability(url: str) -> Dict:
    """Test endpoint availability and content relevance"""
    result = {
        'url': url,
        'available': False,
        'status_code': None,
        'has_auction_content': False,
        'error': None
    }
    
    if not client:
        result['error'] = "No client available (dry-run mode)"
        return result
    
    try:
        logger.info(f"Testing {url}...")
        response = await client.get(url, timeout=15)
        result['status_code'] = response.status_code
        
        if response.status_code == 200:
            content = response.text.lower()
            
            # Check for auction/foreclosure content
            auction_keywords = ['foreclosure', 'auction', 'sale', 'property', 'deed', 'bid', 'listing']
            has_content = any(keyword in content for keyword in auction_keywords)
            
            result['available'] = True
            result['has_auction_content'] = has_content
            
            logger.info(f"✅ {url} - Available, Auction content: {has_content}")
        else:
            logger.warning(f"⚠️ {url} - Status {response.status_code}")
            
    except Exception as e:
        result['error'] = str(e)
        logger.error(f"❌ {url} - Error: {e}")
    
    return result

async def check_existing_county_config(county: str) -> Optional[Dict]:
    """Check if county already exists in pipeline.counties"""
    if not client:
        logger.info(f"Dry-run: Would check existing config for {county}")
        return None
    
    try:
        params = {'county_slug': f'eq.{county}'}
        response = await client.get(f"{BASE}/counties", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            results = response.json()
            if results:
                logger.info(f"✅ Found existing config for {county}")
                return results[0]
            else:
                logger.info(f"ℹ️ No existing config for {county}")
                return None
        else:
            logger.error(f"❌ Failed to check config for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error checking config for {county}: {e}")
        return None

async def configure_county_a_lane(county: str) -> Dict:
    """Configure A-lane dual-product setup for county"""
    logger.info(f"🚀 Configuring A-lane for {county}...")
    
    result = {
        'county': county,
        'configuration_status': 'pending',
        'endpoints_tested': {},
        'database_operation': None,
        'errors': [],
        'sql_evidence': []
    }
    
    config = SHARD11_COUNTY_CONFIGS.get(county)
    if not config:
        error = f"No configuration defined for {county}"
        result['errors'].append(error)
        result['configuration_status'] = 'error'
        return result
    
    # Test all endpoints
    endpoint_tests = {}
    for endpoint_type, url in [
        ('foreclosure', config.get('foreclosure_url')),
        ('tax_deed', config.get('tax_deed_url')), 
        ('appraiser', config.get('appraiser_url'))
    ]:
        if url:
            test_result = await test_endpoint_availability(url)
            endpoint_tests[endpoint_type] = test_result
            result['endpoints_tested'][endpoint_type] = test_result
    
    # Check existing configuration
    existing_config = await check_existing_county_config(county)
    
    # Prepare county configuration
    county_config = {
        'county_slug': county,
        'county_name': config['county_name'],
        'state': config['state'],
        'foreclosure_platform': config['foreclosure_platform'],
        'foreclosure_url': config['foreclosure_url'],
        'tax_deed_platform': config['tax_deed_platform'],
        'tax_deed_url': config['tax_deed_url'],
        'appraiser_url': config['appraiser_url'],
        'status': 'configured',
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    if not existing_config:
        county_config['created_at'] = datetime.now(timezone.utc).isoformat()
    
    # Database operation
    if not client:
        logger.info(f"Dry-run: Would configure database for {county}")
        result['database_operation'] = 'dry_run'
        result['configuration_status'] = 'dry_run_success'
    else:
        try:
            if existing_config:
                # Update existing
                params = {'county_slug': f'eq.{county}'}
                response = await client.patch(
                    f"{BASE}/counties",
                    headers=HEADERS,
                    params=params,
                    json=county_config
                )
                result['database_operation'] = 'update'
            else:
                # Insert new
                response = await client.post(
                    f"{BASE}/counties",
                    headers=HEADERS,
                    json=county_config
                )
                result['database_operation'] = 'insert'
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Successfully configured A-lane for {county}")
                result['configuration_status'] = 'success'
                
                # Add SQL evidence
                result['sql_evidence'].append({
                    'operation': result['database_operation'],
                    'table': 'counties',
                    'county': county,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'response_code': response.status_code
                })
            else:
                error = f"Database operation failed: {response.status_code} - {response.text}"
                result['errors'].append(error)
                result['configuration_status'] = 'database_error'
                logger.error(error)
                
        except Exception as e:
            error = f"Database operation error: {e}"
            result['errors'].append(error)
            result['configuration_status'] = 'database_error' 
            logger.error(error)
    
    return result

async def verify_a_lane_configuration(county: str) -> Dict:
    """Verify A-lane configuration was successful"""
    logger.info(f"🔍 Verifying A-lane configuration for {county}...")
    
    verification = {
        'county': county,
        'verification_status': 'pending',
        'database_check': None,
        'expected_metrics': {
            'A_lane_configured': True,
            'foreclosure_url_set': True,
            'tax_deed_url_set': True,
            'ready_for_ingestion': True
        },
        'actual_status': {},
        'verification_passed': False
    }
    
    if not client:
        verification['verification_status'] = 'dry_run_skip'
        return verification
    
    try:
        # Check database configuration
        config_check = await check_existing_county_config(county)
        
        if config_check:
            verification['database_check'] = 'found'
            verification['actual_status'] = {
                'foreclosure_platform': config_check.get('foreclosure_platform'),
                'foreclosure_url': config_check.get('foreclosure_url'),
                'tax_deed_platform': config_check.get('tax_deed_platform'),
                'tax_deed_url': config_check.get('tax_deed_url'),
                'status': config_check.get('status')
            }
            
            # Verify all required fields are set
            required_fields = ['foreclosure_platform', 'foreclosure_url', 'tax_deed_platform', 'tax_deed_url']
            all_configured = all(config_check.get(field) for field in required_fields)
            
            verification['verification_passed'] = all_configured
            verification['verification_status'] = 'success' if all_configured else 'incomplete'
        else:
            verification['database_check'] = 'not_found'
            verification['verification_status'] = 'failed'
            
    except Exception as e:
        verification['verification_status'] = 'error'
        verification['error'] = str(e)
        logger.error(f"Verification error for {county}: {e}")
    
    return verification

async def run_shard11_a_lane_bootstrap():
    """Run complete A-lane bootstrap for SHARD-11 counties"""
    logger.info("🚀 SHARD-11 A-Lane Bootstrap Starting...")
    logger.info("Target counties: gadsden, wakulla (both at A=0)")
    
    bootstrap_results = {
        'session_info': {
            'start_time': datetime.now(timezone.utc).isoformat(),
            'shard': 'SHARD-11',
            'operation': 'A-lane bootstrap',
            'target_counties': ['gadsden', 'wakulla'],
            'dry_run_mode': SUPABASE_KEY is None
        },
        'configurations': {},
        'verifications': {},
        'summary': {},
        'sql_evidence': []
    }
    
    target_counties = ['gadsden', 'wakulla']
    
    # Configure each county
    for county in target_counties:
        logger.info(f"\n{'='*60}")
        logger.info(f"CONFIGURING {county.upper()} A-LANE")
        logger.info("="*60)
        
        # Configure A-lane
        config_result = await configure_county_a_lane(county)
        bootstrap_results['configurations'][county] = config_result
        
        # Collect SQL evidence
        if config_result.get('sql_evidence'):
            bootstrap_results['sql_evidence'].extend(config_result['sql_evidence'])
        
        # Verify configuration
        verification_result = await verify_a_lane_configuration(county)
        bootstrap_results['verifications'][county] = verification_result
        
        # Report status
        config_status = config_result.get('configuration_status', 'unknown')
        verify_status = verification_result.get('verification_status', 'unknown')
        
        print(f"\n{county.upper()} A-Lane Bootstrap:")
        print(f"  Configuration: {config_status}")
        print(f"  Verification: {verify_status}")
        print(f"  Endpoints tested: {len(config_result.get('endpoints_tested', {}))}")
        
        if config_result.get('errors'):
            print(f"  Errors: {config_result['errors']}")
    
    # Generate summary
    success_count = sum(1 for result in bootstrap_results['configurations'].values() 
                       if result.get('configuration_status') == 'success')
    verified_count = sum(1 for result in bootstrap_results['verifications'].values() 
                        if result.get('verification_passed'))
    
    bootstrap_results['summary'] = {
        'total_counties': len(target_counties),
        'successful_configurations': success_count,
        'successful_verifications': verified_count,
        'ready_for_ingestion': verified_count,
        'next_step': 'Run ingestion to populate fc/td metrics for A-lane'
    }
    
    bootstrap_results['session_info']['end_time'] = datetime.now(timezone.utc).isoformat()
    
    logger.info(f"\n✅ SHARD-11 A-Lane Bootstrap Complete")
    logger.info(f"Configured: {success_count}/{len(target_counties)}")
    logger.info(f"Verified: {verified_count}/{len(target_counties)}")
    
    return bootstrap_results

def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in ['gadsden', 'wakulla']:
            # Single county mode
            result = asyncio.run(configure_county_a_lane(county))
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Error: Unknown county '{county}'. Supported: gadsden, wakulla")
            sys.exit(1)
    else:
        # Full bootstrap mode
        results = asyncio.run(run_shard11_a_lane_bootstrap())
        
        print(f"\n{'='*80}")
        print("SHARD-11 A-LANE BOOTSTRAP RESULTS")
        print("="*80)
        print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()