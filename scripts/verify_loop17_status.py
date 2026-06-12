#!/usr/bin/env python3
"""
Loop 17 County Status Verification
Check current A-J letter grades for charlotte, citrus, broward counties

Usage:
  python scripts/verify_loop17_status.py
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

# Target counties for Loop 17
LOOP17_COUNTIES = ['charlotte', 'citrus', 'broward']

def test_connection():
    """Test Supabase connection"""
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found in environment")
        return False
        
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

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={
                "county_slug": f"eq.{county}",
                "order": "loop_run_id.desc",
                "limit": "1"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]
            else:
                print(f"⚠️ No status found for {county}")
                return None
        else:
            print(f"⚠️ Failed to get status for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting status for {county}: {e}")
        return None

def get_auction_counts(county):
    """Get basic auction counts for a county"""
    try:
        response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "select": "count",
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return len(data) if data else 0
        else:
            print(f"⚠️ Failed to get auction counts for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting auction counts for {county}: {e}")
        return None

def print_county_summary(county, evaluation, status, auction_count):
    """Print formatted county summary"""
    print(f"\n{'='*50}")
    print(f"COUNTY: {county.upper()}")
    print(f"{'='*50}")
    
    # Current pass count from status
    if status:
        pass_count = status.get('pass_count', 'N/A')
        print(f"Current Score: {pass_count}/10")
        print(f"Loop Run: {status.get('loop_run_id', 'N/A')}")
    
    # Auction count
    if auction_count is not None:
        print(f"Total Auctions: {auction_count:,}")
    
    # Letter by letter evaluation
    if evaluation:
        print(f"\nLetter Details:")
        for letter_data in evaluation:
            letter = letter_data.get('letter', '?')
            metric = letter_data.get('metric')
            passed = letter_data.get('pass', False)
            status_icon = "✅ PASS" if passed else "❌ FAIL"
            
            if metric is not None:
                if isinstance(metric, (int, float)):
                    if metric > 1:
                        metric_str = f"{metric:,.1f}"
                    else:
                        metric_str = f"{metric:.1f}%"
                else:
                    metric_str = str(metric)
            else:
                metric_str = "null"
                
            print(f"  {letter}: {status_icon} metric={metric_str}")
    
    print()

def run_gold_standard_verification():
    """Execute gold standard verification protocol"""
    print("\n" + "="*60)
    print("GOLD STANDARD VERIFICATION PROTOCOL")
    print("="*60)
    
    # Test connection first
    if not test_connection():
        return False
    
    # Get evaluation for each county
    results = {}
    for county in LOOP17_COUNTIES:
        print(f"\n--- Evaluating {county} ---")
        
        # Get fresh evaluation
        evaluation = get_county_evaluation(county)
        
        # Get status from table
        status = get_county_status_direct(county)
        
        # Get auction counts
        auction_count = get_auction_counts(county)
        
        # Store results
        results[county] = {
            'evaluation': evaluation,
            'status': status,
            'auction_count': auction_count
        }
        
        # Print summary
        print_county_summary(county, evaluation, status, auction_count)
    
    # Print prioritization analysis
    print("="*60)
    print("PRIORITIZATION ANALYSIS")
    print("="*60)
    
    failing_letters = {}
    for county, data in results.items():
        if data['evaluation']:
            for letter_data in data['evaluation']:
                letter = letter_data.get('letter')
                passed = letter_data.get('pass', False)
                if not passed and letter:
                    if letter not in failing_letters:
                        failing_letters[letter] = []
                    failing_letters[letter].append(county)
    
    # Priority based on issue description
    critical_letters = ['B', 'I', 'J']  # Critical three per issue
    
    print(f"\nFailing Letters Summary:")
    for letter in sorted(failing_letters.keys()):
        counties = failing_letters[letter]
        priority = "🔥 CRITICAL" if letter in critical_letters else "📋 Standard"
        print(f"  Letter {letter}: {priority} - {len(counties)} counties ({', '.join(counties)})")
    
    # Specific recommendations
    print(f"\nRECOMMENDATIONS:")
    print(f"1. Letter B (Verified Outcomes): Build independent clerk scrapers")
    print(f"2. Letter E (Parcel Linkage): Improve broward from 20.6% to 95%+") 
    print(f"3. Letters C/D (Parity): Fix matching algorithms")
    print(f"4. Letter F (Tier1 Sold): Verify sold amounts")
    
    return results

if __name__ == "__main__":
    print("="*60)
    print("LOOP 17 GOLD STANDARD STATUS VERIFICATION")
    print(f"Counties: {', '.join(LOOP17_COUNTIES)}")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("="*60)
    
    results = run_gold_standard_verification()
    
    print(f"\n✅ Verification completed at {datetime.utcnow().isoformat()}Z")
    print(f"Next step: Implement highest-leverage improvements for failing letters")