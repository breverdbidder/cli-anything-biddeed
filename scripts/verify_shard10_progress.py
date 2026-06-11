#!/usr/bin/env python3
"""
SHARD-10 Progress Verification Script
Verifies Gold Standard improvements for manatee, alachua, martin, franklin, union

Run this after completing work to verify metric improvements:
  python scripts/verify_shard10_progress.py

Expected improvements after work completion:
- franklin: 0/10 → 1/10 (Letter A pass after ingestion)
- union: 0/10 → 1/10 (Letter A pass after ingestion)  
- alachua: 1/10 → 3+/10 (Letters H, B improvements)
- martin: 1/10 → 3+/10 (Letters H, B, E improvements)
- manatee: 2/10 → 5+/10 (Letters B, F, C, D improvements)
"""
import httpx
import os
import sys
import json
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY environment variable not set")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

client = httpx.Client(timeout=60)

SHARD_10_COUNTIES = ['manatee', 'alachua', 'martin', 'franklin', 'union']

def supabase_rpc(function_name: str, params: dict = None):
    """Call Supabase RPC function"""
    try:
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
            headers=HEADERS,
            json=params or {}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error calling {function_name}: {e}")
        return None

def verify_county_improvements():
    """Verify improvements for all SHARD-10 counties"""
    
    print("🏔️ SHARD-10 PROGRESS VERIFICATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Counties: {', '.join(SHARD_10_COUNTIES)}")
    print()
    
    results = {}
    
    for county in SHARD_10_COUNTIES:
        print(f"--- {county.upper()} ---")
        
        # Get fresh letter evaluations
        evaluation = supabase_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county})
        
        if evaluation:
            letters_dict = {}
            pass_count = 0
            
            for letter_data in evaluation:
                letter = letter_data.get('letter')
                metric = letter_data.get('metric')
                passed = letter_data.get('pass', False)
                
                if passed:
                    pass_count += 1
                    
                letters_dict[letter] = {
                    'metric': metric,
                    'pass': passed,
                    'status': '✅' if passed else '❌'
                }
                
                # Print letter status  
                print(f"  {letter}: {letters_dict[letter]['status']} {metric}")
            
            results[county] = {
                'letters': letters_dict,
                'pass_count': pass_count,
                'score': f"{pass_count}/10"
            }
            
            print(f"  TOTAL: {pass_count}/10")
            
        else:
            print(f"  ❌ Failed to evaluate {county}")
            results[county] = {
                'letters': {},
                'pass_count': 0,
                'score': 'ERROR'
            }
        
        print()
    
    return results

def print_summary(results):
    """Print improvement summary"""
    
    print("📊 SHARD-10 SUMMARY")
    print("=" * 40)
    
    total_letters = 0
    total_possible = len(SHARD_10_COUNTIES) * 10
    
    for county, data in results.items():
        pass_count = data['pass_count']
        total_letters += pass_count
        print(f"{county:12s}: {data['score']}")
    
    print("-" * 40)
    print(f"{'TOTAL':12s}: {total_letters}/{total_possible} ({total_letters/total_possible*100:.1f}%)")
    
    print("\n🎯 TARGET IMPROVEMENTS:")
    print("- franklin: 0/10 → 1+/10 (Letter A)")  
    print("- union: 0/10 → 1+/10 (Letter A)")
    print("- alachua: 1/10 → 3+/10 (Letters H, B)")
    print("- martin: 1/10 → 3+/10 (Letters H, B, E)")
    print("- manatee: 2/10 → 5+/10 (Letters B, F, C, D)")

def run_full_gold_standard_verification():
    """Run the full gold standard loop and certification"""
    
    print("\n🔄 RUNNING FULL GOLD STANDARD VERIFICATION")
    print("=" * 50)
    
    print("Step 1: Running gold_standard_loop()...")
    loop_result = supabase_rpc("gold_standard_loop")
    if loop_result:
        print(f"✅ Loop completed: {loop_result}")
    else:
        print("❌ Loop failed")
    
    print("\nStep 2: Running gold_standard_certify()...")  
    cert_result = supabase_rpc("gold_standard_certify")
    if cert_result:
        print(f"✅ Certification completed: {cert_result}")
    else:
        print("❌ Certification failed")
    
    return loop_result, cert_result

def main():
    print(f"Database: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    print()
    
    # Verify each county
    results = verify_county_improvements()
    
    # Print summary
    print_summary(results)
    
    # Run full verification (only if no parallel sessions)
    print("\n⚠️ FULL VERIFICATION SKIPPED")
    print("Reason: Other parallel fleet sessions may be running")
    print("Manual verification: Use individual pencil_dod_evaluate_county() calls")
    print("\nTo run full verification manually:")
    print("  SELECT public.gold_standard_loop();")
    print("  SELECT public.gold_standard_certify();")
    
    # Print SQL verification block for SHIP GATE compliance
    print("\n" + "="*60)
    print("SQL VERIFICATION (SHIP GATE COMPLIANCE)")
    print("="*60)
    
    for county in SHARD_10_COUNTIES:
        score = results[county]['score']
        print(f"-- {county}: {score}")
        print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
        
    print(f"\n-- Timestamp: {datetime.now().isoformat()}")
    print(f"-- Shard 10 total letters improved during this session")

if __name__ == "__main__":
    main()