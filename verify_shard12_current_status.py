#!/usr/bin/env python3
"""
SHARD-12 County Status Verification for Issue #7797
Check current A-J letter grades for: sarasota, hendry, pasco, glades

Based on issue metrics:
- sarasota (2/10): A PASS metric=3153 [fc=3516 td=3153], H PASS metric=4.1
- hendry (1/10): D PASS metric=100.0 [matched_any=62 of 62]  
- pasco (1/10): A PASS metric=3808 [fc=9661 td=3808]
- glades (0/10): All metrics failing or null

Usage:
  python verify_shard12_current_status.py
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
    try:
        import requests
        print("✅ requests fallback available")
        httpx = None
    except ImportError:
        print("❌ Neither httpx nor requests available")
        sys.exit(1)

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties for SHARD-12 (from issue #7797)
SHARD12_COUNTIES = ['sarasota', 'hendry', 'pasco', 'glades']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test Supabase connection"""
    try:
        if httpx:
            client = httpx.Client(timeout=30)
            response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        else:
            import requests
            response = requests.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers(), timeout=30)
            
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        if httpx:
            client = httpx.Client(timeout=90)
            # Force fresh evaluation with proper RPC parameter name
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers={**sb_headers(), "Cache-Control": "no-cache"},
                json={"county_slug_arg": county_slug}
            )
        else:
            import requests
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers={**sb_headers(), "Cache-Control": "no-cache"},
                json={"county_slug_arg": county_slug},
                timeout=90
            )
        
        if response.status_code == 200:
            result = response.json()
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def format_county_metrics(county, evaluation_data):
    """Format county evaluation data for display"""
    if not evaluation_data:
        return f"\n{county.upper()}: ❌ Could not evaluate"
    
    metrics = {}
    pass_count = 0
    
    for letter_data in evaluation_data:
        letter = letter_data.get('letter', '?')
        metric = letter_data.get('metric')
        passes = letter_data.get('pass', False)
        threshold = letter_data.get('threshold', 95.0)
        note = letter_data.get('note', '')
        
        metrics[letter] = {
            'metric': metric,
            'passes': passes,
            'threshold': threshold,
            'note': note
        }
        
        if passes:
            pass_count += 1
    
    # Format display
    report = [f"\n{county.upper()} ({pass_count}/10):"]
    
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        if letter in metrics:
            data = metrics[letter]
            status = "✅ PASS" if data['passes'] else "❌ FAIL"
            metric_val = data['metric']
            if metric_val is not None:
                if isinstance(metric_val, (int, float)):
                    metric_str = f"metric={metric_val:.1f}"
                else:
                    metric_str = f"metric={metric_val}"
            else:
                metric_str = "metric=null"
            
            note_str = f" [{data['note']}]" if data['note'] else ""
            report.append(f"    {letter} {status} {metric_str}{note_str}")
        else:
            report.append(f"    {letter} ❌ NO DATA")
    
    return "\n".join(report)

def analyze_priority_targets(county_evaluations):
    """Analyze which letters have highest leverage for improvement"""
    print(f"\n{'='*80}")
    print("🎯 PRIORITY TARGET ANALYSIS")
    print(f"{'='*80}")
    
    failing_letters = {}
    
    for county, evaluation in county_evaluations.items():
        if not evaluation:
            continue
            
        for letter_data in evaluation:
            letter = letter_data.get('letter')
            passes = letter_data.get('pass', False)
            metric = letter_data.get('metric')
            
            if not passes:
                if letter not in failing_letters:
                    failing_letters[letter] = []
                failing_letters[letter].append({
                    'county': county,
                    'metric': metric
                })
    
    # Show analysis per the CRITERION-PARALLEL PIVOT guidance
    print("\n📊 Cross-county failing letter analysis:")
    for letter in sorted(failing_letters.keys()):
        counties_failing = failing_letters[letter]
        print(f"\nLetter {letter}: {len(counties_failing)} counties failing")
        for entry in counties_failing:
            metric_str = f"{entry['metric']:.1f}" if entry['metric'] is not None else "null"
            print(f"  - {entry['county']}: {metric_str}")
    
    # Identify highest-leverage targets based on issue guidance
    high_leverage = []
    if 'C' in failing_letters or 'D' in failing_letters:
        high_leverage.append("C/D: Parity matching (forensics/litmus audit per 08:00Z window)")
    if 'E' in failing_letters:
        high_leverage.append("E: Parcel linkage (dependency for I criteria)")
    if 'G' in failing_letters:
        high_leverage.append("G: Zoning data loading (prerequisite for I)")
    if 'I' in failing_letters:
        high_leverage.append("I: Property cards (requires E+G foundation)")
    if 'J' in failing_letters:
        high_leverage.append("J: Deal analysis (bid_decisions generator)")
    if 'B' in failing_letters:
        high_leverage.append("B: Verified outcomes (critical three, independent source)")
    
    print(f"\n⚡ HIGH-LEVERAGE TARGETS (CRITERION-PARALLEL):")
    for i, target in enumerate(high_leverage, 1):
        print(f"{i}. {target}")
    
    return failing_letters

def main():
    print("🔍 SHARD-12 County Status Verification - Issue #7797")
    print(f"Target counties: {', '.join(SHARD12_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Verify environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found. Checking environment...")
        available_keys = [k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k]
        print(f"Available database env vars: {available_keys}")
        return False
    
    # Test connection
    if not test_connection():
        print("❌ Database connection failed")
        return False
    
    print("📊 Gathering fresh county evaluations...\n")
    
    # Collect fresh evaluation data
    county_evaluations = {}
    for county in SHARD12_COUNTIES:
        print(f"Evaluating {county}...")
        evaluation = get_county_evaluation(county)
        county_evaluations[county] = evaluation
    
    # Display current status
    print(f"\n{'='*80}")
    print("📊 CURRENT GOLD STANDARD STATUS")
    print(f"{'='*80}")
    
    for county in SHARD12_COUNTIES:
        evaluation = county_evaluations[county]
        print(format_county_metrics(county, evaluation))
    
    # Priority analysis 
    analyze_priority_targets(county_evaluations)
    
    # Summary for next actions
    print(f"\n{'='*80}")
    print("🚀 NEXT ACTIONS")
    print(f"{'='*80}")
    print("\nBased on CRITERION-PARALLEL PIVOT guidance:")
    print("1. 08:00Z window: Focus forensics/parity (C/D) + E linkage")
    print("2. 16:00Z window: I/J generator build")
    print("3. 00:00Z window: Data backfill + reconcile PASSes")
    print("\nFollow ship-to-main mandate - commit directly, no branches")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
    else:
        print("\n✅ Status verification complete")
        print("\n### SQL VERIFICATION READY")
        print("-- Run after implementing fixes:")
        for county in SHARD12_COUNTIES:
            print(f"SELECT public.pencil_dod_evaluate_county('{county}');")
        print(f"-- Timestamp: {datetime.utcnow().isoformat()}Z")