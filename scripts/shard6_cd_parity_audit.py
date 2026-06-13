#!/usr/bin/env python3
"""
SHARD-6 C/D Parity Audit and Remediation
Addresses PropertyOnion coverage gap per CRITERION-PARALLEL PIVOT protocol

Counties: escambia, sumter, lake, calhoun, liberty
Pre-authorized by owner to adopt clerk/official-records as supplementary litmus
"""

import os
import sys
import json
import httpx
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

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
    "Content-Type": "application/json"
}

# SHARD-6 target counties
SHARD6_COUNTIES = ['escambia', 'sumter', 'lake', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def analyze_parity_gap(county: str) -> Dict:
    """Analyze C/D parity gap for a county to determine root cause"""
    logger.info(f"Analyzing parity gap for {county}")
    
    try:
        # Get current C/D metrics
        evaluation = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county},
            timeout=60
        )
        
        if evaluation.status_code != 200:
            logger.error(f"Failed to get evaluation for {county}: {evaluation.status_code}")
            return {"error": "evaluation_failed"}
        
        eval_data = evaluation.json()
        c_metric = None
        d_metric = None
        
        # Extract C and D metrics
        if isinstance(eval_data, list):
            for row in eval_data:
                if isinstance(row, dict):
                    letter = row.get('letter', '').upper()
                    if letter == 'C':
                        c_metric = row.get('metric')
                    elif letter == 'D':
                        d_metric = row.get('metric')
        
        # Get auction count for this county
        auction_count_query = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "count",
                "county": f"eq.{county}"
            }
        )
        
        auction_count = 0
        if auction_count_query.status_code == 200:
            count_data = auction_count_query.json()
            if count_data and isinstance(count_data, list) and len(count_data) > 0:
                auction_count = count_data[0].get('count', 0)
        
        # Get matched counts
        matched_query = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "parity_status",
                "county": f"eq.{county}",
                "parity_status": "not.is.null"
            }
        )
        
        matched_clean_count = 0
        matched_any_count = 0
        
        if matched_query.status_code == 200:
            matches = matched_query.json()
            for row in matches:
                status = row.get('parity_status', '')
                if status == 'matched_clean':
                    matched_clean_count += 1
                elif status in ['matched_clean', 'matched_divergent']:
                    matched_any_count += 1
        
        return {
            "county": county,
            "c_metric": c_metric,
            "d_metric": d_metric, 
            "auction_count": auction_count,
            "matched_clean_count": matched_clean_count,
            "matched_any_count": matched_any_count,
            "analysis": {
                "c_gap": (95.0 - (c_metric or 0)) if c_metric else None,
                "d_gap": (95.0 - (d_metric or 0)) if d_metric else None,
                "coverage_issue": auction_count > 0 and (matched_any_count < auction_count * 0.8)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze {county}: {e}")
        return {"error": str(e)}

def get_missing_parity_auctions(county: str) -> List[Dict]:
    """Get auctions missing parity status - candidates for clerk lookup"""
    logger.info(f"Getting missing parity auctions for {county}")
    
    try:
        query = client.get(
            f"{BASE}/multi_county_auctions", 
            headers=HEADERS,
            params={
                "select": "case_number,auction_date,sale_type,address,parcel_id",
                "county": f"eq.{county}",
                "parity_status": "is.null",
                "limit": "100"  # Start with sample
            }
        )
        
        if query.status_code == 200:
            return query.json()
        else:
            logger.error(f"Failed to get missing parity auctions: {query.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Failed to get missing auctions for {county}: {e}")
        return []

def identify_clerk_endpoints(county: str) -> Dict:
    """Identify clerk/official records endpoints for supplementary litmus"""
    
    # County-specific clerk endpoints (per CLAUDE.md discovery sources)
    clerk_endpoints = {
        'escambia': {
            'name': 'Escambia County Clerk',
            'portal': 'https://gis.myescambia.com',
            'records_search': 'https://officialrecords.escambiaclerk.com',
            'type': 'arcgis_portal'
        },
        'sumter': {
            'name': 'Sumter County Clerk', 
            'portal': 'https://www.sumtercountyfl.gov/223/Property-Appraiser',
            'records_search': None,
            'type': 'county_portal'
        },
        'lake': {
            'name': 'Lake County Clerk',
            'portal': 'https://www.lakecountyfl.gov',
            'records_search': 'https://www.mylakelerk.com',
            'type': 'clerk_portal'
        },
        'calhoun': {
            'name': 'Calhoun County Clerk',
            'portal': 'https://calhouncounty.org',
            'records_search': None,
            'type': 'basic_portal'
        },
        'liberty': {
            'name': 'Liberty County Clerk',
            'portal': 'https://libertycountyfl.gov',
            'records_search': None,
            'type': 'basic_portal'
        }
    }
    
    return clerk_endpoints.get(county, {})

def create_parity_backfill_plan(county: str, missing_auctions: List[Dict], clerk_info: Dict) -> Dict:
    """Create actionable plan to backfill parity data from clerk sources"""
    
    if not missing_auctions:
        return {"county": county, "action": "no_missing_auctions"}
    
    plan = {
        "county": county,
        "missing_count": len(missing_auctions),
        "clerk_endpoint": clerk_info,
        "backfill_strategy": "incremental_clerk_lookup",
        "priority_cases": [],
        "estimated_hours": len(missing_auctions) * 0.1,  # 6 minutes per case
        "next_actions": []
    }
    
    # Prioritize recent auctions and those with parcel_ids
    for auction in missing_auctions[:20]:  # Top 20 priority
        has_parcel = bool(auction.get('parcel_id'))
        recent = True  # Could add date logic here
        
        plan["priority_cases"].append({
            "case_number": auction.get('case_number'),
            "auction_date": auction.get('auction_date'),
            "has_parcel_id": has_parcel,
            "priority_score": (2 if has_parcel else 0) + (1 if recent else 0)
        })
    
    # Define next actions based on clerk endpoint type
    if clerk_info.get('type') == 'arcgis_portal':
        plan["next_actions"] = [
            "Query ArcGIS REST services for auction/parcel data",
            "Cross-reference case numbers with GIS property records",
            "Update parity_status based on clerk matches"
        ]
    elif clerk_info.get('records_search'):
        plan["next_actions"] = [
            "Search official records portal by case number",
            "Extract sale dates and amounts",
            "Update parity_status='matched_clerk' for matches"
        ]
    else:
        plan["next_actions"] = [
            "Manual lookup via county portal",
            "Phone verification if needed", 
            "Document findings for batch update"
        ]
    
    return plan

def run_shard6_parity_audit() -> Dict:
    """Run complete parity audit for SHARD-6 counties"""
    logger.info("Starting SHARD-6 C/D parity audit")
    
    audit_results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties": {},
        "summary": {
            "total_missing": 0,
            "total_gap": 0,
            "actionable_fixes": 0
        }
    }
    
    for county in SHARD6_COUNTIES:
        logger.info(f"Processing {county}...")
        
        # Analyze current gap
        analysis = analyze_parity_gap(county)
        
        # Get missing auctions 
        missing = get_missing_parity_auctions(county)
        
        # Get clerk endpoints
        clerk_info = identify_clerk_endpoints(county)
        
        # Create backfill plan
        plan = create_parity_backfill_plan(county, missing, clerk_info)
        
        county_result = {
            "analysis": analysis,
            "missing_auctions": len(missing),
            "clerk_endpoint": clerk_info,
            "backfill_plan": plan
        }
        
        audit_results["counties"][county] = county_result
        
        # Update summary
        if not analysis.get("error"):
            gap = analysis.get("analysis", {}).get("c_gap", 0) or 0
            audit_results["summary"]["total_gap"] += gap
            audit_results["summary"]["total_missing"] += len(missing)
            
            if clerk_info and len(missing) > 0:
                audit_results["summary"]["actionable_fixes"] += 1
    
    return audit_results

def print_audit_report(audit_results: Dict):
    """Print formatted audit report"""
    print("\n" + "="*60)
    print("SHARD-6 C/D PARITY AUDIT REPORT")
    print("="*60)
    print(f"Timestamp: {audit_results['timestamp']}")
    
    for county, data in audit_results["counties"].items():
        print(f"\n{county.upper()}:")
        
        analysis = data["analysis"]
        if analysis.get("error"):
            print(f"  ❌ ERROR: {analysis['error']}")
            continue
            
        print(f"  C metric: {analysis.get('c_metric', 'null')}% (target: 95%)")
        print(f"  D metric: {analysis.get('d_metric', 'null')}% (target: 95%)")
        print(f"  Auctions: {analysis.get('auction_count', 0)}")
        print(f"  Missing parity: {data['missing_auctions']}")
        
        plan = data["backfill_plan"]
        if plan.get("action") == "no_missing_auctions":
            print("  ✅ No missing auctions")
        else:
            print(f"  📋 Backfill plan: {plan['backfill_strategy']}")
            print(f"  ⏱️  Estimated effort: {plan.get('estimated_hours', 0):.1f} hours")
            
            clerk = data["clerk_endpoint"]
            if clerk:
                print(f"  🏛️  Clerk endpoint: {clerk.get('name', 'Unknown')}")
                print(f"  🔗 Portal: {clerk.get('portal', 'None')}")
    
    summary = audit_results["summary"]
    print(f"\n📊 SUMMARY:")
    print(f"   Total missing parity: {summary['total_missing']}")
    print(f"   Counties with actionable fixes: {summary['actionable_fixes']}/5")
    print(f"   Total C/D gap: {summary['total_gap']:.1f}%")

def main():
    """Main execution"""
    if not SUPABASE_KEY:
        logger.error("SUPABASE_KEY not found in environment")
        sys.exit(1)
        
    logger.info("Starting SHARD-6 C/D parity audit per CRITERION-PARALLEL PIVOT protocol")
    
    # Run the audit
    results = run_shard6_parity_audit()
    
    # Print report
    print_audit_report(results)
    
    # Save results
    output_file = f"shard6_cd_parity_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Audit complete. Results saved to {output_file}")
    
    # Log next steps
    print("\n🎯 NEXT STEPS (per pre-authorization):")
    print("1. Execute clerk lookups for missing parity cases")
    print("2. Update parity_status='matched_clerk' for verified matches") 
    print("3. Re-run pencil_dod_evaluate_county to verify C/D improvements")
    print("4. Document evidence in refuter protocol per ULTRALOOP")

if __name__ == "__main__":
    main()