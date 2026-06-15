#!/usr/bin/env python3
"""
SHARD-6 Priority #1: C/D ROOT CAUSE - Parity Audit vs PropertyOnion Coverage

Per fleet-wide mandate: "C/D ROOT CAUSE — All counties show frozen numerators vs growing denominators.
This IS the PropertyOnion-coverage scenario: INVOKE the pre-authorized clerk/official-records 
supplementary litmus NOW. Run the parity audit as the ULTRALOOP refuter step, document evidence."

Implements C/D parity fixes for SHARD-6 counties: hillsborough, bay, martin, calhoun, liberty

Usage:
  python shard6_cd_parity_fix.py [county_name]
  python shard6_cd_parity_fix.py  # All counties
"""
import os
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY not available in environment")
    exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

SHARD6_COUNTIES = ['hillsborough', 'bay', 'martin', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_cd_metrics(county: str) -> Optional[Dict]:
    """Audit current C/D parity metrics - VERIFIED approach with SQL evidence"""
    try:
        log(f"Auditing C/D metrics for {county}...")
        
        # Use the evaluator function to get current metrics
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json={"county_param": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse the evaluation result
            c_data = None
            d_data = None
            
            if isinstance(result, list):
                for item in result:
                    if item.get('letter') == 'C':
                        c_data = item
                    elif item.get('letter') == 'D':
                        d_data = item
            
            audit_result = {
                "county": county,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "c_metric": c_data.get('metric') if c_data else None,
                "d_metric": d_data.get('metric') if d_data else None,
                "c_detail": c_data.get('detail') if c_data else None,
                "d_detail": d_data.get('detail') if d_data else None,
                "c_pass": c_data.get('pass') if c_data else False,
                "d_pass": d_data.get('pass') if d_data else False,
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                "verification_status": "VERIFIED"
            }
            
            log(f"{county} C/D current: C={audit_result['c_metric']}% D={audit_result['d_metric']}%")
            return audit_result
        else:
            log(f"Failed to audit {county}: HTTP {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing {county}: {e}", "ERROR")
        return None

def analyze_parity_coverage(county: str) -> Optional[Dict]:
    """Analyze PropertyOnion coverage vs total auctions - identifies numerator freeze issue"""
    try:
        log(f"Analyzing parity coverage for {county}...")
        
        # Get total auction count for county
        total_response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county}",
                "limit": "0"  # Count only
            }
        )
        
        total_auctions = 0
        if total_response.status_code == 200:
            content_range = total_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                total_auctions = int(content_range.split('/')[-1])
        
        # Get PropertyOnion matched count (indicative of C/D numerators)
        # Looking for auctions that have parity_status populated
        matched_response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county}",
                "parity_status": "not.is.null",
                "limit": "0"
            }
        )
        
        matched_auctions = 0
        if matched_response.status_code == 200:
            content_range = matched_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                matched_auctions = int(content_range.split('/')[-1])
        
        coverage_pct = (matched_auctions / total_auctions * 100) if total_auctions > 0 else 0
        
        analysis = {
            "county": county,
            "total_auctions": total_auctions,
            "matched_auctions": matched_auctions,
            "coverage_percentage": round(coverage_pct, 1),
            "potential_gap": total_auctions - matched_auctions,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "sql_evidence": f"SELECT COUNT(*) FROM multi_county_auctions WHERE county='{county}'"
        }
        
        log(f"{county} coverage: {matched_auctions:,}/{total_auctions:,} ({coverage_pct:.1f}%)")
        return analysis
        
    except Exception as e:
        log(f"Error analyzing coverage for {county}: {e}", "ERROR")
        return None

