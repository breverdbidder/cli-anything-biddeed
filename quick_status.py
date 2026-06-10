#!/usr/bin/env python3
"""
Quick database status check using standard library
"""
import json
import os
import urllib.request
import urllib.parse

def check_gold_standard():
    """Check current gold standard status"""
    SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    print(f"Database URL: {SUPABASE_URL}")
    print(f"API Key available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    if not SUPABASE_KEY:
        print("\n❌ CRITICAL: No SUPABASE_KEY found")
        print("Available env vars:")
        for key in sorted(os.environ.keys()):
            if 'SUPABASE' in key or 'KEY' in key:
                print(f"  {key}: {'[SET]' if os.environ[key] else '[EMPTY]'}")
        return
    
    # Test API connection
    url = f"{SUPABASE_URL}/rest/v1/gold_standard_scoreboard?select=county_slug,pass_count,gold_standard,critical_three_pass&order=pass_count.desc&limit=20"
    
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        print("\n✅ Database connection successful!")
        print("\n📊 Current Gold Standard Status:")
        print("=" * 60)
        print(f"{'County':<15} {'Pass':<6} {'Gold':<6} {'Critical3':<10}")
        print("=" * 60)
        
        for county in data:
            pass_count = county.get('pass_count', 0)
            gold = "🏆" if county.get('gold_standard', False) else "  "
            critical = "✅" if county.get('critical_three_pass', False) else "  "
            print(f"{county['county_slug']:<15} {pass_count:<6}/10 {gold:<6} {critical:<10}")
            
        # Focus on our target counties
        print("\n🎯 TARGET COUNTIES (Issue #7498):")
        print("=" * 40)
        targets = ['charlotte', 'brevard', 'broward']
        target_data = [c for c in data if c['county_slug'] in targets]
        
        for county in target_data:
            pass_count = county.get('pass_count', 0)
            print(f"  {county['county_slug']:<12} {pass_count}/10 PASS")
            
    except Exception as e:
        print(f"\n❌ Database error: {e}")

if __name__ == "__main__":
    check_gold_standard()