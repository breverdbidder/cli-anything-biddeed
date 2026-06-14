#!/usr/bin/env python3
"""
SHARD24 Verification Runner: Execute database operations for brevard+duval improvements
This script applies the SQL fixes prepared by shard24_brevard_duval_coordinator.py

USAGE:
  python scripts/shard24_verification_runner.py --execute-all
  python scripts/shard24_verification_runner.py --county brevard --phase C_D_ROOT_CAUSE
  python scripts/shard24_verification_runner.py --verify-only
"""
import os
import sys
import argparse
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Any

# Import the coordinator functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from shard24_brevard_duval_coordinator import (
    brevard_c_d_root_cause,
    brevard_j_generator, 
    brevard_g_hit_list,
    brevard_b_reconciliation,
    duval_g_i_substrate_build,
    evaluate_county_live,
    sb_headers,
    log_action,
    SHARD_COUNTIES,
    SUPABASE_URL
)

client = httpx.Client(timeout=300, headers={"User-Agent": "SHARD24-VerificationRunner"})

def execute_sql(sql: str, description: str) -> Dict:
    """Execute SQL against Supabase and return result"""
    log_action(f"Executing: {description}", "INFO", "UNTESTED")
    
    try:
        headers = sb_headers()
        
        # For complex SQL, use the SQL editor endpoint
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
            headers=headers,
            json={"sql_query": sql}
        )
        
        if response.status_code == 200:
            result = response.json()
            log_action(f"✅ {description} completed successfully", "INFO", "VERIFIED")
            return {"success": True, "result": result, "description": description}
        else:
            log_action(f"❌ {description} failed: {response.status_code} {response.text[:200]}", "ERROR", "VERIFIED")
            return {"success": False, "error": response.text, "description": description}
            
    except Exception as e:
        log_action(f"❌ {description} error: {e}", "ERROR", "VERIFIED")
        return {"success": False, "error": str(e), "description": description}

def execute_phase_fixes(county: str, phase: str) -> List[Dict]:
    """Execute all fixes for a specific county/phase"""
    log_action(f"Executing {county} {phase} fixes...", "INFO", "UNTESTED")
    
    # Get fixes from coordinator
    if county == 'brevard':
        if phase == 'C_D_ROOT_CAUSE':
            fixes = brevard_c_d_root_cause()
        elif phase == 'J_GENERATOR':
            fixes = brevard_j_generator()
        elif phase == 'G_HIT_LIST':
            fixes = brevard_g_hit_list()
        elif phase == 'B_RECONCILIATION':
            fixes = brevard_b_reconciliation()
        else:
            fixes = []
    elif county == 'duval':
        if phase == 'G_I_SUBSTRATE_BUILD':
            fixes = duval_g_i_substrate_build()
        elif phase == 'C_D_ROOT_CAUSE':
            fixes = brevard_c_d_root_cause()  # Reuse pattern for Duval
        elif phase == 'J_GENERATOR':
            fixes = brevard_j_generator()  # County-agnostic
        elif phase == 'B_RECONCILIATION':
            fixes = brevard_b_reconciliation()  # Reuse pattern
        else:
            fixes = []
    else:
        fixes = []
    
    # Execute each fix
    results = []
    for fix_name, fix_sql in fixes:
        result = execute_sql(fix_sql, f"{county} {phase}: {fix_name}")
        results.append(result)
        
        # Short pause between operations
        time.sleep(1)
    
    return results

