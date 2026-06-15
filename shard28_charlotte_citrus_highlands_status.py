#!/usr/bin/env python3
"""
Verify current status for charlotte, citrus, highlands counties (Shard 28 Session)
"""
import os
import sys
import httpx
import json
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co" 
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for assigned counties"""
    try:
        client = httpx.Client(timeout=60)
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        print(f"\n=== {county_slug.upper()} CURRENT STATUS ===")
        if r.status_code == 200:
            result = r.json()
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passes = letter_data.get('pass', False)
                    if passes:
                        pass_count += 1
                    status = "✅" if passes else "❌"
                    print(f"  {letter}: {status} {metric}")
                print(f"\nScore: {pass_count}/10")
                return result
            else:
                print(f"  ❌ No data returned for {county_slug}")
                return None
        else:
            print(f"  ❌ API error {r.status_code}: {r.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def analyze_priority_targets(counties_data):
    """Analyze counties and identify highest leverage failing letters"""
    print(f"\n{'='*60}")
    print("🎯 PRIORITY TARGET ANALYSIS")
    print(f"{'='*60}")
    
    # Collect all failing letters across counties
    failing_letters = {}
    for county, data in counties_data.items():
        if data:
            for letter_data in data:
                letter = letter_data.get('letter', '?')
                passes = letter_data.get('pass', False)
                metric = letter_data.get('metric')
                
                if not passes:
                    if letter not in failing_letters:
                        failing_letters[letter] = []
                    failing_letters[letter].append({
                        'county': county,
                        'metric': metric
                    })
    
    # Sort by impact (letters failing across most counties)
    sorted_letters = sorted(failing_letters.items(), key=lambda x: len(x[1]), reverse=True)
    
    print("\n🔥 HIGHEST LEVERAGE TARGETS:")
    for letter, failures in sorted_letters[:5]:  # Top 5 priorities
        print(f"\n  Letter {letter}: {len(failures)}/3 counties failing")
        for failure in failures:
            print(f"    - {failure['county']}: {failure['metric']}")
    
    return failing_letters

if __name__ == "__main__":
    print(f"🎯 SHARD 28 GOLD STANDARD: CHARLOTTE, CITRUS, HIGHLANDS")
    print(f"Session start: {datetime.now(timezone.utc).isoformat()}")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    # Test connection
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
        else:
            print(f"❌ Database connection failed: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)
    
    # Evaluate our assigned counties
    target_counties = ['charlotte', 'citrus', 'highlands']
    counties_data = {}
    
    for county in target_counties:
        counties_data[county] = evaluate_county(county)
    
    # Analyze and prioritize
    failing_letters = analyze_priority_targets(counties_data)
    
    print(f"\n{'='*60}")
    print("📋 READY FOR AUTONOMOUS EXECUTION")
    print("Target counties verified, proceeding with highest-leverage fixes...")
    print(f"Session budget: 6 hours")