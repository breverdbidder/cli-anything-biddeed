#!/usr/bin/env python3
"""
SHARD-11 Priority #4: B RECONCILIATION - verified_outcomes anomaly

Per issue directive: "B RECONCILIATION — verified=8547 > closed_sold=6373 (134%). 
Refuter must find the double-count/denominator mismatch BEFORE any certify counts B. 
Anomalous PASS = not a PASS."

This issue affects multiple counties where verified_outcomes exceeds closed_sold,
creating anomalous B metrics >100%. Must reconcile before certification.

For SHARD-11 counties: manatee, bay, okeechobee, gadsden, wakulla

Usage:
  python scripts/shard11_b_reconciliation.py
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

SHARD11_COUNTIES = ['manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla']

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_b_status(county):
    """Audit current B metric status - VERIFIED approach with anomaly detection"""
    try:
        payload = {"county_name": county}
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            b_metric = evaluation.get('metric_b')
            b_grade = evaluation.get('grade_b')
            
            # Flag anomalous B metrics (>100%)
            is_anomalous = b_metric is not None and b_metric > 100
            
            audit_result = {
                "county": county,
                "b_metric": b_metric,
                "b_grade": b_grade,
                "is_anomalous": is_anomalous,
                "anomaly_severity": "CRITICAL" if is_anomalous else "NORMAL",
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                "verification_status": "VERIFIED"
            }
            
            status = "ANOMALOUS" if is_anomalous else "NORMAL"
            log(f"{county} B audit: {b_metric}% ({status}) - {'CRITICAL' if is_anomalous else b_grade}")
            return audit_result
        else:
            log(f"Failed to audit {county}: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing {county}: {e}", "ERROR")
        return None

def analyze_verified_vs_closed_counts(county):
    """Analyze verified_outcomes vs closed_sold counts for anomaly detection - VERIFIED approach"""
    try:
        # Query the B metric calculation components
        # This requires understanding the pencil_dod_criteria logic for B
        
        # Get total closed sales for county
        closed_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county_name": f"eq.{county}",
                "sale_status": "eq.SOLD",
                "limit": "1"
            },
            timeout=30
        )
        
        closed_count = 0
        if closed_response.status_code == 206:
            content_range = closed_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                closed_count = int(content_range.split('/')[-1])
        
        # Get verified outcomes count for county
        verified_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/verified_outcomes",
            headers={**HEADERS, "Prefer": "count=exact"},
            params={
                "select": "case_number",
                "county": f"eq.{county}",
                "limit": "1"
            },
            timeout=30
        )
        
        verified_count = 0
        if verified_response.status_code == 206:
            content_range = verified_response.headers.get('content-range', '')
            if content_range and '/' in content_range:
                verified_count = int(content_range.split('/')[-1])
        
        # Calculate ratio and detect anomalies
        ratio = verified_count / closed_count if closed_count > 0 else 0
        is_anomalous = ratio > 1.0
        
        analysis = {
            "county": county,
            "closed_sold_count": closed_count,
            "verified_outcomes_count": verified_count,
            "ratio": ratio,
            "ratio_percent": ratio * 100,
            "is_anomalous": is_anomalous,
            "anomaly_type": "DOUBLE_COUNT" if is_anomalous else "NORMAL",
            "sql_evidence": {
                "closed_query": f"SELECT COUNT(*) FROM multi_county_auctions WHERE county_name = '{county}' AND sale_status = 'SOLD'",
                "verified_query": f"SELECT COUNT(*) FROM verified_outcomes WHERE county = '{county}'"
            },
            "verification_status": "VERIFIED"
        }
        
        log(f"{county} count analysis: {verified_count} verified / {closed_count} closed = {ratio:.1%} {'ANOMALOUS' if is_anomalous else 'NORMAL'}")
        return analysis
        
    except Exception as e:
        log(f"Error analyzing verified vs closed for {county}: {e}", "ERROR")
        return None

def investigate_data_source_overlaps(county):
    """Investigate potential data source overlaps causing double-counting - INFERRED from data patterns"""
    try:
        # Check for multiple data sources in verified_outcomes
        sources_response = requests.get(
            f"{SUPABASE_URL}/rest/v1/verified_outcomes",
            headers=HEADERS,
            params={
                "select": "data_source,count",
                "county": f"eq.{county}",
                "limit": "100"
            },
            timeout=30
        )
        
        if sources_response.status_code == 200:
            outcomes = sources_response.json()
            
            # Analyze data sources
            source_counts = {}
            case_number_counts = {}
            
            for outcome in outcomes:
                source = outcome.get('data_source', 'UNKNOWN')
                case_number = outcome.get('case_number')
                
                source_counts[source] = source_counts.get(source, 0) + 1
                
                if case_number:
                    case_number_counts[case_number] = case_number_counts.get(case_number, 0) + 1
            
            # Find duplicate case numbers
            duplicates = {case_num: count for case_num, count in case_number_counts.items() if count > 1}
            
            investigation = {
                "county": county,
                "total_verified_outcomes": len(outcomes),
                "data_sources": source_counts,
                "duplicate_case_numbers": len(duplicates),
                "sample_duplicates": list(duplicates.items())[:10],
                "potential_causes": [
                    "Multiple data sources for same case (PropertyOnion + Clerk)",
                    "Duplicate ingestion from same source",
                    "Case number format inconsistencies",
                    "Temporal overlaps in data collection"
                ],
                "sql_duplicate_query": f"""
                SELECT case_number, data_source, COUNT(*) as occurrence_count
                FROM verified_outcomes 
                WHERE county = '{county}'
                GROUP BY case_number, data_source
                HAVING COUNT(*) > 1
                ORDER BY occurrence_count DESC
                """,
                "verification_status": "INFERRED"
            }
            
            log(f"{county} data source investigation: {len(source_counts)} sources, {len(duplicates)} duplicate cases")
            return investigation
        else:
            log(f"Failed to investigate data sources for {county}: {sources_response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error investigating data sources for {county}: {e}", "ERROR")
        return None

def design_reconciliation_strategy():
    """Design reconciliation strategy for B metric anomalies - FRAMEWORK per issue directive"""
    
    # Per issue: "Refuter must find the double-count/denominator mismatch BEFORE any certify counts B"
    
    strategy = {
        "reconciliation_principle": "Find and fix double-count/denominator mismatch before certification",
        "investigation_steps": [
            "1. Audit verified_outcomes vs closed_sold counts per county",
            "2. Identify data source overlaps and duplicates",
            "3. Map case_number formats across data sources",
            "4. Find temporal collection overlaps",
            "5. Implement deduplication logic with source priority"
        ],
        "deduplication_framework": {
            "source_priority": [
                "1. Clerk official records (highest confidence)",
                "2. PropertyOnion verified data", 
                "3. Automated scraper results",
                "4. Legacy data sources"
            ],
            "deduplication_sql": """
            WITH ranked_outcomes AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY case_number, county 
                        ORDER BY 
                            CASE data_source
                                WHEN 'clerk_official' THEN 1
                                WHEN 'propertyonion_verified' THEN 2  
                                WHEN 'automated_scraper' THEN 3
                                ELSE 4
                            END,
                            created_at DESC
                    ) as rn
                FROM verified_outcomes
            )
            DELETE FROM verified_outcomes 
            WHERE (case_number, county, created_at) IN (
                SELECT case_number, county, created_at 
                FROM ranked_outcomes 
                WHERE rn > 1
            )
            """,
            "verification_query": """
            SELECT 
                county,
                COUNT(*) as total_verified,
                COUNT(DISTINCT case_number) as unique_cases,
                COUNT(*) - COUNT(DISTINCT case_number) as duplicate_count
            FROM verified_outcomes
            GROUP BY county
            """
        },
        "denominator_validation": {
            "approach": "Ensure closed_sold count matches actual sale records",
            "validation_sql": """
            SELECT 
                county_name,
                COUNT(*) as multi_county_auctions_sold,
                (SELECT COUNT(*) FROM verified_outcomes WHERE county = mca.county_name) as verified_count,
                ROUND(100.0 * (SELECT COUNT(*) FROM verified_outcomes WHERE county = mca.county_name) / COUNT(*), 2) as b_metric
            FROM multi_county_auctions mca
            WHERE sale_status = 'SOLD'
            GROUP BY county_name
            HAVING COUNT(*) > 0
            """
        },
        "certification_gates": [
            "No verified_outcomes count > closed_sold count for any county",
            "B metric ≤ 100% for all counties before certification",
            "Deduplication audit trail with source priority evidence",
            "Independent verification of denominator calculations"
        ],
        "verification_status": "FRAMEWORK_READY"
    }
    
    log("B reconciliation strategy designed per issue directive")
    return strategy

def execute_b_reconciliation():
    """Execute B reconciliation for SHARD-11 counties"""
    log("🔢 SHARD-11 B RECONCILIATION Implementation Starting")
    
    results = {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "priority": "B_RECONCILIATION",
        "counties": SHARD11_COUNTIES,
        "b_audits": {},
        "count_analysis": {},
        "source_investigations": {},
        "reconciliation_strategy": None,
        "sql_verification_evidence": []
    }
    
    # Phase 1: Audit current B status for anomalies
    for county in SHARD11_COUNTIES:
        audit = audit_current_b_status(county)
        if audit:
            results["b_audits"][county] = audit
            results["sql_verification_evidence"].append({
                "query": audit["sql_evidence"],
                "county": county,
                "purpose": "B metric anomaly detection"
            })
    
    # Phase 2: Analyze verified vs closed counts
    for county in SHARD11_COUNTIES:
        count_analysis = analyze_verified_vs_closed_counts(county)
        if count_analysis:
            results["count_analysis"][county] = count_analysis
            results["sql_verification_evidence"].extend([
                {
                    "query": count_analysis["sql_evidence"]["closed_query"],
                    "county": county,
                    "purpose": "Closed sales count verification"
                },
                {
                    "query": count_analysis["sql_evidence"]["verified_query"],
                    "county": county,
                    "purpose": "Verified outcomes count verification"
                }
            ])
    
    # Phase 3: Investigate data source overlaps
    for county in SHARD11_COUNTIES:
        investigation = investigate_data_source_overlaps(county)
        if investigation:
            results["source_investigations"][county] = investigation
    
    # Phase 4: Design reconciliation strategy
    results["reconciliation_strategy"] = design_reconciliation_strategy()
    
    # Summary analysis
    anomalous_counties = []
    counties_needing_dedup = []
    
    for county in SHARD11_COUNTIES:
        audit = results["b_audits"].get(county, {})
        count_analysis = results["count_analysis"].get(county, {})
        investigation = results["source_investigations"].get(county, {})
        
        if audit.get("is_anomalous"):
            anomalous_counties.append(county)
            
        if investigation.get("duplicate_case_numbers", 0) > 0:
            counties_needing_dedup.append(county)
    
    results["summary"] = {
        "anomalous_counties": anomalous_counties,
        "counties_needing_dedup": counties_needing_dedup,
        "total_anomalies": len(anomalous_counties),
        "total_duplicates": len(counties_needing_dedup),
        "certification_blockers": {
            "anomalous_b_metrics": len(anomalous_counties) > 0,
            "data_source_duplicates": len(counties_needing_dedup) > 0
        },
        "next_steps": [
            "Execute deduplication framework for counties with duplicates",
            "Validate denominator calculations for anomalous counties", 
            "Re-run B evaluation after reconciliation",
            "Confirm B ≤ 100% before any certification"
        ]
    }
    
    log("✅ B RECONCILIATION analysis complete")
    log(f"Anomalous counties: {len(anomalous_counties)}/{len(SHARD11_COUNTIES)}")
    log(f"Counties needing deduplication: {len(counties_needing_dedup)}/{len(SHARD11_COUNTIES)}")
    
    return results

def main():
    """Main execution for B reconciliation"""
    try:
        results = execute_b_reconciliation()
        
        # Save results for verification
        with open("/tmp/shard11_b_reconciliation_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print("\n" + "="*60)
        print("SHARD-11 B RECONCILIATION RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2, default=str))
        
        return results
        
    except Exception as e:
        log(f"CRITICAL ERROR: {e}", "ERROR")
        return None

if __name__ == "__main__":
    main()