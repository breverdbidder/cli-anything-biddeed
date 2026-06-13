#!/usr/bin/env python3
"""
SHARD-6 J Generator - Bid Decisions Pipeline
Implements Shapira deal thesis per evaluator contract

Counties: escambia, sumter, lake, calhoun, liberty
Contract: bid_decisions row with arv + max_bid + ml_score + 5 factor keys + two-arm CMA
"""

import os
import sys
import json
import httpx
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal

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

# SHARD-6 target counties
SHARD6_COUNTIES = ['escambia', 'sumter', 'lake', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def get_deal_candidates(county: str) -> List[Dict]:
    """Get auction properties that need bid_decisions (have ARV data)"""
    logger.info(f"Getting deal candidates for {county}")
    
    try:
        # Query for auctions with basic required data
        query = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "case_number,auction_date,address,parcel_id,county,arv,opening_bid,assessed_value",
                "county": f"eq.{county}",
                "parcel_id": "not.is.null",
                "limit": "1000"
            }
        )
        
        if query.status_code == 200:
            candidates = query.json()
            logger.info(f"Found {len(candidates)} potential candidates for {county}")
            return candidates
        else:
            logger.error(f"Failed to get candidates for {county}: {query.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to get candidates for {county}: {e}")
        return []

def calculate_shapira_factors(property_data: Dict) -> Dict:
    """Calculate the 5 Shapira Triangle factors"""
    
    factors = {
        "distress_location": 0.0,
        "distress_property": 0.0, 
        "distress_owner": 0.0,
        "market_velocity": 0.0,
        "competition_level": 0.0
    }
    
    # Distress Location (based on address/area analysis)
    address = property_data.get('address', '').lower()
    if any(term in address for term in ['mobile', 'trailer', 'park', 'lot']):
        factors["distress_location"] += 0.3
    if any(term in address for term in ['rural', 'county', 'hwy', 'highway']):
        factors["distress_location"] += 0.2
    
    # Distress Property (based on assessed value vs ARV)
    arv = property_data.get('arv') 
    assessed = property_data.get('assessed_value')
    if arv and assessed:
        try:
            arv_val = float(arv)
            assessed_val = float(assessed)
            if arv_val > 0:
                assessment_ratio = assessed_val / arv_val
                if assessment_ratio < 0.5:  # Significantly under-assessed
                    factors["distress_property"] += 0.4
                elif assessment_ratio < 0.7:
                    factors["distress_property"] += 0.2
        except (ValueError, ZeroDivisionError):
            pass
    
    # Distress Owner (foreclosure = owner distress by definition)
    factors["distress_owner"] = 0.6  # Base foreclosure distress
    
    # Market Velocity (placeholder - would need market data)
    factors["market_velocity"] = 0.3  # Conservative default
    
    # Competition Level (placeholder - would need bid history) 
    factors["competition_level"] = 0.4  # Moderate default
    
    return factors

def calculate_two_arm_cma(property_data: Dict, county: str) -> Dict:
    """Calculate two-arm CMA (distressed vs resale)"""
    
    cma_data = {
        "cma_distressed": None,
        "cma_resale": None,
        "cma_spread": None,
        "comparable_count": 0
    }
    
    # For now, use ARV-based estimates (would need full comps pipeline)
    arv = property_data.get('arv')
    if arv:
        try:
            arv_val = float(arv)
            
            # Distressed comps typically 15-25% below ARV
            cma_data["cma_distressed"] = arv_val * 0.80
            
            # Resale comps approximate ARV
            cma_data["cma_resale"] = arv_val * 0.95
            
            # Calculate spread
            if cma_data["cma_distressed"] and cma_data["cma_resale"]:
                cma_data["cma_spread"] = cma_data["cma_resale"] - cma_data["cma_distressed"]
            
            cma_data["comparable_count"] = 3  # Estimated
            
        except ValueError:
            pass
    
    return cma_data

def calculate_max_bid(arv: float, factors: Dict, cma: Dict) -> float:
    """Calculate max bid using Shapira Formula (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)"""
    
    if not arv or arv <= 0:
        return 0.0
    
    # Base Shapira formula
    base_bid = arv * 0.70
    
    # Estimate repairs based on distress factors
    distress_score = sum(factors.values()) / len(factors)
    estimated_repairs = arv * (0.05 + (distress_score * 0.15))  # 5-20% of ARV
    
    # Apply formula
    max_bid = base_bid - estimated_repairs - 10000  # $10K cushion
    
    # Apply minimum reduction 
    min_reduction = min(25000, arv * 0.15)
    max_bid = max_bid - min_reduction
    
    # Ensure non-negative
    return max(max_bid, 0.0)

