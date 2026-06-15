#!/usr/bin/env python3
"""
SHARD-5 Current Status Query - GOLD STANDARD CAMPAIGN

Queries live status for shard-5 counties: highlands, collier, miami_dade, bradford, levy
Using verified pencil_dod_evaluate_county function pattern.
"""

import os
import json
import requests
from datetime import datetime

# Supabase configuration from CLAUDE.md
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')

def get_county_status(county):
    """Get live county status using pencil_dod_evaluate_county function"""
    if not SUPABASE_SERVICE_ROLE_KEY:
        print(f"ERROR: SUPABASE_SERVICE_ROLE_KEY not found in environment")
        return None
        
    headers = {
        'apikey': SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={'county_slug_arg': county},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"ERROR querying {county}: {e}")
        return None

def analyze_shard5_status():
    """Query and analyze current status for all shard-5 counties"""
    print("=== SHARD-5 GOLD STANDARD STATUS ===")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print()
    
    counties = ['highlands', 'collier', 'miami_dade', 'bradford', 'levy']
    
    for county in counties:
        print(f"📊 {county.upper()} STATUS:")
        
        status = get_county_status(county)
        if not status:
            print("   ❌ Failed to query - check connection")
            continue
            
        # Parse the status based on expected JSON structure
        if isinstance(status, list) and len(status) > 0:
            data = status[0]
        else:
            data = status
            
        try:
            # Extract metrics - adjust based on actual response structure
            letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
            for letter in letters:
                # This may need adjustment based on actual response structure
                metric_key = f"letter_{letter.lower()}_metric"
                status_key = f"letter_{letter.lower()}_status" 
                note_key = f"letter_{letter.lower()}_note"
                
                metric = data.get(metric_key, 'UNKNOWN')
                letter_status = data.get(status_key, 'UNKNOWN')
                note = data.get(note_key, '')
                
                status_emoji = "✅" if letter_status == 'PASS' else "❌" if letter_status == 'FAIL' else "?"
                print(f"   {letter}: {status_emoji} {metric} - {note}")
                
        except Exception as e:
            print(f"   ❌ Error parsing response: {e}")
            print(f"   Raw response: {json.dumps(data, indent=2)}")
        
        print()

def identify_priorities():
    """Identify highest-leverage failing letters for prioritization"""
    print("🎯 SHARD-5 PRIORITY ANALYSIS (from issue brief):")
    print()
    
    priority_mapping = {
        'highlands': '2/10 (A,H pass) - Focus: B,F,C/D,E,G,I,J',
        'collier': '1/10 (A pass) - Focus: All letters except A',
        'miami_dade': '1/10 (A pass) - Focus: All letters except A', 
        'bradford': '0/10 - Zero state, need complete bootstrapping',
        'levy': '0/10 - Zero state, need complete bootstrapping'
    }
    
    for county, priority in priority_mapping.items():
        print(f"   {county}: {priority}")
    
    print()
    print("📋 EXPECTED FOCUS AREAS:")
    print("   • Bradford/Levy: Complete county setup (A lane configuration)")
    print("   • All counties: B verified outcomes (critical path)")
    print("   • All counties: J deal thesis pipeline (highest leverage)")
    print("   • Highlands: C/D parity fixes")
    print("   • Miami-Dade: E parcel linkage (16.7%)")
    print("   • All: G zoning standards completion")

if __name__ == "__main__":
    analyze_shard5_status()
    identify_priorities()
    print("\n✅ Status query complete. Proceeding with prioritized fixes.")