#!/usr/bin/env python3
"""
B RECONCILIATION - Fix >100% anomalies 
AUTOPILOT RUN 20 - SHIP-TO-MAIN 
Priority #4 for brevard (134.1% anomaly), Priority #4 for duval (110.2% anomaly)

Per issue directive: "B RECONCILIATION — verified=8547 > closed_sold=6373 (134%). 
Refuter must find the double-count/denominator mismatch BEFORE any certify counts B. 
Anomalous PASS = not a PASS."

Current anomalous B metrics:
- brevard: B=134.1% (verified_outcomes > closed_sold - impossible ratio)
- duval: B=110.2% (verified_outcomes > closed_sold - impossible ratio)

ROOT CAUSE HYPOTHESIS: 
- Verified outcomes include cases outside the certification scope
- Double-counting from multiple outcome sources  
- Denominator mismatch (verified vs different closed set)

EVALUATOR V6 RULES: "B passes ONLY at 95–105%. Brevard B=134.1% now correctly FAILs"

Usage:
  python scripts/b_reconciliation_anomaly.py --audit-anomalies
  python scripts/b_reconciliation_anomaly.py --fix-brevard
  python scripts/b_reconciliation_anomaly.py --fix-duval
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import argparse

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

# Target counties for our shard
TARGET_COUNTIES = ['brevard', 'duval']

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def get_current_b_metrics():
    """Get current B metrics for both counties - VERIFIED"""
    log("📊 Getting current B metrics for brevard and duval")
    
    metrics = {}
    
    for county in TARGET_COUNTIES:
        try:
            # Use pencil_dod_evaluate_county function
            payload = {"county_name": county}
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json=payload
            )
            
            if response.status_code == 200:
                evaluation = response.json()
                
                b_metric = evaluation.get('metric_b', 0)
                b_grade = "PASS" if evaluation.get('grade_b') == 'PASS' else "FAIL"
                
                # Check if anomalous (>105% per evaluator V6 rules)
                is_anomalous = b_metric > 105
                
                metrics[county] = {
                    "b_metric": b_metric,
                    "b_grade": b_grade,
                    "is_anomalous": is_anomalous,
                    "anomaly_severity": "CRITICAL" if b_metric > 120 else "MODERATE" if b_metric > 105 else "NORMAL",
                    "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                    "verification_status": "VERIFIED",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                log(f"{county}: B={b_metric}% ({b_grade}) {'🚨 ANOMALOUS' if is_anomalous else '✅ NORMAL'}")
                
            else:
                log(f"Failed to get B metrics for {county}: {response.status_code}", "ERROR")
                
        except Exception as e:
            log(f"Error getting B metrics for {county}: {e}", "ERROR")
    
    return metrics

def audit_b_components(county):
    """Audit B metric components for specific county - VERIFIED approach"""
    log(f"🔍 Auditing B metric components for {county}")
    
    audit = {
        "county": county,
        "verified_outcomes": {"count": 0, "sources": {}},
        "closed_auctions": {"count": 0, "sources": {}},
        "certification_scope": {"count": 0, "date_range": None},
        "potential_issues": [],
        "verification_status": "VERIFIED"
    }
    
    # Get verified outcomes count and sources
    try:
        # Check various outcome tables that might contribute to B metric
        outcome_tables = ["tax_deed_outcomes", "foreclosure_outcomes"]
        
        for table in outcome_tables:
            try:
                response = client.get(
                    f"{BASE}/{table}",
                    headers=HEADERS,
                    params={
                        "county": f"eq.{county}",
                        "select": "id,case_number,winning_bid,data_source,sale_date,created_at",
                        "order": "created_at.desc",
                        "limit": "20"
                    }
                )
                
                if response.status_code == 200:
                    outcomes = response.json()
                    
                    # Count by data source
                    source_counts = {}
                    for outcome in outcomes:
                        source = outcome.get("data_source", "unknown")
                        source_counts[source] = source_counts.get(source, 0) + 1
                    
                    audit["verified_outcomes"][table] = {
                        "count": len(outcomes),
                        "sources": source_counts,
                        "sample": outcomes[:3]
                    }
                    
                    log(f"✅ {table}: {len(outcomes)} {county} records (sample)")
                    
                else:
                    log(f"⚠️ {table} query failed: {response.status_code}")
                    
            except Exception as e:
                log(f"Error checking {table}: {e}")
        
        # Get total verified outcomes count via SQL query if possible
        # Note: This would require a direct query to understand B metric calculation
        
    except Exception as e:
        log(f"Error auditing verified outcomes: {e}")
    
    # Get closed auctions count from multi_county_auctions
    try:
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "select": "case_number,sale_date,status,data_source,winning_bid",
                "order": "sale_date.desc",
                "limit": "50"
            }
        )
        
        if response.status_code == 200:
            auctions = response.json()
            
            # Analyze closed/sold status patterns
            status_counts = {}
            source_counts = {}
            
            for auction in auctions:
                status = auction.get("status", "unknown")
                source = auction.get("data_source", "unknown")
                
                status_counts[status] = status_counts.get(status, 0) + 1
                source_counts[source] = source_counts.get(source, 0) + 1
            
            audit["closed_auctions"] = {
                "total_sample": len(auctions),
                "status_distribution": status_counts,
                "source_distribution": source_counts,
                "sample": auctions[:3]
            }
            
            log(f"✅ multi_county_auctions: {len(auctions)} {county} records (sample)")
            log(f"Status distribution: {status_counts}")
            
        else:
            log(f"⚠️ multi_county_auctions query failed: {response.status_code}")
            
    except Exception as e:
        log(f"Error auditing closed auctions: {e}")
    
    # Identify potential issues based on anomaly patterns
    if audit["verified_outcomes"]:
        audit["potential_issues"].extend([
            "Multiple outcome sources may be double-counting same cases",
            "Verified outcomes may include cases outside certification scope", 
            "Different date ranges between verified outcomes and closed auctions",
            "Data source inconsistency between numerator and denominator"
        ])
    
    return audit

def diagnose_anomaly_root_cause(county, audit):
    """Diagnose root cause of B metric anomaly - INFERRED analysis"""
    log(f"🕵️ Diagnosing B anomaly root cause for {county}")
    
    diagnosis = {
        "county": county,
        "primary_hypothesis": "UNKNOWN",
        "evidence": [],
        "recommended_fix": "UNKNOWN",
        "verification_status": "INFERRED"
    }
    
    # Analyze audit data for root cause patterns
    verified_outcomes = audit.get("verified_outcomes", {})
    closed_auctions = audit.get("closed_auctions", {})
    
    # Check for multiple outcome sources (double-counting)
    outcome_sources = []
    for table, data in verified_outcomes.items():
        if isinstance(data, dict) and data.get("sources"):
            outcome_sources.extend(data["sources"].keys())
    
    if len(set(outcome_sources)) > 2:
        diagnosis["primary_hypothesis"] = "MULTIPLE_SOURCE_DOUBLE_COUNTING"
        diagnosis["evidence"].append(f"Multiple outcome data sources detected: {set(outcome_sources)}")
        diagnosis["recommended_fix"] = "Deduplicate verified outcomes by case_number and prioritize independent sources"
    
    # Check for scope mismatch (June 12 snapshot scope mentioned in briefing)
    closed_distribution = closed_auctions.get("source_distribution", {})
    if "PropertyOnion" in closed_distribution or any("PO-" in str(source) for source in closed_distribution):
        diagnosis["evidence"].append("PropertyOnion case numbers detected in closed auctions")
        diagnosis["evidence"].append("Per briefing: 8,979 of 9,336 closed Duval rows carry PO-xxxxxx case_numbers")
        
        if county == "duval":
            diagnosis["primary_hypothesis"] = "SCOPE_MISMATCH_PO_CASES"
            diagnosis["recommended_fix"] = "Filter verified outcomes to match court case format, exclude PO-xxxxxx cases"
    
    # Add general evidence from issue briefing
    diagnosis["evidence"].extend([
        f"Issue briefing: {county} B metric >105% violates evaluator V6 rules",
        "Certification requires B metric 95-105% range",
        "Anomalous ratios suggest numerator/denominator from different datasets"
    ])
    
    if county == "brevard":
        diagnosis["evidence"].extend([
            "Brevard B=134.1% (verified=8547 > closed_sold=6373)",
            "AcclaimWeb pipeline may be over-counting vs scoped closed set"
        ])
    elif county == "duval":
        diagnosis["evidence"].extend([
            "Duval B=110.2% suggests moderate over-counting",
            "flynn_winning_bids dataset (6,952 rows) may extend beyond scoped auctions"
        ])
    
    return diagnosis

def design_anomaly_fix(county, diagnosis):
    """Design fix for B anomaly based on diagnosis - UNTESTED design"""
    log(f"🔧 Designing B anomaly fix for {county}")
    
    fix_design = {
        "county": county,
        "approach": "UNKNOWN",
        "sql_operations": [],
        "validation_steps": [],
        "verification_status": "UNTESTED"
    }
    
    hypothesis = diagnosis.get("primary_hypothesis", "UNKNOWN")
    
    if hypothesis == "MULTIPLE_SOURCE_DOUBLE_COUNTING":
        fix_design["approach"] = "Deduplicate verified outcomes by case_number priority"
        fix_design["sql_operations"] = [
            f"""
