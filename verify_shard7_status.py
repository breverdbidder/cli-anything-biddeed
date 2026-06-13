#!/usr/bin/env python3
"""
SHARD-7 County Status Verification
Check current A-J letter grades for highlands, volusia, miami_dade, columbia, madison

Usage:
  python verify_shard7_status.py
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

# Target counties for SHARD-7
SHARD7_COUNTIES = ['highlands', 'volusia', 'miami_dade', 'columbia', 'madison']

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
    """Identify highest priority counties and letters based on CRITERION-PARALLEL strategy"""
    
    # Aggregate failing letters across all counties
    failing_by_letter = {}
    county_scores = {}
    
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
                # Track which counties fail each letter
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
        
        county_scores[county] = {
            'score': score,
            'failing_letters': failing_letters
        }
    
    # Priority order based on briefing instructions - criterion parallel fixes
    letter_priorities = ['C', 'D', 'E', 'J', 'I', 'B', 'G', 'F']
    
    return {
        'by_letter': failing_by_letter,
        'by_county': county_scores,
        'priority_order': letter_priorities
    }

def main():
    print("🔍 SHARD-7 County Status Verification")
    print(f"Target counties: {', '.join(SHARD7_COUNTIES)}")
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
    for county in SHARD7_COUNTIES:
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
    print("SHARD-7 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Priority analysis using CRITERION-PARALLEL strategy
    priorities = identify_priority_targets(county_data)
    
    print(f"\n" + "="*60)
    print("CRITERION-PARALLEL ANALYSIS")
    print("="*60)
    
    print("\n📊 Failing Letters Across Shard:")
    for letter in priorities['priority_order']:
        counties = priorities['by_letter'].get(letter, [])
        if counties:
            print(f"**{letter}**: {', '.join(counties)} ({len(counties)} counties)")
    
    print(f"\n📊 County Scores:")
    for county, data in priorities['by_county'].items():
        score = data['score']
        failing = data['failing_letters']
        print(f"**{county}**: {score}/10 - Failing: {', '.join(failing) if failing else 'None'}")
    
    # Recommended action plan based on shard 7 specifics
    print(f"\n" + "="*60)
    print("SHARD-7 ACTION PLAN")
    print("="*60)
    
    print("\n🎯 **Priority Order (criterion-parallel fixes):**")
    print("1. **C/D PARITY** - reconcile auction counts vs PropertyOnion litmus")
    print("2. **E LINKAGE** - parcel_id via county property appraiser GIS") 
    print("3. **J GENERATOR** - build Shapira Formula bid_decisions pipeline")
    print("4. **I CARDS** - property card completion (requires E linkage)")
    print("5. **B VERIFIED** - independent verified outcomes scraping")
    print("6. **G ZONING** - zoning district data ingestion")
    print("7. **F TIER1** - tier1 sold amount verification")
    
    print("\n📝 **Next Steps for SHARD-7:**")
    print("1. Focus on counties with existing data (highlands, volusia, miami_dade)")
    print("2. Bootstrap columbia and madison if needed")
    print("3. Apply criterion-parallel fixes fleet-wide")
    print("4. All changes commit directly to main (ship-to-main mandate)")
    print("5. Use ULTRALOOP verification protocol for all claims")

if __name__ == "__main__":
    main()