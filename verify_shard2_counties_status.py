#!/usr/bin/env python3
"""
SHARD-2 County Status Verification - GOLD STANDARD CAMPAIGN
Check current A-J letter grades for brevard, washington, lake, st_johns, holmes

Usage:
  python verify_shard2_counties_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for our shard (from issue description)
SHARD_COUNTIES = ['brevard', 'washington', 'lake', 'st_johns', 'holmes']

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to the evaluation function
        payload = {"county_name": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def format_county_report(county, evaluation):
    """Format a detailed county report with current metrics from issue"""
    report = [f"\n## {county.upper()} County Status"]
    
    # Reference current metrics from the issue
    current_metrics = {
        'brevard': {'A': 5506, 'B': 137.4, 'C': 20.9, 'D': 31.9, 'E': 94.0, 'F': 52.4, 'G': 48.9, 'H': 7.8, 'I': 19.8, 'J': 0.0},
        'washington': {'A': 30, 'B': 'null', 'C': 45.4, 'D': 84.8, 'E': 24.8, 'F': 18.6, 'G': 'null', 'H': 1.4, 'I': 'null', 'J': 0.0},
        'lake': {'A': 1113, 'B': 'null', 'C': 17.3, 'D': 54.0, 'E': 74.4, 'F': 0.0, 'G': 'null', 'H': 433.0, 'I': 'null', 'J': 0.0},
        'st_johns': {'A': 558, 'B': 'null', 'C': 27.8, 'D': 60.3, 'E': 87.1, 'F': 5.2, 'G': 'null', 'H': 107.7, 'I': 'null', 'J': 0.0},
        'holmes': {'A': 0, 'B': 'null', 'C': 'null', 'D': 'null', 'E': 'null', 'F': 'null', 'G': 'null', 'H': 'null', 'I': 'null', 'J': 'null'}
    }
    
    if evaluation:
        report.append("\n### Live Database Metrics:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            # Compare with issue metrics if available
            issue_metric = current_metrics.get(county, {}).get(letter, 'N/A')
            comparison = f" [Issue: {issue_metric}]" if issue_metric != 'N/A' else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}{comparison}")
    else:
        # Fall back to issue metrics if database unavailable
        report.append("\n### Issue Metrics (Fallback):")
        current = current_metrics.get(county, {})
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            metric = current.get(letter, 'N/A')
            if metric == 'null' or metric == 'N/A':
                status = "❓ NULL"
            elif letter == 'H' and isinstance(metric, (int, float)) and metric <= 48:
                status = "✅ PASS"
            elif letter in ['B', 'C', 'D', 'E', 'F', 'G', 'I', 'J'] and isinstance(metric, (int, float)) and metric >= 95:
                status = "✅ PASS"
            elif letter == 'A' and isinstance(metric, (int, float)) and metric > 0:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
            
            report.append(f"**{letter}**: {status} (metric={metric})")
    
    return "\n".join(report)

def identify_sprint_priorities():
    """Identify priorities based on sprint order from issue"""
    priorities = {
        'brevard': {
            'score': '2/10',
            'priority_order': ['C/D root cause', 'J generator', 'G hit list', 'B reconciliation'],
            'rationale': 'Current leader at 2/10, sprint directive specifies work order'
        },
        'washington': {
            'score': '2/10', 
            'priority_order': ['A dual-product coverage', 'B verified outcomes', 'E parcel linkage'],
            'rationale': 'Second tier, basic coverage issues'
        },
        'lake': {
            'score': '1/10',
            'priority_order': ['H freshness (433h > 48h SLA)', 'B verified outcomes', 'F tier1 sold'],
            'rationale': 'Major freshness issue blocking other progress'
        },
        'st_johns': {
            'score': '1/10',
            'priority_order': ['H freshness (107h > 48h SLA)', 'B verified outcomes', 'E parcel linkage'],
            'rationale': 'Similar to lake, freshness first'
        },
        'holmes': {
            'score': '0/10',
            'priority_order': ['A dual-product coverage (bootstrap)', 'Basic data ingestion'],
            'rationale': 'Complete bootstrap needed'
        }
    }
    
    return priorities

def main():
    print("🔍 GOLD STANDARD SHARD-2 County Status Verification")
    print(f"Target counties: {', '.join(SHARD_COUNTIES)}")
    print(f"Session: 6h autonomous, 08:00Z wave")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    db_available = test_connection()
    if not db_available:
        print("⚠️ Database connection failed. Using issue metrics as fallback...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
    
    print("\n📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD_COUNTIES:
        print(f"Processing {county}...")
        
        if db_available:
            # Get evaluation using function
            evaluation = get_county_evaluation(county)
        else:
            evaluation = None
        
        county_data[county] = {'evaluation': evaluation}
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-2 COUNTY STATUS REPORT")
    print("="*60)
    
    for county in SHARD_COUNTIES:
        evaluation = county_data[county].get('evaluation')
        print(format_county_report(county, evaluation))
    
    # Sprint priority analysis
    priorities = identify_sprint_priorities()
    
    print(f"\n" + "="*60)
    print("SPRINT PRIORITY ANALYSIS")
    print("="*60)
    
    for county, data in priorities.items():
        print(f"\n### {county.upper()}")
        print(f"**Score**: {data['score']}")
        print(f"**Priority Order**: {' → '.join(data['priority_order'])}")
        print(f"**Rationale**: {data['rationale']}")
    
    # Action plan
    print(f"\n" + "="*60)
    print("RECOMMENDED EXECUTION PLAN")
    print("="*60)
    
    print(f"🎯 **Primary Target**: BREVARD (per Jun12 sprint directive)")
    print("**Work Order**:")
    print("1. **C/D ROOT CAUSE** - PropertyOnion coverage audit, clerk/official-records litmus")
    print("2. **J GENERATOR** - Shapira V14 bid_decisions pipeline") 
    print("3. **G HIT LIST** - zone_standards backfill for ~15 districts")
    print("4. **B RECONCILIATION** - verified=8547 > closed_sold=6220 (134%% anomaly)")
    print("\n**Secondary Targets**: washington, lake, st_johns (basic coverage)")
    print("**Bootstrap Target**: holmes (complete data ingestion needed)")
    print("\n**Ship Gate**: All changes to main branch, verify with pencil_dod_evaluate_county")

if __name__ == "__main__":
    main()