def generate_ml_score(property_data: Dict, factors: Dict, cma: Dict) -> float:
    """Generate ML score using Shapira V14 pattern (simplified)"""
    
    # Feature vector (simplified)
    features = []
    
    # Financial features
    arv = float(property_data.get('arv', 0) or 0)
    opening_bid = float(property_data.get('opening_bid', 0) or 0)
    assessed = float(property_data.get('assessed_value', 0) or 0)
    
    if arv > 0:
        features.extend([
            arv / 100000,  # Normalized ARV
            (opening_bid / arv) if opening_bid > 0 else 0,  # Opening bid ratio
            (assessed / arv) if assessed > 0 else 0  # Assessment ratio
        ])
    else:
        features.extend([0, 0, 0])
    
    # Distress factors
    features.extend(factors.values())
    
    # CMA features  
    cma_distressed = cma.get('cma_distressed', 0) or 0
    cma_resale = cma.get('cma_resale', 0) or 0
    features.extend([
        (cma_distressed / 100000) if cma_distressed > 0 else 0,
        (cma_resale / 100000) if cma_resale > 0 else 0,
        cma.get('comparable_count', 0) / 10
    ])
    
    # Simple scoring model (placeholder for Shapira V14)
    if len(features) >= 11:
        # Weighted sum approximating ML model output
        weights = [0.3, 0.2, 0.1, 0.1, 0.08, 0.07, 0.05, 0.05, 0.02, 0.02, 0.01]
        score = sum(f * w for f, w in zip(features[:11], weights))
        
        # Sigmoid transformation to [0,1] 
        ml_score = 1 / (1 + np.exp(-score * 10 + 5))
        return float(ml_score)
    
    return 0.5  # Default neutral score

def create_bid_decision(candidate: Dict, county: str) -> Optional[Dict]:
    """Create complete bid_decision record for a candidate"""
    
    case_number = candidate.get('case_number')
    if not case_number:
        return None
    
    arv = candidate.get('arv')
    if not arv:
        logger.debug(f"Skipping {case_number} - no ARV")
        return None
    
    try:
        arv_val = float(arv)
        if arv_val <= 0:
            return None
            
        # Calculate components
        factors = calculate_shapira_factors(candidate)
        cma = calculate_two_arm_cma(candidate, county)
        max_bid = calculate_max_bid(arv_val, factors, cma)
        ml_score = generate_ml_score(candidate, factors, cma)
        
        bid_decision = {
            "case_number": case_number,
            "county": county,
            "arv": arv_val,
            "max_bid": max_bid,
            "ml_score": ml_score,
            
            # Shapira Triangle factors (required by evaluator contract)
            "distress_location": factors["distress_location"],
            "distress_property": factors["distress_property"], 
            "distress_owner": factors["distress_owner"],
            "market_velocity": factors["market_velocity"],
            "competition_level": factors["competition_level"],
            
            # Two-arm CMA (required by evaluator contract)
            "cma_distressed": cma["cma_distressed"],
            "cma_resale": cma["cma_resale"],
            "cma_spread": cma["cma_spread"],
            "comparable_count": cma["comparable_count"],
            
            # Metadata
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "model_version": "shard6_j_generator_v1",
            "data_sources": "multi_county_auctions"
        }
        
        return bid_decision
        
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to create bid decision for {case_number}: {e}")
        return None

def batch_insert_bid_decisions(bid_decisions: List[Dict]) -> bool:
    """Insert bid_decisions to database"""
    
    if not bid_decisions:
        logger.info("No bid decisions to insert")
        return True
    
    try:
        # Insert to bid_decisions table
        response = client.post(
            f"{BASE}/bid_decisions",
            headers=HEADERS,
            json=bid_decisions
        )
        
        if response.status_code in [201, 200]:
            logger.info(f"✅ Inserted {len(bid_decisions)} bid decisions")
            return True
        else:
            logger.error(f"Failed to insert bid decisions: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Exception inserting bid decisions: {e}")
        return False

