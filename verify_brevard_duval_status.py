#!/usr/bin/env python3
"""
Brevard & Duval Gold Standard Verification Script
GOLD STANDARD AUTOPILOT-BD Session verification for brevard and duval counties

Usage:
  python verify_brevard_duval_status.py
"""
import os
import sys
import json
from datetime import datetime

# Add project root to Python path
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try importing httpx (better than requests for async operations)
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available, trying requests")
    import requests as httpx_fallback

# Supabase configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Check for GitHub Actions environment
if not SUPABASE_KEY:
    # Try to find other possible env var names
    possible_keys = [
        "SUPABASE_ANON_KEY", 
        "SUPABASE_SERVICE_ROLE_KEY",
        "DB_PASSWORD",
        "SUPABASE_DB_PASSWORD"
    ]
    for key_name in possible_keys:
        test_key = os.environ.get(key_name)
        if test_key:
            SUPABASE_KEY = test_key
            print(f"Using {key_name} for database access")
            break

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# Target counties for this session
TARGET_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No Supabase key found in environment")
        print("Available environment variables:")
        env_vars = [k for k in os.environ.keys() if any(pattern in k.lower() for pattern in ['supabase', 'db', 'key', 'pass'])]
        print(f"  {env_vars}")
        return False
        
    try:
        client = httpx.Client(timeout=30)
        # Try a simple query to test connectivity - use fl_counties like the test script
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties", headers=sb_headers(), params={"select": "count", "limit": "1"})
        
        if r.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        elif r.status_code == 401:
            print("❌ Authentication failed - check SUPABASE_KEY")
            return False
        else:
            print(f"❌ Connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        client = httpx.Client(timeout=60)
        
        # Use RPC call to the evaluation function - try both parameter names
        payload = {"county_slug_arg": county}  # First try the arg format from test script
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=sb_headers(), 
            json=payload
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ {county} evaluation successful")
            return result
        else:
            # Try alternative parameter name if first fails
            payload = {"county_name": county}
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
                headers=sb_headers(), 
                json=payload
            )
            if r.status_code == 200:
                result = r.json()
                print(f"✅ {county} evaluation successful (alt param)")
                return result
            else:
                print(f"⚠️ Failed to evaluate {county}: {r.status_code} - {r.text}")
                return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_gold_standard_status(county):
    """Get county status from gold_standard_county_status table"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/gold_standard_county_status", 
            headers=sb_headers(), 
            params={
                "county_slug": f"eq.{county}",  # Try county_slug first
                "select": "*",
                "order": "loop_run_id.desc",
                "limit": "1"
            }
        )
        
        if r.status_code == 200:
            data = r.json()
            return data[0] if data else None
        else:
            # Try alternative column name
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/gold_standard_county_status", 
                headers=sb_headers(), 
                params={
                    "county": f"eq.{county}",  
                    "select": "*",
                    "order": "updated_at.desc",
                    "limit": "1"
                }
            )
            if r.status_code == 200:
                data = r.json()
                return data[0] if data else None
            else:
                print(f"⚠️ Failed to get gold standard status for {county}: {r.status_code}")
                return None
            
    except Exception as e:
        print(f"⚠️ Error getting gold standard status for {county}: {e}")
        return None

def format_county_report(county, evaluation, status):
    """Format a detailed county report with A-J letter analysis"""
    report = [f"\n## {county.upper()} County Analysis"]
    
    if status:
        total_score = status.get('total_score', 'N/A')
        updated_at = status.get('updated_at', 'Unknown')
        report.append(f"**Score**: {total_score}/10")
        report.append(f"**Last Updated**: {updated_at}")
    
    if evaluation:
        passing_letters = []
        failing_letters = []
        
        report.append("\n### A-J Letter Status:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            if grade == "PASS":
                status_icon = "✅ PASS"
                passing_letters.append(letter)
            else:
                status_icon = "❌ FAIL"
                failing_letters.append(letter)
                
            metric_str = f" (metric={metric})" if metric is not None else ""
            report.append(f"**{letter}**: {status_icon}{metric_str}")
        
        # Analyze priority based on BREVARD SPRINT ORDER and CRITERION-PARALLEL PIVOT
        report.append(f"\n### Priority Analysis:")
        report.append(f"**Passing ({len(passing_letters)}/10)**: {', '.join(passing_letters)}")
        report.append(f"**Failing ({len(failing_letters)}/10)**: {', '.join(failing_letters)}")
        
        # Highlight critical letters per issue description
        critical_failing = [l for l in failing_letters if l in ['B', 'I', 'J']]
        if critical_failing:
            report.append(f"**🎯 Critical Failing (B/I/J)**: {', '.join(critical_failing)}")
        
        # Anomaly detection for B letter >100%
        if 'B' in failing_letters:
            b_metric = evaluation.get('metric_b')
            if b_metric and float(b_metric) > 105:
                report.append(f"**🚨 B ANOMALY DETECTED**: {b_metric}% (>105% indicates denominator/double-count issue)**")
    
    return "\n".join(report)

def analyze_priorities(county_data):
    """Analyze priorities based on BREVARD SPRINT ORDER and CRITERION-PARALLEL PIVOT"""
    analysis = {
        "session_assignment": "brevard + duval (parallel criterion approach)",
        "brevard_sprint_order": ["C/D ROOT CAUSE", "J GENERATOR", "G HIT LIST", "B RECONCILIATION"],
        "criterion_parallel_pivot": "fix criteria fleet-wide, not counties serially",
        "priority_targets": {},
        "recommended_actions": []
    }
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            continue
            
        county_priority = {
            "county": county,
            "current_score": 0,
            "failing_letters": [],
            "critical_issues": [],
            "anomalies": []
        }
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field)
            metric = evaluation.get(metric_field)
            
            if grade == 'PASS':
                county_priority["current_score"] += 1
            else:
                county_priority["failing_letters"].append(letter)
                
                # Check for anomalies
                if letter == 'B' and metric and float(metric) > 105:
                    county_priority["anomalies"].append(f"B={metric}% >105% (verified_outcomes > closed_sold)")
                elif letter in ['G', 'I'] and metric is None:
                    county_priority["anomalies"].append(f"{letter}=null (unmeasurable, not merely failing)")
        
        # Identify critical failing letters
        county_priority["critical_issues"] = [l for l in county_priority["failing_letters"] if l in ['B', 'I', 'J']]
        
        analysis["priority_targets"][county] = county_priority
    
    # Generate recommended actions based on analysis
    analysis["recommended_actions"] = [
        "1. C/D ROOT CAUSE - PropertyOnion coverage issue, invoke clerk/official-records supplementary litmus",
        "2. J GENERATOR - Build bid_decisions generator (arv+max_bid+ml_score+5 factors, Shapira V14)",
        "3. G HIT LIST - Backfill zone_standards for Brevard districts (density/FAR gaps)",
        "4. B RECONCILIATION - Reconcile verified_outcomes vs closed_sold anomaly >100%"
    ]
    
    return analysis

def main():
    print("🏆 GOLD STANDARD AUTOPILOT-BD: Brevard & Duval Verification")
    print(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Cannot proceed with verification.")
        print("Required: SUPABASE_KEY environment variable")
        return 1
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each target county
    county_data = {}
    for county in TARGET_COUNTIES:
        print(f"🔄 Processing {county}...")
        
        # Get evaluation using pencil_dod_evaluate_county function  
        evaluation = get_county_evaluation(county)
        
        # Get gold standard status from table
        status = get_gold_standard_status(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'status': status
        }
    
    # Generate reports
    print("\n" + "="*80)
    print("BREVARD & DUVAL COUNTY STATUS REPORT")
    print("="*80)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Priority analysis
    priorities = analyze_priorities(county_data)
    
    print(f"\n" + "="*80)
    print("BREVARD SPRINT ORDER PRIORITY ANALYSIS")
    print("="*80)
    
    print(f"\n**Session Assignment**: {priorities['session_assignment']}")
    print(f"**Approach**: {priorities['criterion_parallel_pivot']}")
    
    for county, priority_data in priorities['priority_targets'].items():
        score = priority_data['current_score']
        failing = priority_data['failing_letters']
        critical = priority_data['critical_issues']
        anomalies = priority_data['anomalies']
        
        print(f"\n### {county.upper()} ({score}/10)")
        print(f"**Failing letters**: {', '.join(failing) if failing else 'None'}")
        if critical:
            print(f"**🎯 Critical failing (B,I,J)**: {', '.join(critical)}")
        if anomalies:
            print(f"**🚨 Anomalies detected**: {'; '.join(anomalies)}")
    
    # Recommended actions
    print(f"\n" + "="*80)
    print("RECOMMENDED ACTION PLAN")
    print("="*80)
    print("**Brevard Sprint Order (velocity-derived priority)**:")
    
    for action in priorities['recommended_actions']:
        print(f"  {action}")
    
    print(f"\n**Evidence-Before-Claims Protocol**:")
    print("  - Run verification queries after each fix")
    print("  - Paste SQL verification evidence in issue comments")
    print("  - Use pencil_dod_evaluate_county for metric validation")
    print("  - Commit directly to main branch (ship-to-main mandate)")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)