#!/usr/bin/env python3
"""
SHARD-17 Letter F: Tier1 Sold Amount Promotion
Promote verified outcome amounts to tier1_sold_amount for charlotte, citrus, broward

CURRENT METRICS:
- charlotte: F=2.1% (20/945 tier1_sold), target ≥95%
- citrus: F=6.1% (80/1308 tier1_sold), target ≥95%  
- broward: F=2.5% (300/12198 tier1_sold), target ≥95%

STRATEGY:
1. Query existing verified outcomes in tax_deed_outcomes/foreclosure_outcomes
2. Match by case_number to multi_county_auctions
3. Promote sale_amount/winning_bid to tier1_sold_amount
4. Follow autoloop pattern: promote_tier1_from_outcomes() referenced in issue
5. Measure F criterion improvement via pencil_dod_evaluate_county
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("SUPABASE_KEY or SUPABASE_SERVICE_KEY environment variable required")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Assigned counties for this session
SHARD17_COUNTIES = ['charlotte', 'citrus', 'broward']

class Tier1Promoter:
    """Promotes verified outcomes to tier1_sold_amount for F criterion improvement"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=30)
    
    def query_supabase(self, table: str, params: Dict = None) -> List[Dict]:
        """Query Supabase table"""
        try:
            url = f"{BASE}/{table}"
            query_params = params or {}
            
            response = self.client.get(url, headers=HEADERS, params=query_params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Query failed {table}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Query error {table}: {e}")
            return []
    
    def upsert_supabase(self, table: str, data: List[Dict]) -> int:
        """Upsert to Supabase table"""
        if not data:
            return 0
            
        try:
            response = self.client.post(f"{BASE}/{table}", headers=HEADERS, json=data)
            if response.status_code in [200, 201]:
                logger.info(f"✅ Upserted {len(data)} rows to {table}")
                return len(data)
            else:
                logger.error(f"Upsert failed {table}: {response.status_code} - {response.text}")
                return 0
        except Exception as e:
            logger.error(f"Upsert error {table}: {e}")
            return 0
    
    def get_county_auctions_missing_tier1(self, county_slug: str) -> List[Dict]:
        """Get closed auctions missing tier1_sold_amount for the county"""
        params = {
            'county': f'eq.{county_slug}',
            'auction_status': 'in.(sold,no_sale,canceled)',
            'tier1_sold_amount': 'is.null',
            'select': '*'
        }
        return self.query_supabase('multi_county_auctions', params)
    
    def get_verified_outcomes_for_county(self, county_slug: str) -> List[Dict]:
        """Get verified outcomes from independent sources for the county"""
        
        # Get tax deed outcomes
        td_outcomes = self.query_supabase('tax_deed_outcomes', {
            'county_slug': f'eq.{county_slug}',
            'sale_status': 'eq.sold',
            'sale_amount': 'not.is.null',
            'select': '*'
        })
        
        # Get foreclosure outcomes  
        fc_outcomes = self.query_supabase('foreclosure_outcomes', {
            'county_slug': f'eq.{county_slug}',
            'sale_status': 'eq.sold', 
            'sale_amount': 'not.is.null',
            'select': '*'
        })
        
        # Combine and normalize
        outcomes = []
        for outcome in td_outcomes + fc_outcomes:
            outcomes.append({
                'case_number': outcome.get('case_number'),
                'sale_amount': outcome.get('sale_amount'),
                'auction_date': outcome.get('auction_date'),
                'data_source': outcome.get('data_source'),
                'outcome_type': 'tax_deed' if outcome in td_outcomes else 'foreclosure'
            })
        
        return outcomes
    
    def promote_tier1_for_county(self, county_slug: str) -> Dict:
        """Promote verified outcomes to tier1_sold_amount for a county"""
        logger.info(f"Processing tier1 promotion for {county_slug}")
        
        # Get auctions missing tier1_sold_amount
        auctions = self.get_county_auctions_missing_tier1(county_slug)
        logger.info(f"Found {len(auctions)} auctions missing tier1_sold_amount in {county_slug}")
        
        if not auctions:
            return {
                'county': county_slug,
                'auctions_processed': 0,
                'promotions': 0,
                'outcome_matches': 0
            }
        
        # Get verified outcomes
        outcomes = self.get_verified_outcomes_for_county(county_slug)
        logger.info(f"Found {len(outcomes)} verified outcomes in {county_slug}")
        
        if not outcomes:
            logger.warning(f"No verified outcomes found for {county_slug} - B criterion must be implemented first")
            return {
                'county': county_slug,
                'auctions_processed': len(auctions),
                'promotions': 0,
                'outcome_matches': 0
            }
        
        # Match outcomes to auctions by case_number
        outcome_lookup = {o['case_number']: o for o in outcomes if o.get('case_number')}
        
        promotions = []
        matches = 0
        
        for auction in auctions:
            case_number = auction.get('case_number')
            if not case_number:
                continue
                
            # Try to match with verified outcome
            outcome = outcome_lookup.get(case_number)
            if outcome and outcome.get('sale_amount'):
                promotions.append({
                    'id': auction['id'],
                    'tier1_sold_amount': float(outcome['sale_amount']),
                    'tier1_verified_at': datetime.now(timezone.utc).isoformat(),
                    'tier1_data_source': outcome['data_source']
                })
                matches += 1
        
        # Batch update auctions with tier1_sold_amount
        promoted = 0
        if promotions:
            # Build PATCH requests for each auction
            for promo in promotions:
                auction_id = promo.pop('id')
                try:
                    response = self.client.patch(
                        f"{BASE}/multi_county_auctions?id=eq.{auction_id}",
                        headers=HEADERS,
                        json=promo
                    )
                    if response.status_code in [200, 204]:
                        promoted += 1
                    else:
                        logger.error(f"Failed to update auction {auction_id}: {response.text}")
                except Exception as e:
                    logger.error(f"Error updating auction {auction_id}: {e}")
                    
                # Throttle to avoid overwhelming DB
                time.sleep(0.1)
        
        result = {
            'county': county_slug,
            'auctions_processed': len(auctions),
            'promotions': promoted,
            'outcome_matches': matches
        }
        
        logger.info(f"✅ {county_slug}: {promoted} tier1 promotions from {matches} outcome matches")
        return result
    
    def evaluate_county_f_criterion(self, county_slug: str) -> Optional[Dict]:
        """Evaluate F criterion for county using pencil_dod_evaluate_county function"""
        try:
            response = self.client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={"county_name": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                # Find F criterion result
                for letter_result in result:
                    if letter_result.get('letter') == 'F':
                        return letter_result
                return None
            else:
                logger.error(f"County evaluation failed for {county_slug}: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error evaluating {county_slug}: {e}")
            return None
    
    def run_full_promotion_cycle(self):
        """Run tier1 promotion for all SHARD-17 counties"""
        logger.info("Starting SHARD-17 F Criterion Promotion Cycle")
        logger.info(f"Target counties: {', '.join(SHARD17_COUNTIES)}")
        
        results = {}
        
        for county in SHARD17_COUNTIES:
            logger.info(f"\n=== PROCESSING {county.upper()} ===")
            
            # Get baseline F criterion
            baseline = self.evaluate_county_f_criterion(county)
            baseline_metric = baseline.get('metric', 0.0) if baseline else 0.0
            baseline_pass = baseline.get('pass', False) if baseline else False
            
            logger.info(f"Baseline F criterion: {baseline_metric}% ({'PASS' if baseline_pass else 'FAIL'})")
            
            # Run promotion
            promo_result = self.promote_tier1_for_county(county)
            
            # Get post-promotion F criterion
            post_promo = self.evaluate_county_f_criterion(county)
            post_metric = post_promo.get('metric', 0.0) if post_promo else 0.0
            post_pass = post_promo.get('pass', False) if post_promo else False
            
            logger.info(f"Post-promotion F criterion: {post_metric}% ({'PASS' if post_pass else 'FAIL'})")
            
            improvement = post_metric - baseline_metric
            logger.info(f"F criterion improvement: {improvement:+.1f} percentage points")
            
            results[county] = {
                **promo_result,
                'f_baseline': baseline_metric,
                'f_post_promotion': post_metric,
                'f_improvement': improvement,
                'f_now_passing': post_pass
            }
            
            time.sleep(2)  # Throttle between counties
        
        return results

def main():
    """Main execution function"""
    promoter = Tier1Promoter()
    
    print("=== GOLD STANDARD AUTOPILOT - F CRITERION PROMOTION ===")
    print("Target: Promote verified outcomes to tier1_sold_amount")
    print("Counties: charlotte, citrus, broward")
    print("Expected improvement: F metric from ~2-6% toward 95%")
    print()
    
    # Run promotion cycle
    results = promoter.run_full_promotion_cycle()
    
    # Summary report
    print("\n" + "="*60)
    print("PROMOTION SUMMARY")
    print("="*60)
    
    total_promotions = 0
    improved_counties = 0
    passing_counties = 0
    
    for county, result in results.items():
        print(f"\n{county.upper()}:")
        print(f"  Auctions processed: {result['auctions_processed']}")
        print(f"  Tier1 promotions: {result['promotions']}")
        print(f"  Outcome matches: {result['outcome_matches']}")
        print(f"  F baseline: {result['f_baseline']:.1f}%")
        print(f"  F post-promotion: {result['f_post_promotion']:.1f}%")
        print(f"  F improvement: {result['f_improvement']:+.1f}pp")
        print(f"  F status: {'✅ PASS' if result['f_now_passing'] else '❌ FAIL'}")
        
        total_promotions += result['promotions']
        if result['f_improvement'] > 0:
            improved_counties += 1
        if result['f_now_passing']:
            passing_counties += 1
    
    print(f"\nTOTALS:")
    print(f"  Counties improved: {improved_counties}/{len(SHARD17_COUNTIES)}")
    print(f"  Counties passing F: {passing_counties}/{len(SHARD17_COUNTIES)}")
    print(f"  Total promotions: {total_promotions}")
    
    if total_promotions > 0:
        print(f"\n✅ SUCCESS: {total_promotions} tier1_sold_amount promotions completed")
        print(f"F criterion advanced for {improved_counties} counties")
    else:
        print(f"\n⚠️  No promotions possible - B criterion (verified outcomes) needs implementation first")
        print(f"Refer to shard17_b_criterion_research.py for building verified outcome scrapers")

if __name__ == "__main__":
    main()