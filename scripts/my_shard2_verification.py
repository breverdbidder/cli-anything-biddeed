#!/usr/bin/env python3
"""
MY SHARD-2 County Status Verification
Check current A-J letter grades for charlotte, polk, hendry, st_lucie, holmes
Test database connectivity and run baseline evaluation

Usage:
  python scripts/my_shard2_verification.py
"""
import os
import sys
import httpx
import json
from datetime import datetime
from typing import Dict, List, Optional

# Supabase configuration  
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# MY assigned counties for SHARD-2 (from issue #7556)
MY_SHARD2_COUNTIES = ['charlotte', 'polk', 'hendry', 'st_lucie', 'holmes']

client = httpx.Client(timeout=60)

def test_connection():
    """Test Supabase connection"""
    try:
        if not SUPABASE_KEY:
            print("❌ SUPABASE_KEY not found in environment")
            print(f"Available env vars with 'SUPABASE': {[k for k in os.environ.keys() if 'SUPABASE' in k]}")
            return False
            
        response = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            print(f"Database: {SUPABASE_URL}")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Try multiple parameter formats since docs aren't clear
        for param_name in ["county_name", "county_slug_arg", "county_slug", "county"]:
            try:
                payload = {param_name: county}
                response = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county", 
                    headers=HEADERS, 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code != 404:  # Only log non-404 errors
                    print(f"⚠️ Param {param_name} failed: {response.status_code}")
            except Exception as inner_e:
                continue
                
        print(f"⚠️ Failed to evaluate {county} with all parameter formats")
        return None
        
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_auction_counts(county):
    """Get basic auction counts for the county"""
    try:
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "select": "count",
                "county": f"eq.{county}"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get('count', 0)
        return 0
    except Exception as e:
        print(f"⚠️ Error getting auction count for {county}: {e}")
        return 0

def format_county_report(county, evaluation, auction_count=0):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    report.append(f"Total auctions: {auction_count}")
    
    if evaluation:
        # Count passing grades
        passing = 0
        failing_letters = []
        
        # Handle different response formats
        if isinstance(evaluation, dict):
            # Direct dict format
            eval_data = evaluation
        elif isinstance(evaluation, list) and len(evaluation) > 0:
            # List format - use first item or merge
            eval_data = evaluation[0] if len(evaluation) == 1 else {}
            # Try to merge multiple items
            for item in evaluation:
                if isinstance(item, dict):
                    eval_data.update(item)
        else:
            eval_data = {}
        
        report.append(f"\n### Letter Grades:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = eval_data.get(grade_field, 'UNKNOWN')
            metric = eval_data.get(metric_field)
            
            if grade == "PASS":
                status_icon = "✅ PASS"
                passing += 1
            elif grade == "FAIL":
                status_icon = "❌ FAIL"
                failing_letters.append(letter)
            else:
                status_icon = "⚪ UNKNOWN"
            
            metric_str = f" (metric={metric})" if metric is not None else ""
            report.append(f"    {letter}: {status_icon}{metric_str}")
        
        report.insert(1, f"**Score**: {passing}/10")
        
        if failing_letters:
            critical_failing = [l for l in failing_letters if l in ['B', 'I', 'J']]
            report.append(f"\n### Priority Fixes Needed:")
            if critical_failing:
                report.append(f"🎯 **CRITICAL**: {', '.join(critical_failing)}")
            other_failing = [l for l in failing_letters if l not in ['B', 'I', 'J']]
            if other_failing:
                report.append(f"⚠️ Other: {', '.join(other_failing)}")
    else:
        report.append("❌ No evaluation data available")
    
    return "\n".join(report)

def main():
    print("🔍 MY SHARD-2 County Status Verification")
    print(f"Target counties: {', '.join(MY_SHARD2_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Cannot proceed.")
        return False
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    total_score = 0
    total_possible = 0
    
    for county in MY_SHARD2_COUNTIES:
        print(f"Processing {county}...")
        
        evaluation = get_county_evaluation(county)
        auction_count = get_auction_counts(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'auction_count': auction_count
        }
    
    # Generate reports
    print("\n" + "="*80)
    print("MY SHARD-2 COUNTY STATUS REPORT")
    print("="*80)
    
    for county in MY_SHARD2_COUNTIES:
        data = county_data.get(county, {})
        evaluation = data.get('evaluation')
        auction_count = data.get('auction_count', 0)
        
        print(format_county_report(county, evaluation, auction_count))
        
        # Count scores
        if evaluation and isinstance(evaluation, dict):
            passing = sum(1 for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                         if evaluation.get(f"grade_{letter.lower()}") == "PASS")
            total_score += passing
            total_possible += 10
    
    print(f"\n" + "="*80)
    print("OVERALL SUMMARY")
    print("="*80)
    if total_possible > 0:
        print(f"Total Score: {total_score}/{total_possible} ({total_score/total_possible*100:.1f}%)")
    
    print(f"\nRECOMMENDED FOCUS ORDER:")
    print("1. B: Verified independent outcomes (CRITICAL)")
    print("2. I: Property card completion (CRITICAL)") 
    print("3. J: Deal thesis completion (CRITICAL)")
    print("4. Start with highest-scoring counties first")
    
    print(f"\n🎯 NEXT ACTIONS:")
    print("1. Create Letter B verified outcomes scrapers for each county")
    print("2. Build Letter I property card enrichment pipelines")
    print("3. Enable Letter J deal thesis calculation")
    print("4. Verify metrics move with fresh evaluations after each fix")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)