#!/usr/bin/env python3
"""
SHARD-3 C/D Parity Analysis - PropertyOnion vs Court Records Gap Analysis
GOLD STANDARD SESSION 24 - SHIP-TO-MAIN

Per issue brief: "C/D ROOT CAUSE — numerators frozen (~4.1K/6.6K) while denominator grew 33%%. 
This IS the PropertyOnion-coverage scenario: INVOKE the pre-authorized clerk/official-records 
supplementary litmus NOW. Run the parity audit as the ULTRALOOP refuter step, document evidence, 
adopt, backfill matches."

Target counties: broward, sumter, lake, walton, jefferson

Current C/D metrics from brief:
- broward: C=19.4% (5836/30109), D=47.7% (14364/30109) 
- sumter: C=0.0% (0/1), D=100.0% (1/1)
- lake: C=17.3% (529/3063), D=54.0% (1654/3063) 
- walton: C=15.1% (176/1169), D=63.0% (736/1169)
- jefferson: C=null, D=null (no auctions)

Purpose: Identify PropertyOnion source coverage gaps and recommend court records supplementation

Usage:
  python scripts/shard3_cd_parity_analysis.py
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import re

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

# SHARD-3 target counties  
TARGET_COUNTIES = ['broward', 'sumter', 'lake', 'walton', 'jefferson']

# Expected PropertyOnion patterns for case numbers
PROPERTYONION_PATTERNS = [
    r'^PO-\d+$',           # Standard PO-123456
    r'^PROP-\d+$',         # Alternative format
    r'^PO\d+$',            # Without dash
    r'PropertyOnion',       # Contains text
]

# Court case number patterns by county
COURT_CASE_PATTERNS = {
    'broward': [
        r'^\d{2}-\d{4}-CA-\d{6}-\w{2,4}-\w{2}$',  # 05-2024-CA-123456-XXCA-BC
        r'^\d{2}-\d{4}-CC-\d+$',                   # 05-2024-CC-123456
        r'^\d{2}-\d{4}-FC-\d+$',                   # Foreclosure format
    ],
    'sumter': [
        r'^\d{4}-CA-\d+-\w{1,2}$',                 # 2024-CA-123-A
        r'^\d{2}-\d{4}-CA-\d+$',                   # Standard format
    ],
    'lake': [
        r'^\d{2}-\d{4}-CA-\d{6}-\w+$',            # Similar to Broward
        r'^\d{2}-CA-\d{4}-\d+$',                   # Alternative format
    ],
    'walton': [
        r'^\d{2}-\d{4}-CA-\d+$',                   # Standard format
        r'^\d{4}-CA-\d+-\w+$',                     # Year first
    ],
    'jefferson': [
        r'^\d{2}-\d{4}-CA-\d+$',                   # Standard format
        r'^\d{4}-\d+-CA$',                         # Alternative
    ]
}

client = httpx.Client(timeout=60)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def verify_database_connection():
    """Test Supabase connection"""
    try:
        response = client.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"})
        if response.status_code == 200:
            log("✅ Database connection verified")
            return True
        else:
            log(f"❌ Connection failed: {response.status_code} - {response.text}", "ERROR")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}", "ERROR")
        return False

def classify_case_number(case_number: str, county: str) -> Dict[str, any]:
    """Classify a case number as PropertyOnion, Court, or Unknown"""
    if not case_number or case_number.strip() == "":
        return {"type": "empty", "pattern": None, "confidence": 1.0}
    
    case_clean = case_number.strip().upper()
    
    # Check PropertyOnion patterns
    for pattern in PROPERTYONION_PATTERNS:
        if re.match(pattern, case_clean):
            return {"type": "propertyonion", "pattern": pattern, "confidence": 0.95}
    
    # Check court case patterns for this county
    court_patterns = COURT_CASE_PATTERNS.get(county, [])
    for pattern in court_patterns:
        if re.match(pattern, case_clean):
            return {"type": "court", "pattern": pattern, "confidence": 0.9}
    
    # Heuristic checks
    if "PO" in case_clean or "PROP" in case_clean:
        return {"type": "propertyonion", "pattern": "heuristic", "confidence": 0.8}
    
    if re.match(r'^\d{2}-\d{4}-', case_clean):  # Common court format start
        return {"type": "court", "pattern": "heuristic", "confidence": 0.7}
    
    return {"type": "unknown", "pattern": None, "confidence": 0.5}

def analyze_county_parity(county: str) -> Dict[str, any]:
    """Analyze C/D parity for a single county"""
    log(f"🔍 Analyzing C/D parity for {county}")
    
    try:
        # Get multi_county_auctions for this county
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "case_number,county,sale_date,opening_bid,sold_amount,property_address,parcel_id",
                "county": f"eq.{county}",
                "limit": "5000"  # Reasonable sample size
            }
        )
        
        if response.status_code != 200:
            log(f"❌ Failed to get auctions for {county}: {response.status_code}", "ERROR")
            return {"error": f"HTTP {response.status_code}", "county": county}
        
        auctions = response.json()
        log(f"{county}: Retrieved {len(auctions)} auction records")
        
        if not auctions:
            return {
                "county": county,
                "total_auctions": 0,
                "analysis": "No auction data found",
                "recommendation": "Check data ingestion for this county"
            }
        
        # Classify case numbers
        po_cases = []
        court_cases = []
        unknown_cases = []
        empty_cases = []
        
        for auction in auctions:
            case_num = auction.get('case_number', '')
            classification = classify_case_number(case_num, county)
            
            auction_data = {
                **auction,
                "classification": classification
            }
            
            if classification["type"] == "propertyonion":
                po_cases.append(auction_data)
            elif classification["type"] == "court":
                court_cases.append(auction_data)
            elif classification["type"] == "empty":
                empty_cases.append(auction_data)
            else:
                unknown_cases.append(auction_data)
        
        total = len(auctions)
        po_count = len(po_cases)
        court_count = len(court_cases)
        unknown_count = len(unknown_cases)
        empty_count = len(empty_cases)
        
        # Check matching data availability
        with_sold_amount = sum(1 for a in auctions if a.get('sold_amount'))
        with_parcel_id = sum(1 for a in auctions if a.get('parcel_id'))
        with_address = sum(1 for a in auctions if a.get('property_address'))
        
        analysis = {
            "county": county,
            "total_auctions": total,
            "case_number_breakdown": {
                "propertyonion_cases": po_count,
                "court_cases": court_count,
                "unknown_cases": unknown_count,
                "empty_cases": empty_count,
                "propertyonion_pct": round(po_count * 100 / total, 1) if total > 0 else 0,
                "court_pct": round(court_count * 100 / total, 1) if total > 0 else 0
            },
            "matching_data_availability": {
                "with_sold_amount": with_sold_amount,
                "with_parcel_id": with_parcel_id, 
                "with_property_address": with_address,
                "sold_amount_pct": round(with_sold_amount * 100 / total, 1) if total > 0 else 0,
                "parcel_id_pct": round(with_parcel_id * 100 / total, 1) if total > 0 else 0,
                "address_pct": round(with_address * 100 / total, 1) if total > 0 else 0
            },
            "parity_impact_analysis": {},
            "recommendations": []
        }
        
        # Analyze parity impact
        if po_count > court_count * 2:  # Majority PropertyOnion
            analysis["parity_impact_analysis"] = {
                "primary_source": "PropertyOnion",
                "coverage_limitation": "High PropertyOnion dependency limits court record matching",
                "c_d_ceiling": f"C/D metrics ceiling due to {po_count} PropertyOnion cases that cannot match official records",
                "gap_estimate": f"{po_count} cases need alternative matching strategy"
            }
            
            analysis["recommendations"].extend([
                "URGENT: Implement parcel_id + address matching for PropertyOnion cases",
                "Build court record supplemental pipeline for date-range enumeration",
                "Consider tax deed record crosswalk for sold_amount verification"
            ])
        
        elif court_count > 0:
            analysis["parity_impact_analysis"] = {
                "primary_source": "Mixed court + PropertyOnion",
                "coverage_potential": f"{court_count} court cases can match official records",
                "optimization_target": f"Focus C/D improvements on {court_count} court-format cases first"
            }
            
            analysis["recommendations"].extend([
                "Optimize official record matching for court-format cases",
                "Develop parcel-based matching for PropertyOnion cases as secondary"
            ])
        
        else:
            analysis["parity_impact_analysis"] = {
                "primary_source": "Unknown/Empty",
                "data_quality_issue": "Insufficient case number data for meaningful matching",
                "immediate_action": "Data quality investigation required"
            }
            
            analysis["recommendations"].extend([
                "CRITICAL: Investigate case number data quality",
                "Review data ingestion pipeline for this county",
                "Check source data consistency"
            ])
        
        # Sample data for manual verification
        analysis["sample_cases"] = {
            "propertyonion_sample": po_cases[:5],
            "court_cases_sample": court_cases[:5],
            "unknown_sample": unknown_cases[:3]
        }
        
        return analysis
        
    except Exception as e:
        log(f"Error analyzing {county}: {e}", "ERROR")
        return {"error": str(e), "county": county}

def get_current_cd_metrics():
    """Get current C/D metrics via pencil_dod_evaluate_county"""
    log("📊 Retrieving current C/D metrics for verification")
    
    metrics = {}
    
    for county in TARGET_COUNTIES:
        try:
            payload = {"county_slug_arg": county}
            response = client.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county",
                headers=HEADERS,
                json=payload
            )
            
            if response.status_code == 200:
                evaluation = response.json()
                
                c_data = None
                d_data = None
                
                if isinstance(evaluation, list):
                    c_data = next((item for item in evaluation if item.get('letter') == 'C'), None)
                    d_data = next((item for item in evaluation if item.get('letter') == 'D'), None)
                
                if c_data and d_data:
                    metrics[county] = {
                        "c_metric": c_data.get('metric'),
                        "c_pass": c_data.get('pass', False),
                        "d_metric": d_data.get('metric'),
                        "d_pass": d_data.get('pass', False),
                        "verification_status": "VERIFIED"
                    }
                    log(f"{county}: C={c_data.get('metric')}%, D={d_data.get('metric')}%")
                else:
                    log(f"No C/D data in evaluation for {county}", "ERROR")
                    
            else:
                log(f"Failed to evaluate {county}: {response.status_code}", "ERROR")
                metrics[county] = {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            log(f"Error evaluating {county}: {e}", "ERROR")
            metrics[county] = {"error": str(e)}
    
    return metrics

def generate_court_records_recommendation():
    """Generate specific recommendations for court records supplementation"""
    
    recommendations = {
        "pre_authorized_action": "Per issue brief: INVOKE the pre-authorized clerk/official-records supplementary litmus NOW",
        "implementation_strategy": {
            "phase_1": "County clerk website discovery and API/endpoint analysis",
            "phase_2": "Date-range enumeration of foreclosure case filings (vs case-by-case lookup)",
            "phase_3": "Crosswalk clerk records with existing MCA data via address + date matching",
            "phase_4": "Backfill C/D numerators with verified court record matches"
        },
        "county_specific_sources": {
            "broward": {
                "primary": "Broward Clerk AcclaimWeb (already implemented in scripts/acclaim_ct_sweep.py)",
                "endpoint": "https://vaclmweb1.brevardclerk.us/AcclaimWeb/",
                "status": "READY - use existing pipeline",
                "action": "Execute existing AcclaimWeb scraper for case enumeration"
            },
            "sumter": {
                "primary": "Sumter County Clerk official records",
                "discovery_needed": "Identify clerk case search endpoint",
                "strategy": "Date-range foreclosure case enumeration"
            },
            "lake": {
                "primary": "Lake County Clerk records",
                "discovery_needed": "Court records API or search interface",
                "strategy": "Alternative: Florida Courts E-Filing portal lookup"
            },
            "walton": {
                "primary": "Walton County Clerk",
                "discovery_needed": "Remote county - may need specialized approach",
                "strategy": "Florida statewide court records if available"
            },
            "jefferson": {
                "primary": "Jefferson County Clerk",
                "discovery_needed": "Small county - manual verification feasible",
                "strategy": "Direct clerk website scraping"
            }
        },
        "technical_approach": {
            "matching_strategy": "property_address + sale_date proximity (±30 days)",
            "data_validation": "Court case number format validation per county patterns",
            "conflict_resolution": "Court records take precedence over PropertyOnion",
            "progress_tracking": "County-specific progress tables with cursor/checkpoint"
        }
    }
    
    return recommendations

def execute_full_analysis():
    """Execute comprehensive C/D parity analysis"""
    log("🚀 Starting SHARD-3 C/D Parity Analysis")
    
    results = {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "session_id": "SHARD3_CD_PARITY_SESSION_24",
        "target_counties": TARGET_COUNTIES,
        "analysis_type": "PropertyOnion_vs_CourtRecords_gap_analysis",
        "verification_evidence": []
    }
    
    # Phase 1: Database connection
    if not verify_database_connection():
        results["status"] = "FAILED"
        results["error"] = "Database connection failed"
        return results
    
    # Phase 2: Get current C/D metrics
    log("Phase 2: Getting current C/D metrics")
    results["current_cd_metrics"] = get_current_cd_metrics()
    
    # Phase 3: County-by-county parity analysis
    log("Phase 3: County-by-county parity analysis")
    results["county_analyses"] = {}
    
    total_auctions = 0
    total_po_cases = 0
    total_court_cases = 0
    
    for county in TARGET_COUNTIES:
        county_analysis = analyze_county_parity(county)
        results["county_analyses"][county] = county_analysis
        
        if "total_auctions" in county_analysis:
            total_auctions += county_analysis["total_auctions"]
            breakdown = county_analysis.get("case_number_breakdown", {})
            total_po_cases += breakdown.get("propertyonion_cases", 0)
            total_court_cases += breakdown.get("court_cases", 0)
    
    # Phase 4: Fleet-wide analysis
    log("Phase 4: Fleet-wide gap analysis")
    results["fleet_analysis"] = {
        "total_auctions": total_auctions,
        "total_propertyonion_cases": total_po_cases,
        "total_court_cases": total_court_cases,
        "propertyonion_fleet_pct": round(total_po_cases * 100 / total_auctions, 1) if total_auctions > 0 else 0,
        "court_fleet_pct": round(total_court_cases * 100 / total_auctions, 1) if total_auctions > 0 else 0,
        "parity_ceiling_analysis": {
            "gap_source": "PropertyOnion cases cannot match court records directly",
            "impact": f"{total_po_cases} cases need alternative matching (address + date)",
            "severity": "HIGH" if total_po_cases > total_court_cases else "MODERATE"
        }
    }
    
    # Phase 5: Actionable recommendations
    log("Phase 5: Generating actionable recommendations")
    results["recommendations"] = generate_court_records_recommendation()
    
    # Phase 6: Next steps prioritization
    high_po_counties = []
    mixed_counties = []
    
    for county, analysis in results["county_analyses"].items():
        if "case_number_breakdown" in analysis:
            po_pct = analysis["case_number_breakdown"].get("propertyonion_pct", 0)
            if po_pct > 70:
                high_po_counties.append(county)
            elif po_pct > 20:
                mixed_counties.append(county)
    
    results["prioritized_actions"] = {
        "immediate_priority": {
            "counties": high_po_counties,
            "action": "Implement parcel_id + address matching for PropertyOnion cases",
            "rationale": "Highest PropertyOnion dependency, biggest C/D impact"
        },
        "secondary_priority": {
            "counties": mixed_counties,
            "action": "Optimize court record matching first, then address PropertyOnion",
            "rationale": "Mixed sources - get quick wins from court cases"
        },
        "court_records_supplementation": {
            "ready_counties": ["broward"],  # Has AcclaimWeb pipeline
            "discovery_needed": ["sumter", "lake", "walton", "jefferson"],
            "action": "Execute pre-authorized clerk records enumeration"
        }
    }
    
    log(f"✅ Analysis complete: {total_auctions} total auctions analyzed")
    log(f"PropertyOnion: {total_po_cases} ({results['fleet_analysis']['propertyonion_fleet_pct']}%)")
    log(f"Court cases: {total_court_cases} ({results['fleet_analysis']['court_fleet_pct']}%)")
    
    results["status"] = "COMPLETED"
    return results

def main():
    """Main execution"""
    try:
        log("🎯 SHARD-3 C/D PARITY ANALYSIS - SESSION 24")
        log("Objective: Identify PropertyOnion coverage gaps limiting C/D metrics")
        
        # Execute analysis
        results = execute_full_analysis()
        
        # Save results
        results_file = "/tmp/shard3_cd_parity_analysis.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print("\\n" + "="*60)
        print("SHARD-3 C/D PARITY ANALYSIS RESULTS")
        print("="*60)
        
        if results.get("fleet_analysis"):
            fleet = results["fleet_analysis"]
            print(f"Fleet Analysis:")
            print(f"  Total auctions: {fleet['total_auctions']}")
            print(f"  PropertyOnion cases: {fleet['total_propertyonion_cases']} ({fleet['propertyonion_fleet_pct']}%)")
            print(f"  Court cases: {fleet['total_court_cases']} ({fleet['court_fleet_pct']}%)")
        
        print("\\nNext Steps:")
        print("1. Execute pre-authorized court records supplementation") 
        print("2. Implement parcel_id + address matching for PropertyOnion cases")
        print("3. Start with Broward AcclaimWeb (pipeline ready)")
        print("4. Extend to remaining counties with clerk discovery")
        
        return results
        
    except Exception as e:
        log(f"CRITICAL ERROR: {e}", "ERROR")
        return {"status": "CRITICAL_ERROR", "error": str(e)}

if __name__ == "__main__":
    main()