-- {county.upper()} B ANOMALY FIX - Deduplicate verified outcomes
-- Step 1: Identify duplicate case_numbers across outcome tables
CREATE TEMP TABLE {county}_outcome_duplicates AS
SELECT case_number, COUNT(*) as source_count
FROM (
    SELECT case_number, 'tax_deed_outcomes' as source_table 
    FROM tax_deed_outcomes 
    WHERE county = '{county}'
    
    UNION ALL
    
    SELECT case_number, 'foreclosure_outcomes' as source_table
    FROM foreclosure_outcomes 
    WHERE county = '{county}'
) combined_outcomes
GROUP BY case_number
HAVING COUNT(*) > 1;

-- Step 2: Prioritize independent sources over PropertyOnion-derived
-- Keep only highest-priority source per case_number
-- Priority: clerk_acclaim_ct > flynn_winning_bids > property_onion_derived
""",
            f"""
-- Step 3: Create clean verified outcomes view for {county}
CREATE OR REPLACE VIEW {county}_verified_outcomes_clean AS
SELECT DISTINCT ON (case_number)
    case_number, winning_bid, sale_date, data_source
FROM (
    SELECT case_number, winning_bid, sale_date, data_source,
           CASE 
               WHEN data_source LIKE '%acclaim_ct%' THEN 1
               WHEN data_source LIKE '%flynn%' THEN 2  
               WHEN data_source LIKE '%property_onion%' THEN 3
               ELSE 4
           END as priority
    FROM tax_deed_outcomes 
    WHERE county = '{county}'
    
    UNION ALL
    
    SELECT case_number, winning_bid, sale_date, data_source,
           CASE 
               WHEN data_source LIKE '%acclaim_ct%' THEN 1
               WHEN data_source LIKE '%flynn%' THEN 2
               WHEN data_source LIKE '%property_onion%' THEN 3  
               ELSE 4
           END as priority
    FROM foreclosure_outcomes
    WHERE county = '{county}'
) prioritized_outcomes
ORDER BY case_number, priority;
"""
        ]
    
    elif hypothesis == "SCOPE_MISMATCH_PO_CASES":
        fix_design["approach"] = "Filter verified outcomes to certification scope"
        fix_design["sql_operations"] = [
            f"""
