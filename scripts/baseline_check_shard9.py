#!/usr/bin/env python3
"""
Quick baseline check for SHARD-9 counties
Connects to database and gets current metrics
"""
import os
import requests
import json
from datetime import datetime

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"  
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_KEY", ""))
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-9 counties
COUNTIES = ['lee', 'baker', 'okaloosa', 'dixie', 'taylor']

def test_connection():
    """Test database connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        return response.status_code == 200
    except:
        return False

def get_county_evaluation(county):
    """Get county evaluation using RPC function"""
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
            return {"error": f"HTTP {response.status_code}: {response.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def main():
    print("SHARD-9 BASELINE CHECK")
    print("=" * 40)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found")
        return
    
    if not test_connection():
        print("❌ Database connection failed")
        return
    
    print("✅ Database connected")
    print()
    
    for county in COUNTIES:
        print(f"📊 {county.upper()}")
        evaluation = get_county_evaluation(county)
        
        if "error" in evaluation:
            print(f"   ❌ {evaluation['error']}")
        else:
            # Parse the evaluation data
            if evaluation and isinstance(evaluation, dict):
                total_pass = 0
                letters_detail = []
                
                for letter in 'ABCDEFGHIJ':
                    letter_key = f'letter_{letter.lower()}'
                    if letter_key in evaluation:
                        letter_data = evaluation[letter_key]
                        if isinstance(letter_data, dict):
                            is_pass = letter_data.get('pass', False)
                            metric = letter_data.get('metric')
                            if is_pass:
                                total_pass += 1
                            status = "✓" if is_pass else "✗"
                            if metric is not None:
                                letters_detail.append(f"{letter}:{status}{metric}")
                            else:
                                letters_detail.append(f"{letter}:{status}")
                
                print(f"   Score: {total_pass}/10")
                print(f"   Details: {' '.join(letters_detail[:5])}")
                if len(letters_detail) > 5:
                    print(f"            {' '.join(letters_detail[5:])}")
            else:
                print(f"   Raw response: {json.dumps(evaluation, indent=2)[:200]}...")
        print()

if __name__ == "__main__":
    main()