#!/usr/bin/env python3
"""
SHARD-6 County Status Verification
Check current A-J letter grades for highlands, sumter, jackson, calhoun, liberty

Usage:
  python scripts/shard6_verification.py
"""
import os
import sys
import json
from datetime import datetime

# Try importing httpx first
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties for SHARD-6
SHARD6_COUNTIES = ['highlands', 'sumter', 'jackson', 'calhoun', 'liberty']

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
        # Test with a simple query
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Supabase connection successful")
            return True
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
        
        # Try different parameter names that might work
        for param_name in ["county_name", "county_slug_arg", "county_slug"]:
            payload = {param_name: county}
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
                headers=sb_headers(), 
                json=payload
            )
            
            if r.status_code == 200:
                result = r.json()
                print(f"✅ Successfully evaluated {county} with param '{param_name}'")
                return result
            else:
                print(f"⚠️ Attempt with {param_name} failed: {r.status_code}")
        
        print(f"❌ All parameter attempts failed for {county}")
        return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        client = httpx.Client(timeout=30)
        
        # Try both county and county_slug fields
        for field in ["county", "county_slug"]:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/gold_standard_county_status", 
                headers=sb_headers(), 
                params={
                    field: f"eq.{county}",
                    "select": "*",
                    "order": "loop_run_id.desc",
                    "limit": "1"
                }
            )
            
            if r.status_code == 200:
                data = r.json()
                if data:
                    print(f"✅ Found status for {county} using field '{field}'")
                    return data[0]
            
        print(f"⚠️ No status found for {county}")
        return None
            
    except Exception as e:
        print(f"⚠️ Error getting status for {county}: {e}")
        return None

def format_county_report(county, evaluation, status):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Pass Count**: {status.get('pass_count', 'N/A')}/10") 
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
        report.append(f"**Loop Run**: {status.get('loop_run_id', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        if isinstance(evaluation, list):
            for letter_data in evaluation:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                is_pass = letter_data.get('pass', False)
                
                status_icon = "✅ PASS" if is_pass else "❌ FAIL"
                metric_str = f" (metric={metric})" if metric is not None else ""
                
                report.append(f"**{letter}**: {status_icon}{metric_str}")
        else:
            # Handle legacy format if needed
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade_field = f"grade_{letter.lower()}"
                metric_field = f"metric_{letter.lower()}"
                
                grade = evaluation.get(grade_field, 'UNKNOWN')
                metric = evaluation.get(metric_field)
                
                status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
                metric_str = f" (metric={metric})" if metric is not None else ""
                
                report.append(f"**{letter}**: {status_icon}{metric_str}")
    
    return "\n".join(report)

def main():
    print("🔍 SHARD-6 County Status Verification")
    print(f"Target counties: {', '.join(SHARD6_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Check for API key
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found. Checking GitHub secrets availability...")
        # In GitHub Actions, secrets should be available as environment variables
        print("Available environment variables with 'SUPABASE':", 
              [k for k in os.environ.keys() if 'SUPABASE' in k.upper()])
        return
    
    # Test connection first
    if not test_connection():
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD6_COUNTIES:
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
    print("SHARD-6 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Summary
    print(f"\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    total_counties = len(SHARD6_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"Counties evaluated: {evaluated_counties}/{total_counties}")
    
    if evaluated_counties > 0:
        print("\nNext steps based on current status:")
        print("1. Focus on critical letters B (verified outcomes), I (property cards), J (deal decisions)")
        print("2. Implement and wire all solutions to executors")
        print("3. Follow ship-to-main mandate - commit directly")
        print("4. Verify improvements with fresh evaluations")

if __name__ == "__main__":
    main()