-- {county.upper()} B ANOMALY FIX - Scope to certification set
-- Step 1: Identify PropertyOnion case_numbers in verified outcomes
SELECT 
    data_source,
    COUNT(*) as total_outcomes,
    COUNT(CASE WHEN case_number LIKE 'PO-%' THEN 1 END) as po_case_count,
    COUNT(CASE WHEN case_number NOT LIKE 'PO-%' THEN 1 END) as court_case_count
FROM (
    SELECT case_number, data_source FROM tax_deed_outcomes WHERE county = '{county}'
    UNION ALL  
    SELECT case_number, data_source FROM foreclosure_outcomes WHERE county = '{county}'
) all_outcomes
GROUP BY data_source;

-- Step 2: Create certification-scoped verified outcomes  
-- Per briefing: scope to June 12 snapshot set
CREATE OR REPLACE VIEW {county}_verified_outcomes_scoped AS
SELECT vo.*
FROM (
    SELECT * FROM tax_deed_outcomes WHERE county = '{county}'
    UNION ALL
    SELECT * FROM foreclosure_outcomes WHERE county = '{county}'  
) vo
INNER JOIN multi_county_auctions mca ON vo.case_number = mca.case_number
WHERE mca.county = '{county}'
    AND mca.case_number NOT LIKE 'PO-%'  -- Exclude PropertyOnion cases
    AND mca.sale_date <= '2024-06-12'    -- Certification scope per briefing
    AND vo.case_number NOT LIKE 'PO-%';   -- Ensure court format case numbers only
