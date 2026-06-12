#!/usr/bin/env python3
"""
SHARD-14 Letter J: Deal Thesis Pipeline (Shapira Formula)
Implements complete bid decision pipeline for Gold Standard compliance

Letter J requires ≥95% of auctions to have complete deal thesis in bid_decisions:
- arv (After Repair Value from comparables/appraiser)
- max_bid (Maximum recommended bid from Shapira Formula)
- ml_score (Machine learning assessment score)
- triangle_score (Comparable market analysis score)

Currently 0% across all SHARD-14 counties.

The Shapira Formula: (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)

Usage:
  python scripts/shard14_letter_j_deal_thesis.py --county osceola
  python scripts/shard14_letter_j_deal_thesis.py --all-counties
"""
import os
import sys
import httpx
import argparse
import json
import random
import math
from datetime import datetime
import time

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-14 target counties
TARGET_COUNTIES = [
    {'name': 'Osceola', 'slug': 'osceola', 'co_no': 59},
    {'name': 'Bay', 'slug': 'bay', 'co_no': 13}, 
    {'name': 'Okeechobee', 'slug': 'okeechobee', 'co_no': 57},
    {'name': 'Hamilton', 'slug': 'hamilton', 'co_no': 34}
]

# Shapira Formula constants
SHAPIRA_FORMULA = {
    'arv_multiplier': 0.70,           # ARV × 70%
    'base_costs': 10000,              # $10K base costs
    'min_profit_pct': 0.15,           # 15% minimum profit
    'min_profit_floor': 25000,        # $25K minimum profit
    'default_repair_pct': 0.12        # 12% of ARV for repairs if unknown
}

# Property type repair estimates (as % of ARV)
PROPERTY_REPAIR_ESTIMATES = {
    'SFR': 0.10,          # Single family residential
    'MFR': 0.15,          # Multi-family residential  
    'CONDO': 0.08,        # Condominium
    'VAC-RES': 0.05,      # Vacant residential land
    'COM': 0.20,          # Commercial
    'IND': 0.25,          # Industrial
    'UNKNOWN': 0.12       # Default
}

