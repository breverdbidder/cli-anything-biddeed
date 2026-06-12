#!/usr/bin/env python3
"""
Verify current status of target counties: charlotte, citrus, broward
Based on the Gold Standard criteria A-J
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

# Target counties from issue brief
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

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

def main():
    print("🔍 Gold Standard County Status - Charlotte, Citrus, Broward")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    for county in TARGET_COUNTIES:
        print(f"\n=== {county.upper()} COUNTY ===")
        
        # Get evaluation using function  
        evaluation = get_county_evaluation(county)
        
        if evaluation:
            score = 0
            failing_letters = []
            
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade_field = f"grade_{letter.lower()}"
                metric_field = f"metric_{letter.lower()}"
                
                grade = evaluation.get(grade_field, 'UNKNOWN')
                metric = evaluation.get(metric_field)
                
                if grade == 'PASS':
                    score += 1
                    status_icon = "✅ PASS"
                else:
                    failing_letters.append(letter)
                    status_icon = "❌ FAIL"
                
                metric_str = f" metric={metric}" if metric is not None else ""
                print(f"    {letter}: {status_icon}{metric_str}")
            
            print(f"\n    SCORE: {score}/10")
            if failing_letters:
                print(f"    FAILING: {', '.join(failing_letters)}")
        else:
            print("    ❌ Could not retrieve evaluation")

if __name__ == "__main__":
    main()