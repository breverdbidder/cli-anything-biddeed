#!/usr/bin/env python3
"""
Brevard + Duval Priority #1: C/D ROOT CAUSE - Parity Audit vs PropertyOnion Coverage

Per issue directive: "C/D ROOT CAUSE — numerators frozen (~4.1K/6.6K) while denominator grew 33%. 
This IS the PropertyOnion-coverage scenario: INVOKE the pre-authorized clerk/official-records 
supplementary litmus NOW."

Implementation for brevard and duval counties with pre-authorized clerk/official-records 
supplementary litmus source adoption.

Usage:
  python scripts/brevard_duval_cd_parity_fix.py
"""
import os
import requests
import json
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

TARGET_COUNTIES = ['brevard', 'duval']

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_parity_status(county_slug):
    """Audit current C/D parity status - VERIFIED approach with SQL evidence"""
    try:
        # Get current C/D metrics using the evaluation function (correct parameter name)
        payload = {"county_slug_arg": county_slug}
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            # Extract C/D metrics from the list response
            c_data = next((item for item in evaluation if item.get('letter') == 'C'), {})
            d_data = next((item for item in evaluation if item.get('letter') == 'D'), {})
            
            c_metric = c_data.get('metric')
            d_metric = d_data.get('metric') 
            c_pass = c_data.get('pass', False)
            d_pass = d_data.get('pass', False)
            
            audit_result = {
                "county": county_slug,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "c_metric": c_metric,
                "d_metric": d_metric,
                "c_pass": c_pass,
                "d_pass": d_pass,
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county_slug}')",
                "verification_status": "VERIFIED"
            }
            
            log(f"{county_slug} C/D audit: C={c_metric}% D={d_metric}%")
            return audit_result
        else:
            log(f"Failed to audit {county_slug}: {response.status_code} - {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing {county_slug}: {e}", "ERROR")
        return None

def analyze_propertyonion_coverage(county_slug):
    """Analyze PropertyOnion vs clerk records coverage - INFERRED from pattern analysis"""
    try:
        # Query multi_county_auctions for total auctions in county
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county_slug}",
                "limit": "1"
            },
            timeout=30
        )
        
        total_auctions = 0
        if response.status_code == 206:
            content_range = response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                total_auctions = int(content_range.split('/')[-1])
        
        # Get PropertyOnion IDs (starting with PO-)
        po_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county_slug}",
                "case_number": "like.PO-%",
                "limit": "1"
            },
            timeout=30
        )
        
        po_count = 0
        if po_response.status_code == 206:
            content_range = po_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                po_count = int(content_range.split('/')[-1])
        
        # Get court format case numbers (not PO-)
        court_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county_slug}",
                "case_number": "not.like.PO-%",
                "limit": "1"
            },
            timeout=30
        )
        
        court_count = 0
        if court_response.status_code == 206:
            content_range = court_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                court_count = int(content_range.split('/')[-1])
        
        coverage_analysis = {
            "county": county_slug,
            "total_auctions": total_auctions,
            "propertyonion_ids": po_count,
            "court_format_ids": court_count,
            "po_percentage": (po_count / total_auctions * 100) if total_auctions > 0 else 0,
            "court_percentage": (court_count / total_auctions * 100) if total_auctions > 0 else 0,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "verification_status": "INFERRED"
        }
        
        log(f"{county_slug} coverage: {po_count} PO IDs ({coverage_analysis['po_percentage']:.1f}%), {court_count} court format ({coverage_analysis['court_percentage']:.1f}%)")
        return coverage_analysis
        
    except Exception as e:
        log(f"Error analyzing coverage for {county_slug}: {e}", "ERROR")
        return None

def implement_clerk_supplementary_litmus(county_slug):
    """Implement pre-authorized clerk/official-records supplementary litmus source"""
    log(f"🚀 Implementing clerk supplementary litmus for {county_slug}")
    
    if county_slug == 'brevard':
        return implement_brevard_acclaim_endpoint()
    elif county_slug == 'duval':
        return implement_duval_clerk_records()
    else:
        log(f"No clerk endpoint configured for {county_slug}", "ERROR")
        return None

def implement_brevard_acclaim_endpoint():
    """Port Duval Acclaim recording pipeline to Brevard (verified endpoint)"""
    # Per issue: Brevard Acclaim endpoint VERIFIED live: https://vaclmweb1.brevardclerk.us/AcclaimWeb/
    brevard_acclaim_config = {
        "endpoint": "https://vaclmweb1.brevardclerk.us/AcclaimWeb/",
        "doc_types": ["CT", "CERT TITLE"],  # Certificate of Title for sale amounts
        "target_table": "foreclosure_outcomes",
        "data_source": "acclaim_ct:BREVARD-FC-V1",
        "match_strategy": "case_number",
        "harvest_period": "24 months",
        "implementation_status": "READY_TO_BUILD"
    }
    
    log("Brevard Acclaim configuration prepared")
    log(f"Endpoint: {brevard_acclaim_config['endpoint']}")
    log(f"Doc types: {brevard_acclaim_config['doc_types']}")
    
    return brevard_acclaim_config

