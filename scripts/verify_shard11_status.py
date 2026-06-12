#!/usr/bin/env python3
"""
SHARD-11 County Status Verification
Check current A-J letter grades for manatee, bay, okeechobee, gadsden, wakulla

Usage:
  python scripts/verify_shard11_status.py
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

# Target counties for SHARD-11
SHARD11_COUNTIES = ['manatee', 'bay', 'okeechobee', 'gadsden', 'wakulla']

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

def check_pipeline_counties():
    """Check if counties are configured in pipeline.counties table"""
    try:
        response = requests.get(
            f"{BASE}/pipeline_counties",
            headers=HEADERS,
            params={"select": "county,platform,foreclosure_platform,tax_deed_platform,active"},
            timeout=10
        )
        
        if response.status_code == 200:
            return {row['county']: row for row in response.json()}
        else:
            print(f"⚠️ Failed to get pipeline counties: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"⚠️ Error getting pipeline counties: {e}")
        return {}

def format_county_report(county, evaluation, status, pipeline_config):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if pipeline_config:
        report.append(f"**Pipeline**: {pipeline_config.get('platform', 'Not configured')}")
        report.append(f"**Active**: {pipeline_config.get('active', False)}")
    else:
        report.append("**Pipeline**: ⚠️ NOT CONFIGURED - Needs bootstrap")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            # Highlight critical letters B, I, J
            critical_marker = " 🎯" if letter in ['B', 'I', 'J'] else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}{critical_marker}")
    
    return "\n".join(report)

def identify_priority_actions(county_data, pipeline_configs):
    """Identify immediate action items for the session"""
    actions = []
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        pipeline_config = pipeline_configs.get(county)
        
        # Priority 1: Bootstrap missing counties
        if not pipeline_config or not evaluation:
            actions.append({
                'priority': 1,
                'county': county,
                'action': 'BOOTSTRAP',
                'description': f'Configure {county} in pipeline.counties and run initial data ingestion'
            })
            continue
            
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
        
        # Priority 2: Fix stale data (H failures)
        if 'H' in failing_letters:
            actions.append({
                'priority': 2,
                'county': county,
                'action': 'FIX_STALENESS',
                'description': f'Update {county} data sources - H failing (>48h stale)'
            })
        
        # Priority 3: Critical letters B, I, J
        critical_failing = [l for l in failing_letters if l in ['B', 'I', 'J']]
        if critical_failing:
            actions.append({
                'priority': 3,
                'county': county,
                'action': 'CRITICAL_LETTERS',
                'description': f'Implement {county} critical letters: {", ".join(critical_failing)}'
            })
        
        # Priority 4: Parcel linkage (E) - high leverage
        if 'E' in failing_letters:
            actions.append({
                'priority': 4,
                'county': county,
                'action': 'PARCEL_LINKAGE',
                'description': f'Fix {county} parcel linking via county GIS'
            })
    
    # Sort by priority
    actions.sort(key=lambda x: (x['priority'], x['county']))
    return actions

def main():
    print("🔍 SHARD-11 County Status Verification")
    print(f"Target counties: {', '.join(SHARD11_COUNTIES)}")
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
    
    # Check pipeline configurations
    pipeline_configs = check_pipeline_counties()
    
    # Collect data for each county
    county_data = {}
    for county in SHARD11_COUNTIES:
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
    print("SHARD-11 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        pipeline_config = pipeline_configs.get(county)
        
        print(format_county_report(county, evaluation, status, pipeline_config))
    
    # Action plan
    actions = identify_priority_actions(county_data, pipeline_configs)
    
    print(f"\n" + "="*60)
    print("IMMEDIATE ACTION PLAN")
    print("="*60)
    
    for i, action in enumerate(actions, 1):
        priority_labels = {
            1: "🚨 P1 - Bootstrap",
            2: "⚡ P2 - Staleness", 
            3: "🎯 P3 - Critical",
            4: "🔗 P4 - Linkage"
        }
        
        label = priority_labels.get(action['priority'], f"P{action['priority']}")
        print(f"\n{i}. {label}")
        print(f"   County: {action['county'].upper()}")
        print(f"   Action: {action['description']}")
    
    # Session execution plan
    print(f"\n" + "="*60)
    print("SHARD-11 SESSION EXECUTION PLAN")
    print("="*60)
    print("\nExecute in this order:")
    print("1. Bootstrap gadsden + wakulla (if not configured)")
    print("2. Fix staleness (H) for bay + okeechobee")  
    print("3. Implement verified outcomes (B) - highest leverage")
    print("4. Fix parcel linkage (E) for existing counties")
    print("5. Address remaining critical letters (I, J)")
    print("6. Verify metrics movement with pencil_dod_evaluate_county")
    print("7. Commit all changes directly to main branch")
    
    # Summary by county
    print(f"\n" + "="*60)
    print("COUNTY PRIORITY SUMMARY")
    print("="*60)
    
    bootstrap_needed = [c for c in SHARD11_COUNTIES if c not in pipeline_configs]
    if bootstrap_needed:
        print(f"🚨 Bootstrap needed: {', '.join(bootstrap_needed)}")
    
    for county, data in county_data.items():
        if data.get('evaluation'):
            eval_data = data['evaluation']
            score = sum(1 for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                       if eval_data.get(f"grade_{letter.lower()}") == 'PASS')
            print(f"{county.upper()}: {score}/10 - {'Bootstrap' if county in bootstrap_needed else 'Active'}")

if __name__ == "__main__":
    main()