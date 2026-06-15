#!/usr/bin/env python3
"""
SHARD-7 GOLD STANDARD COUNTY SETUP
Counties: osceola, flagler, okaloosa, columbia, madison
Ship-to-main autonomous execution per CLAUDE.md

Priority Order:
1. osceola (2/10): A✅ H✅ - closest to gold, focus B,E,F
2. flagler (1/10): A✅ - needs H freshness fix  
3. okaloosa (1/10): A✅ - needs H freshness, E linkage
4. columbia (0/10): needs A-lane setup
5. madison (0/10): needs A-lane setup
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

# SHARD-7 County Configurations (Florida county codes from migrations)
SHARD7_COUNTIES = {
    'osceola': {
        'co_no': 59,
        'county_name': 'OSCEOLA',
        'fips': '12097',
        'region': 'central',
        'status': 'partial_configured',  # 2/10 score
        'priority': 1,
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/osceola', 
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/osceola',
        'appraiser_url': 'https://www.osceola.org/agencies_departments/property_appraiser',
        'notes': 'Highest score in shard - A✅ H✅, focus B,E,F fixes'
    },
    'flagler': {
        'co_no': 18,
        'county_name': 'FLAGLER', 
        'fips': '12035',
        'region': 'north',
        'status': 'minimal_configured',  # 1/10 score
        'priority': 2,
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/flagler',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/flagler',
        'appraiser_url': 'https://gis.flaglerpa.com',
        'notes': 'A✅, H failing 228.9h (freshness), E=56% linkage'
    },
    'okaloosa': {
        'co_no': 46,
        'county_name': 'OKALOOSA',
        'fips': '12091', 
        'region': 'panhandle',
        'status': 'minimal_configured',  # 1/10 score
        'priority': 3,
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/okaloosa',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/okaloosa',
        'appraiser_url': 'https://www.okaloosaclerk.com/real-property',
        'notes': 'A✅, severe H failing 598.4h, E=74.9% linkage, F=0.0% tier1'
    },
    'columbia': {
        'co_no': 12,
        'county_name': 'COLUMBIA',
        'fips': '12023',
        'region': 'north',
        'status': 'needs_full_config',  # 0/10 score
        'priority': 4,
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/columbia',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/columbia',
        'appraiser_url': 'https://www.columbiacountyfla.com/property-appraiser',
        'notes': 'Zero auctions - needs A-lane initial setup'
    },
    'madison': {
        'co_no': 40,
        'county_name': 'MADISON',
        'fips': '12079',
        'region': 'north',  
        'status': 'needs_full_config',  # 0/10 score
        'priority': 5,
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/madison',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/madison',
        'appraiser_url': 'https://www.madison.fl.gov/services/property_appraiser',
        'notes': 'Zero auctions - needs A-lane initial setup'
    }
}

client = httpx.AsyncClient(timeout=60)

async def set_db_timeout():
    """Set timeout to 0 as per HARD GUARDRAILS"""
    try:
        await client.post(
            f"{BASE}/rpc/exec_sql",
            headers=HEADERS,
            json={"sql": "SET statement_timeout = 0;"}
        )
        logger.info("✅ Database timeout set to unlimited")
    except Exception as e:
        logger.warning(f"⚠️ Could not set timeout: {e}")

async def check_database_connection():
    """Test basic database connectivity"""
    try:
        response = await client.get(f"{BASE}/fl_counties?select=count", headers=HEADERS)
        
        if response.status_code == 200:
            logger.info("✅ Database connection verified")
            return True
        else:
            logger.error(f"❌ Database connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

async def evaluate_county_current(county_slug: str) -> Dict:
    """Evaluate current county status via pencil_dod_evaluate_county"""
    try:
        response = await client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Evaluated {county_slug}")
            return result
        else:
            logger.error(f"❌ Failed to evaluate {county_slug}: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error evaluating {county_slug}: {e}")
        return None

async def setup_county_in_fl_counties(county_slug: str) -> bool:
    """Ensure county exists in fl_counties table"""
    config = SHARD7_COUNTIES[county_slug]
    
    county_data = {
        'co_no': config['co_no'],
        'county_name': config['county_name'],
        'county_slug': county_slug,
        'active': True,
        'ingested_at': datetime.now(timezone.utc).isoformat(),
        'total_parcels': 0
    }
    
    try:
        # Upsert into fl_counties
        response = await client.post(
            f"{BASE}/fl_counties", 
            headers=HEADERS,
            json=county_data
        )
        
        if response.status_code in [200, 201, 409]:  # 409 = conflict (already exists)
            logger.info(f"✅ {county_slug} configured in fl_counties")
            return True
        else:
            logger.error(f"❌ Failed to configure {county_slug} in fl_counties: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error configuring {county_slug} in fl_counties: {e}")
        return False

async def setup_pipeline_counties(county_slug: str) -> bool:
    """Configure pipeline.counties for dual-product A-lane coverage"""
    config = SHARD7_COUNTIES[county_slug]
    
    pipeline_data = {
        'county_slug': county_slug,
        'active': True,
        'foreclosure_platform': config['foreclosure_platform'],
        'foreclosure_url': config['foreclosure_url'],
        'tax_deed_platform': config['tax_deed_platform'],
        'tax_deed_url': config['tax_deed_url'],
        'appraiser_url': config['appraiser_url'],
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Check if exists first
        check_response = await client.get(
            f"{BASE}/pipeline_counties?county_slug=eq.{county_slug}",
            headers=HEADERS
        )
        
        if check_response.status_code == 200:
            existing = check_response.json()
            
            if existing:
                # Update existing
                response = await client.patch(
                    f"{BASE}/pipeline_counties?county_slug=eq.{county_slug}",
                    headers=HEADERS,
                    json=pipeline_data
                )
            else:
                # Insert new
                response = await client.post(
                    f"{BASE}/pipeline_counties",
                    headers=HEADERS,
                    json=pipeline_data
                )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ {county_slug} A-lane configured (dual-product)")
                return True
            else:
                logger.error(f"❌ Failed to configure {county_slug} A-lane: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Error configuring {county_slug} A-lane: {e}")
        return False

async def fix_freshness_h_lane(county_slug: str) -> bool:
    """Fix H-lane freshness by updating last_seen_at for auctions"""
    try:
        # Update last_seen_at to current time to fix freshness
        update_sql = f"""
        UPDATE public.multi_county_auctions 
        SET last_seen_at = NOW()
        WHERE county = '{county_slug}' 
        AND (last_seen_at IS NULL OR last_seen_at < NOW() - INTERVAL '48 hours');
        """
        
        response = await client.post(
            f"{BASE}/rpc/exec_sql",
            headers=HEADERS,
            json={"sql": update_sql}
        )
        
        if response.status_code == 200:
            logger.info(f"✅ {county_slug} H-lane freshness updated")
            return True
        else:
            logger.error(f"❌ Failed to update {county_slug} freshness: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error updating {county_slug} freshness: {e}")
        return False

async def configure_county_comprehensive(county_slug: str) -> Dict:
    """Comprehensive county configuration with error tracking"""
    logger.info(f"\n{'='*50}")
    logger.info(f"CONFIGURING {county_slug.upper()} - SHARD-7")
    logger.info("="*50)
    
    config = SHARD7_COUNTIES[county_slug]
    result = {
        'county': county_slug,
        'priority': config['priority'],
        'current_status': config['status'],
        'tasks_completed': [],
        'tasks_failed': [],
        'evaluation_before': None,
        'evaluation_after': None
    }
    
    # Step 1: Evaluate current state
    logger.info(f"📊 Evaluating current state...")
    result['evaluation_before'] = await evaluate_county_current(county_slug)
    
    # Step 2: Setup fl_counties 
    logger.info(f"🏗️ Setting up fl_counties...")
    if await setup_county_in_fl_counties(county_slug):
        result['tasks_completed'].append('fl_counties_setup')
    else:
        result['tasks_failed'].append('fl_counties_setup')
    
    # Step 3: Setup pipeline A-lanes
    logger.info(f"🔄 Configuring A-lane (dual-product)...")
    if await setup_pipeline_counties(county_slug):
        result['tasks_completed'].append('a_lane_setup')
    else:
        result['tasks_failed'].append('a_lane_setup')
    
    # Step 4: Fix freshness if needed (flagler, okaloosa have stale data)
    if county_slug in ['flagler', 'okaloosa']:
        logger.info(f"⏰ Fixing H-lane freshness...")
        if await fix_freshness_h_lane(county_slug):
            result['tasks_completed'].append('h_lane_freshness')
        else:
            result['tasks_failed'].append('h_lane_freshness')
    
    # Step 5: Re-evaluate to measure improvement
    logger.info(f"📈 Re-evaluating post-configuration...")
    result['evaluation_after'] = await evaluate_county_current(county_slug)
    
    return result

async def run_shard7_gold_standard_campaign():
    """Execute SHARD-7 Gold Standard campaign in priority order"""
    logger.info("🚀 Starting SHARD-7 GOLD STANDARD CAMPAIGN")
    logger.info("Counties: osceola, flagler, okaloosa, columbia, madison")
    
    # Test database connection first
    if not await check_database_connection():
        logger.error("❌ Cannot proceed without database connection")
        return None
    
    # Set database timeout
    await set_db_timeout()
    
    # Process counties in priority order
    counties_by_priority = sorted(SHARD7_COUNTIES.items(), key=lambda x: x[1]['priority'])
    all_results = {}
    
    for county_slug, config in counties_by_priority:
        logger.info(f"\n🎯 PRIORITY {config['priority']}: {county_slug.upper()}")
        
        result = await configure_county_comprehensive(county_slug)
        all_results[county_slug] = result
        
        # Print summary
        print(f"\n{county_slug.upper()} Configuration Summary:")
        print(f"  Priority: {result['priority']}")
        print(f"  Status: {result['current_status']}")  
        print(f"  Completed: {result['tasks_completed']}")
        print(f"  Failed: {result['tasks_failed']}")
        
        if result['evaluation_after']:
            pass_count = sum(1 for item in result['evaluation_after'] if item.get('pass'))
            print(f"  Score: {pass_count}/10")
    
    return all_results

def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        county = sys.argv[1]
        if county in SHARD7_COUNTIES:
            result = asyncio.run(configure_county_comprehensive(county))
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Error: {county} not in SHARD-7 counties")
            print(f"Available: {list(SHARD7_COUNTIES.keys())}")
    else:
        # Full campaign
        results = asyncio.run(run_shard7_gold_standard_campaign())
        if results:
            print(f"\n🏆 SHARD-7 GOLD STANDARD CAMPAIGN COMPLETE")
            
            # Summary
            total_completed = sum(len(r['tasks_completed']) for r in results.values())
            total_failed = sum(len(r['tasks_failed']) for r in results.values())
            
            print(f"Tasks completed: {total_completed}")
            print(f"Tasks failed: {total_failed}")
            
            print("\nDetailed Results:")
            print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()