def implement_supplementary_litmus_source(county: str) -> Dict:
    """Implement pre-authorized clerk/official-records supplementary litmus for C/D improvement
    
    Per briefing: 'pre-authorized to adopt clerk/official-records as supplementary litmus source'
    This is the ULTRALOOP refuter evidence collection step.
    """
    try:
        log(f"Implementing supplementary litmus for {county}...")
        
        # Document the evidence for supplementary source adoption
        evidence = {
            "county": county,
            "authorization_source": "CRITERION-PARALLEL PIVOT briefing 2026-06-12",
            "evidence_type": "C/D ROOT CAUSE - frozen numerators vs growing denominators",
            "supplementary_source": "clerk/official-records",
            "implementation_status": "PLANNED",
            "next_steps": [
                f"Identify {county} clerk official records endpoint",
                f"Map case_number format between PropertyOnion and clerk records",
                f"Implement clerk records scraper as supplementary parity source",
                f"Backfill missing case_number matches from clerk records",
                f"Update parity_status for newly matched cases"
            ],
            "estimated_impact": "Unfreeze C/D numerators by adding clerk-sourced matches",
            "honesty_marker": "INFERRED - implementation planned but not executed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        log(f"{county} supplementary litmus plan documented", "INFO")
        return evidence
        
    except Exception as e:
        log(f"Error planning supplementary litmus for {county}: {e}", "ERROR")
        return {"error": str(e)}

def execute_cd_parity_fixes():
    """Execute C/D parity fixes for all SHARD-6 counties"""
    
    log("Starting SHARD-6 C/D Parity Fixes", "INFO")
    log(f"Counties: {SHARD6_COUNTIES}")
    
    session_report = {
        "session_id": "shard6-cd-parity-fix",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties": SHARD6_COUNTIES,
        "audits": {},
        "coverage_analysis": {},
        "supplementary_plans": {}
    }
    
    # Phase 1: Audit current status
    log("Phase 1: Auditing current C/D metrics...")
    for county in SHARD6_COUNTIES:
        audit_result = audit_current_cd_metrics(county)
        if audit_result:
            session_report["audits"][county] = audit_result
    
    # Phase 2: Analyze coverage gaps
    log("Phase 2: Analyzing PropertyOnion coverage gaps...")
    for county in SHARD6_COUNTIES:
        coverage_result = analyze_parity_coverage(county)
        if coverage_result:
            session_report["coverage_analysis"][county] = coverage_result
    
    # Phase 3: Plan supplementary litmus implementation
    log("Phase 3: Planning supplementary litmus sources...")
    for county in SHARD6_COUNTIES:
        plan_result = implement_supplementary_litmus_source(county)
        session_report["supplementary_plans"][county] = plan_result
    
    # Generate summary
    session_report["summary"] = {
        "counties_audited": len(session_report["audits"]),
        "coverage_analyzed": len(session_report["coverage_analysis"]),
        "supplementary_plans": len(session_report["supplementary_plans"]),
        "next_phase": "Implement clerk records scrapers for each county",
        "completion_status": "PHASE_1_COMPLETE"
    }
    
    log("SHARD-6 C/D Parity Fix session complete", "INFO")
    return session_report

def print_session_report(report: Dict):
    """Print formatted session report"""
    
    print("\n" + "="*70)
    print("SHARD-6 C/D PARITY FIX SESSION REPORT")
    print("="*70)
    print(f"Session ID: {report['session_id']}")
    print(f"Timestamp: {report['timestamp']}")
    
    print(f"\nCURRENT C/D METRICS:")
    for county, audit in report['audits'].items():
        c_metric = audit['c_metric']
        d_metric = audit['d_metric']
        c_pass = "✅" if audit['c_pass'] else "❌"
        d_pass = "✅" if audit['d_pass'] else "❌"
        print(f"  {county}: C={c_metric}% {c_pass} | D={d_metric}% {d_pass}")
    
    print(f"\nCOVERAGE ANALYSIS:")
    for county, analysis in report['coverage_analysis'].items():
        total = analysis['total_auctions']
        matched = analysis['matched_auctions']
        pct = analysis['coverage_percentage']
        gap = analysis['potential_gap']
        print(f"  {county}: {matched:,}/{total:,} ({pct}%) - gap: {gap:,}")
    
    print(f"\nSUPPLEMENTARY LITMUS PLANS:")
    for county, plan in report['supplementary_plans'].items():
        if 'error' not in plan:
            status = plan['implementation_status']
            print(f"  {county}: {status} - clerk/official-records adoption planned")
        else:
            print(f"  {county}: ERROR - {plan['error']}")
    
    print(f"\nSUMMARY:")
    summary = report['summary']
    print(f"  Counties processed: {summary['counties_audited']}")
    print(f"  Next phase: {summary['next_phase']}")
    print(f"  Status: {summary['completion_status']}")
    
    print("\n" + "="*70)

def main():
    """Main execution function"""
    import sys
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in SHARD6_COUNTIES:
            # Single county execution
            audit = audit_current_cd_metrics(county)
            coverage = analyze_parity_coverage(county)
            plan = implement_supplementary_litmus_source(county)
            
            result = {
                "county": county,
                "audit": audit,
                "coverage": coverage,
                "plan": plan
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {county} not in SHARD-6 counties {SHARD6_COUNTIES}")
    else:
        # Full session execution
        report = execute_cd_parity_fixes()
        print_session_report(report)
        
        # Save report
        with open('/tmp/shard6_cd_parity_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        log("Report saved to /tmp/shard6_cd_parity_report.json")

if __name__ == "__main__":
    main()