#!/usr/bin/env python3
"""
SHARD-2 County Status Verification
Check current A-J letter grades for citrus, pinellas, collier, santa_rosa, holmes

Usage:
  python scripts/verify_shard2_status.py
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

# Target counties for SHARD-2
SHARD2_COUNTIES = ['citrus', 'pinellas', 'collier', 'santa_rosa', 'holmes']

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
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
    
    return "\n".join(report)

def identify_priority_targets(county_data):
    """Identify highest priority counties and letters to target"""
    priorities = []
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            continue
            
        score = 0
        failing_letters = []
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            if evaluation.get(grade_field) == 'PASS':
                score += 1
            else:
                failing_letters.append(letter)
        
        # Critical letters B, I, J get higher priority
        critical_failing = [l for l in failing_letters if l in ['B', 'I', 'J']]
        
        priorities.append({
            'county': county,
            'score': score,
            'failing_letters': failing_letters,
            'critical_failing': critical_failing,
            'priority_score': score + len(critical_failing) * 2  # Boost for critical fixes
        })
    
    # Sort by priority score descending (higher score = better foundation to build on)
    priorities.sort(key=lambda x: x['priority_score'], reverse=True)
    
    return priorities

def main():
    print("🔍 SHARD-2 County Status Verification")
    print(f"Target counties: {', '.join(SHARD2_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        print(f"Available env vars: {[k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]}")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD2_COUNTIES:
        print(f"Processing {county}...")
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        # Get status from table
        status = get_county_status_direct(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'status': status
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-2 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Priority analysis
    priorities = identify_priority_targets(county_data)
    
    print(f"\n" + "="*60)
    print("PRIORITY TARGET ANALYSIS")
    print("="*60)
    
    for i, priority in enumerate(priorities, 1):
        county = priority['county']
        score = priority['score']
        failing = priority['failing_letters']
        critical = priority['critical_failing']
        
        print(f"\n{i}. {county.upper()} ({score}/10)")
        print(f"   Failing letters: {', '.join(failing) if failing else 'None'}")
        if critical:
            print(f"   🎯 Critical failing (B,I,J): {', '.join(critical)}")
    
    # Summary
    print(f"\n" + "="*60)
    print("RECOMMENDED ACTION PLAN")
    print("="*60)
    
    if priorities:
        top_county = priorities[0]['county']
        print(f"🎯 Start with: {top_county.upper()}")
        print("Focus order: B (verified outcomes) → I (property cards) → J (deal thesis)")
        print("\nNext steps:")
        print("1. Implement verified outcomes scraper for highest-scoring county")
        print("2. Build property card enrichment pipeline") 
        print("3. Enable deal thesis calculation")
        print("4. Verify metrics move with pencil_dod_evaluate_county")
        print("5. Commit directly to main branch")
    else:
        print("❌ No county data available - check database connectivity")

if __name__ == "__main__":
    main()