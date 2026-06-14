#!/usr/bin/env python3
"""
SHARD-11 County Verification - Session 24 (2026-06-14)
Verify assigned counties: orange, flagler, pasco, gadsden, wakulla
Get current A-J letter grades and plan execution
"""
import os
import requests
import json
from datetime import datetime

# Issue briefing assigned counties
ISSUE_COUNTIES = ['orange', 'flagler', 'pasco', 'gadsden', 'wakulla']

# Supabase configuration  
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY found in environment")
    print("Available keys:", [k for k in os.environ.keys() if 'SUPABASE' in k])
    exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def test_connection():
    """Test basic Supabase connection"""
    try:
        # Try to access a simple table
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={"limit": "1"},
            timeout=10
        )
        
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
    """Get current A-J metrics for county using pencil_dod_evaluate_county"""
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
            print(f"⚠️ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def analyze_county_priorities(county, evaluation):
    """Analyze which letters need priority work for this county"""
    if not evaluation:
        return {"priority": "UNKNOWN - no evaluation data"}
    
    failing_letters = []
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        grade_field = f"grade_{letter.lower()}"
        if evaluation.get(grade_field) != "PASS":
            failing_letters.append(letter)
    
    # Map to Brevard Sprint Order priorities
    priority_analysis = {
        "failing_letters": failing_letters,
        "total_passing": 10 - len(failing_letters),
        "brevard_priorities": []
    }
    
    # C/D ROOT CAUSE priority
    if 'C' in failing_letters or 'D' in failing_letters:
        priority_analysis["brevard_priorities"].append("C/D ROOT CAUSE - parity audit")
    
    # J GENERATOR priority  
    if 'J' in failing_letters:
        priority_analysis["brevard_priorities"].append("J GENERATOR - bid_decisions pipeline")
    
    # G HIT LIST priority
    if 'G' in failing_letters:
        priority_analysis["brevard_priorities"].append("G HIT LIST - zone_standards backfill")
    
    # B RECONCILIATION priority
    if 'B' in failing_letters:
        priority_analysis["brevard_priorities"].append("B RECONCILIATION - verified_outcomes anomaly")
    
    return priority_analysis

def main():
    print("🎯 SHARD-11 County Verification - Session 24")
    print(f"Assigned counties: {', '.join(ISSUE_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Test connection
    if not test_connection():
        return False
    
    print("📊 Getting current county metrics...\n")
    
    # Collect data for each assigned county
    county_results = {}
    session_priorities = []
    
    for county in ISSUE_COUNTIES:
        print(f"🔍 Processing {county}...")
        
        evaluation = get_county_evaluation(county)
        if evaluation:
            priorities = analyze_county_priorities(county, evaluation)
            county_results[county] = {
                "evaluation": evaluation,
                "analysis": priorities
            }
            
            # Extract current scores
            total_pass = priorities["total_passing"]
            print(f"  📈 Current score: {total_pass}/10 PASS")
            print(f"  🎯 Priority work: {priorities['brevard_priorities']}")
            
            # Add to session priorities
            session_priorities.extend(priorities['brevard_priorities'])
        else:
            print(f"  ❌ No evaluation data for {county}")
            county_results[county] = {"error": "No evaluation data"}
    
    # Generate session execution plan
    print(f"\n{'='*60}")
    print("SHARD-11 EXECUTION PLAN")
    print("="*60)
    
    # Deduplicate and prioritize
    unique_priorities = []
    for priority in ["C/D ROOT CAUSE - parity audit", "J GENERATOR - bid_decisions pipeline", 
                     "G HIT LIST - zone_standards backfill", "B RECONCILIATION - verified_outcomes anomaly"]:
        if priority in session_priorities and priority not in unique_priorities:
            unique_priorities.append(priority)
    
    print("Session priorities based on current failing letters:")
    for i, priority in enumerate(unique_priorities, 1):
        print(f"{i}. {priority}")
    
    print(f"\n💾 Saving results to shard11_session_plan.json")
    
    # Save detailed results
    session_data = {
        "session_info": {
            "timestamp": datetime.now().isoformat(),
            "shard": "SHARD-11",
            "assigned_counties": ISSUE_COUNTIES,
            "session_budget": "6 hours",
            "ship_to_main": True
        },
        "county_evaluations": county_results,
        "execution_priorities": unique_priorities,
        "next_steps": [
            "Execute priority fixes in Brevard Sprint Order",
            "Apply ULTRALOOP adversarial verification",
            "Collect SQL verification evidence",
            "Commit directly to main (no PRs)"
        ]
    }
    
    with open("shard11_session_plan.json", "w") as f:
        json.dump(session_data, f, indent=2)
    
    print("✅ County verification complete")
    return True

if __name__ == "__main__":
    main()