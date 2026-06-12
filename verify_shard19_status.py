#!/usr/bin/env python3
"""
SHARD-19 County Status Verification - Run 19 Autonomous Session  
Check current A-J letter grades for charlotte, citrus, broward

Usage:
  python verify_shard19_status.py
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

# Target counties for SHARD-19 (Run 19)
SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

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
        # Use RPC call to the evaluation function - try both parameter patterns
        for param_name in ["county_slug_arg", "county_name"]:
            payload = {param_name: county}
            response = requests.post(
                f"{BASE}/rpc/pencil_dod_evaluate_county", 
                headers=HEADERS, 
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code != 400:  # Not a parameter name issue
                print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
                return None
        
        print(f"⚠️ Failed to evaluate {county} with both parameter patterns")
        return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_county_status_scoreboard():
    """Get current gold standard scoreboard for all counties"""
    try:
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={
                "select": "*",
                "order": "county_slug"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to get scoreboard: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting scoreboard: {e}")
        return None

def format_county_report(county, evaluation_result):
    """Format a detailed county report from evaluation result"""
    report = [f"\n## {county.upper()} County Status"]
    
    if evaluation_result and isinstance(evaluation_result, list):
        total_pass = sum(1 for item in evaluation_result if item.get('pass', False))
        report.append(f"**Score**: {total_pass}/10")
        
        report.append("\n### Letter Grades:")
        
        # Sort by letter
        sorted_letters = sorted(evaluation_result, key=lambda x: x.get('letter', 'Z'))
        
        for item in sorted_letters:
            letter = item.get('letter', '?')
            metric = item.get('metric')
            passed = item.get('pass', False)
            
            status_icon = "✅ PASS" if passed else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else " (metric=null)"
            
            # Extract context for failed letters
            context = ""
            if not passed and 'context' in item:
                ctx = item['context']
                if isinstance(ctx, dict):
                    # Extract key metrics from context
                    ctx_parts = []
                    for key in ['fc', 'td', 'verified', 'closed_sold', 'matched_clean', 'matched_any', 'parcel_linked', 'tier1_sold']:
                        if key in ctx:
                            ctx_parts.append(f"{key}={ctx[key]}")
                    if ctx_parts:
                        context = f" [{' '.join(ctx_parts)}]"
            
            report.append(f"**{letter}**: {status_icon}{metric_str}{context}")
    else:
        report.append("❌ No evaluation data available")
    
    return "\n".join(report)

def main():
    print("🔍 SHARD-19 County Status Verification - AUTOPILOT Run 19")
    print(f"Target counties: {', '.join(SHARD19_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        available_env_vars = [k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]
        print(f"Available env vars: {available_env_vars}")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD19_COUNTIES:
        print(f"Processing {county}...")
        
        # Get live evaluation using function
        evaluation = get_county_evaluation(county)
        
        county_data[county] = {
            'evaluation': evaluation
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("SHARD-19 COUNTY STATUS REPORT (Live Evaluation)")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        print(format_county_report(county, evaluation))
    
    # Summary with specific failing letters per brief
    print(f"\n" + "="*60)
    print("PRIORITY ANALYSIS PER BRIEF")
    print("="*60)
    
    print("\nFrom issue brief:")
    print("charlotte (3/10): A✓ H✓ | B❌ null | C❌ 10.1 | D✓ 97.4 | E❌ 43.8 | F❌ 2.1 | G❌ null | I❌ null | J❌ 0.0")
    print("citrus (3/10): A✓ H✓ | B❌ null | C❌ 9.5 | D❌ 75.3 | E✓ 95.3 | F❌ 6.1 | G❌ null | I❌ null | J❌ 0.0")  
    print("broward (2/10): A✓ H✓ | B❌ null | C❌ 19.4 | D❌ 47.7 | E❌ 20.6 | F❌ 2.5 | G❌ null | I❌ null | J❌ 0.0")
    
    print("\nNext steps based on briefing directives:")
    print("1. Focus C/D parity fixes (PropertyOnion vs clerk source coverage)")
    print("2. Build J generator (bid_decisions pipeline) - highest leverage") 
    print("3. E parcel linkage improvements (county GIS integration)")
    print("4. B verified outcomes (independent source requirement)")
    print("5. Wire all implementations to schedulers/executors")
    
    total_counties = len(SHARD19_COUNTIES)
    evaluated_counties = sum(1 for data in county_data.values() if data.get('evaluation'))
    
    print(f"\nCounties successfully evaluated: {evaluated_counties}/{total_counties}")
    
    return county_data

if __name__ == "__main__":
    main()