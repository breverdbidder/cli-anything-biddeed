#!/usr/bin/env python3
"""
SHARD-12 County Status Verification (UPDATED ASSIGNMENT)
Check current A-J letter grades for osceola, gilchrist, pinellas, glades

Target counties from ISSUE-7701 briefing (updated assignment):
- osceola (2/10)
- gilchrist (1/10)  
- pinellas (1/10)
- glades (0/10)

Usage:
  python scripts/verify_shard12_updated_status.py
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

# Target counties for SHARD-12 (UPDATED ASSIGNMENT per ISSUE-7701)
SHARD12_COUNTIES = ['osceola', 'gilchrist', 'pinellas', 'glades']

# County DOR numbers for FL GIO integration
COUNTY_DOR_NUMBERS = {
    'osceola': 57,    # Osceola County
    'gilchrist': 23,  # Gilchrist County  
    'pinellas': 52,   # Pinellas County
    'glades': 22      # Glades County
}

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/fl_counties", headers=HEADERS, params={"limit": "1"}, timeout=10)
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
        # Try the function with different parameter names
        for param_name in ['county_name', 'county_slug', 'county']:
            payload = {param_name: county}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        
        print(f"⚠️ Failed to evaluate {county}: RPC call unsuccessful")
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

def get_auction_counts(county):
    """Get auction data counts for a county"""
    try:
        response = requests.get(
            f"{BASE}/multi_county_auctions", 
            headers=HEADERS, 
            params={
                "county": f"eq.{county}",
                "select": "count"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return len(data)
        else:
            return 0
            
    except Exception as e:
        print(f"⚠️ Error getting auction count for {county}: {e}")
        return 0

def format_county_report(county, evaluation, status, auction_count):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    report.append(f"**Auction Count**: {auction_count}")
    report.append(f"**DOR Number**: {COUNTY_DOR_NUMBERS.get(county, 'Unknown')}")
    
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

def check_county_setup(county):
    """Check if county is properly set up in database"""
    try:
        dor_num = COUNTY_DOR_NUMBERS.get(county)
        response = requests.get(
            f"{BASE}/fl_counties", 
            headers=HEADERS, 
            params={
                "co_no": f"eq.{dor_num}",
                "select": "*"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        return None
            
    except Exception as e:
        print(f"⚠️ Error checking county setup for {county}: {e}")
        return None

def main():
    print("🔍 SHARD-12 County Status Verification (UPDATED ASSIGNMENT)")
    print(f"Target counties: {', '.join(SHARD12_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Need Supabase credentials.")
        print("Cannot proceed with autonomous improvements without database access.")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD12_COUNTIES:
        print(f"Processing {county}...")
        
        # Check if county is properly configured
        county_config = check_county_setup(county)
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        # Get status from table
        status = get_county_status_direct(county)
        
        # Get auction count
        auction_count = get_auction_counts(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'status': status,
            'auction_count': auction_count,
            'configured': bool(county_config),
            'config': county_config
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-12 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        auction_count = data.get('auction_count', 0)
        
        print(format_county_report(county, evaluation, status, auction_count))
        
        if not data.get('configured'):
            print(f"⚠️ **{county.upper()} NOT CONFIGURED** - needs county setup")
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY & RECOMMENDATIONS")
    print("="*60)
    
    total_counties = len(SHARD12_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    configured_counties = sum(1 for data in county_data.values() if data.get('configured'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    print(f"Counties configured: {configured_counties}/{total_counties}")
    
    # Priority actions based on briefing
    print(f"\nPRIORITY ACTIONS (Per CRITERION-PARALLEL PIVOT):")
    print("1. **BREVARD SPRINT ORDER** - C/D root cause analysis")
    print("2. **J GENERATOR** - Build to evaluator contract")  
    print("3. **G HIT LIST** - Ordinance-text values with honesty markers")
    print("4. **B RECONCILIATION** - Fix verified_outcomes > closed_sold anomaly")
    
    print(f"\nHIGHEST-LEVERAGE FIXES:")
    for county, data in county_data.items():
        auction_count = data.get('auction_count', 0)
        if auction_count == 0:
            print(f"- **{county}**: Letter A bootstrap (0 auctions found)")
        else:
            print(f"- **{county}**: Letters B/E/J focus ({auction_count} auctions available)")

if __name__ == "__main__":
    main()