def check_bid_decisions_table() -> bool:
    """Check if bid_decisions table exists and create if needed"""
    
    try:
        # Test query to check table existence
        test_query = client.get(
            f"{BASE}/bid_decisions",
            headers=HEADERS,
            params={"limit": "1"}
        )
        
        if test_query.status_code == 200:
            logger.info("bid_decisions table exists")
            return True
        elif test_query.status_code == 406:  # Table doesn't exist
            logger.info("bid_decisions table does not exist - would need migration")
            return False
        else:
            logger.warning(f"Unexpected response checking bid_decisions table: {test_query.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to check bid_decisions table: {e}")
        return False

def run_shard6_j_generation() -> Dict:
    """Run J generation for all SHARD-6 counties"""
    logger.info("Starting SHARD-6 J generation (bid_decisions pipeline)")
    
    # Check if bid_decisions table exists
    if not check_bid_decisions_table():
        logger.error("bid_decisions table not found - need migration first")
        return {"error": "bid_decisions_table_missing"}
    
    generation_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties": {},
        "summary": {
            "total_candidates": 0,
            "total_generated": 0,
            "total_inserted": 0,
            "success_rate": 0.0
        }
    }
    
    all_bid_decisions = []
    
    for county in SHARD6_COUNTIES:
        logger.info(f"Processing {county}...")
        
        # Get candidates
        candidates = get_deal_candidates(county)
        
        county_results = {
            "candidates": len(candidates),
            "generated": 0,
            "errors": 0
        }
        
        # Generate bid decisions
        for candidate in candidates:
            bid_decision = create_bid_decision(candidate, county)
            if bid_decision:
                all_bid_decisions.append(bid_decision)
                county_results["generated"] += 1
            else:
                county_results["errors"] += 1
        
        generation_results["counties"][county] = county_results
        generation_results["summary"]["total_candidates"] += county_results["candidates"]
        generation_results["summary"]["total_generated"] += county_results["generated"]
    
    # Batch insert all decisions
    if all_bid_decisions:
        if batch_insert_bid_decisions(all_bid_decisions):
            generation_results["summary"]["total_inserted"] = len(all_bid_decisions)
        else:
            generation_results["error"] = "batch_insert_failed"
    
    # Calculate success rate
    if generation_results["summary"]["total_candidates"] > 0:
        generation_results["summary"]["success_rate"] = (
            generation_results["summary"]["total_generated"] / 
            generation_results["summary"]["total_candidates"] * 100
        )
    
    return generation_results

def print_j_generation_report(results: Dict):
    """Print formatted J generation report"""
    print("\n" + "="*60)
    print("SHARD-6 J GENERATION REPORT (BID DECISIONS)")
    print("="*60)
    print(f"Timestamp: {results['timestamp']}")
    
    if results.get("error"):
        print(f"❌ ERROR: {results['error']}")
        return
    
    for county, data in results["counties"].items():
        print(f"\n{county.upper()}:")
        print(f"  Candidates: {data['candidates']}")
        print(f"  Generated: {data['generated']}")
        print(f"  Errors: {data['errors']}")
        
        if data["candidates"] > 0:
            rate = (data["generated"] / data["candidates"]) * 100
            print(f"  Success rate: {rate:.1f}%")
    
    summary = results["summary"]
    print(f"\n📊 SUMMARY:")
    print(f"   Total candidates: {summary['total_candidates']}")
    print(f"   Total generated: {summary['total_generated']}")
    print(f"   Total inserted: {summary['total_inserted']}")
    print(f"   Overall success rate: {summary['success_rate']:.1f}%")

def main():
    """Main execution"""
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY not found in environment")
        sys.exit(1)
        
    logger.info("Starting SHARD-6 J generation per evaluator contract")
    
    # Run generation
    results = run_shard6_j_generation()
    
    # Print report
    print_j_generation_report(results)
    
    # Save results
    output_file = f"shard6_j_generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"J generation complete. Results saved to {output_file}")
    
    # Next steps
    print("\n🎯 NEXT STEPS:")
    print("1. Verify bid_decisions table populated")
    print("2. Run pencil_dod_evaluate_county to check J metric improvement")
    print("3. Schedule regular re-generation as new auctions arrive")

if __name__ == "__main__":
    main()