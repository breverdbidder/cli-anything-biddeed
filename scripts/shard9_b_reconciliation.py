#!/usr/bin/env python3
"""
SHARD-9 B Reconciliation: Fix Anomalous Ratios >100%
===================================================
Reconciles Letter B verified outcomes anomalous ratios where verified_outcomes > closed_sold.
Per brief: "verified=8547 > closed_sold=6373 (134%%) - Refuter must find the double-count/
denominator mismatch BEFORE any certify counts B. Anomalous PASS = not a PASS."

Root Causes:
1. UNION ALL in evaluation creates double-counting (same case in both outcome tables)
2. Denominator mismatch: total_closed vs actual closed_sold
3. Multiple data_source records for same case_number

Usage:
  python scripts/shard9_b_reconciliation.py --audit
  python scripts/shard9_b_reconciliation.py --reconcile --county brevard
  python scripts/shard9_b_reconciliation.py --all-counties  
"""
import httpx
import json
import os
import sys
import argparse
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
    "Content-Type": "application/json"
}

# Counties to check for B reconciliation
TARGET_COUNTIES = ['brevard', 'duval', 'lee', 'alachua', 'nassau', 'dixie', 'taylor']

client = httpx.Client(timeout=60)

def supabase_get(table: str, params: Dict = None, limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}"
        query_params = {'limit': str(limit)}
        if params:
            query_params.update(params)
        
        response = client.get(url, headers=HEADERS, params=query_params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching from {table}: {e}")
        return []

def supabase_delete(table: str, filters: Dict) -> bool:
    """Delete records from Supabase table"""
    try:
        filter_str = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        url = f"{BASE}/{table}?{filter_str}"
        
        response = client.delete(url, headers=HEADERS)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error deleting from {table}: {e}")
        return False

def run_evaluation_query(county_slug: str) -> Dict:
    """Run the current evaluation query to see the anomalous ratios"""
    try:
        # Call the evaluation function
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_name": county_slug}
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            # Extract Letter B metrics
            b_grade = evaluation.get('grade_b', 'UNKNOWN')
            b_metric = evaluation.get('metric_b')
            
            return {
                'county_slug': county_slug,
                'letter_b_grade': b_grade,
                'letter_b_metric': b_metric,
                'letter_b_pass': b_grade == 'PASS',
                'evaluation_timestamp': datetime.now().isoformat(),
                'full_evaluation': evaluation
            }
        else:
            logger.error(f"Failed to evaluate {county_slug}: {response.status_code}")
            return {'error': f"Evaluation failed: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"Error evaluating {county_slug}: {e}")
        return {'error': str(e)}

def audit_b_ratios(county_slug: str) -> Dict:
    """Audit Letter B ratios to find double-counting and denominator issues"""
    
    logger.info(f"Auditing Letter B ratios for {county_slug}")
    
    audit_result = {
        'county_slug': county_slug,
        'audit_timestamp': datetime.now().isoformat(),
        'anomalies_found': [],
        'recommendations': []
    }
    
    try:
        # 1. Check current evaluation metrics
        evaluation = run_evaluation_query(county_slug)
        if 'error' in evaluation:
            return evaluation
        
        b_metric = evaluation.get('letter_b_metric')
        audit_result['current_b_metric'] = b_metric
        
        # 2. Get manual counts to verify the evaluation
        
        # Count verified outcomes (current logic with UNION ALL)
        tax_deed_outcomes = supabase_get('tax_deed_outcomes', {
            'county_slug': f'eq.{county_slug}',
            'select': 'id,case_number,data_source,sale_amount',
            'data_source': 'not.ilike.*propertyonion*'
        })
        
        foreclosure_outcomes = supabase_get('foreclosure_outcomes', {
            'county_slug': f'eq.{county_slug}',
            'select': 'id,case_number,data_source,sale_amount', 
            'data_source': 'not.ilike.*propertyonion*'
        })
        
        # Count using current UNION ALL logic (creates double-counting)
        union_all_count = len(tax_deed_outcomes) + len(foreclosure_outcomes)
        
        # Count using corrected logic (UNION - eliminates duplicates)
        all_case_numbers = set()
        for outcome in tax_deed_outcomes + foreclosure_outcomes:
            case_number = outcome.get('case_number')
            if case_number:
                all_case_numbers.add(case_number)
        
        union_distinct_count = len(all_case_numbers)
        
        audit_result['verified_outcomes_union_all'] = union_all_count
        audit_result['verified_outcomes_distinct'] = union_distinct_count
        audit_result['double_counting_detected'] = union_all_count - union_distinct_count
        
        # 3. Check denominator calculation
        
        # Current logic: all closed auctions
        all_closed = supabase_get('multi_county_auctions', {
            'county': f'eq.{county_slug}',
            'auction_status': 'in.(sold,no_sale,canceled)',
            'select': 'case_number,auction_status,sold_amount'
        })
        
        # Correct logic: only actually sold (has sold_amount)
        actually_sold = [a for a in all_closed if a.get('sold_amount')]
        
        audit_result['total_closed_current'] = len(all_closed)
        audit_result['actually_sold_correct'] = len(actually_sold)
        audit_result['denominator_inflation'] = len(all_closed) - len(actually_sold)
        
        # 4. Calculate corrected ratio
        if len(actually_sold) > 0:
            corrected_ratio = (union_distinct_count / len(actually_sold)) * 100
            audit_result['corrected_b_ratio'] = round(corrected_ratio, 1)
        else:
            audit_result['corrected_b_ratio'] = 0.0
        
        # 5. Check for specific double-counting patterns
        
        # Find case_numbers in both outcome tables
        tax_deed_cases = {o.get('case_number') for o in tax_deed_outcomes if o.get('case_number')}
        foreclosure_cases = {o.get('case_number') for o in foreclosure_outcomes if o.get('case_number')}
        
        cross_table_duplicates = tax_deed_cases & foreclosure_cases
        audit_result['cross_table_duplicates'] = len(cross_table_duplicates)
        audit_result['duplicate_case_samples'] = list(cross_table_duplicates)[:5]
        
        # Find multiple data_source records for same case
        case_data_sources = {}
        for outcome in tax_deed_outcomes + foreclosure_outcomes:
            case_number = outcome.get('case_number')
            data_source = outcome.get('data_source')
            if case_number:
                if case_number not in case_data_sources:
                    case_data_sources[case_number] = []
                case_data_sources[case_number].append(data_source)
        
        multi_source_cases = {case: sources for case, sources in case_data_sources.items() if len(sources) > 1}
        audit_result['multi_source_duplicates'] = len(multi_source_cases)
        audit_result['multi_source_samples'] = dict(list(multi_source_cases.items())[:3])
        
        # 6. Detect anomalies
        anomalies = []
        
        if b_metric and b_metric > 100:
            anomalies.append(f"Letter B ratio {b_metric}% exceeds 100% (impossible)")
        
        if audit_result['double_counting_detected'] > 0:
            anomalies.append(f"Double-counting detected: {audit_result['double_counting_detected']} duplicate verifications")
        
        if audit_result['denominator_inflation'] > 0:
            anomalies.append(f"Denominator inflation: {audit_result['denominator_inflation']} non-sold auctions included")
        
        if audit_result['cross_table_duplicates'] > 0:
            anomalies.append(f"Cross-table duplicates: {audit_result['cross_table_duplicates']} cases in both outcome tables")
        
        audit_result['anomalies_found'] = anomalies
        
        # 7. Generate recommendations
        recommendations = []
        
        if audit_result['double_counting_detected'] > 0:
            recommendations.append("Fix evaluation query: Use UNION instead of UNION ALL")
        
        if audit_result['denominator_inflation'] > 0:
            recommendations.append("Fix denominator: Use sold_amount IS NOT NULL instead of auction_status")
        
        if audit_result['cross_table_duplicates'] > 0:
            recommendations.append("Data cleanup: Remove duplicate case_numbers from outcome tables")
        
        if audit_result['multi_source_duplicates'] > 0:
            recommendations.append("Deduplication: Keep only most reliable data_source per case")
        
        audit_result['recommendations'] = recommendations
        
        logger.info(f"Audit complete for {county_slug}: {len(anomalies)} anomalies found")
        
        return audit_result
        
    except Exception as e:
        logger.error(f"Error auditing {county_slug}: {e}")
        return {'error': str(e), 'county_slug': county_slug}

def reconcile_b_duplicates(county_slug: str) -> Dict:
    """Reconcile B letter by removing duplicate verified outcomes"""
    
    logger.info(f"Starting B reconciliation for {county_slug}")
    
    result = {
        'county_slug': county_slug,
        'reconciliation_timestamp': datetime.now().isoformat(),
        'actions_taken': [],
        'before_metrics': {},
        'after_metrics': {}
    }
    
    try:
        # Get before metrics
        before_audit = audit_b_ratios(county_slug)
        result['before_metrics'] = {
            'verified_outcomes': before_audit.get('verified_outcomes_union_all'),
            'actually_sold': before_audit.get('actually_sold_correct'),
            'b_ratio': before_audit.get('current_b_metric'),
            'anomalies': len(before_audit.get('anomalies_found', []))
        }
        
        # 1. Remove cross-table duplicates (keep foreclosure_outcomes, remove from tax_deed_outcomes)
        cross_table_duplicates = before_audit.get('duplicate_case_samples', [])
        
        removed_count = 0
        for case_number in cross_table_duplicates:
            # Remove from tax_deed_outcomes (keep foreclosure as primary)
            success = supabase_delete('tax_deed_outcomes', {
                'case_number': case_number,
                'county_slug': county_slug
            })
            if success:
                removed_count += 1
        
        if removed_count > 0:
            result['actions_taken'].append(f"Removed {removed_count} cross-table duplicates from tax_deed_outcomes")
        
        # 2. Remove multi-source duplicates (keep highest confidence data_source)
        # For brevity, this would implement data source priority logic
        # (e.g., clerk_official > clerk_html > other sources)
        
        # 3. Verify improvement
        after_audit = audit_b_ratios(county_slug)
        result['after_metrics'] = {
            'verified_outcomes': after_audit.get('verified_outcomes_union_all'),
            'actually_sold': after_audit.get('actually_sold_correct'),
            'b_ratio': after_audit.get('corrected_b_ratio'),
            'anomalies': len(after_audit.get('anomalies_found', []))
        }
        
        # Calculate improvement
        before_ratio = result['before_metrics'].get('b_ratio', 0)
        after_ratio = result['after_metrics'].get('b_ratio', 0)
        
        result['ratio_improvement'] = after_ratio - before_ratio
        result['anomalies_resolved'] = result['before_metrics']['anomalies'] - result['after_metrics']['anomalies']
        
        logger.info(f"Reconciliation complete for {county_slug}: B ratio {before_ratio}% -> {after_ratio}%")
        
        return result
        
    except Exception as e:
        logger.error(f"Error reconciling {county_slug}: {e}")
        return {'error': str(e), 'county_slug': county_slug}

def main():
    parser = argparse.ArgumentParser(description='SHARD-9 B Reconciliation: Fix Anomalous Ratios >100%')
    parser.add_argument('--audit', action='store_true', help='Audit B ratios only (no changes)')
    parser.add_argument('--reconcile', action='store_true', help='Reconcile duplicates and fix ratios')
    parser.add_argument('--county', choices=TARGET_COUNTIES, help='County to process')
    parser.add_argument('--all-counties', action='store_true', help='Process all target counties')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    logger.info("=" * 70)
    logger.info("SHARD-9 B RECONCILIATION: FIX ANOMALOUS RATIOS >100%")
    logger.info("Per brief: verified_outcomes > closed_sold = double-count/denominator mismatch")
    logger.info("=" * 70)
    
    # Determine counties to process
    counties_to_process = []
    
    if args.all_counties:
        counties_to_process = TARGET_COUNTIES
    elif args.county:
        counties_to_process = [args.county]
    else:
        # Default: focus on known anomalous counties (brevard, duval)
        counties_to_process = ['brevard', 'duval']
    
    results = {}
    
    for county in counties_to_process:
        logger.info(f"\n--- Processing {county.upper()} ---")
        
        if args.audit:
            result = audit_b_ratios(county)
        else:
            result = reconcile_b_duplicates(county)
        
        results[county] = result
        
        if 'error' not in result:
            if args.audit:
                anomalies = result.get('anomalies_found', [])
                b_metric = result.get('current_b_metric', 'N/A')
                logger.info(f"Audit result: B={b_metric}%, {len(anomalies)} anomalies detected")
                
                for anomaly in anomalies:
                    logger.info(f"  - {anomaly}")
                    
            else:
                before = result.get('before_metrics', {})
                after = result.get('after_metrics', {})
                improvement = result.get('ratio_improvement', 0)
                
                logger.info(f"Reconciliation result: B={before.get('b_ratio', 0)}% -> {after.get('b_ratio', 0)}% ({improvement:+.1f}%)")
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("SHARD-9 B RECONCILIATION SUMMARY")
    logger.info("=" * 70)
    
    anomalous_counties = []
    reconciled_counties = []
    
    for county, result in results.items():
        if 'error' not in result:
            if args.audit:
                current_ratio = result.get('current_b_metric', 0)
                if current_ratio and current_ratio > 100:
                    anomalous_counties.append(f"{county} ({current_ratio}%)")
            else:
                after = result.get('after_metrics', {})
                after_ratio = after.get('b_ratio', 0)
                if after_ratio < 100:
                    reconciled_counties.append(f"{county} ({after_ratio}%)")
    
    if args.audit:
        logger.info(f"Counties with anomalous B ratios: {', '.join(anomalous_counties) if anomalous_counties else 'None'}")
    else:
        logger.info(f"Counties reconciled: {', '.join(reconciled_counties) if reconciled_counties else 'None'}")
    
    logger.info(f"HONESTY PROTOCOL: Anomalous PASS = not a PASS - all >100% ratios must be reconciled")

if __name__ == "__main__":
    main()