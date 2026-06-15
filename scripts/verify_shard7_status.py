#!/usr/bin/env python3
"""
SHARD-7 County Status Verification
Check current A-J letter grades for marion, collier, miami_dade, columbia, madison

Usage:
  python scripts/verify_shard7_status.py
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
SHARD7_COUNTIES = ['marion', 'collier', 'miami_dade', 'columbia', 'madison']

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
        # Use RPC call to the evaluation function with correct parameter name
        payload = {"county_slug_arg": county}
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
    """Format a detailed county report based on issue format"""
    report = [f"\n## {county.upper()}"]
    
    if evaluation:
        # Count passes
        pass_count = 0
        fail_letters = []
        
        for item in evaluation:
            letter = item.get('letter', '?')
            metric = item.get('metric')
            is_pass = item.get('pass', False)
            
            if is_pass:
                status = "PASS"
                pass_count += 1
            else:
                status = "FAIL"
                fail_letters.append(letter)
            
            metric_str = f"metric={metric}" if metric is not None else "metric=null"
            report.append(f"    {letter} {status} {metric_str}")
        
        report.insert(1, f"Pass Count: {pass_count}/10")
        if fail_letters:
            report.insert(2, f"Failing Letters: {', '.join(fail_letters)}")
    else:
        report.append("    No evaluation data available")
    
    return "\n".join(report)

def identify_priority_fixes(county_data):
    """Identify priority fixes based on the issue guidance"""
    
    # From the issue, each county has specific priorities:
    priorities = {
        'marion': 'B, C/D, E parity fixes - has some base data (A=PASS)',
        'collier': 'H freshness (610.4h > 48h SLA), C/D parity, basic setup',
        'miami_dade': 'H freshness (314h), E parcel linkage (16.7%), scale issues',
        'columbia': 'Zero auctions - full A-lane setup needed first',
        'madison': 'Zero auctions - full A-lane setup needed first'
    }
    
    failing_by_letter = {}
    high_impact_fixes = []
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            if county in ['columbia', 'madison']:
                high_impact_fixes.append(f"{county}: A-lane setup (zero auctions)")
            continue
            
        for item in evaluation:
            letter = item.get('letter')
            is_pass = item.get('pass', False)
            metric = item.get('metric')
            
            if not is_pass:
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append({
                    'county': county, 
                    'metric': metric
                })
                
                # Identify high-impact opportunities
                if letter == 'H' and metric and metric > 48:
                    high_impact_fixes.append(f"{county}: H freshness fix ({metric}h > 48h SLA)")
                elif letter in ['C', 'D'] and metric and metric < 50:
                    high_impact_fixes.append(f"{county}: {letter} parity fix ({metric}%)")
                elif letter == 'E' and metric and metric < 50:
                    high_impact_fixes.append(f"{county}: E parcel linkage fix ({metric}%)")
                elif letter == 'J' and metric == 0:
                    high_impact_fixes.append(f"{county}: J generator build (bid_decisions pipeline)")
    
    return {
        'by_letter': failing_by_letter,
        'high_impact': high_impact_fixes,
        'county_priorities': priorities
    }

def main():
    print("🔍 SHARD-7 County Status Verification")
    print(f"Target counties: {', '.join(SHARD7_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking environment setup...")
        # Try with empty key to see if public access works
        global HEADERS
        HEADERS = {"Content-Type": "application/json"}
        print("Attempting public access...")
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD7_COUNTIES:
        print(f"Processing {county}...")
        evaluation = get_county_evaluation(county)
        county_data[county] = {'evaluation': evaluation}
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-7 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        print(format_county_report(county, evaluation))
    
    # Priority analysis
    priorities = identify_priority_fixes(county_data)
    
    print(f"\n" + "="*60)
    print("HIGH-IMPACT FIX OPPORTUNITIES")
    print("="*60)
    
    for fix in priorities['high_impact']:
        print(f"🎯 {fix}")
    
    print(f"\n" + "="*60)
    print("SHARD-7 ACTION PLAN")
    print("="*60)
    
    print("\n📋 **County Priorities (from issue):**")
    for county, priority in priorities['county_priorities'].items():
        print(f"**{county}**: {priority}")
    
    print("\n📝 **Execution Order:**")
    print("1. **columbia/madison**: A-lane setup (pipeline.counties config)")
    print("2. **collier/miami_dade**: H freshness fixes") 
    print("3. **marion/collier**: C/D parity improvements")
    print("4. **miami_dade**: E parcel linkage scale fixes")
    print("5. **All**: J generator (bid_decisions pipeline)")
    print("\n⚠️ **SHIP TO MAIN**: All commits direct to main branch")

if __name__ == "__main__":
    main()