def verify_county_metrics(county: str) -> Dict:
    """Get live county metrics using pencil_dod_evaluate_county"""
    log_action(f"Verifying {county} metrics...", "INFO", "UNTESTED")
    
    try:
        headers = sb_headers()
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_name": county}
        )
        
        if response.status_code == 200:
            metrics = response.json()
            log_action(f"✅ {county} metrics retrieved", "INFO", "VERIFIED")
            
            # Extract key metrics for display
            if isinstance(metrics, list) and len(metrics) > 0:
                m = metrics[0]
                summary = {
                    'county': county,
                    'letters_passing': m.get('pass_count', 0),
                    'a_metric': m.get('a_dual_product', 0),
                    'b_metric': m.get('b_verified_outcomes', 0),
                    'c_metric': m.get('c_parity_clean', 0),
                    'd_metric': m.get('d_parity_any', 0),
                    'e_metric': m.get('e_parcel_linkage', 0),
                    'f_metric': m.get('f_tier1_sold', 0),
                    'g_metric': m.get('g_zoning_kpi', 0),
                    'h_metric': m.get('h_freshness', 0),
                    'i_metric': m.get('i_property_card', 0),
                    'j_metric': m.get('j_deal_thesis', 0),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                return summary
            else:
                return {'county': county, 'error': 'No metrics returned', 'timestamp': datetime.now(timezone.utc).isoformat()}
                
        else:
            log_action(f"❌ {county} metrics failed: {response.status_code}", "ERROR", "VERIFIED")
            return {'county': county, 'error': response.text, 'timestamp': datetime.now(timezone.utc).isoformat()}
            
    except Exception as e:
        log_action(f"❌ {county} metrics error: {e}", "ERROR", "VERIFIED")
        return {'county': county, 'error': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()}

def create_ultraloop_audit_record(county: str, phase: str, results: List[Dict]) -> Dict:
    """Create ULTRALOOP audit record for the phase execution"""
    
    audit_record = {
        'dispatch_id': f"shard24_{county}_{phase}_{int(time.time())}",
        'ultraloop_mode': 'manual_execution',
        'county_slug': county,
        'letter': phase[0],  # First letter of phase
        'claim': f"{county} {phase}: executed {len(results)} fixes",
        'refuter_evidence': {
            'fixes_executed': len(results),
            'successful_fixes': sum(1 for r in results if r['success']),
            'failed_fixes': sum(1 for r in results if not r['success']),
            'execution_timestamp': datetime.now(timezone.utc).isoformat(),
            'errors': [r['error'] for r in results if not r['success']]
        },
        'survived': all(r['success'] for r in results),
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    return audit_record

def execute_full_pipeline():
    """Execute the complete SHARD24 pipeline for both counties"""
    log_action("🚀 EXECUTING FULL SHARD24 PIPELINE", "INFO", "VERIFIED")
    
    pipeline_start = time.time()
    all_results = []
    ultraloop_audits = []
    
    # Brevard sprint order
    brevard_phases = ['C_D_ROOT_CAUSE', 'J_GENERATOR', 'G_HIT_LIST', 'B_RECONCILIATION']
    
    log_action("Phase 1: Brevard Sprint Execution", "INFO", "VERIFIED")
    for phase in brevard_phases:
        phase_results = execute_phase_fixes('brevard', phase)
        all_results.extend(phase_results)
        
        # Create audit record
        audit = create_ultraloop_audit_record('brevard', phase, phase_results)
        ultraloop_audits.append(audit)
        
        log_action(f"Brevard {phase}: {len(phase_results)} fixes, {sum(1 for r in phase_results if r['success'])} successful", "INFO", "VERIFIED")
    
    # Duval sprint order
    duval_phases = ['G_I_SUBSTRATE_BUILD', 'C_D_ROOT_CAUSE', 'J_GENERATOR', 'B_RECONCILIATION']
    
    log_action("Phase 2: Duval Sprint Execution", "INFO", "VERIFIED")
    for phase in duval_phases:
        phase_results = execute_phase_fixes('duval', phase)
        all_results.extend(phase_results)
        
        # Create audit record
        audit = create_ultraloop_audit_record('duval', phase, phase_results)
        ultraloop_audits.append(audit)
        
        log_action(f"Duval {phase}: {len(phase_results)} fixes, {sum(1 for r in phase_results if r['success'])} successful", "INFO", "VERIFIED")
    
    # Verification phase
    log_action("Phase 3: Final Verification", "INFO", "VERIFIED")
    final_metrics = {}
    for county in ['brevard', 'duval']:
        metrics = verify_county_metrics(county)
        final_metrics[county] = metrics
    
    pipeline_elapsed = time.time() - pipeline_start
    
    # Summary report
    log_action("=" * 80, "INFO", "VERIFIED")
    log_action("SHARD24 PIPELINE EXECUTION COMPLETE", "INFO", "VERIFIED")
    log_action("=" * 80, "INFO", "VERIFIED")
    log_action(f"Total fixes executed: {len(all_results)}", "INFO", "VERIFIED")
    log_action(f"Successful fixes: {sum(1 for r in all_results if r['success'])}", "INFO", "VERIFIED")
    log_action(f"Failed fixes: {sum(1 for r in all_results if not r['success'])}", "INFO", "VERIFIED")
    log_action(f"Execution time: {pipeline_elapsed/60:.1f} minutes", "INFO", "VERIFIED")
    
    # Display final metrics
    log_action("FINAL METRICS (VERIFIED):", "INFO", "VERIFIED")
    for county, metrics in final_metrics.items():
        if 'error' not in metrics:
            log_action(f"{county}: {metrics['letters_passing']}/10 letters passing", "INFO", "VERIFIED")
            log_action(f"  B={metrics['b_metric']:.1f}%, C={metrics['c_metric']:.1f}%, D={metrics['d_metric']:.1f}%, G={metrics['g_metric']:.1f}%, I={metrics['i_metric']:.1f}%, J={metrics['j_metric']:.1f}%", "INFO", "VERIFIED")
        else:
            log_action(f"{county}: ERROR retrieving metrics - {metrics['error']}", "ERROR", "VERIFIED")
    
    return {
        'all_results': all_results,
        'ultraloop_audits': ultraloop_audits,
        'final_metrics': final_metrics,
        'pipeline_elapsed': pipeline_elapsed
    }

def main():
    parser = argparse.ArgumentParser(description='SHARD24 Verification Runner - Execute database operations')
    parser.add_argument('--execute-all', action='store_true', help='Execute complete pipeline for both counties')
    parser.add_argument('--county', choices=['brevard', 'duval'], help='Execute single county')
    parser.add_argument('--phase', choices=['C_D_ROOT_CAUSE', 'J_GENERATOR', 'G_HIT_LIST', 'B_RECONCILIATION', 'G_I_SUBSTRATE_BUILD'], help='Execute single phase')
    parser.add_argument('--verify-only', action='store_true', help='Only run metrics verification')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be executed without running')
    
    args = parser.parse_args()
    
    if not any([args.execute_all, args.verify_only, (args.county and args.phase)]):
        parser.print_help()
        sys.exit(1)
    
    log_action("🔧 SHARD24 VERIFICATION RUNNER STARTING", "INFO", "VERIFIED")
    
    if args.dry_run:
        log_action("DRY RUN MODE - No database operations will be executed", "WARNING", "VERIFIED")
    
    if args.verify_only:
        log_action("VERIFICATION ONLY MODE", "INFO", "VERIFIED")
        for county in ['brevard', 'duval']:
            metrics = verify_county_metrics(county)
            print(f"\n{county.upper()} METRICS:")
            print(f"  Letters passing: {metrics.get('letters_passing', 'ERROR')}/10")
            if 'error' not in metrics:
                print(f"  B: {metrics['b_metric']:.1f}%")
                print(f"  C: {metrics['c_metric']:.1f}%") 
                print(f"  D: {metrics['d_metric']:.1f}%")
                print(f"  G: {metrics['g_metric']:.1f}%")
                print(f"  I: {metrics['i_metric']:.1f}%")
                print(f"  J: {metrics['j_metric']:.1f}%")
    
    elif args.execute_all:
        log_action("FULL PIPELINE EXECUTION MODE", "INFO", "VERIFIED")
        if not args.dry_run:
            result = execute_full_pipeline()
            
            # Save execution report
            report_file = f"shard24_execution_report_{int(time.time())}.json"
            try:
                import json
                with open(report_file, 'w') as f:
                    json.dump(result, f, indent=2, default=str)
                log_action(f"📄 Execution report saved: {report_file}", "INFO", "VERIFIED")
            except Exception as e:
                log_action(f"⚠️ Could not save report: {e}", "WARNING", "VERIFIED")
        else:
            log_action("DRY RUN: Would execute full pipeline", "INFO", "VERIFIED")
    
    elif args.county and args.phase:
        log_action(f"SINGLE PHASE EXECUTION: {args.county} {args.phase}", "INFO", "VERIFIED")
        if not args.dry_run:
            results = execute_phase_fixes(args.county, args.phase)
            log_action(f"Phase complete: {len(results)} fixes, {sum(1 for r in results if r['success'])} successful", "INFO", "VERIFIED")
        else:
            log_action(f"DRY RUN: Would execute {args.county} {args.phase}", "INFO", "VERIFIED")
    
    log_action("✅ SHARD24 VERIFICATION RUNNER COMPLETE", "INFO", "VERIFIED")

if __name__ == "__main__":
    main()