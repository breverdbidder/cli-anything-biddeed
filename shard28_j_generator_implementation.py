#!/usr/bin/env python3
"""
SHARD-28 J GENERATOR: Build bid_decisions pipeline for brevard and duval
Implements Shapira Formula pipeline to move Letter J from 0.0% to 95%

Contract: bid_decisions table with:
- case_number (FK to multi_county_auctions)  
- arv (After Repair Value)
- max_bid (Shapira calculated)
- ml_score (from Shapira V14 model)
- factors (JSON with 5 keys: distress_location, distress_property, distress_owner, cma_distressed, cma_resale)

Data sources:
- ARV: gen_valuations_comps_batch (existing)
- ML Score: Shapira V14 model (shapira_models table)
- CMA: gen_valuations_comps_batch for distressed + resale comparables
- Max Bid: ARV * 70% - Repairs - $10K - MIN($25K, 15% * ARV)

COUNTY-AGNOSTIC: Works for both brevard and duval
"""

import os
import sys
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_KEY", "")

# Target counties
TARGET_COUNTIES = ['brevard', 'duval']

def sb_headers():
    """Supabase request headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def query_supabase(table: str, params: str = "") -> List[Dict]:
    """Query Supabase table with optional filters"""
    try:
        with httpx.Client(timeout=60) as client:
            url = f"{SUPABASE_URL}/rest/v1/{table}"
            if params:
                url += f"?{params}"
            
            response = client.get(url, headers=sb_headers())
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"❌ Error querying {table}: {e}")
        return []

def upsert_supabase(table: str, data: List[Dict], on_conflict: str = "") -> bool:
    """Upsert data to Supabase table"""
    try:
        with httpx.Client(timeout=120) as client:
            url = f"{SUPABASE_URL}/rest/v1/{table}"
            if on_conflict:
                url += f"?on_conflict={on_conflict}"
            
            response = client.post(url, headers=sb_headers(), json=data)
            response.raise_for_status()
            return True
    except Exception as e:
        print(f"❌ Error upserting to {table}: {e}")
        return False

def get_auction_cases_for_county(county: str) -> List[Dict]:
    """Get auction cases that need bid decisions"""
    print(f"📋 Getting auction cases for {county}...")
    
    # Get cases that don't have bid_decisions yet
    query = (
        "select=case_number,parcel_id,sale_date,auction_status"
        f"&county=eq.{county}"
        "&auction_status=in.(sold,no_sale,canceled)"
        "&limit=1000"
    )
    
    auctions = query_supabase("multi_county_auctions", query)
    
    # Filter out cases that already have bid_decisions
    existing_decisions = query_supabase("bid_decisions", f"select=case_number&county_slug=eq.{county}")
    existing_case_numbers = {bd['case_number'] for bd in existing_decisions}
    
    new_cases = [a for a in auctions if a['case_number'] not in existing_case_numbers]
    
    print(f"  📊 {county}: {len(auctions)} total auctions, {len(existing_decisions)} have decisions, {len(new_cases)} need processing")
    return new_cases

def get_valuations_data(case_numbers: List[str]) -> Dict[str, Dict]:
    """Get valuations/comps data for case numbers"""
    print(f"💰 Getting valuations data for {len(case_numbers)} cases...")
    
    if not case_numbers:
        return {}
    
    # Query gen_valuations_comps_batch for ARV and CMA data
    case_filter = ",".join(f'"{cn}"' for cn in case_numbers[:500])  # Limit to avoid URL length issues
    query = f"select=*&case_number=in.({case_filter})"
    
    valuations = query_supabase("gen_valuations_comps_batch", query)
    
    # Index by case_number
    return {v['case_number']: v for v in valuations if v.get('case_number')}

def get_ml_scores(county: str) -> Dict[str, float]:
    """Get ML scores from Shapira V14 model"""
    print(f"🤖 Getting ML scores for {county}...")
    
    # Query shapira_models table for V14 scores
    query = f"select=case_number,ml_score,model_version&county=eq.{county}&model_version=eq.V14"
    scores = query_supabase("shapira_models", query)
    
    return {s['case_number']: s['ml_score'] for s in scores if s.get('ml_score') is not None}

def calculate_shapira_factors(valuations: Dict) -> Dict:
    """Calculate the 5 required Shapira factors from valuations data"""
    
    # Default factor structure
    factors = {
        "distress_location": 0.0,
        "distress_property": 0.0, 
        "distress_owner": 0.0,
        "cma_distressed": 0.0,
        "cma_resale": 0.0
    }
    
    if not valuations:
        return factors
    
    # Calculate factors based on available valuations data
    # These calculations are simplified - in production would use more sophisticated logic
    
    # Distress location: Based on days on market, price reductions
    if valuations.get('days_on_market'):
        factors["distress_location"] = min(1.0, valuations['days_on_market'] / 180.0)
    
    # Distress property: Based on condition, needed repairs
    if valuations.get('condition_score'):
        factors["distress_property"] = 1.0 - (valuations['condition_score'] / 10.0)
    
    # Distress owner: Based on foreclosure timeline, liens
    if valuations.get('foreclosure_timeline_days'):
        factors["distress_owner"] = min(1.0, valuations['foreclosure_timeline_days'] / 365.0)
    
    # CMA distressed: Average sale price of distressed properties in area
    if valuations.get('distressed_comps_avg_price'):
        factors["cma_distressed"] = valuations['distressed_comps_avg_price']
    
    # CMA resale: Average sale price of retail properties in area  
    if valuations.get('retail_comps_avg_price'):
        factors["cma_resale"] = valuations['retail_comps_avg_price']
    
    return factors

def calculate_max_bid(arv: float, repair_estimate: float = 25000) -> float:
    """
    Calculate max bid using Shapira Formula:
    ARV × 70% - Repairs - $10K - MIN($25K, 15% × ARV)
    """
    if not arv or arv <= 0:
        return 0.0
    
    # Apply Shapira formula
    base_bid = arv * 0.70
    safety_buffer = 10000  # $10K buffer
    profit_cushion = min(25000, 0.15 * arv)  # MIN($25K, 15% × ARV)
    
    max_bid = base_bid - repair_estimate - safety_buffer - profit_cushion
    
    # Ensure non-negative
    return max(0.0, max_bid)

def generate_bid_decisions_batch(county: str, auction_cases: List[Dict]) -> List[Dict]:
    """Generate bid decisions for a batch of auction cases"""
    
    if not auction_cases:
        return []
    
    case_numbers = [case['case_number'] for case in auction_cases]
    
    # Get supporting data
    valuations_data = get_valuations_data(case_numbers)
    ml_scores = get_ml_scores(county)
    
    bid_decisions = []
    
    for case in auction_cases:
        case_number = case['case_number']
        valuations = valuations_data.get(case_number, {})
        ml_score = ml_scores.get(case_number, 0.0)
        
        # Get ARV (After Repair Value)
        arv = valuations.get('arv_estimate') or valuations.get('estimated_value')
        if not arv:
            continue  # Skip cases without ARV
        
        # Calculate factors
        factors = calculate_shapira_factors(valuations)
        
        # Calculate max bid
        repair_estimate = valuations.get('repair_estimate', 25000)  # Default $25K
        max_bid = calculate_max_bid(arv, repair_estimate)
        
        # Skip cases with very low max bids (likely data quality issues)
        if max_bid < 1000:
            continue
        
        # Create bid decision record
        decision = {
            "case_number": case_number,
            "county_slug": county,
            "parcel_id": case.get('parcel_id'),
            "arv": float(arv),
            "max_bid": float(max_bid),
            "ml_score": float(ml_score) if ml_score else None,
            "ml_model_version": "V14" if ml_score else None,
            "factors": factors,
            "repair_estimate": float(repair_estimate) if repair_estimate else None,
            "profit_potential": float(arv - max_bid - repair_estimate) if arv and repair_estimate else None,
            "confidence_score": min(1.0, sum([
                0.3 if arv else 0,
                0.2 if ml_score else 0,
                0.2 if factors.get("cma_distressed") else 0,
                0.2 if factors.get("cma_resale") else 0,
                0.1 if repair_estimate else 0
            ])),
            "data_sources": ["shapira_formula", "gen_valuations_comps_batch"],
            "notes": f"Generated by SHARD-28 J generator for {county}",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        bid_decisions.append(decision)
    
    return bid_decisions

def process_county_j_pipeline(county: str) -> Tuple[int, int]:
    """Process J pipeline for a single county"""
    print(f"\n🎯 Processing J pipeline for {county.upper()}")
    
    # Get auction cases needing bid decisions
    auction_cases = get_auction_cases_for_county(county)
    
    if not auction_cases:
        print(f"  ✅ {county}: No new cases to process")
        return 0, 0
    
    # Generate bid decisions in batches
    batch_size = 100
    total_processed = 0
    total_inserted = 0
    
    for i in range(0, len(auction_cases), batch_size):
        batch = auction_cases[i:i + batch_size]
        print(f"  📦 Processing batch {i//batch_size + 1} ({len(batch)} cases)")
        
        # Generate decisions for batch
        decisions = generate_bid_decisions_batch(county, batch)
        total_processed += len(batch)
        
        if decisions:
            # Upsert to database
            success = upsert_supabase("bid_decisions", decisions, on_conflict="case_number")
            
            if success:
                total_inserted += len(decisions)
                print(f"    ✅ Inserted {len(decisions)} bid decisions")
            else:
                print(f"    ❌ Failed to insert batch")
        else:
            print(f"    ⚠️ No valid decisions generated for batch")
    
    print(f"  📊 {county} summary: {total_processed} processed, {total_inserted} inserted")
    return total_processed, total_inserted

def verify_j_metrics():
    """Verify J metrics after processing"""
    print(f"\n🔍 Verifying Letter J metrics...")
    
    # Refresh the materialized view
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/refresh_letter_j_metrics",
                headers=sb_headers(),
                json={}
            )
            response.raise_for_status()
            print("  ✅ Refreshed v_letter_j_metrics materialized view")
    except Exception as e:
        print(f"  ⚠️ Could not refresh materialized view: {e}")
    
    # Query current J metrics
    metrics = query_supabase("v_letter_j_metrics", "select=*")
    
    for metric in metrics:
        county = metric['county_slug']
        percentage = metric['j_metric_percentage']
        complete = metric['complete_decisions']
        total = metric['total_auctions_with_decisions']
        
        status_emoji = "✅" if percentage >= 95.0 else "❌"
        print(f"  {county}: {status_emoji} {percentage:.1f}% ({complete}/{total} complete)")

def main():
    print("=" * 60)
    print("SHARD-28 J GENERATOR: Shapira Formula Pipeline")
    print("Target: brevard J=0.0, duval J=0.0 → 95%+ completion")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_SERVICE_KEY or SUPABASE_KEY required")
        sys.exit(1)
    
    total_processed = 0
    total_inserted = 0
    
    # Process each target county
    for county in TARGET_COUNTIES:
        processed, inserted = process_county_j_pipeline(county)
        total_processed += processed
        total_inserted += inserted
    
    print(f"\n🏆 J GENERATOR COMPLETE")
    print(f"Total processed: {total_processed}")
    print(f"Total inserted: {total_inserted}")
    
    # Verify metrics
    verify_j_metrics()
    
    print(f"\n✅ J Generator execution finished at {datetime.now().isoformat()}")
    print("Next: Run pencil_dod_evaluate_county to verify Letter J improvements")

if __name__ == "__main__":
    main()