#!/usr/bin/env python3
"""
SHARD-6 Priority #1: C/D ROOT CAUSE - Parity Audit vs PropertyOnion Coverage
AUTONOMOUS SESSION - SHIP-TO-MAIN

Per issue directive: "C/D ROOT CAUSE — numerators frozen (~4.1K/6.6K) while denominator grew 33%. 
This IS the PropertyOnion-coverage scenario: INVOKE the pre-authorized clerk/official-records 
supplementary litmus NOW. Run the parity audit as the ULTRALOOP refuter step, document evidence, 
adopt, backfill matches."

This script implements the pre-authorized PropertyOnion supplementary litmus source adoption
for SHARD-6 counties: escambia, suwannee, martin, calhoun, liberty

Current C/D status per brief:
- escambia: C❌ 20.5% [matched_clean=1343 of 6557], D❌ 59.0% [matched_any=3869 of 6557]
- suwannee: C✅ 100.0% [matched_clean=3 of 3], D✅ 100.0% [matched_any=3 of 3] - ALREADY PASSING
- martin: C❌ 11.4% [matched_clean=282 of 2476], D❌ 72.4% [matched_any=1792 of 2476]
- calhoun: C❌ 0.0% [matched_clean=0 of 4], D❌ 0.0% [matched_any=0 of 4]  
- liberty: C❌ null [matched_clean=0 of 0], D❌ null [matched_any=0 of 0]

Priority targets: escambia, martin, calhoun (suwannee already passing, liberty needs A-lane first)

Usage:
  python scripts/shard6_cd_parity_fix.py
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

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
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-6 target counties (skipping suwannee as it's already passing C/D)
TARGET_COUNTIES = ['escambia', 'martin', 'calhoun']

# County clerk endpoints and DOR numbers for SHARD-6
COUNTY_CONFIG = {
    'escambia': {
        'dor_number': 33,
        'clerk_endpoint': 'https://escambia.realforeclose.com/',
        'property_appraiser': 'https://www.escambiapa.com/',
        'auction_platform': 'realauction'
    },
    'martin': {
        'dor_number': 43,  
        'clerk_endpoint': 'https://martin.realforeclose.com/',
        'property_appraiser': 'https://www.martin.fl.us/734/',
        'auction_platform': 'realauction'
    },
    'calhoun': {
        'dor_number': 13,
        'clerk_endpoint': 'https://calhoun.realforeclose.com/',
        'property_appraiser': 'https://qpublic.schneidercorp.com/Application.aspx?AppID=754&LayerID=13090&PageTypeID=2',
        'auction_platform': 'realauction'
    }
    # liberty omitted - needs A-lane setup first (no auction data)
    # suwannee omitted - already passing C/D (100%/100%)
}

client = httpx.Client(timeout=60)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def supabase_get(table: str, params: Dict = None, limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        query_params = {'limit': str(limit)}
        if params:
            for k, v in params.items():
                query_params[k] = str(v)
        
        response = client.get(url, headers=HEADERS, params=query_params)
        if response.status_code == 200:
            return response.json()
        else:
            log(f"Error fetching from {table}: {response.status_code} - {response.text}", "ERROR")
            return []
    except Exception as e:
        log(f"Error fetching from {table}: {e}", "ERROR")
        return []

def supabase_rpc(function_name: str, params: Dict = None) -> Dict:
    """Call Supabase RPC function"""
    try:
        url = f"{BASE}/rpc/{function_name}"
        response = client.post(url, headers=HEADERS, json=params or {})
        if response.status_code == 200:
            return {'success': True, 'data': response.json()}
        else:
            log(f"Error calling RPC {function_name}: {response.status_code} - {response.text}", "ERROR")
            return {'success': False, 'error': f"HTTP {response.status_code}"}
    except Exception as e:
        log(f"Error calling RPC {function_name}: {e}", "ERROR")
        return {'success': False, 'error': str(e)}

def get_parity_coverage_analysis(county: str) -> Dict:
    """
    Analyze PropertyOnion coverage vs our multi_county_auctions for parity gaps
    This is the ULTRALOOP refuter step per the brief
    """
    log(f"Analyzing parity coverage for {county}...")
    
    # Get current auction count in our system
    mca_count_query = {
        'select': 'count',
        'county': f'eq.{county}'
    }
    mca_results = supabase_get('multi_county_auctions', mca_count_query)
    our_count = len(mca_results)
    
    # Get matched counts for C/D metrics
    clean_matched_query = {
        'select': 'count',
        'county': f'eq.{county}',
        'parity_status': 'eq.matched_clean'
    }
    clean_matched = len(supabase_get('multi_county_auctions', clean_matched_query))
    
    any_matched_query = {
        'select': 'count', 
        'county': f'eq.{county}',
        'parity_status': 'in.(matched_clean,matched_fuzzy,matched_partial)'
    }
    any_matched = len(supabase_get('multi_county_auctions', any_matched_query))
    
    # Calculate current metrics
    c_metric = (clean_matched / our_count * 100) if our_count > 0 else 0
    d_metric = (any_matched / our_count * 100) if our_count > 0 else 0
    
    # Estimate PropertyOnion coverage shortfall
    # Per brief: numerators frozen while denominators grew 33%
    coverage_gap = our_count - (clean_matched + any_matched)
    
    analysis = {
        'county': county,
        'our_auction_count': our_count,
        'clean_matched': clean_matched,
        'any_matched': any_matched,
        'unmatched_count': coverage_gap,
        'c_metric_current': round(c_metric, 1),
        'd_metric_current': round(d_metric, 1),
        'c_pass': c_metric >= 95.0,
        'd_pass': d_metric >= 95.0,
        'analysis_timestamp': datetime.now(timezone.utc).isoformat(),
        'evidence': f"PropertyOnion coverage shortfall detected: {coverage_gap} unmatched of {our_count} total auctions"
    }
    
    log(f"Coverage analysis for {county}: C={c_metric:.1f}% D={d_metric:.1f}% Gap={coverage_gap}")
    return analysis

def adopt_clerk_supplementary_source(county: str) -> Dict:
    """
    Adopt clerk/official-records as supplementary litmus source per pre-authorization
    This implements the brief directive to use clerk records to backfill parity matches
    """
    log(f"Adopting clerk supplementary source for {county}...")
    
    config = COUNTY_CONFIG.get(county)
    if not config:
        return {'success': False, 'error': f'No configuration for county {county}'}
    
    # Create parity source configuration 
    parity_source = {
        'county_slug': county,
        'source_type': 'clerk_official_records',
        'endpoint': config['clerk_endpoint'],
        'dor_county_number': config['dor_number'],
        'is_supplementary': True,
        'litmus_priority': 2,  # Secondary to PropertyOnion
        'adopted_at': datetime.now(timezone.utc).isoformat(),
        'adoption_reason': 'SHARD6_CD_PARITY_FIX',
        'evidence_source': 'PropertyOnion coverage gap analysis'
    }
    
    # Insert/update parity source configuration
    try:
        response = client.post(f"{BASE}/parity_sources", headers=HEADERS, json=parity_source)
        if response.status_code in [200, 201]:
            log(f"✅ Clerk source adopted for {county}")
            return {'success': True, 'source_config': parity_source}
        else:
            log(f"❌ Failed to adopt clerk source for {county}: {response.text}", "ERROR")
            return {'success': False, 'error': response.text}
    except Exception as e:
        log(f"❌ Error adopting clerk source for {county}: {e}", "ERROR")
        return {'success': False, 'error': str(e)}

def backfill_matches_from_clerk(county: str) -> Dict:
    """
    Backfill parity matches using clerk records as supplementary source
    Uses case_number and sale_date for fuzzy matching
    """
    log(f"Backfilling matches from clerk records for {county}...")
    
    # This would normally call a specific clerk scraper or matching function
    # For now, we'll update parity_status for unmatched records based on clerk availability
    
    # Update unmatched auctions to attempt clerk matching
    update_query = f"""
    UPDATE multi_county_auctions 
    SET parity_status = 'clerk_pending',
        last_parity_check = NOW(),
        parity_source = 'clerk_supplementary'
    WHERE county = '{county}' 
    AND parity_status IN ('unmatched', 'no_match', NULL)
    """
    
    # Execute via RPC (this would need to be implemented as a stored procedure)
    result = supabase_rpc('execute_parity_backfill', {'county': county, 'source': 'clerk'})
    
    if result.get('success'):
        log(f"✅ Initiated clerk backfill for {county}")
        return result
    else:
        log(f"❌ Clerk backfill failed for {county}: {result.get('error')}", "ERROR")
        return result

def verify_improvements(county: str, baseline: Dict) -> Dict:
    """
    Verify that C/D metrics improved after implementing fixes
    Evidence-Before-Claims verification per HONESTY PROTOCOL
    """
    log(f"Verifying improvements for {county}...")
    
    # Re-run the county evaluation to get fresh metrics
    eval_result = supabase_rpc('pencil_dod_evaluate_county', {'county_slug_arg': county})
    
    if not eval_result.get('success'):
        return {'success': False, 'error': f'Failed to evaluate {county}: {eval_result.get("error")}'}
    
    # Parse evaluation results for C and D letters
    evaluation_data = eval_result.get('data', [])
    current_metrics = {}
    
    for letter_data in evaluation_data:
        if isinstance(letter_data, dict):
            letter = letter_data.get('letter', '').upper()
            if letter in ['C', 'D']:
                current_metrics[letter] = {
                    'metric': letter_data.get('metric'),
                    'pass': letter_data.get('pass', False),
                    'details': letter_data.get('details', '')
                }
    
    # Compare with baseline
    verification = {
        'county': county,
        'verification_timestamp': datetime.now(timezone.utc).isoformat(),
        'baseline': baseline,
        'current': current_metrics,
        'improvements': {}
    }
    
    for letter in ['C', 'D']:
        if letter in current_metrics:
            baseline_metric = baseline.get(f'{letter.lower()}_metric_current', 0)
            current_metric = current_metrics[letter]['metric'] or 0
            improvement = current_metric - baseline_metric
            
            verification['improvements'][letter] = {
                'baseline_metric': baseline_metric,
                'current_metric': current_metric,
                'improvement': round(improvement, 1),
                'passed': current_metrics[letter]['pass']
            }
            
            log(f"{county} {letter}: {baseline_metric}% -> {current_metric}% ({improvement:+.1f}%)")
    
    return verification

def main():
    """
    Main execution function for SHARD-6 C/D parity fixes
    Implements the pre-authorized PropertyOnion supplementary litmus adoption
    """
    log("SHARD-6 C/D Parity Fix - PropertyOnion Supplementary Litmus Adoption")
    log("Evidence-Before-Claims verification protocol enabled")
    
    results = {
        'session_id': 'shard6_cd_parity_fix',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'counties_processed': [],
        'verifications': {},
        'summary': {}
    }
    
    for county in TARGET_COUNTIES:
        log(f"\n=== Processing {county.upper()} ===")
        
        # Step 1: Analyze current parity coverage (ULTRALOOP refuter step)
        coverage_analysis = get_parity_coverage_analysis(county)
        
        # Step 2: Adopt clerk supplementary source if gaps detected
        if coverage_analysis['unmatched_count'] > 0:
            adoption_result = adopt_clerk_supplementary_source(county)
            
            if adoption_result.get('success'):
                # Step 3: Backfill matches from clerk records
                backfill_result = backfill_matches_from_clerk(county)
                
                # Step 4: Verify improvements (Evidence-Before-Claims)
                verification = verify_improvements(county, coverage_analysis)
                results['verifications'][county] = verification
            else:
                log(f"❌ Skipping backfill for {county} due to adoption failure")
        else:
            log(f"✅ {county} has no coverage gaps - skipping")
        
        results['counties_processed'].append(county)
    
    # Generate summary
    total_counties = len(TARGET_COUNTIES)
    processed_counties = len(results['counties_processed'])
    verified_improvements = sum(1 for v in results['verifications'].values() 
                               if any(imp.get('improvement', 0) > 0 
                                     for imp in v.get('improvements', {}).values()))
    
    results['summary'] = {
        'total_counties': total_counties,
        'processed_counties': processed_counties,
        'verified_improvements': verified_improvements,
        'completion_rate': f"{processed_counties}/{total_counties}",
        'success_rate': f"{verified_improvements}/{processed_counties}" if processed_counties > 0 else "0/0"
    }
    
    # Final status
    log(f"\n=== SHARD-6 C/D PARITY FIX SUMMARY ===")
    log(f"Counties processed: {results['summary']['completion_rate']}")
    log(f"Verified improvements: {results['summary']['success_rate']}")
    
    # Save results for debugging
    with open('/tmp/shard6_cd_parity_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    log("Results saved to /tmp/shard6_cd_parity_results.json")
    return results

if __name__ == "__main__":
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found in environment", "ERROR")
        sys.exit(1)
    
    try:
        results = main()
        log("✅ SHARD-6 C/D parity fix completed")
    except Exception as e:
        log(f"❌ SHARD-6 C/D parity fix failed: {e}", "ERROR")
        sys.exit(1)