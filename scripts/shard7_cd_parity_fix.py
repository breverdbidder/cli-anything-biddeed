#!/usr/bin/env python3
"""
SHARD-7 C/D Parity Fix - Marion & Collier Counties
Fix failing C/D criteria (≥95% parity matching)

Current status from issue:
- marion: C=9.6% [matched_clean=628 of 6512], D=55.1% [matched_any=3588 of 6512]
- collier: C=17.3% [matched_clean=289 of 1670], D=59.2% [matched_any=988 of 1670]

C criterion: parity_status = 'matched_clean' ≥95%
D criterion: parity_status IN ('matched_clean', 'matched_divergent') ≥95%

From issue brief: "PRE-AUTHORIZED to adopt clerk/official-records as supplementary 
litmus source" when PropertyOnion coverage is the root cause.
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
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Target counties with C/D failures
PARITY_FIX_COUNTIES = {
    'marion': {
        'c_metric': 9.6,   # matched_clean %
        'd_metric': 55.1,  # matched_any %
        'matched_clean': 628,
        'matched_any': 3588,
        'total_auctions': 6512,
        'clerk_url': 'https://www.marioncountyclerk.org',
        'co_no': 52
    },
    'collier': {
        'c_metric': 17.3,
        'd_metric': 59.2, 
        'matched_clean': 289,
        'matched_any': 988,
        'total_auctions': 1670,
        'clerk_url': 'https://www.collierclerk.com',
        'co_no': 21
    }
}

client = httpx.AsyncClient(timeout=60)

async def analyze_parity_gap(county: str) -> Dict:
    """Analyze the parity gap and identify root causes"""
    logger.info(f"Analyzing parity gap for {county}...")
    
    try:
        # Get sample of unmatched auctions
        response = await client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "parity_status": "is.null",  # Unmatched auctions
                "select": "case_number,auction_date,property_address,defendant,plaintiff,auction_status",
                "order": "auction_date.desc",
                "limit": "50"
            }
        )
        
        unmatched_sample = []
        if response.status_code == 200:
            unmatched_sample = response.json()
        
        # Get sample of matched auctions for comparison
        response = await client.get(
            f"{BASE}/multi_county_auctions", 
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "parity_status": f"in.(matched_clean,matched_divergent)",
                "select": "case_number,auction_date,property_address,parity_status",
                "order": "auction_date.desc", 
                "limit": "20"
            }
        )
        
        matched_sample = []
        if response.status_code == 200:
            matched_sample = response.json()
        
        # Get parity status distribution
        response = await client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "select": "parity_status",
                "limit": "1000"  # Sample for distribution
            }
        )
        
        parity_distribution = {}
        if response.status_code == 200:
            data = response.json()
            for item in data:
                status = item.get('parity_status') or 'null'
                parity_distribution[status] = parity_distribution.get(status, 0) + 1
        
        return {
            'county': county,
            'unmatched_count': len(unmatched_sample),
            'matched_count': len(matched_sample), 
            'unmatched_sample': unmatched_sample[:10],  # First 10 for review
            'matched_sample': matched_sample[:10],
            'parity_distribution': parity_distribution,
            'root_cause_hypotheses': [
                'PropertyOnion coverage gap (missing cases)',
                'Case number format mismatch', 
                'Date range mismatch between sources',
                'Auction status canonicalization differences',
                'Missing supplementary clerk data source'
            ]
        }
        
    except Exception as e:
        logger.error(f"Error analyzing parity gap for {county}: {e}")
        return {'county': county, 'error': str(e)}

async def apply_parity_fixes(county: str, analysis: Dict) -> Dict:
    """Apply parity fixes based on gap analysis"""
    logger.info(f"Applying parity fixes for {county}...")
    
    fixes_applied = []
    errors = []
    
    try:
        # Fix 1: Update null parity_status to 'unmatched' for clear tracking
        null_count = analysis.get('parity_distribution', {}).get('null', 0)
        if null_count > 0:
            logger.info(f"Updating {null_count} null parity_status records to 'unmatched'")
            
            response = await client.patch(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={"county": f"eq.{county}", "parity_status": "is.null"},
                json={"parity_status": "unmatched", "updated_at": datetime.now(timezone.utc).isoformat()}
            )
            
            if response.status_code == 200:
                fixes_applied.append(f"Updated {null_count} null parity_status → 'unmatched'")
            else:
                errors.append(f"Failed to update null parity_status: {response.status_code}")
        
        # Fix 2: Case number normalization for better matching
        unmatched_sample = analysis.get('unmatched_sample', [])
        case_number_fixes = 0
        
        for auction in unmatched_sample[:20]:  # Process sample
            case_number = auction.get('case_number', '')
            if case_number and '-' not in case_number and len(case_number) > 6:
                # Try adding common format separators
                year_part = case_number[:4] if case_number[:4].isdigit() else case_number[-4:]
                if year_part in ['2023', '2024', '2025', '2026']:
                    # Attempt format normalization
                    normalized_case = f"{year_part}-{case_number.replace(year_part, '')}"
                    
                    # Update the record
                    response = await client.patch(
                        f"{BASE}/multi_county_auctions",
                        headers=HEADERS,
                        params={
                            "county": f"eq.{county}",
                            "case_number": f"eq.{case_number}"
                        },
                        json={
                            "case_number_normalized": normalized_case,
                            "parity_status": "needs_rematch",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    
                    if response.status_code == 200:
                        case_number_fixes += 1
        
        if case_number_fixes > 0:
            fixes_applied.append(f"Normalized {case_number_fixes} case numbers for rematching")
        
        # Fix 3: Clerk records supplementary source (PRE-AUTHORIZED per issue brief)
        config = PARITY_FIX_COUNTIES.get(county)
        if config:
            logger.info(f"Implementing clerk records as supplementary litmus source for {county}")
            
            # Mark cases for clerk supplementary matching
            response = await client.patch(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={
                    "county": f"eq.{county}",
                    "parity_status": f"eq.unmatched"
                },
                json={
                    "supplementary_source": "clerk_records",
                    "needs_clerk_verification": True,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
            if response.status_code == 200:
                fixes_applied.append(f"Marked unmatched cases for clerk supplementary verification")
        
        return {
            'county': county,
            'fixes_applied': fixes_applied,
            'errors': errors,
            'case_number_fixes': case_number_fixes,
            'null_status_fixes': null_count if null_count > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error applying parity fixes for {county}: {e}")
        return {
            'county': county,
            'fixes_applied': fixes_applied,
            'errors': errors + [str(e)]
        }

async def verify_parity_improvement(county: str) -> Dict:
    """Verify C/D criterion improvement after fixes"""
    try:
        # Use the evaluation function to get fresh metrics
        payload = {"county_slug_arg": county}
        response = await client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            metrics = {}
            
            for item in results:
                letter = item.get('letter')
                if letter in ['C', 'D']:
                    metrics[letter] = {
                        'metric': item.get('metric'),
                        'pass': item.get('pass'),
                        'threshold': 95.0
                    }
            
            return {
                'county': county,
                'verification_successful': True,
                'c_metric': metrics.get('C', {}).get('metric'),
                'c_pass': metrics.get('C', {}).get('pass'),
                'd_metric': metrics.get('D', {}).get('metric'), 
                'd_pass': metrics.get('D', {}).get('pass')
            }
        
        logger.warning(f"Could not verify improvements for {county}")
        return {'county': county, 'verification_successful': False}
        
    except Exception as e:
        logger.error(f"Error verifying improvements for {county}: {e}")
        return {'county': county, 'verification_successful': False, 'error': str(e)}

async def fix_county_parity(county: str) -> Dict:
    """Complete parity fix for a county"""
    logger.info(f"\n{'='*50}")
    logger.info(f"C/D PARITY FIX: {county.upper()}")
    logger.info("="*50)
    
    config = PARITY_FIX_COUNTIES.get(county)
    if not config:
        return {'county': county, 'error': 'County not in parity fix targets'}
    
    logger.info(f"Current C/D metrics: C={config['c_metric']}%, D={config['d_metric']}%")
    logger.info(f"Target: C≥95%, D≥95%")
    
    # Step 1: Analyze the parity gap
    analysis = await analyze_parity_gap(county)
    
    # Step 2: Apply fixes
    fix_results = await apply_parity_fixes(county, analysis)
    
    # Step 3: Verify improvement
    verification = await verify_parity_improvement(county)
    
    result = {
        'county': county,
        'before_c_metric': config['c_metric'],
        'before_d_metric': config['d_metric'],
        'after_c_metric': verification.get('c_metric'),
        'after_d_metric': verification.get('d_metric'),
        'c_improved': verification.get('c_pass', False),
        'd_improved': verification.get('d_pass', False),
        'gap_analysis': analysis,
        'fixes_applied': fix_results.get('fixes_applied', []),
        'improvement_summary': {
            'c_points_gained': (verification.get('c_metric', 0) - config['c_metric']),
            'd_points_gained': (verification.get('d_metric', 0) - config['d_metric']),
            'fixes_count': len(fix_results.get('fixes_applied', []))
        }
    }
    
    return result

async def run_shard7_parity_fixes():
    """Run C/D parity fixes for SHARD-7 counties"""
    logger.info("Starting SHARD-7 C/D parity fixes for marion & collier...")
    
    target_counties = ['marion', 'collier']
    all_results = {}
    
    for county in target_counties:
        results = await fix_county_parity(county)
        all_results[county] = results
        
        # Print summary
        print(f"\n{county.upper()} C/D Parity Fix Results:")
        print(f"  📊 Before C: {results.get('before_c_metric')}% → After C: {results.get('after_c_metric')}%")
        print(f"  📊 Before D: {results.get('before_d_metric')}% → After D: {results.get('after_d_metric')}%")
        print(f"  ✅ C criterion now passes: {results.get('c_improved')}")
        print(f"  ✅ D criterion now passes: {results.get('d_improved')}")
        print(f"  🔧 Fixes applied: {len(results.get('fixes_applied', []))}")
        
        for fix in results.get('fixes_applied', []):
            print(f"    • {fix}")
        
        # Additional recommendations
        if not (results.get('c_improved') and results.get('d_improved')):
            print(f"  📋 Additional steps needed:")
            print(f"    • Implement clerk records scraping for supplementary matching")
            print(f"    • Review PropertyOnion coverage gaps")
            print(f"    • Consider alternative parity sources")
    
    return all_results

def main():
    """Main function"""
    logger.info("SHARD-7 C/D Parity Fix (Marion & Collier)")
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in PARITY_FIX_COUNTIES:
            result = asyncio.run(fix_county_parity(county))
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Error: County '{county}' not in SHARD-7 parity fix targets")
            print(f"Available counties: {list(PARITY_FIX_COUNTIES.keys())}")
    else:
        # Process all SHARD-7 parity targets
        results = asyncio.run(run_shard7_parity_fixes())
        print(f"\nSHARD-7 C/D Parity Fix Campaign Complete!")
        
        # Summary
        total_c_pass = sum(1 for r in results.values() if r.get('c_improved'))
        total_d_pass = sum(1 for r in results.values() if r.get('d_improved'))
        print(f"Counties with C criterion passing: {total_c_pass}/2")
        print(f"Counties with D criterion passing: {total_d_pass}/2")
        
        # JSON output for verification
        print("\nDetailed Results:")
        print(json.dumps(results, indent=2, default=str))

if __name__ == "__main__":
    main()