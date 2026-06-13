#!/usr/bin/env python3
"""
SHARD-6 Tier1 Promotion (F-lane) Implementation
Promote winning_bid amounts from verified outcomes to tier1 status

This addresses F-lane failures by ensuring verified outcomes get promoted
to tier1 sold amounts, following the tier1-promote-hourly automation pattern.

Counties: escambia (F=0.1%), martin (F=0.0%), suwannee (F=0.0%)
"""

import os
import sys
import json
import httpx
import logging
import asyncio
from typing import Dict, List, Optional
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

SHARD6_COUNTIES = ['escambia', 'suwannee', 'martin', 'calhoun', 'liberty']

client = httpx.AsyncClient(timeout=120)

async def get_verified_outcomes_for_promotion(county: str) -> List[Dict]:
    """Get verified outcomes that have winning_bid but haven't been promoted to tier1"""
    
    # Check both foreclosure_outcomes and tax_deed_outcomes tables
    tables = ['foreclosure_outcomes', 'tax_deed_outcomes']
    all_outcomes = []
    
    for table in tables:
        try:
            # Get outcomes with winning_bid that need promotion
            params = {
                'county': f'eq.{county}',
                'winning_bid': 'not.is.null',
                'select': 'id,case_number,winning_bid,buyer,sale_date,data_source',
                'limit': 100
            }
            
            response = await client.get(f"{BASE}/{table}", headers=HEADERS, params=params)
            
            if response.status_code == 200:
                outcomes = response.json()
                logger.info(f"Found {len(outcomes)} verified outcomes in {table} for {county}")
                
                # Add table info for tracking
                for outcome in outcomes:
                    outcome['source_table'] = table
                
                all_outcomes.extend(outcomes)
            else:
                logger.warning(f"Failed to get {table} for {county}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error getting {table} for {county}: {e}")
    
    return all_outcomes

async def find_matching_auction(case_number: str, county: str) -> Optional[Dict]:
    """Find the matching auction in multi_county_auctions"""
    
    try:
        params = {
            'case_number': f'eq.{case_number}',
            'county': f'eq.{county}',
            'select': 'id,case_number,address,sale_date,plaintiff,defendant,tier1_sold',
            'limit': 1
        }
        
        response = await client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params=params)
        
        if response.status_code == 200:
            results = response.json()
            if results:
                return results[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error finding auction for {case_number}: {e}")
        return None

async def promote_tier1_amount(auction_id: int, winning_bid: float, data_source: str) -> bool:
    """Promote winning_bid to tier1_sold for an auction"""
    
    try:
        # Update the auction with tier1_sold amount
        update_data = {
            'tier1_sold': winning_bid,
            'tier1_data_source': data_source,
            'tier1_promoted_at': datetime.now(timezone.utc).isoformat()
        }
        
        params = {'id': f'eq.{auction_id}'}
        
        response = await client.patch(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params=params,
            json=update_data
        )
        
        if response.status_code in [200, 204]:
            logger.info(f"✅ Promoted tier1_sold=${winning_bid:.2f} for auction {auction_id}")
            return True
        else:
            logger.error(f"❌ Failed to promote auction {auction_id}: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error promoting auction {auction_id}: {e}")
        return False

async def process_county_tier1_promotion(county: str) -> Dict:
    """Process tier1 promotion for a county"""
    logger.info(f"Starting tier1 promotion for {county}...")
    
    results = {
        'county': county,
        'verified_outcomes': 0,
        'auctions_found': 0,
        'promotions_made': 0,
        'failed': 0,
        'errors': []
    }
    
    # Get verified outcomes that need promotion
    outcomes = await get_verified_outcomes_for_promotion(county)
    results['verified_outcomes'] = len(outcomes)
    
    if not outcomes:
        logger.info(f"No verified outcomes found for promotion in {county}")
        return results
    
    # Process each outcome
    for outcome in outcomes:
        case_number = outcome.get('case_number')
        winning_bid = outcome.get('winning_bid')
        data_source = outcome.get('data_source')
        
        if not case_number or not winning_bid:
            results['failed'] += 1
            continue
        
        # Find matching auction
        auction = await find_matching_auction(case_number, county)
        
        if auction:
            results['auctions_found'] += 1
            
            # Check if already promoted
            if auction.get('tier1_sold'):
                logger.debug(f"Auction {case_number} already has tier1_sold")
                continue
            
            # Promote the amount
            success = await promote_tier1_amount(
                auction['id'], 
                float(winning_bid), 
                data_source
            )
            
            if success:
                results['promotions_made'] += 1
            else:
                results['failed'] += 1
        else:
            logger.debug(f"No matching auction found for {case_number}")
            results['failed'] += 1
        
        # Rate limiting
        await asyncio.sleep(0.1)
    
    logger.info(f"Completed {county}: {results['promotions_made']} promotions, {results['failed']} failed")
    return results

async def run_tier1_promotion_campaign():
    """Run tier1 promotion for all SHARD-6 counties"""
    logger.info("Starting SHARD-6 tier1 promotion campaign (F-lane)...")
    
    all_results = {}
    total_promotions = 0
    
    for county in SHARD6_COUNTIES:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {county.upper()} - F-LANE TIER1 PROMOTION")
        logger.info("="*50)
        
        results = await process_county_tier1_promotion(county)
        all_results[county] = results
        total_promotions += results['promotions_made']
        
        # Print results
        print(f"\n{county.upper()} F-Lane Results:")
        print(f"  Verified outcomes: {results['verified_outcomes']}")
        print(f"  Auctions found: {results['auctions_found']}")
        print(f"  Promotions made: {results['promotions_made']}")
        print(f"  Failed: {results['failed']}")
        
        if results['errors']:
            print(f"  Errors: {results['errors']}")
    
    print(f"\nTotal promotions across all counties: {total_promotions}")
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-6 Tier1 Promotion (F-lane) Implementation")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        if county in SHARD6_COUNTIES:
            # Process single county
            result = asyncio.run(process_county_tier1_promotion(county))
            print(json.dumps(result, indent=2))
        else:
            logger.error(f"County {county} not in SHARD-6 assignment")
            sys.exit(1)
    else:
        # Process all counties
        results = asyncio.run(run_tier1_promotion_campaign())
        print(f"\nF-Lane Campaign Complete!")
        print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()