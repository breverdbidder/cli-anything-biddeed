#!/usr/bin/env python3
"""
SHARD-3 County Status Verification
Check current A-J letter grades for bay, marion, walton, jefferson (charlotte in SHARD-1)

Usage:
  python scripts/verify_shard3_status.py
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

# Target counties for SHARD-3 (charlotte managed by SHARD-1)  
SHARD3_COUNTIES = ['bay', 'marion', 'walton', 'jefferson']

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

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={
                "county": f"eq.{county}",
                "select": "*"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        else:
            print(f"⚠️ Failed to get status for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting status for {county}: {e}")
        return None

def format_county_report(county, evaluation, status):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅" if grade == "PASS" else "❌" if grade == "FAIL" else "⚠️"
            metric_str = f"({metric})" if metric is not None else "(null)"
            
            report.append(f"**{letter}**: {status_icon} {grade} {metric_str}")
    
    return "\n".join(report)

def analyze_shard_priorities():
    """Analyze priority work for SHARD-3"""
    print("\n" + "="*60)
    print("SHARD-3 PRIORITY ANALYSIS")
    print("="*60)
    
    # Use briefing data for analysis since database connection may not be available
    briefing_metrics = {
        'bay': {
            'score': 1,
            'failing_letters': ['B', 'C', 'D', 'F', 'G', 'H', 'I', 'J'],
            'critical_issues': ['B=null (no verified outcomes)', 'H=391h (stale)', 'J=0% (no deal pipeline)']
        },
        'marion': {
            'score': 1, 
            'failing_letters': ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
            'critical_issues': ['B=null (no verified outcomes)', 'J=0% (no deal pipeline)', 'C=9.6% (poor parity)']
        },
        'walton': {
            'score': 1,
            'failing_letters': ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
            'critical_issues': ['B=null (no verified outcomes)', 'H=391h (stale)', 'J=0% (no deal pipeline)']
        },
        'jefferson': {
            'score': 0,
            'failing_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
            'critical_issues': ['A=0 (no lane config)', 'Needs full bootstrap']
        }
    }
    
    # Analyze fleet-wide failures
    fleet_issues = {
        'B': 4,  # All counties fail Letter B
        'J': 4,  # All counties fail Letter J  
        'G': 4,  # All counties fail Letter G
        'I': 4,  # All counties fail Letter I
        'C': 4,  # All counties fail Letter C
        'D': 3,  # bay, marion, walton fail Letter D
        'H': 2,  # bay, walton fail Letter H (freshness)
        'E': 2,  # marion, walton fail Letter E
        'F': 4,  # All counties fail Letter F
    }
    
    print(f"\n📊 **Fleet-Wide Failing Letters** (SHARD-3):")
    for letter, count in sorted(fleet_issues.items(), key=lambda x: x[1], reverse=True):
        print(f"**{letter}**: {count}/4 counties failing")
    
    print(f"\n🎯 **CRITERION-PARALLEL PRIORITY ORDER:**")
    print("1. **Letter B** - Verified Outcomes (4/4 counties fail)")
    print("   - All counties null metrics = no independent verification")
    print("   - Blocks Letter F progression (tier1 promotion depends on outcomes)")
    
    print("2. **Letter J** - Deal Thesis (4/4 counties fail)")  
    print("   - All counties 0% = bid_decisions pipeline missing")
    print("   - Shapira Formula not implemented for any SHARD-3 county")
    
    print("3. **Letter C/D** - Parity Issues (3-4 counties fail)")
    print("   - C: 9.6%-15.6% vs 95% target")
    print("   - D: Mixed performance, PropertyOnion mismatch")
    
    print("4. **Letter H** - Freshness (2/4 counties fail)")
    print("   - bay/walton: 391h = 16+ days stale (SLA: 48h)")
    
    print("5. **Letter A** - Jefferson only (1/4 counties fail)")
    print("   - jefferson=0: needs lane configuration first")
    
    print(f"\n📝 **Session Work Order:**")
    print("1. County setup (database foundation)")
    print("2. Letter B fixes (independent outcome scrapers)")  
    print("3. Letter J generator (bid_decisions pipeline)")
    print("4. Letter C/D parity fixes")
    print("5. Letter H freshness fixes (bay/walton)")
    print("6. Letter A bootstrap (jefferson only)")

def main():
    """Main execution function"""
    print("=== SHARD-3 COUNTY STATUS VERIFICATION ===")
    print(f"Counties: {', '.join(SHARD3_COUNTIES)}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    
    # Test connection
    if not test_connection():
        print("\n⚠️ Database connection failed. Using briefing data for analysis.")
        analyze_shard_priorities()
        return
    
    # Get current status for each county
    all_evaluations = {}
    all_status = {}
    
    for county in SHARD3_COUNTIES:
        print(f"\n📊 Evaluating {county}...")
        
        evaluation = get_county_evaluation(county)
        status = get_county_status_direct(county)
        
        all_evaluations[county] = evaluation
        all_status[county] = status
        
        if evaluation or status:
            print(format_county_report(county, evaluation, status))
        else:
            print(f"❌ Failed to get data for {county}")
    
    # Fleet summary
    print("\n" + "="*60)
    print("SHARD-3 FLEET SUMMARY")
    print("="*60)
    
    passing_counties = []
    failing_counties = []
    
    for county in SHARD3_COUNTIES:
        status = all_status.get(county)
        if status and status.get('total_score', 0) >= 8:
            passing_counties.append(county)
        else:
            failing_counties.append(county)
    
    print(f"✅ **Passing**: {len(passing_counties)} counties - {', '.join(passing_counties) if passing_counties else 'None'}")
    print(f"❌ **Failing**: {len(failing_counties)} counties - {', '.join(failing_counties) if failing_counties else 'None'}")
    
    # Priority analysis
    analyze_shard_priorities()

if __name__ == "__main__":
    main()