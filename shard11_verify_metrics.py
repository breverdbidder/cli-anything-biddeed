#!/usr/bin/env python3
"""
SHARD-11 Gold Standard: Verify current metrics for assigned counties
Counties: manatee(51), clay(20), pasco(61), gadsden(30), wakulla(75)
"""
import os
import httpx
import json
import sys
from datetime import datetime, timezone

# Supabase connection  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

SHARD11_COUNTIES = {
    'manatee': 51,
    'clay': 20, 
    'pasco': 61,
    'gadsden': 30,
    'wakulla': 75
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json"
    }

def verify_connection():
    """Test basic Supabase connectivity"""
    print("🔍 Testing Supabase connectivity...")
    
    if not SUPABASE_KEY:
        print("❌ No SUPABASE_KEY found in environment")
        return False
        
    try:
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=1", headers=sb_headers())
        
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county_slug):
    """Get pencil_dod_evaluate_county results"""
    try:
        client = httpx.Client(timeout=60) 
        payload = {"county_name": county_slug}
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json=payload
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Failed to evaluate {county_slug}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county_slug}: {e}")
        return None

def analyze_priority_fixes():
    """Analyze current status and prioritize fixes"""
    print("\n📊 Current County Metrics (LIVE VERIFICATION)")
    print("=" * 70)
    
    results = {}
    
    for county_slug, co_no in SHARD11_COUNTIES.items():
        print(f"\n🏠 {county_slug.upper()} (CO_NO={co_no})")
        
        # Get current evaluation
        evaluation = get_county_evaluation(county_slug)
        
        if evaluation:
            total_score = evaluation.get('total_score', 0)
            print(f"  Current Score: {total_score}/10")
            
            # Show letter grades and metrics
            failing_letters = []
            for letter in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']:
                grade = evaluation.get(f'grade_{letter}', 'FAIL')
                metric = evaluation.get(f'metric_{letter}')
                
                if grade != 'PASS':
                    failing_letters.append(letter.upper())
                    
                print(f"    {letter.upper()}: {grade:<4} | {metric}")
            
            # Priority analysis based on Brevard Sprint Order
            if len(failing_letters) >= 8:
                priority = "BASIC_SETUP"
            elif 'C' in failing_letters or 'D' in failing_letters:
                priority = "C_D_ROOT_CAUSE"
            elif 'J' in failing_letters:
                priority = "J_GENERATOR"
            elif 'G' in failing_letters:
                priority = "G_HIT_LIST"
            elif 'B' in failing_letters:
                priority = "B_RECONCILIATION"
            else:
                priority = "MAINTENANCE"
                
            results[county_slug] = {
                'evaluation': evaluation,
                'total_score': total_score,
                'failing_letters': failing_letters,
                'priority': priority
            }
            
        else:
            print(f"  ❌ Could not evaluate {county_slug}")
            results[county_slug] = {
                'evaluation': None,
                'total_score': 0,
                'failing_letters': ['ALL'],
                'priority': 'BASIC_SETUP'
            }
    
    # Summary and recommendations
    print("\n🎯 PRIORITY RECOMMENDATIONS")
    print("=" * 70)
    
    basic_setup = [k for k, v in results.items() if v['priority'] == 'BASIC_SETUP']
    high_impact = [k for k, v in results.items() if v['total_score'] > 0 and v['total_score'] < 5]
    
    if basic_setup:
        print(f"🚀 HIGHEST IMPACT: Basic setup for {', '.join(basic_setup)}")
        print("   - Run county ingestion (Letter A)")
        print("   - Move from 0/10 to 1-3/10 quickly")
    
    if high_impact:
        print(f"⚡ HIGH LEVERAGE: Targeted fixes for {', '.join(high_impact)}")
        for county in high_impact:
            failing = results[county]['failing_letters'] 
            print(f"   - {county}: focus on {', '.join(failing[:3])}")
    
    return results

def main():
    print("🚀 SHARD-11 Gold Standard Metrics Verification")
    print(f"Counties: {', '.join(SHARD11_COUNTIES.keys())}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)
    
    # Test connectivity first
    if not verify_connection():
        sys.exit(1)
    
    # Analyze current metrics and priorities
    results = analyze_priority_fixes()
    
    # Save results for reference
    output_file = "/tmp/shard11_metrics_verification.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("✅ Verification complete")

if __name__ == "__main__":
    main()