#!/usr/bin/env python3
"""
SHARD-28 ASSIGNED COUNTIES VERIFICATION
Charlotte, Citrus, Highlands county status verification

This script checks the current Gold Standard metrics for the counties
assigned to this session: charlotte, citrus, highlands
"""
import os
import sys
import json
import httpx
from datetime import datetime, timezone

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ASSIGNED_COUNTIES = ['charlotte', 'citrus', 'highlands']

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY environment variable required")
    print("Set via: export SUPABASE_KEY='your-key-here'")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=HEADERS)
        
        if r.status_code == 200:
            log("✅ Database connection successful")
            return True
        else:
            log(f"❌ Database connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            log(f"✅ County evaluation for {county_slug.upper()}:")
            
            pass_count = 0
            metrics = {}
            
            if isinstance(result, list) and len(result) > 0:
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    threshold = letter_data.get('threshold')
                    
                    if passes:
                        pass_count += 1
                    
                    status = "✅ PASS" if passes else "❌ FAIL"
                    print(f"  {letter}: {status} metric={metric} [{letter_data.get('details', '')}]")
                    
                    metrics[letter] = {
                        'metric': metric,
                        'passes': passes,
                        'threshold': threshold,
                        'details': letter_data.get('details', '')
                    }
                
                log(f"📊 {county_slug.upper()} TOTAL: {pass_count}/10")
            return metrics
        else:
            log(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        log(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_failing_letters(county_metrics):
    """Get list of failing letters for a county"""
    failing_letters = []
    if county_metrics:
        for letter, data in county_metrics.items():
            if not data.get('passes', False):
                failing_letters.append({
                    'letter': letter,
                    'metric': data.get('metric'),
                    'details': data.get('details', '')
                })
    return failing_letters

def prioritize_fixes(county_metrics_dict):
    """Prioritize fixes based on sprint orders and highest leverage"""
    priorities = []
    
    for county, metrics in county_metrics_dict.items():
        failing = get_failing_letters(metrics)
        
        # Based on the sprint orders in the issue:
        # 1. B verified outcomes (critical three)
        # 2. I property card complete (critical three) 
        # 3. J deal thesis (critical three)
        # 4. C/D parity
        # 5. E parcel linkage
        # 6. F tier1 sold
        # 7. G zoning
        # 8. H freshness
        
        letter_priority = {'B': 1, 'I': 2, 'J': 3, 'C': 4, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8}
        
        for fail in failing:
            letter = fail['letter']
            priority = letter_priority.get(letter, 9)
            priorities.append({
                'county': county,
                'letter': letter,
                'priority': priority,
                'metric': fail['metric'],
                'details': fail['details']
            })
    
    # Sort by priority (lower number = higher priority)
    priorities.sort(key=lambda x: (x['priority'], x['county'], x['letter']))
    return priorities

def main():
    """Main verification function"""
    log("🎯 GOLD STANDARD AUTOPILOT-NEXT: County Status Verification")
    log(f"Assigned counties: {', '.join(ASSIGNED_COUNTIES)}")
    
    # Test connection first
    if not test_connection():
        return None
    
    # Get current metrics for all assigned counties
    county_metrics = {}
    
    for county in ASSIGNED_COUNTIES:
        log(f"\n📊 Evaluating {county.upper()}...")
        metrics = evaluate_county_current(county)
        if metrics:
            county_metrics[county] = metrics
    
    # Calculate total metrics
    total_passes = 0
    total_possible = len(ASSIGNED_COUNTIES) * 10
    
    for county, metrics in county_metrics.items():
        county_passes = sum(1 for data in metrics.values() if data.get('passes', False))
        total_passes += county_passes
        log(f"📈 {county.upper()}: {county_passes}/10")
    
    log(f"🎯 TOTAL SHARD SCORE: {total_passes}/{total_possible}")
    
    # Get prioritized fix list
    priority_fixes = prioritize_fixes(county_metrics)
    
    log("\n🔧 PRIORITIZED FIX LIST:")
    for i, fix in enumerate(priority_fixes[:10], 1):  # Top 10 priorities
        log(f"{i:2d}. {fix['county'].upper()}-{fix['letter']} (P{fix['priority']}) - {fix['details']}")
    
    return {
        'county_metrics': county_metrics,
        'total_score': f"{total_passes}/{total_possible}",
        'priority_fixes': priority_fixes
    }

if __name__ == "__main__":
    try:
        result = main()
        if result:
            log("\n✅ County verification complete")
        else:
            log("\n❌ County verification failed")
            sys.exit(1)
    except Exception as e:
        log(f"❌ Verification error: {e}", "ERROR")
        sys.exit(1)