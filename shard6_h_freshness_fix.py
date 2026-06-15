#!/usr/bin/env python3
"""
SHARD-6 Priority #3: H FRESHNESS - Fix SLA breaches

Per county metrics: bay (415h vs 48h SLA breach)

Addresses H letter failures for SHARD-6 counties where last_seen > 48h SLA

Usage:
  python shard6_h_freshness_fix.py [county_name]
  python shard6_h_freshness_fix.py  # All counties
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
H_SLA_THRESHOLD = 48  # hours

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_h_metrics(county: str) -> Optional[Dict]:
    """Audit current H (freshness) metrics - VERIFIED approach"""
    try:
        log(f"Auditing H metrics for {county}...")
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json={"county_param": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse H metric from evaluation result
            h_data = None
            if isinstance(result, list):
                for item in result:
                    if item.get('letter') == 'H':
                        h_data = item
                        break
            
            audit_result = {
                "county": county,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "h_metric": h_data.get('metric') if h_data else None,
                "h_detail": h_data.get('detail') if h_data else None,
                "h_pass": h_data.get('pass') if h_data else False,
                "h_threshold": h_data.get('threshold') if h_data else None,
                "sla_breach": (h_data.get('metric') or 0) > H_SLA_THRESHOLD,
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                "verification_status": "VERIFIED"
            }
            
            breach_status = "🚨 BREACH" if audit_result['sla_breach'] else "✅ OK"
            log(f"{county} H metric: {audit_result['h_metric']}h {breach_status} (SLA: {H_SLA_THRESHOLD}h)")
            return audit_result
        else:
            log(f"Failed to audit {county}: HTTP {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing {county}: {e}", "ERROR")
        return None

def analyze_scraper_configuration(county: str) -> Dict:
    """Analyze scraper configuration and last execution for county"""
    try:
        log(f"Analyzing scraper configuration for {county}...")
        
        # Check if county is configured in scraper systems
        # This is INFERRED analysis based on patterns in other shards
        
        analysis = {
            "county": county,
            "configuration_status": "INFERRED - needs verification",
            "probable_sources": [],
            "analysis_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Based on county characteristics, suggest probable scraper sources
        if county == "bay":
            analysis["probable_sources"] = [
                "realauction.com Bay County FL foreclosures",
                "Bay County Clerk official records",
                "Property appraiser Bay County"
            ]
        elif county == "hillsborough":
            analysis["probable_sources"] = [
                "realauction.com Hillsborough County FL foreclosures", 
                "Hillsborough County Clerk official records"
            ]
        elif county == "martin":
            analysis["probable_sources"] = [
                "realauction.com Martin County FL foreclosures",
                "Martin County Clerk official records"
            ]
        elif county in ["calhoun", "liberty"]:
            analysis["probable_sources"] = [
                f"realauction.com {county.title()} County FL foreclosures",
                f"{county.title()} County Clerk official records",
                "Note: Small counties may have infrequent auction schedules"
            ]
        
        return analysis
        
    except Exception as e:
        log(f"Error analyzing scraper config for {county}: {e}", "ERROR")
        return {"error": str(e)}

def check_last_data_ingestion(county: str) -> Dict:
    """Check when data was last ingested for the county"""
    try:
        log(f"Checking last data ingestion for {county}...")
        
        # Get most recent auction record for county
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "created_at,auction_date,source_platform",
                "county": f"eq.{county}",
                "order": "created_at.desc",
                "limit": "1"
            }
        )
        
        if response.status_code == 200:
            results = response.json()
            if results:
                latest = results[0]
                created_at = latest.get('created_at')
                auction_date = latest.get('auction_date')
                source_platform = latest.get('source_platform')
                
                return {
                    "county": county,
                    "last_ingestion": created_at,
                    "last_auction_date": auction_date,
                    "source_platform": source_platform,
                    "sql_evidence": f"SELECT created_at FROM multi_county_auctions WHERE county='{county}' ORDER BY created_at DESC LIMIT 1",
                    "verification_status": "VERIFIED"
                }
            else:
                return {
                    "county": county,
                    "last_ingestion": None,
                    "error": "No auction records found",
                    "verification_status": "VERIFIED"
                }
        else:
            log(f"Failed to check ingestion for {county}: HTTP {response.status_code}", "ERROR")
            return {"error": f"HTTP {response.status_code}"}
            
    except Exception as e:
        log(f"Error checking ingestion for {county}: {e}", "ERROR")
        return {"error": str(e)}

def implement_freshness_fix_plan(county: str) -> Dict:
    """Create implementation plan for fixing H freshness issues"""
    try:
        log(f"Creating freshness fix plan for {county}...")
        
        # Per WIRING MANDATE - fixes must be scheduled, not just implemented
        fix_plan = {
            "county": county,
            "fix_type": "H_FRESHNESS_SLA_RESTORATION",
            "target_sla": f"<{H_SLA_THRESHOLD}h",
            "implementation_steps": [
                f"1. Verify {county} county configuration in cairn_multi_county_scraper.py",
                f"2. Check {county} scraper endpoint availability and authentication",
                f"3. Ensure {county} is included in scheduled scraper runs (pg_cron/GHA)",
                f"4. Implement error handling for {county} scraper failures",
                f"5. Add {county} to monitoring/alerting for SLA breaches",
                f"6. Test manual scraper execution for {county}",
                f"7. Verify automatic scheduling works for {county}"
            ],
            "probable_root_causes": [
                f"{county} not configured in scraper rotation",
                f"{county} scraper endpoint changed/authentication failed",
                f"{county} scraper failing silently",
                f"{county} excluded from scheduled runs"
            ],
            "wiring_requirements": [
                f"Schedule {county} scraper in cairn rotation",
                f"Verify {county} in pg_cron scraper schedule",
                f"Add {county} to monitoring dashboard"
            ],
            "honesty_marker": "INFERRED - implementation plan created but not executed",
            "estimated_impact": f"Restore {county} H metric from breach to <{H_SLA_THRESHOLD}h",
            "priority": "HIGH" if county == "bay" else "MEDIUM",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        log(f"{county} freshness fix plan created")
        return fix_plan
        
    except Exception as e:
        log(f"Error creating fix plan for {county}: {e}", "ERROR")
        return {"error": str(e)}

def execute_freshness_fix_session():
    """Execute H freshness fix session for SHARD-6"""
    
    log("Starting SHARD-6 H Freshness Fix Session", "INFO")
    log(f"Counties: {SHARD6_COUNTIES}")
    log(f"SLA Threshold: {H_SLA_THRESHOLD}h")
    
    session_report = {
        "session_id": "shard6-h-freshness-fix",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties": SHARD6_COUNTIES,
        "sla_threshold": H_SLA_THRESHOLD,
        "h_audits": {},
        "scraper_analysis": {},
        "ingestion_checks": {},
        "fix_plans": {}
    }
    
    # Phase 1: Audit current H metrics
    log("Phase 1: Auditing current H metrics...")
    for county in SHARD6_COUNTIES:
        audit_result = audit_current_h_metrics(county)
        if audit_result:
            session_report["h_audits"][county] = audit_result
    
    # Phase 2: Analyze scraper configurations
    log("Phase 2: Analyzing scraper configurations...")
    for county in SHARD6_COUNTIES:
        config_analysis = analyze_scraper_configuration(county)
        session_report["scraper_analysis"][county] = config_analysis
    
    # Phase 3: Check last data ingestion
    log("Phase 3: Checking last data ingestion...")
    for county in SHARD6_COUNTIES:
        ingestion_check = check_last_data_ingestion(county)
        session_report["ingestion_checks"][county] = ingestion_check
    
    # Phase 4: Create fix plans
    log("Phase 4: Creating fix plans...")
    for county in SHARD6_COUNTIES:
        fix_plan = implement_freshness_fix_plan(county)
        session_report["fix_plans"][county] = fix_plan
    
    # Generate summary
    sla_breaches = sum(1 for audit in session_report["h_audits"].values() if audit.get("sla_breach"))
    
    session_report["summary"] = {
        "counties_audited": len(session_report["h_audits"]),
        "sla_breaches": sla_breaches,
        "critical_counties": [k for k, v in session_report["h_audits"].items() if v.get("sla_breach")],
        "next_phase": "Implement scraper configuration fixes",
        "completion_status": "ANALYSIS_COMPLETE"
    }
    
    log(f"SHARD-6 H Freshness Fix session complete - {sla_breaches} SLA breaches found", "INFO")
    return session_report

def print_session_report(report: Dict):
    """Print formatted session report"""
    
    print("\n" + "="*70)
    print("SHARD-6 H FRESHNESS FIX SESSION REPORT")
    print("="*70)
    print(f"Session ID: {report['session_id']}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"SLA Threshold: {report['sla_threshold']}h")
    
    print(f"\nCURRENT H METRICS:")
    for county, audit in report['h_audits'].items():
        h_metric = audit['h_metric']
        h_pass = "✅" if audit['h_pass'] else "❌"
        breach = "🚨" if audit['sla_breach'] else "✅"
        print(f"  {county}: {h_metric}h {breach} {h_pass}")
    
    print(f"\nLAST DATA INGESTION:")
    for county, check in report['ingestion_checks'].items():
        if 'error' not in check:
            last_ingestion = check['last_ingestion']
            source = check.get('source_platform', 'unknown')
            print(f"  {county}: {last_ingestion} ({source})")
        else:
            print(f"  {county}: ERROR - {check['error']}")
    
    print(f"\nFIX PLANS:")
    for county, plan in report['fix_plans'].items():
        if 'error' not in plan:
            priority = plan.get('priority', 'MEDIUM')
            steps = len(plan.get('implementation_steps', []))
            print(f"  {county}: {priority} priority, {steps} steps planned")
        else:
            print(f"  {county}: ERROR - {plan['error']}")
    
    print(f"\nSUMMARY:")
    summary = report['summary']
    print(f"  Counties audited: {summary['counties_audited']}")
    print(f"  SLA breaches: {summary['sla_breaches']}")
    print(f"  Critical counties: {summary.get('critical_counties', [])}")
    print(f"  Next phase: {summary['next_phase']}")
    
    print("\n" + "="*70)

def main():
    """Main execution function"""
    import sys
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in SHARD6_COUNTIES:
            # Single county execution
            audit = audit_current_h_metrics(county)
            ingestion = check_last_data_ingestion(county)
            plan = implement_freshness_fix_plan(county)
            
            result = {
                "county": county,
                "audit": audit,
                "ingestion": ingestion,
                "plan": plan
            }
            print(json.dumps(result, indent=2))
        else:
            print(f"Error: {county} not in SHARD-6 counties {SHARD6_COUNTIES}")
    else:
        # Full session execution
        report = execute_freshness_fix_session()
        print_session_report(report)
        
        # Save report
        with open('/tmp/shard6_h_freshness_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        log("Report saved to /tmp/shard6_h_freshness_report.json")

if __name__ == "__main__":
    main()