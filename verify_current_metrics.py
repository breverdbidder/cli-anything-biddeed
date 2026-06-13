#!/usr/bin/env python3
"""
Verify current Gold Standard metrics for brevard and duval counties
Run 20 status check - session start verification
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties for this session
TARGET_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test database connection"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/audit_log",
            headers=headers,
            params={"limit": "1"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get county evaluation using pencil_dod_evaluate_county"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_name": county},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error evaluating {county}: {e}")
        return None

def main():
    print("🔍 Gold Standard Autopilot - Run 20 Verification")
    print(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test connection
    if not test_connection():
        print("❌ Cannot proceed without database access")
        print("Environment check:")
        print(f"SUPABASE_URL: {SUPABASE_URL}")
        print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
        return
    
    print("\n📊 Current Gold Standard Metrics:")
    
    for county in TARGET_COUNTIES:
        print(f"\n## {county.upper()} County")
        
        evaluation = get_county_evaluation(county)
        if evaluation:
            score = sum(1 for letter in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'] 
                       if evaluation.get(f'grade_{letter}') == 'PASS')
            
            print(f"Score: {score}/10")
            
            # Show letter grades with metrics
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade_field = f"grade_{letter.lower()}"
                metric_field = f"metric_{letter.lower()}"
                
                grade = evaluation.get(grade_field, 'UNKNOWN')
                metric = evaluation.get(metric_field)
                
                status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL" 
                metric_str = f" metric={metric}" if metric is not None else ""
                
                print(f"    {letter}: {status_icon}{metric_str}")
        else:
            print("    ❌ Could not retrieve evaluation")

if __name__ == "__main__":
    main()