def get_auction_deal_status(county_slug, limit=None):
    """Get current deal thesis status for auctions"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Get auctions with basic info needed for deal analysis
        params = {
            "county": f"eq.{county_slug}",
            "select": "case_number,sale_type,opening_bid,parcel_id,property_address,appraised_value"
        }
        
        if limit:
            params["limit"] = str(limit)
        
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=headers,
            params=params
        )
        
        auctions = response.json() if response.status_code == 200 else []
        
        # Check existing bid_decisions
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions?county_slug=eq.{county_slug}&select=case_number,arv,max_bid,ml_score,triangle_score",
            headers=headers
        )
        
        existing_decisions = response.json() if response.status_code == 200 else []
        
        # Analyze completeness
        total_auctions = len(auctions)
        complete_decisions = sum(1 for d in existing_decisions if all([
            d.get('arv'),
            d.get('max_bid'),
            d.get('ml_score'),
            d.get('triangle_score')
        ]))
        
        analysis = {
            'total_auctions': total_auctions,
            'existing_decisions': len(existing_decisions),
            'complete_decisions': complete_decisions,
            'completion_pct': (complete_decisions / total_auctions * 100) if total_auctions > 0 else 0,
            'gap': total_auctions - complete_decisions
        }
        
        return analysis, auctions, existing_decisions
        
    except Exception as e:
        print(f"❌ Error getting deal status for {county_slug}: {e}")
        return None, [], []

def calculate_arv_estimate(auction, county_slug):
    """Calculate ARV estimate for an auction property"""
    # Use appraised value as starting point if available
    if auction.get('appraised_value'):
        appraised = float(auction['appraised_value'])
        # ARV typically 110-130% of appraised value for distressed properties
        arv_estimate = appraised * random.uniform(1.10, 1.30)
        confidence = 0.8
        source = 'appraiser_adjusted'
    else:
        # Fallback: estimate based on opening bid and market conditions
        opening_bid = float(auction.get('opening_bid', 50000))
        # ARV typically 150-200% of tax auction opening bid  
        arv_estimate = opening_bid * random.uniform(1.50, 2.00)
        confidence = 0.5
        source = 'opening_bid_estimate'
    
    return {
        'arv': round(arv_estimate, 2),
        'arv_confidence': confidence,
        'arv_source': source
    }

def calculate_repair_estimate(arv, property_type=None):
    """Calculate repair estimate based on property type and ARV"""
    if property_type and property_type in PROPERTY_REPAIR_ESTIMATES:
        repair_pct = PROPERTY_REPAIR_ESTIMATES[property_type]
    else:
        repair_pct = PROPERTY_REPAIR_ESTIMATES['UNKNOWN']
    
    repair_estimate = arv * repair_pct
    return round(repair_estimate, 2)

def calculate_shapira_max_bid(arv, repair_estimate):
    """Calculate maximum bid using Shapira Formula"""
    # Shapira Formula: (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)
    
    base_value = arv * SHAPIRA_FORMULA['arv_multiplier']
    profit_15pct = arv * SHAPIRA_FORMULA['min_profit_pct']
    profit_required = min(SHAPIRA_FORMULA['min_profit_floor'], profit_15pct)
    
    max_bid = (base_value - 
               repair_estimate - 
               SHAPIRA_FORMULA['base_costs'] - 
               profit_required)
    
    # Ensure max_bid is not negative
    max_bid = max(0, max_bid)
    
    return round(max_bid, 2)

def calculate_ml_score(auction, arv, max_bid):
    """Calculate ML-style risk assessment score (0.0 to 1.0)"""
    score_factors = []
    
    # Factor 1: Bid margin safety (higher margin = lower risk)
    opening_bid = float(auction.get('opening_bid', 0))
    if opening_bid > 0 and max_bid > opening_bid:
        margin_factor = min(1.0, (max_bid - opening_bid) / opening_bid)
        score_factors.append(margin_factor * 0.3)  # 30% weight
    else:
        score_factors.append(0.0)  # No margin safety
    
    # Factor 2: Property data completeness
    completeness = 0
    if auction.get('property_address'):
        completeness += 0.25
    if auction.get('parcel_id'):
        completeness += 0.25  
    if auction.get('appraised_value'):
        completeness += 0.5
    score_factors.append(completeness * 0.2)  # 20% weight
    
    # Factor 3: ARV confidence (from earlier calculation)
    # This would come from the ARV calculation
    arv_confidence = 0.7  # Default for now
    score_factors.append(arv_confidence * 0.3)  # 30% weight
    
    # Factor 4: Market velocity (simulated)
    market_velocity = random.uniform(0.5, 0.9)  # Would come from market data
    score_factors.append(market_velocity * 0.2)  # 20% weight
    
    # Combine factors
    ml_score = sum(score_factors)
    return round(ml_score, 3)

def calculate_triangle_score(arv, county_slug):
    """Calculate triangle/comparable analysis score"""
    # This would normally compare against recent sales
    # For now, simulate based on ARV and market conditions
    
    # Factors affecting triangle score:
    # - Number of recent comparables
    # - Price per square foot consistency  
    # - Market velocity
    # - Geographic proximity
    
    comparable_count = random.randint(2, 8)  # Simulated
    
    # More comparables = higher confidence
    comparable_factor = min(1.0, comparable_count / 5.0) * 0.4
    
    # Price consistency factor (simulated)
    consistency_factor = random.uniform(0.6, 0.9) * 0.3
    
    # Market velocity factor
    velocity_factor = random.uniform(0.5, 0.8) * 0.3
    
    triangle_score = comparable_factor + consistency_factor + velocity_factor
    
    return {
        'triangle_score': round(triangle_score, 3),
        'comparable_count': comparable_count,
        'avg_price_per_sqft': round(arv / random.uniform(800, 2000), 2),  # Simulated
        'market_velocity': 'normal'  # Would be calculated from market data
    }

def generate_deal_recommendation(max_bid, opening_bid, ml_score, triangle_score):
    """Generate deal recommendation and reasoning"""
    # Decision logic
    if max_bid <= opening_bid * 0.8:
        recommendation = 'SKIP'
        reason = 'Maximum bid too low relative to opening bid'
    elif ml_score < 0.4:
        recommendation = 'SKIP' 
        reason = 'High risk score'
    elif triangle_score < 0.5:
        recommendation = 'RESEARCH'
        reason = 'Weak comparable analysis - need more market data'
    elif max_bid >= opening_bid * 1.5 and ml_score >= 0.7 and triangle_score >= 0.7:
        recommendation = 'BID'
        reason = 'Strong margin and low risk'
    elif max_bid >= opening_bid * 1.2:
        recommendation = 'BID'
        reason = 'Acceptable margin and risk profile'
    else:
        recommendation = 'RESEARCH'
        reason = 'Marginal deal - requires detailed analysis'
    
    max_bid_ratio = (max_bid / opening_bid * 100) if opening_bid > 0 else 0
    
    return {
        'recommendation': recommendation,
        'recommendation_reason': reason,
        'max_bid_ratio': round(max_bid_ratio, 2)
    }

def create_sample_bid_decisions(county_slug, auctions, sample_size=10):
    """Create sample bid decisions using Shapira Formula"""
    print(f"\n🎯 Creating sample bid decisions for {county_slug} (sample: {sample_size})...")
    
    sample_auctions = auctions[:sample_size] if len(auctions) >= sample_size else auctions
    bid_decisions = []
    
    for auction in sample_auctions:
        case_number = auction['case_number']
        
        print(f"  🔍 Analyzing {case_number}...")
        
        # Step 1: Calculate ARV
        arv_data = calculate_arv_estimate(auction, county_slug)
        arv = arv_data['arv']
        
        # Step 2: Calculate repair estimate  
        repair_estimate = calculate_repair_estimate(arv)
        
        # Step 3: Calculate max bid using Shapira Formula
        max_bid = calculate_shapira_max_bid(arv, repair_estimate)
        
        # Step 4: Calculate ML score
        ml_score = calculate_ml_score(auction, arv, max_bid)
        
        # Step 5: Calculate triangle score
        triangle_data = calculate_triangle_score(arv, county_slug)
        triangle_score = triangle_data['triangle_score']
        
        # Step 6: Generate recommendation
        opening_bid = float(auction.get('opening_bid', 0))
        recommendation_data = generate_deal_recommendation(
            max_bid, opening_bid, ml_score, triangle_score
        )
        
        # Compile complete bid decision
        bid_decision = {
            'case_number': case_number,
            'county_slug': county_slug,
            'parcel_id': auction.get('parcel_id'),
            
            # ARV components
            'arv': arv,
            'arv_source': arv_data['arv_source'],
            'arv_confidence': arv_data['arv_confidence'],
            
            # Shapira Formula components
            'max_bid': max_bid,
            'repair_estimate': repair_estimate,
            'holding_costs': round(arv * 0.02, 2),  # 2% for 6-month holding
            'profit_target': min(25000, arv * 0.15),
            
            # ML Score
            'ml_score': ml_score,
            'ml_model_version': 'shapira_v1_sample',
            'ml_features_used': ['margin_safety', 'data_completeness', 'arv_confidence', 'market_velocity'],
            
            # Triangle analysis
            'triangle_score': triangle_score,
            'comparable_count': triangle_data['comparable_count'],
            'avg_price_per_sqft': triangle_data['avg_price_per_sqft'],
            'market_velocity': triangle_data['market_velocity'],
            
            # CMA range
            'cma_low': round(arv * 0.90, 2),
            'cma_high': round(arv * 1.10, 2),
            'cma_confidence': 0.75,
            
            # Final recommendation
            'recommendation': recommendation_data['recommendation'],
            'recommendation_reason': recommendation_data['recommendation_reason'],
            'max_bid_ratio': recommendation_data['max_bid_ratio'],
            
            # Audit trail
            'calculated_by': 'shard14_letter_j_sample',
            'calculated_at': datetime.now().isoformat()
        }
        
        bid_decisions.append(bid_decision)
        
        print(f"    ARV: ${arv:,.0f}, Max Bid: ${max_bid:,.0f}, Rec: {bid_decision['recommendation']}")
    
    print(f"✅ Generated {len(bid_decisions)} bid decisions for {county_slug}")
    
    # Summary by recommendation
    recommendations = {}
    for decision in bid_decisions:
        rec = decision['recommendation']
        recommendations[rec] = recommendations.get(rec, 0) + 1
    
    print(f"Recommendations: {dict(recommendations)}")
    
    return bid_decisions

def analyze_deal_thesis_gap(county_slug):
    """Analyze the gap in deal thesis completion"""
    print(f"\n📊 DEAL THESIS ANALYSIS: {county_slug}")
    print("-" * 50)
    
    analysis, auctions, decisions = get_auction_deal_status(county_slug)
    if not analysis:
        return None
    
    total = analysis['total_auctions']
    complete = analysis['complete_decisions']
    completion_pct = analysis['completion_pct']
    
    print(f"Total auctions: {total}")
    print(f"Complete deal thesis: {complete}")
    print(f"Completion rate: {completion_pct:.1f}%")
    print(f"Letter J threshold: ≥95% ({int(total * 0.95)} complete decisions needed)")
    print(f"Gap: {analysis['gap']} auctions need deal analysis")
    
    return analysis

def main():
    parser = argparse.ArgumentParser(description='SHARD-14 Letter J: Deal Thesis Pipeline')
    parser.add_argument('--county', help='Process specific county only')
    parser.add_argument('--all-counties', action='store_true', help='Process all SHARD-14 counties')
    parser.add_argument('--create-samples', action='store_true', help='Create sample bid decisions')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze gaps, do not create decisions')
    parser.add_argument('--sample-size', type=int, default=10, help='Number of decisions to create in sample mode')
    
    args = parser.parse_args()
    
    if not args.county and not args.all_counties:
        parser.print_help()
        sys.exit(1)
    
    print("🎯 SHARD-14 LETTER J: DEAL THESIS PIPELINE")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()
    
    # Display Shapira Formula
    print("SHAPIRA FORMULA:")
    print("Max Bid = (ARV × 70%) - Repairs - $10K - MIN($25K, 15% × ARV)")
    print()
    
    # Determine counties to process
    if args.county:
        counties = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        if not counties:
            print(f"❌ County '{args.county}' not found in SHARD-14")
            sys.exit(1)
    else:
        counties = TARGET_COUNTIES
    
    print(f"Processing {len(counties)} counties for Letter J compliance...")
    
    total_gap = 0
    results = []
    
    for county in counties:
        county_slug = county['slug']
        county_name = county['name']
        
        print(f"\n{'='*20} {county_name.upper()} {'='*20}")
        
        # Analyze current deal thesis status
        gap_analysis = analyze_deal_thesis_gap(county_slug)
        if gap_analysis:
            results.append(gap_analysis)
            total_gap += gap_analysis['gap']
        
        if not args.analyze_only:
            # Get auction data for processing
            _, auctions, _ = get_auction_deal_status(county_slug)
            
            # Create sample bid decisions if requested
            if args.create_samples and auctions and gap_analysis['gap'] > 0:
                bid_decisions = create_sample_bid_decisions(
                    county_slug,
                    auctions,
                    args.sample_size
                )
                print(f"✅ Sample decisions created: {len(bid_decisions)} for {county_slug}")
    
    # Summary
    print(f"\n{'='*60}")
    print("SHARD-14 LETTER J SUMMARY")
    print(f"{'='*60}")
    print(f"Total gap across all counties: {total_gap} deal decisions needed")
    print()
    
    for result in results:
        county = result['county_slug']
        completion = result['completion_pct'] 
        gap = result['gap']
        status = "✅ PASS" if completion >= 95 else "❌ FAIL"
        print(f"{county:12s} {status} {completion:5.1f}% complete, {gap:4d} gap")
    
    print(f"\nNEXT STEPS:")
    print(f"1. Set up automated ARV calculation pipeline (appraiser + comparable data)")
    print(f"2. Build ML model for risk assessment scoring")
    print(f"3. Integrate MLS/comparable sales data for triangle analysis")
    print(f"4. Create CMA (Comparative Market Analysis) automation")
    print(f"5. Deploy Shapira Formula calculator as database function")
    print(f"6. Set up daily batch processing for new auctions")
    
    if total_gap > 0:
        print(f"\n⚠️ Estimated effort: {total_gap} decisions × 5-10 min/decision = {total_gap * 7.5 / 60:.1f} hours")

if __name__ == "__main__":
    main()