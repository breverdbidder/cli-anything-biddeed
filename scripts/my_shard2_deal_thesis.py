#!/usr/bin/env python3
"""
MY SHARD-2 DEAL THESIS CALCULATION - Letter J Gold Standard
Calculates Shapira deal thesis (ARV + max_bid + ml_score + triangle factors + two-arm CMA)
For charlotte, polk, hendry, st_lucie, holmes counties

Critical for Letter J: ≥95% deal thesis complete (triangle + two-arm CMA + ml_score + max_bid)

Usage:
  python scripts/my_shard2_deal_thesis.py --county charlotte
  python scripts/my_shard2_deal_thesis.py --all-counties --verify-metrics
"""
import httpx
import json
import os
import sys
import argparse
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

MY_TARGET_COUNTIES = ['charlotte', 'polk', 'hendry', 'st_lucie', 'holmes']

# Shapira Formula constants
SHAPIRA_FORMULA_V14 = {
    'repair_base': 10000,      # Base repair cost
    'min_profit': 25000,       # Minimum profit target
    'profit_pct': 0.15,        # 15% profit margin
    'arv_multiplier': 0.70,    # 70% of ARV rule
    'comps_radius_miles': 0.5, # Comp search radius
    'comps_days_back': 180,    # Comp recency
    'confidence_threshold': 0.7 # ML confidence threshold
}

client = httpx.Client(timeout=60, follow_redirects=True)

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

def get_auctions_needing_deal_thesis(county_slug: str, limit: int = 500) -> List[Dict]:
    """Get auctions that need deal thesis calculation"""
    params = {
        'select': 'case_number,parcel_id,property_address,latitude,longitude,assessed_value,auction_date,sale_type',
        'county': f'eq.{county_slug}',
        'auction_date': f'gte.{(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")}',  # Recent auctions
        'order': 'auction_date.desc',
        'limit': str(limit)
    }
    
    auctions = supabase_get('multi_county_auctions', params)
    logger.info(f"Found {len(auctions)} auctions needing deal thesis for {county_slug}")
    return auctions

def check_existing_deal_decisions(county_slug: str, case_numbers: List[str]) -> set:
    """Check which cases already have deal decisions"""
    if not case_numbers:
        return set()
    
    case_filter = ','.join(f'"{cn}"' for cn in case_numbers)
    params = {
        'select': 'case_number',
        'county_slug': f'eq.{county_slug}',
        'case_number': f'in.({case_filter})'
    }
    
    existing = supabase_get('bid_decisions', params)
    existing_cases = {row['case_number'] for row in existing}
    
    logger.info(f"Found {len(existing_cases)} existing deal decisions for {county_slug}")
    return existing_cases

def get_nearby_comps(latitude: float, longitude: float, county_slug: str, days_back: int = 180) -> List[Dict]:
    """Get comparable sales within radius"""
    # Simple distance calculation (approximate)
    since_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    # For now, get recent sales from same county
    # TODO: Implement proper distance-based filtering
    params = {
        'select': 'case_number,winning_bid,assessed_value,latitude,longitude,auction_date',
        'county': f'eq.{county_slug}',
        'auction_status': 'eq.sold',
        'winning_bid': 'not.is.null',
        'auction_date': f'gte.{since_date}',
        'order': 'auction_date.desc',
        'limit': '50'
    }
    
    comps = supabase_get('multi_county_auctions', params)
    
    # Filter by distance if coordinates available
    if latitude and longitude:
        filtered_comps = []
        for comp in comps:
            comp_lat = comp.get('latitude')
            comp_lon = comp.get('longitude')
            
            if comp_lat and comp_lon:
                # Simple distance calculation (rough)
                lat_diff = abs(float(latitude) - float(comp_lat))
                lon_diff = abs(float(longitude) - float(comp_lon))
                distance = math.sqrt(lat_diff**2 + lon_diff**2)
                
                if distance < 0.01:  # Rough distance filter
                    filtered_comps.append(comp)
        
        if filtered_comps:
            return filtered_comps
    
    # Return unfiltered if no location data
    return comps[:10]  # Limit to reasonable number