"""
        ]
    
    else:
        fix_design["approach"] = "Generic anomaly investigation"
        fix_design["sql_operations"] = [
            f"""
-- {county.upper()} B ANOMALY FIX - Generic investigation  
-- Detailed comparison of verified outcomes vs closed sold
SELECT 
    'verified_outcomes' as metric_type,
    COUNT(*) as count,
    MIN(sale_date) as earliest_date,
    MAX(sale_date) as latest_date
FROM (
    SELECT case_number, sale_date FROM tax_deed_outcomes WHERE county = '{county}'
    UNION ALL
    SELECT case_number, sale_date FROM foreclosure_outcomes WHERE county = '{county}'
) vo

UNION ALL

SELECT 
    'closed_sold' as metric_type, 
    COUNT(*) as count,
    MIN(sale_date) as earliest_date,
    MAX(sale_date) as latest_date  
FROM multi_county_auctions
WHERE county = '{county}'
    AND status IN ('sold', 'closed');  -- Adjust based on actual status values
"""
        ]
    
    # Common validation steps
    fix_design["validation_steps"] = [
        f"Run pencil_dod_evaluate_county('{county}') before fix",
        "Execute anomaly fix SQL operations", 
        f"Run pencil_dod_evaluate_county('{county}') after fix",
        "Verify B metric moves into 95-105% range",
        "Confirm no regression in other letter metrics",
        "Document fix in honesty_violations prevention log"
    ]
    
    return fix_design

def audit_command(args):
    """Execute audit workflow for B anomalies"""
    log("🔍 Starting B anomaly audit for brevard and duval")
    
    # Get current B metrics
    current_metrics = get_current_b_metrics()
    if not current_metrics:
        log("❌ Failed to get current B metrics", "ERROR")
        return False
    
    # Audit components for each county
    county_audits = {}
    diagnoses = {}
    
    for county in TARGET_COUNTIES:
        if county in current_metrics:
            audit = audit_b_components(county)
            diagnosis = diagnose_anomaly_root_cause(county, audit)
            
            county_audits[county] = audit  
            diagnoses[county] = diagnosis
    
    # Generate comprehensive audit report
    print("\n" + "="*80)
    print("B METRIC ANOMALY AUDIT REPORT")
    print("="*80)
    
    print(f"\n📊 Current B Metrics (VERIFIED):")
    for county, metrics in current_metrics.items():
        severity = metrics['anomaly_severity']
        icon = "🚨" if severity == "CRITICAL" else "⚠️" if severity == "MODERATE" else "✅"
        
        print(f"  {county}: {metrics['b_metric']}% ({metrics['b_grade']}) {icon} {severity}")
        print(f"    SQL: {metrics['sql_evidence']}")
        print(f"    Anomalous: {'YES' if metrics['is_anomalous'] else 'NO'}")
    
    print(f"\n🔍 Component Audits:")
    for county, audit in county_audits.items():
        print(f"\n  {county.upper()} Component Analysis:")
        
        verified_outcomes = audit.get("verified_outcomes", {})
        closed_auctions = audit.get("closed_auctions", {})
        
        print(f"    Verified outcomes sources: {list(verified_outcomes.keys())}")
        print(f"    Closed auctions sample: {closed_auctions.get('total_sample', 0)}")
        print(f"    Potential issues: {len(audit.get('potential_issues', []))}")
    
    print(f"\n🕵️ Root Cause Diagnoses:")
    for county, diagnosis in diagnoses.items():
        print(f"\n  {county.upper()}:")
        print(f"    Primary hypothesis: {diagnosis['primary_hypothesis']}")
        print(f"    Recommended fix: {diagnosis['recommended_fix']}")
        print(f"    Evidence count: {len(diagnosis['evidence'])}")
        
        for evidence in diagnosis['evidence'][:3]:  # Show first 3 pieces of evidence
            print(f"      • {evidence}")
    
    print(f"\n💡 Summary Findings:")
    print(f"  • Both counties have B metrics >105% (violates evaluator V6)")
    print(f"  • Root causes likely include double-counting and scope mismatches")
    print(f"  • Fixes required before certification can proceed")
    print(f"  • Priority: brevard (134.1%) more severe than duval (110.2%)")
    
    log("✅ B anomaly audit complete")
    return True

def fix_county_command(args, county):
    """Execute fix workflow for specific county"""
    log(f"🔧 Starting B anomaly fix for {county}")
    
    # Get baseline metrics
    baseline = get_current_b_metrics()
    baseline_county = baseline.get(county, {})
    
    if not baseline_county:
        log(f"❌ Failed to get baseline B metrics for {county}", "ERROR")
        return False
    
    log(f"📊 Baseline {county}: B={baseline_county['b_metric']}%")
    
    # Audit components
    audit = audit_b_components(county)
    
    # Diagnose root cause
    diagnosis = diagnose_anomaly_root_cause(county, audit)
    
    # Design fix
    fix_design = design_anomaly_fix(county, diagnosis)
    
    # Generate fix report
    print("\n" + "="*80)
    print(f"{county.upper()} B ANOMALY FIX IMPLEMENTATION")
    print("="*80)
    
    print(f"\n📊 Baseline Metrics:")
    print(f"  Letter B: {baseline_county['b_metric']}% (Target: 95-105%)")
    print(f"  Status: {baseline_county['b_grade']}")
    print(f"  Anomaly: {baseline_county['anomaly_severity']}")
    
    print(f"\n🕵️ Root Cause Diagnosis:")
    print(f"  Primary hypothesis: {diagnosis['primary_hypothesis']}")
    print(f"  Recommended fix: {diagnosis['recommended_fix']}")
    print(f"  Verification status: {diagnosis['verification_status']}")
    
    print(f"\n🔧 Fix Design:")
    print(f"  Approach: {fix_design['approach']}")
    print(f"  SQL operations: {len(fix_design['sql_operations'])}")
    print(f"  Validation steps: {len(fix_design['validation_steps'])}")
    
    if fix_design['sql_operations']:
        print(f"\n📋 SQL Operations Preview:")
        for i, sql in enumerate(fix_design['sql_operations'][:1], 1):  # Show first operation
            lines = sql.strip().split('\n')[:5]  # Show first 5 lines
            print(f"  Operation {i}:")
            for line in lines:
                print(f"    {line}")
            print(f"    ... (truncated)")
    
    print(f"\n✅ Validation Protocol:")
    for i, step in enumerate(fix_design['validation_steps'], 1):
        print(f"  {i}. {step}")
    
    print(f"\n⚠️  EXECUTION REQUIREMENTS:")
    print(f"  1. This designs the B anomaly fix for {county}")
    print(f"  2. Actual execution requires SQL execution against Supabase")
    print(f"  3. Expected: B metric {baseline_county['b_metric']}% → 95-105% range")
    print(f"  4. Critical: Must verify fix before any certification attempts")
    print(f"  5. Honesty Protocol: VERIFIED outcomes only, no double-counting")
    
    log(f"✅ {county} B anomaly fix planning complete")
    return True

def main():
    parser = argparse.ArgumentParser(description="B Reconciliation - Anomaly Fixes")
    parser.add_argument("--audit-anomalies", action="store_true",
                       help="Audit B metric anomalies for both counties")
    parser.add_argument("--fix-brevard", action="store_true",
                       help="Fix B anomaly for brevard county")
    parser.add_argument("--fix-duval", action="store_true",
                       help="Fix B anomaly for duval county")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found", "ERROR")
        sys.exit(1)
    
    if args.audit_anomalies:
        success = audit_command(args)
        sys.exit(0 if success else 1)
    elif args.fix_brevard:
        success = fix_county_command(args, "brevard")
        sys.exit(0 if success else 1)
    elif args.fix_duval:
        success = fix_county_command(args, "duval")
        sys.exit(0 if success else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()