def implement_duval_clerk_records():
    """Extend existing Duval Acclaim pipeline with PO->court case_number repair"""
    # Per issue root cause: 8,979 of 9,336 closed Duval rows carry PropertyOnion IDs as case_number
    duval_repair_config = {
        "problem": "PO IDs can never match official records",
        "solution": "PO→court case_number repair via Duval clerk tax-deed file lookup",
        "lookup_method": "parcel_id + sale_date match",
        "affected_rows": "18,156 PO rows have parcel_id",
        "target_table": "multi_county_auctions",
        "repair_source": "duval_clerk_tax_deed_files",
        "implementation_status": "READY_TO_BUILD"
    }
    
    log("Duval PO→court repair configuration prepared")
    log(f"Affected rows: {duval_repair_config['affected_rows']}")
    
    return duval_repair_config

def verify_fix_effectiveness(county_slug):
    """Re-run evaluation to verify C/D improvement - VERIFIED post-fix metrics"""
    log(f"🔍 Verifying fix effectiveness for {county_slug}")
    
    post_fix_audit = audit_current_parity_status(county_slug)
    if post_fix_audit:
        c_metric = post_fix_audit.get('c_metric', 0)
        d_metric = post_fix_audit.get('d_metric', 0)
        
        # Check if we moved toward 95% threshold
        c_improved = c_metric > 20.8 if county_slug == 'brevard' else c_metric > 16.1  # baseline from issue
        d_improved = d_metric > 34.0 if county_slug == 'brevard' else d_metric > 52.9  # baseline from issue
        
        effectiveness = {
            "county": county_slug,
            "post_fix_c": c_metric,
            "post_fix_d": d_metric,
            "c_improved": c_improved,
            "d_improved": d_improved,
            "sql_verification": f"SELECT public.pencil_dod_evaluate_county('{county_slug}')",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if c_improved or d_improved:
            log(f"✅ {county_slug} C/D improvement detected")
        else:
            log(f"⚠️ {county_slug} C/D metrics unchanged - may need deeper implementation")
            
        return effectiveness
    
    return None

def main():
    """Execute C/D ROOT CAUSE fix for brevard and duval"""
    log("🚀 Starting C/D ROOT CAUSE fix for brevard and duval")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY not available", "ERROR")
        return
    
    results = {
        "session_info": {
            "priority": "C/D ROOT CAUSE",
            "counties": TARGET_COUNTIES,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "authorization": "PRE-AUTHORIZED clerk/official-records supplementary litmus"
        },
        "audits": {},
        "coverage_analysis": {},
        "implementations": {},
        "verification": {}
    }
    
    for county_slug in TARGET_COUNTIES:
        log(f"\n📊 Processing {county_slug.upper()}")
        
        # 1. Audit current status
        audit = audit_current_parity_status(county_slug)
        if audit:
            results["audits"][county_slug] = audit
        
        # 2. Analyze PropertyOnion coverage
        coverage = analyze_propertyonion_coverage(county_slug)
        if coverage:
            results["coverage_analysis"][county_slug] = coverage
        
        # 3. Implement clerk supplementary litmus
        implementation = implement_clerk_supplementary_litmus(county_slug)
        if implementation:
            results["implementations"][county_slug] = implementation
        
        # 4. Verify effectiveness (would need actual implementation first)
        verification = verify_fix_effectiveness(county_slug)
        if verification:
            results["verification"][county_slug] = verification
    
    # Summary
    log("\n📋 C/D ROOT CAUSE FIX SUMMARY")
    log("="*50)
    
    for county_slug in TARGET_COUNTIES:
        audit = results["audits"].get(county_slug, {})
        coverage = results["coverage_analysis"].get(county_slug, {})
        
        log(f"{county_slug.upper()}:")
        log(f"  C: {audit.get('c_metric', 'N/A')}% ({'PASS' if audit.get('c_pass') else 'FAIL'})")
        log(f"  D: {audit.get('d_metric', 'N/A')}% ({'PASS' if audit.get('d_pass') else 'FAIL'})")
        
        if coverage:
            po_pct = coverage.get('po_percentage', 0)
            log(f"  PropertyOnion coverage: {po_pct:.1f}%")
            if po_pct > 50:
                log(f"  🎯 High PO coverage confirms root cause - clerk repair needed")
    
    # Write results to file
    with open('brevard_duval_cd_fix_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    log("\n✅ C/D ROOT CAUSE analysis complete")
    log("Next: Implement actual clerk data pipelines based on configurations")

if __name__ == "__main__":
    main()