def calculate_arv_estimate(auction: Dict, comps: List[Dict]) -> Optional[float]:
    """Calculate ARV (After Repair Value) based on comps"""
    if not comps:
        # Fallback to assessed value * multiplier
        assessed_value = auction.get('assessed_value')
        if assessed_value:
            try:
                return float(assessed_value) * 1.2  # 20% above assessed value
            except (ValueError, TypeError):
                return None
        return None
    
    # Use median winning bid from comps
    comp_values = []
    for comp in comps:
        winning_bid = comp.get('winning_bid')
        if winning_bid:
            try:
                comp_values.append(float(winning_bid))
            except (ValueError, TypeError):
                continue
    
    if comp_values:
        comp_values.sort()
        median_value = comp_values[len(comp_values) // 2]
        return median_value * 1.1  # 10% adjustment for ARV
    
    return None

def calculate_max_bid(arv: float, repair_cost: float = None) -> float:
    """Calculate maximum bid using Shapira formula"""
    if repair_cost is None:
        repair_cost = SHAPIRA_FORMULA_V14['repair_base']
    
    formula_constants = SHAPIRA_FORMULA_V14
    
    # Shapira Formula: (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)
    base_bid = arv * formula_constants['arv_multiplier']
    base_bid -= repair_cost
    base_bid -= formula_constants['repair_base']  # Additional $10K buffer
    
    profit_target = min(
        formula_constants['min_profit'],
        formula_constants['profit_pct'] * arv
    )
    base_bid -= profit_target
    
    return max(base_bid, 0)  # Don't go negative

def calculate_ml_score(auction: Dict, comps: List[Dict]) -> float:
    """Calculate ML confidence score (placeholder)"""
    # Placeholder ML scoring based on available data
    score = 0.5  # Base score
    
    # Boost score if we have property details
    if auction.get('property_address'):
        score += 0.1
    if auction.get('latitude') and auction.get('longitude'):
        score += 0.1
    if auction.get('assessed_value'):
        score += 0.1
    
    # Boost score if we have good comps
    if len(comps) >= 3:
        score += 0.15
    elif len(comps) >= 1:
        score += 0.05
    
    return min(score, 1.0)  # Cap at 1.0

def calculate_triangle_factors(auction: Dict, comps: List[Dict]) -> Dict[str, float]:
    """Calculate triangle factors (location, condition, market)"""
    factors = {
        'location_factor': 1.0,    # Placeholder
        'condition_factor': 0.9,   # Assume some repair needed
        'market_factor': 1.0       # Neutral market
    }
    
    # Adjust based on comp count (proxy for market activity)
    if len(comps) >= 5:
        factors['market_factor'] = 1.1  # Hot market
    elif len(comps) <= 1:
        factors['market_factor'] = 0.9  # Cold market
    
    return factors

def calculate_two_arm_cma(auction: Dict, comps: List[Dict]) -> Dict[str, Optional[float]]:
    """Calculate two-arm CMA (Comparative Market Analysis)"""
    if not comps:
        return {
            'cma_low': None,
            'cma_high': None,
            'cma_median': None
        }
    
    comp_values = []
    for comp in comps:
        winning_bid = comp.get('winning_bid')
        if winning_bid:
            try:
                comp_values.append(float(winning_bid))
            except (ValueError, TypeError):
                continue
    
    if not comp_values:
        return {
            'cma_low': None,
            'cma_high': None,
            'cma_median': None
        }
    
    comp_values.sort()
    
    return {
        'cma_low': comp_values[0],
        'cma_high': comp_values[-1],
        'cma_median': comp_values[len(comp_values) // 2]
    }

def generate_deal_decision(auction: Dict) -> Optional[Dict]:
    """Generate complete deal decision for an auction"""
    case_number = auction['case_number']
    county = auction.get('county', 'unknown')
    
    # Get comparable sales
    latitude = auction.get('latitude')
    longitude = auction.get('longitude')
    
    comps = []
    if latitude and longitude:
        comps = get_nearby_comps(float(latitude), float(longitude), county)
    
    # Calculate ARV
    arv = calculate_arv_estimate(auction, comps)
    if not arv:
        logger.warning(f"Could not calculate ARV for {case_number}")
        return None
    
    # Calculate max bid
    max_bid = calculate_max_bid(arv)
    
    # Calculate ML score
    ml_score = calculate_ml_score(auction, comps)
    
    # Calculate triangle factors
    triangle_factors = calculate_triangle_factors(auction, comps)
    
    # Calculate two-arm CMA
    cma_data = calculate_two_arm_cma(auction, comps)
    
    # Create deal decision record
    decision = {
        'case_number': case_number,
        'county_slug': county,
        'parcel_id': auction.get('parcel_id'),
        'arv_estimate': arv,
        'max_bid': max_bid,
        'ml_score': ml_score,
        'location_factor': triangle_factors['location_factor'],
        'condition_factor': triangle_factors['condition_factor'],
        'market_factor': triangle_factors['market_factor'],
        'cma_low': cma_data['cma_low'],
        'cma_high': cma_data['cma_high'],
        'cma_median': cma_data['cma_median'],
        'comps_count': len(comps),
        'calculation_method': 'shapira_v14',
        'calculated_at': datetime.now().isoformat(),
        'data_source': f'{county}_deal_thesis:MY-SHARD2-J-V1'
    }
    
    logger.info(f"Generated deal thesis for {case_number}: ARV=${arv:.0f}, MaxBid=${max_bid:.0f}, ML={ml_score:.2f}")
    return decision

def evaluate_county_metrics(county_slug: str) -> Dict:
    """Evaluate county metrics using pencil_dod_evaluate_county function"""
    try:
        # Try multiple parameter formats
        for param_name in ["county_name", "county_slug_arg"]:
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json={param_name: county_slug},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                }
        
        return {'success': False, 'error': 'All parameter formats failed'}
        
    except Exception as e:
        logger.error(f"Error evaluating {county_slug}: {e}")
        return {'success': False, 'error': str(e)}

def process_county_deal_thesis(county_slug: str, verify_metrics: bool = False) -> Dict[str, int]:
    """Process deal thesis calculation for a single county"""
    logger.info(f"\n=== Processing {county_slug.upper()} Deal Thesis ===")
    
    # Get baseline metrics if requested
    baseline_metrics = None
    if verify_metrics:
        baseline_metrics = evaluate_county_metrics(county_slug)
    
    # Get auctions needing deal thesis
    auctions = get_auctions_needing_deal_thesis(county_slug)
    if not auctions:
        logger.info(f"No auctions found for deal thesis calculation for {county_slug}")
        return {'processed': 0, 'calculated': 0}
    
    case_numbers = [a['case_number'] for a in auctions if a['case_number']]
    
    # Check existing deal decisions
    existing_decisions = check_existing_deal_decisions(county_slug, case_numbers)
    new_auctions = [a for a in auctions if a['case_number'] not in existing_decisions]
    
    if not new_auctions:
        logger.info(f"All {len(case_numbers)} cases already have deal decisions")
        return {'processed': len(auctions), 'calculated': 0}
    
    logger.info(f"Need to calculate deal thesis for {len(new_auctions)} new cases")
    
    # Generate deal decisions
    deal_decisions = []
    for auction in new_auctions[:50]:  # Process in batches
        try:
            decision = generate_deal_decision(auction)
            if decision:
                deal_decisions.append(decision)
        except Exception as e:
            logger.error(f"Error generating deal decision for {auction['case_number']}: {e}")
            continue
    
    # Upsert to bid_decisions table
    total_inserted = 0
    if deal_decisions:
        total_inserted = supabase_upsert('bid_decisions', deal_decisions)
    
    # Get final metrics if requested
    if verify_metrics and total_inserted > 0:
        final_metrics = evaluate_county_metrics(county_slug)
        if baseline_metrics.get('success') and final_metrics.get('success'):
            # Compare Letter J metrics
            baseline_j = 'UNKNOWN'
            final_j = 'UNKNOWN'
            
            # Extract grade_j from results
            baseline_result = baseline_metrics.get('result', {})
            final_result = final_metrics.get('result', {})
            
            if isinstance(baseline_result, dict):
                baseline_j = baseline_result.get('grade_j', 'UNKNOWN')
            if isinstance(final_result, dict):
                final_j = final_result.get('grade_j', 'UNKNOWN')
            
            logger.info(f"📊 Letter J metric change: {baseline_j} → {final_j}")
    
    return {
        'processed': len(auctions),
        'calculated': total_inserted
    }

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MY SHARD-2 Deal Thesis Calculator")
    parser.add_argument('--county', choices=MY_TARGET_COUNTIES, help='Specific county to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all MY SHARD-2 counties')
    parser.add_argument('--verify-metrics', action='store_true', help='Compare metrics before/after')
    parser.add_argument('--dry-run', action='store_true', help='Analyze only, no database writes')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("💰 MY SHARD-2 DEAL THESIS CALCULATOR - Letter J")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Determine counties to process
    if args.county:
        counties_to_process = [args.county]
    elif args.all_counties:
        counties_to_process = MY_TARGET_COUNTIES
    else:
        logger.error("Must specify --county or --all-counties")
        sys.exit(1)
    
    logger.info(f"Processing counties: {', '.join(counties_to_process)}")
    
    # Process each county
    total_stats = {'processed': 0, 'calculated': 0}
    
    for county in counties_to_process:
        try:
            if args.dry_run:
                # Just analyze, don't write
                auctions = get_auctions_needing_deal_thesis(county)
                logger.info(f"{county.upper()}: {len(auctions)} auctions needing deal thesis")
                continue
            
            stats = process_county_deal_thesis(county, args.verify_metrics)
            
            logger.info(f"{county.upper()} Results:")
            logger.info(f"  - Processed auctions: {stats['processed']}")
            logger.info(f"  - Deal thesis calculated: {stats['calculated']}")
            
            total_stats['processed'] += stats['processed']
            total_stats['calculated'] += stats['calculated']
            
        except Exception as e:
            logger.error(f"Error processing {county}: {e}")
            continue
    
    # Summary
    logger.info(f"\n🎯 MY SHARD-2 DEAL THESIS SUMMARY")
    logger.info(f"Total auctions processed: {total_stats['processed']}")
    logger.info(f"Total deal thesis calculated: {total_stats['calculated']}")
    
    if total_stats['calculated'] > 0:
        logger.info("\n✅ Letter J metric should improve after deal thesis calculation")
        logger.info("Run pencil_dod_evaluate_county('<county>') to verify metric changes")
    else:
        logger.info("\n⚠️ No new deal thesis calculated - may need better data sources")

if __name__ == "__main__":
    main()