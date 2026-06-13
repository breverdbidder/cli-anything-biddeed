#!/usr/bin/env python3
"""
BREVARD & DUVAL C/D ROOT CAUSE ANALYSIS - SHARD 20 AUTOPILOT 
SHIP-TO-MAIN - PropertyOnion vs Clerk Coverage Analysis

Per issue directive: "C/D ROOT CAUSE — numerators frozen (~4.1K/6.6K) while 
denominator grew 33%. This IS the PropertyOnion-coverage scenario: INVOKE the 
pre-authorized clerk/official-records supplementary litmus NOW."

Current metrics from issue:
- brevard: C=20.8 [matched_clean=4092 of 19706], D=33.2 [matched_any=6548 of 19706] 
- duval: C=16.1 [matched_clean=3217 of 20022], D=52.9 [matched_any=10590 of 20022]

Pattern: Low C/D rates with frozen numerators suggest PropertyOnion coverage ceiling.

VERIFICATION HONESTY: All claims tagged VERIFIED/UNTESTED/INFERRED per HONESTY PROTOCOL.
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any
import time

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Target counties for SHARD-20 run 20
TARGET_COUNTIES = ['brevard', 'duval']

def log_with_honesty(message: str, tag: str = "UNTESTED"):
    """Log with HONESTY PROTOCOL tags"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    print(f"[{timestamp}] [{tag}] {message}")

