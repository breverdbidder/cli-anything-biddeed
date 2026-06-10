#!/usr/bin/env python3
"""
Gold Standard SHARD-1 Session: citrus, leon, palm_beach
Autonomous 6-hour session to improve A-J letter grades.
"""

import os
import sys
import json
from datetime import datetime, timezone

def log(message):
    """Log with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def get_db_client():
    """Get Supabase client with error handling."""
    try:
        # Use the exact pattern from the repo scripts
        url = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")
        
        if not key:
            log("❌ SUPABASE_KEY not available - cannot proceed")
            return None
            
        # Install supabase if needed
        try:
            from supabase import create_client
        except ImportError:
            log("Installing supabase package...")
            os.system("pip install supabase")
            from supabase import create_client
            
        client = create_client(url, key)
        log(f"✅ Connected to Supabase: {url[:30]}...")
        return client
        
    except Exception as e:
        log(f"❌ Database connection failed: {e}")
        return None

def verify_county_data(client, target_counties):
    """Verify we can access target county data."""
    log("📊 Verifying county data access...")
    
    county_data = {}
    for county_name in target_counties:
        try:
            # Query fl_counties table
            formatted_name = county_name.replace("_", " ").title()
            result = client.table("fl_counties").select("*").eq("name", formatted_name).execute()
            
            if result.data:
                county = result.data[0]
                county_data[county_name] = county
                log(f"  ✅ {county['name']} (co_no={county['co_no']}, region={county['region']})")
            else:
                log(f"  ❌ County {county_name} not found in fl_counties")
                
        except Exception as e:
            log(f"  ❌ Error querying {county_name}: {e}")
            
    return county_data

def query_gold_standard_status(client, county_data):
    """Query current gold standard status for our counties."""
    log("📈 Querying current gold standard status...")
    
    results = {}
    for county_slug, county_info in county_data.items():
        co_no = county_info['co_no']
        try:
            # Try to query the gold standard scoreboard
            result = client.table("gold_standard_scoreboard").select("*").eq("county_slug", county_slug).execute()
            
            if result.data:
                score_data = result.data[0]
                results[county_slug] = score_data
                pass_count = score_data.get('pass_count', 0)
                log(f"  📊 {county_info['name']}: {pass_count}/10 letters passing")
            else:
                # Fall back to basic county info
                log(f"  ⚠️  {county_info['name']}: No gold standard data found")
                results[county_slug] = {"error": "no_gold_standard_data"}
                
        except Exception as e:
            log(f"  ❌ Error querying gold standard for {county_slug}: {e}")
            results[county_slug] = {"error": str(e)}
            
    return results

def analyze_failing_letters(client, results):
    """Analyze which letters are failing for each county."""
    log("🔍 Analyzing failing letter patterns...")
    
    analysis = {}
    letter_priorities = {
        'B': {'name': 'verified_outcomes', 'critical': True},
        'C': {'name': 'parity_clean', 'critical': False}, 
        'D': {'name': 'parity_any', 'critical': False},
        'E': {'name': 'parcel_linkage', 'critical': False},
        'F': {'name': 'tier1_sold', 'critical': False},
        'G': {'name': 'zoning', 'critical': False},
        'I': {'name': 'property_card', 'critical': True},
        'J': {'name': 'deal_thesis', 'critical': True}
    }
    
    for county_slug, score_data in results.items():
        if isinstance(score_data, dict) and 'error' not in score_data:
            county_analysis = {'failing_letters': [], 'critical_failing': []}
            
            for letter, info in letter_priorities.items():
                field_name = f"{letter.lower()}_{info['name']}"
                is_passing = score_data.get(field_name, False)
                
                if not is_passing:
                    county_analysis['failing_letters'].append(letter)
                    if info['critical']:
                        county_analysis['critical_failing'].append(letter)
                        
            analysis[county_slug] = county_analysis
            failing = ', '.join(county_analysis['failing_letters'])
            critical = ', '.join(county_analysis['critical_failing'])
            log(f"  📋 {county_slug}: Failing={failing} | Critical={critical}")
            
    return analysis

def main():
    """Main autonomous session orchestrator."""
    log("🚀 Starting Gold Standard SHARD-1 Session")
    log("Target counties: citrus, leon, palm_beach")
    
    # Step 1: Database connection
    client = get_db_client()
    if not client:
        log("💔 Cannot proceed without database connection")
        return False
    
    # Step 2: Verify county data access
    target_counties = ["citrus", "leon", "palm_beach"]
    county_data = verify_county_data(client, target_counties)
    
    if not county_data:
        log("💔 Cannot proceed without county data access")
        return False
        
    # Step 3: Query current gold standard status
    results = query_gold_standard_status(client, county_data)
    
    # Step 4: Analyze failing patterns
    analysis = analyze_failing_letters(client, results)
    
    # Step 5: Plan and execute fixes (placeholder for now)
    log("📋 Session planning complete - ready for implementation phase")
    
    # Output session state for GitHub comment update
    session_state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "counties_verified": len(county_data),
        "gold_standard_data": len([r for r in results.values() if 'error' not in r]),
        "analysis": analysis
    }
    
    with open("session_state.json", "w") as f:
        json.dump(session_state, f, indent=2)
        
    log(f"💾 Session state saved - {len(county_data)} counties verified")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)