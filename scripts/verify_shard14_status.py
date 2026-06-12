#!/usr/bin/env python3
"""
SHARD-14 County Status Verification
Check current A-J letter grades for osceola, flagler, santa_rosa, hamilton

Usage:
  python scripts/verify_shard14_status.py
"""
import os
import sys
import json
from datetime import datetime

# Try importing httpx
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

# Target counties for SHARD-14
SHARD14_COUNTIES = ['osceola', 'flagler', 'santa_rosa', 'hamilton']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json"
    }

def test_connection():
    """Test Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
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
        client = httpx.Client(timeout=60)
        
        # Use RPC call to the evaluation function
        payload = {"county_name": county}
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=sb_headers(), 
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_pipeline_config(county):
    """Get pipeline configuration for county"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties", 
            headers=sb_headers(),
            params={
                "county": f"eq.{county}",
                "select": "*"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        else:
            print(f"⚠️ Failed to get pipeline config for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting pipeline config for {county}: {e}")
        return None

def get_auction_counts(county):
    """Get auction counts for county"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions", 
            headers=sb_headers(),
            params={
                "county": f"eq.{county}",
                "select": "count"
            }
        )
        
        if response.status_code == 200:
            return len(response.json())
        else:
            return 0
            
    except Exception as e:
        print(f"⚠️ Error getting auction count for {county}: {e}")
        return 0

def format_county_report(county, evaluation, pipeline_config, auction_count):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    report.append(f"**Auction Count**: {auction_count}")
    
    if pipeline_config:
        report.append(f"**FC Platform**: {pipeline_config.get('foreclosure_platform', 'Not configured')}")
        report.append(f"**TD Platform**: {pipeline_config.get('tax_deed_platform', 'Not configured')}")
    else:
        report.append("**Pipeline**: Not configured")
    
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
            
        # Calculate score
        passing_grades = sum(1 for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'] 
                           if evaluation.get(f"grade_{letter.lower()}") == "PASS")
        report.append(f"\n**Current Score**: {passing_grades}/10")
    else:
        report.append("\n### No evaluation data available")
    
    return "\n".join(report)

def prioritize_work(county_data):
    """Analyze county data and suggest prioritization"""
    priority_suggestions = []
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        auction_count = data.get('auction_count', 0)
        
        if not evaluation:
            if auction_count == 0:
                priority_suggestions.append(f"🔥 **{county}**: Setup pipeline (Letter A) - no auctions found")
            else:
                priority_suggestions.append(f"🔥 **{county}**: Fix evaluation function - {auction_count} auctions exist")
            continue
            
        # Count failing letters
        failing_letters = []
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            if evaluation.get(f"grade_{letter.lower()}") != "PASS":
                failing_letters.append(letter)
        
        # Priority based on issue description
        high_priority = []
        if 'B' in failing_letters:
            high_priority.append('B (verified outcomes)')
        if 'F' in failing_letters:
            high_priority.append('F (tier1 sold-amount)')
        if 'I' in failing_letters:
            high_priority.append('I (property card complete)')
        if 'J' in failing_letters:
            high_priority.append('J (deal thesis)')
        
        if high_priority:
            priority_suggestions.append(f"📊 **{county}**: Focus on {', '.join(high_priority)}")
        elif failing_letters:
            priority_suggestions.append(f"✅ **{county}**: {10-len(failing_letters)}/10 - work on {', '.join(failing_letters[:3])}")
        else:
            priority_suggestions.append(f"🎯 **{county}**: GOLD STANDARD (10/10)")
    
    return priority_suggestions

def main():
    print("🔍 SHARD-14 County Status Verification")
    print(f"Target counties: {', '.join(SHARD14_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed.")
        return
    
    print("📊 Gathering county data...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD14_COUNTIES:
        print(f"Processing {county}...")
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        # Get pipeline configuration
        pipeline_config = get_pipeline_config(county)
        
        # Get auction count
        auction_count = get_auction_counts(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'pipeline_config': pipeline_config,
            'auction_count': auction_count
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-14 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        pipeline_config = data.get('pipeline_config')
        auction_count = data.get('auction_count', 0)
        
        print(format_county_report(county, evaluation, pipeline_config, auction_count))
    
    # Priority analysis
    print(f"\n" + "="*60)
    print("WORK PRIORITIZATION")
    print("="*60)
    
    priority_suggestions = prioritize_work(county_data)
    for suggestion in priority_suggestions:
        print(suggestion)
    
    # Summary
    print(f"\n" + "="*60)
    print("SESSION GUIDANCE")
    print("="*60)
    
    total_counties = len(SHARD14_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    print("\n📋 Remember:")
    print("• Ship directly to main (no PRs)")
    print("• Commit frequently with descriptive messages")
    print("• Run verification protocol after each fix")
    print("• Evidence-before-claims: verify with SQL")
    print("• Focus on highest-leverage failing letters")
    print("• Follow parallel fleet rules (don't touch other shards)")

if __name__ == "__main__":
    main()