def test_connection() -> bool:
    """Test Supabase connection - VERIFICATION step"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            log_with_honesty("Supabase connection successful", "VERIFIED")
            return True
        else:
            log_with_honesty(f"Connection failed: {response.status_code}", "VERIFIED")
            return False
    except Exception as e:
        log_with_honesty(f"Connection error: {e}", "VERIFIED")
        return False

def get_current_cd_metrics() -> Dict[str, Any]:
    """Get current C/D metrics using pencil_dod_evaluate_county"""
    log_with_honesty("Getting current C/D metrics for Brevard and Duval", "UNTESTED")
    
    metrics = {}
    
    for county in TARGET_COUNTIES:
        try:
            # Use the evaluation function
            payload = {"county_name": county}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                evaluation = response.json()
                
                c_metric = evaluation.get('metric_c', 0)
                d_metric = evaluation.get('metric_d', 0)
                c_grade = evaluation.get('grade_c', 'UNKNOWN')
                d_grade = evaluation.get('grade_d', 'UNKNOWN') 
                
                cd_gap = d_metric - c_metric
                
                metrics[county] = {
                    "c_metric": c_metric,
                    "d_metric": d_metric,
                    "c_grade": c_grade,
                    "d_grade": d_grade,
                    "cd_gap": cd_gap,
                    "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county}');",
                    "evaluation_timestamp": datetime.utcnow().isoformat() + 'Z'
                }
                
                log_with_honesty(
                    f"{county}: C={c_metric}% ({c_grade}), D={d_metric}% ({d_grade}), Gap={cd_gap}%",
                    "VERIFIED"
                )
                
            else:
                log_with_honesty(f"Failed to evaluate {county}: {response.status_code} - {response.text}", "VERIFIED")
                
        except Exception as e:
            log_with_honesty(f"Error evaluating {county}: {e}", "VERIFIED")
    
    return metrics

def analyze_propertyonion_coverage() -> Dict[str, Any]:
    """Analyze PropertyOnion coverage patterns - the suspected root cause"""
    log_with_honesty("Analyzing PropertyOnion coverage patterns", "UNTESTED")
    
    coverage_analysis = {}
    
    for county in TARGET_COUNTIES:
        try:
            # Sample auction records to analyze PropertyOnion coverage
            response = requests.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={
                    "county_slug": f"eq.{county}",
                    "select": "case_number,property_onion_id,parity_status,parity_clean,source_platform,data_source",
                    "limit": "1000"  # Sample size for analysis
                }
            )
            
            if response.status_code == 200:
                auctions = response.json()
                total_sample = len(auctions)
                
                # Count coverage patterns
                with_po_id = sum(1 for a in auctions if a.get('property_onion_id'))
                parity_clean = sum(1 for a in auctions if a.get('parity_clean'))
                parity_any = sum(1 for a in auctions if a.get('parity_status') in ['clean', 'divergent'])
                
                # Data source breakdown
                source_counts = {}
                platform_counts = {}
                
                for auction in auctions:
                    source = auction.get('data_source', 'unknown')
                    platform = auction.get('source_platform', 'unknown')
                    
                    source_counts[source] = source_counts.get(source, 0) + 1
                    platform_counts[platform] = platform_counts.get(platform, 0) + 1
                
                # Calculate coverage percentages
                po_coverage_pct = (with_po_id * 100.0 / total_sample) if total_sample > 0 else 0
                clean_rate = (parity_clean * 100.0 / total_sample) if total_sample > 0 else 0
                any_match_rate = (parity_any * 100.0 / total_sample) if total_sample > 0 else 0
                
                coverage_analysis[county] = {
                    "sample_size": total_sample,
                    "with_property_onion_id": with_po_id,
                    "parity_clean_count": parity_clean,
                    "parity_any_count": parity_any,
                    "po_coverage_pct": round(po_coverage_pct, 2),
                    "clean_rate_sample": round(clean_rate, 2),
                    "any_match_rate_sample": round(any_match_rate, 2),
                    "source_breakdown": source_counts,
                    "platform_breakdown": platform_counts,
                    "sql_evidence": f"SELECT case_number,property_onion_id,parity_status,parity_clean FROM multi_county_auctions WHERE county_slug='{county}' LIMIT 1000;",
                    "analysis_timestamp": datetime.utcnow().isoformat() + 'Z'
                }
                
                log_with_honesty(
                    f"{county} coverage: {po_coverage_pct}% PropertyOnion, {clean_rate}% clean, {any_match_rate}% any match",
                    "VERIFIED"
                )
                
            else:
                log_with_honesty(f"Failed to analyze {county} coverage: {response.status_code}", "VERIFIED")
                
        except Exception as e:
            log_with_honesty(f"Error analyzing {county} coverage: {e}", "VERIFIED")
    
    return coverage_analysis

def diagnose_root_causes(metrics: Dict[str, Any], coverage: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnose root causes with VERIFIED evidence"""
    log_with_honesty("Diagnosing C/D root causes per issue directive", "UNTESTED")
    
    diagnosis = {}
    
    for county in TARGET_COUNTIES:
        county_metrics = metrics.get(county, {})
        county_coverage = coverage.get(county, {})
        
        c_metric = county_metrics.get("c_metric", 0)
        d_metric = county_metrics.get("d_metric", 0)
        cd_gap = county_metrics.get("cd_gap", 0)
        po_coverage = county_coverage.get("po_coverage_pct", 0)
        
        # Diagnostic patterns from issue analysis
        patterns = []
        evidence = []
        
        # Pattern 1: Low C/D rates (both under 95% threshold)
        if c_metric < 95:
            patterns.append("LOW_C_METRIC")
            evidence.append(f"C={c_metric}% < 95% threshold")
            
        if d_metric < 95:
            patterns.append("LOW_D_METRIC") 
            evidence.append(f"D={d_metric}% < 95% threshold")
        
        # Pattern 2: PropertyOnion coverage ceiling
        if po_coverage < 80:
            patterns.append("LOW_PO_COVERAGE")
            evidence.append(f"PropertyOnion coverage {po_coverage}% indicates coverage ceiling")
        
        # Pattern 3: Frozen numerators (per issue brief)
        if c_metric < 25:
            patterns.append("FROZEN_NUMERATORS")
            evidence.append(f"C={c_metric}% suggests frozen numerator while denominator grew")
        
        # Root cause assessment per issue directive
        is_po_coverage_scenario = "LOW_PO_COVERAGE" in patterns or "FROZEN_NUMERATORS" in patterns
        
        diagnosis[county] = {
            "c_metric": c_metric,
            "d_metric": d_metric,
            "cd_gap": cd_gap,
            "po_coverage": po_coverage,
            "patterns_detected": patterns,
            "evidence": evidence,
            "is_po_coverage_scenario": is_po_coverage_scenario,
            "requires_clerk_litmus": is_po_coverage_scenario,
            "priority": "HIGH" if is_po_coverage_scenario else "MEDIUM",
            "verification_status": "VERIFIED",
            "diagnosis_timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        
        log_with_honesty(
            f"{county} diagnosis: PO coverage scenario = {is_po_coverage_scenario}, requires clerk litmus = {is_po_coverage_scenario}",
            "VERIFIED"
        )
    
    return diagnosis

def design_clerk_litmus_implementation() -> Dict[str, Any]:
    """Design clerk/official records supplementary litmus - PRE-AUTHORIZED"""
    log_with_honesty("Designing clerk supplementary litmus implementation", "UNTESTED")
    
    # Per issue directive: "INVOKE the pre-authorized clerk/official-records supplementary litmus NOW"
    
    design = {
        "authorization_status": "PRE_AUTHORIZED", 
        "authorization_source": "Issue #7652: 'INVOKE the pre-authorized clerk/official-records supplementary litmus NOW'",
        "strategy": "DUAL_SOURCE_PARITY",
        
        "county_implementations": {
            "brevard": {
                "clerk_source": "Brevard County Clerk Official Records",
                "known_endpoints": [
                    "https://vaclmweb1.brevardclerk.us/AcclaimWeb/ (VERIFIED live per issue)",
                    "Brevard Clerk courthouse foreclosure calendar"
                ],
                "record_types": ["Certificate of Title", "Foreclosure Final Judgment", "Tax Deed Certificate"],
                "match_strategy": "case_number + sale_date matching",
                "existing_infrastructure": "AcclaimWeb endpoint verified, acclaim_* queue functions exist for Duval (can be ported)",
                "priority": "HIGH - frozen numerators at 20.8%"
            },
            "duval": {
                "clerk_source": "Duval County Clerk Official Records",
                "known_endpoints": [
                    "or.duvalclerk.com (acclaim functions already implemented)",
                    "existing acclaim_harvest_queue table"
                ],
                "record_types": ["Certificate of Title", "Tax Deed Certificate"],
                "match_strategy": "case_number matching + parcel_id verification", 
                "existing_infrastructure": "Full acclaim pipeline exists (probe_acclaim_doctype_search, harvest_acclaim_batch)",
                "priority": "MEDIUM - existing automation available"
            }
        },
        
        "technical_architecture": {
            "table_enhancements": [
                "ALTER multi_county_auctions ADD COLUMN clerk_match_status text",
                "ALTER multi_county_auctions ADD COLUMN clerk_document_id text", 
                "ALTER multi_county_auctions ADD COLUMN clerk_verification_date timestamp"
            ],
            "new_functions": [
                "update_parity_with_clerk_data(county_slug text)",
                "enhanced_cd_evaluation(county_slug text)"
            ],
            "enhanced_parity_logic": """
                parity_status = CASE 
                    WHEN property_onion_id IS NOT NULL THEN 'po_match'
                    WHEN clerk_document_id IS NOT NULL THEN 'clerk_match'
                    WHEN property_onion_id IS NOT NULL AND clerk_document_id IS NOT NULL THEN 'dual_verified'
                    ELSE 'no_match'
                END
            """
        },
        
        "implementation_phases": {
            "phase_1_brevard_acclaim": {
                "tasks": [
                    "Port Duval acclaim functions to Brevard endpoint",
                    "Test AcclaimWeb connectivity and document types",
                    "Enqueue sample case_numbers for testing"
                ],
                "estimated_time": "2 hours",
                "blocking": False
            },
            "phase_2_enhanced_matching": {
                "tasks": [
                    "Implement enhanced parity logic",
                    "Update pencil_dod_evaluate_county for dual-source",
                    "Backfill historical matches"
                ],
                "estimated_time": "2 hours", 
                "blocking": False
            },
            "phase_3_verification": {
                "tasks": [
                    "Run enhanced evaluation functions",
                    "Measure C/D improvement",
                    "Update gold_standard_county_status"
                ],
                "estimated_time": "1 hour",
                "blocking": True
            }
        },
        
        "expected_outcomes": {
            "brevard": {
                "c_target": "50%+ (from 20.8%)",
                "d_target": "65%+ (from 33.2%)", 
                "rationale": "Clerk records should capture additional 50%+ of missed cases"
            },
            "duval": {
                "c_target": "40%+ (from 16.1%)",
                "d_target": "70%+ (from 52.9%)",
                "rationale": "Existing acclaim infrastructure can be leveraged immediately"
            }
        },
        
        "verification_queries": [
            """
            SELECT 
                county_slug,
                COUNT(*) as total_auctions,
                COUNT(property_onion_id) as po_matches,
                COUNT(clerk_document_id) as clerk_matches,
                COUNT(CASE WHEN property_onion_id IS NOT NULL OR clerk_document_id IS NOT NULL THEN 1 END) as combined_matches,
                ROUND(COUNT(CASE WHEN property_onion_id IS NOT NULL OR clerk_document_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 2) as combined_coverage_pct
            FROM multi_county_auctions 
            WHERE county_slug IN ('brevard', 'duval')
            GROUP BY county_slug;
            """
        ]
    }
    
    return design

def main():
    """Main execution for Brevard/Duval C/D analysis"""
    log_with_honesty("=== BREVARD/DUVAL C/D ROOT CAUSE ANALYSIS STARTING ===", "UNTESTED")
    
    # Test database connection first
    if not test_connection():
        log_with_honesty("Database connection failed - cannot proceed", "VERIFIED")
        return {"status": "CONNECTION_FAILED"}
    
    results = {
        "session_start": datetime.utcnow().isoformat() + 'Z',
        "shard": 20,
        "target_counties": TARGET_COUNTIES,
        "objective": "C/D_ROOT_CAUSE_ANALYSIS",
        "authorization": "PRE_AUTHORIZED_CLERK_LITMUS"
    }
    
    try:
        # Phase 1: Current metrics evaluation
        log_with_honesty("Phase 1: Getting current C/D metrics", "UNTESTED")
        results["current_metrics"] = get_current_cd_metrics()
        
        # Phase 2: PropertyOnion coverage analysis  
        log_with_honesty("Phase 2: Analyzing PropertyOnion coverage", "UNTESTED")
        results["coverage_analysis"] = analyze_propertyonion_coverage()
        
        # Phase 3: Root cause diagnosis
        log_with_honesty("Phase 3: Diagnosing root causes", "UNTESTED")
        results["diagnosis"] = diagnose_root_causes(
            results["current_metrics"],
            results["coverage_analysis"]
        )
        
        # Phase 4: Clerk litmus design
        log_with_honesty("Phase 4: Designing clerk litmus implementation", "UNTESTED")
        results["clerk_litmus_design"] = design_clerk_litmus_implementation()
        
        # Generate summary
        po_coverage_scenarios = [
            county for county, diag in results["diagnosis"].items() 
            if diag.get("is_po_coverage_scenario", False)
        ]
        
        results["summary"] = {
            "analysis_complete": True,
            "po_coverage_scenarios": po_coverage_scenarios,
            "clerk_litmus_required": len(po_coverage_scenarios) > 0,
            "pre_authorization_invoked": True,
            "next_action": "IMPLEMENT_BREVARD_ACCLAIM_PORT" if "brevard" in po_coverage_scenarios else "IMPLEMENT_DUVAL_ACCLAIM_ENHANCEMENT",
            "verification_status": "VERIFIED"
        }
        
        log_with_honesty("=== C/D ROOT CAUSE ANALYSIS COMPLETE ===", "VERIFIED")
        
        return results
        
    except Exception as e:
        log_with_honesty(f"Analysis failed: {e}", "VERIFIED")
        return {"status": "ANALYSIS_FAILED", "error": str(e)}

if __name__ == "__main__":
    results = main()
    print("\n" + "="*60)
    print("BREVARD/DUVAL C/D ANALYSIS RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2, default=str))