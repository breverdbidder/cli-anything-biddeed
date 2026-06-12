#!/usr/bin/env python3
"""
SHARD 19: BREVARD and DUVAL Counties Verification and Fix Implementation
Run 19 autonomous session - per issue #7602 directives
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration - using pattern from existing scripts
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Our assigned counties per issue #7602
ASSIGNED_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test Supabase connection"""
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

def evaluate_county_live(county):
    """Get live evaluation for county using pencil_dod_evaluate_county function - per issue mandate"""
    try:
        # Use RPC call to the evaluation function as specified in issue
        payload = {"county_name": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=60  # Extended timeout as per CLAUDE.md guidance
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Failed to evaluate {county}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return None

def analyze_metrics(county, evaluation):
    """Analyze metrics and identify priorities per sprint orders in issue"""
    if not evaluation:
        return []
    
    priorities = []
    
    # Extract letter metrics
    metrics = {}
    for letter in 'ABCDEFGHIJ':
        grade_field = f"grade_{letter.lower()}"
        metric_field = f"metric_{letter.lower()}"
        grade = evaluation.get(grade_field, 'UNKNOWN')
        metric = evaluation.get(metric_field)
        metrics[letter] = {'grade': grade, 'metric': metric}
    
    if county == 'brevard':
        # BREVARD Sprint Order per issue: C/D root cause, J generator, G hit list, B reconciliation
        if metrics['C']['grade'] != 'PASS':
            priorities.append(f"1. C/D ROOT CAUSE: PropertyOnion coverage issue (C={metrics['C']['metric']})")
        if metrics['D']['grade'] != 'PASS':
            priorities.append(f"1. C/D ROOT CAUSE: Parity matching (D={metrics['D']['metric']})")
        if metrics['J']['grade'] != 'PASS':
            priorities.append(f"2. J GENERATOR: Deal thesis pipeline (J={metrics['J']['metric']})")
        if metrics['G']['grade'] != 'PASS':
            priorities.append(f"3. G HIT LIST: Zoning density/FAR (G={metrics['G']['metric']})")
        if metrics['B']['metric'] and float(metrics['B']['metric']) > 105:
            priorities.append(f"4. B RECONCILIATION: ANOMALY {metrics['B']['metric']}% > 105%")
            
    elif county == 'duval':
        # DUVAL Sprint Order per issue: G+I substrate, C/D root cause, J generator, B reconciliation  
        if metrics['G']['metric'] is None or metrics['G']['grade'] != 'PASS':
            priorities.append(f"1. G SUBSTRATE: Zoning data missing (G={metrics['G']['metric']})")
        if metrics['I']['metric'] is None or metrics['I']['grade'] != 'PASS':
            priorities.append(f"1. I SUBSTRATE: Property cards missing (I={metrics['I']['metric']})")
        if metrics['C']['grade'] != 'PASS':
            priorities.append(f"2. C/D ROOT CAUSE: PropertyOnion coverage (C={metrics['C']['metric']})")
        if metrics['D']['grade'] != 'PASS':
            priorities.append(f"2. C/D ROOT CAUSE: Parity matching (D={metrics['D']['metric']})")
        if metrics['J']['grade'] != 'PASS':
            priorities.append(f"3. J GENERATOR: Deal thesis pipeline (J={metrics['J']['metric']})")
        if metrics['B']['metric'] and float(metrics['B']['metric']) > 105:
            priorities.append(f"4. B RECONCILIATION: ANOMALY {metrics['B']['metric']}% > 105%")
    
    return priorities, metrics

def format_county_report(county, evaluation):
    """Format detailed county report"""
    report = [f"\n## {county.upper()} METRICS (Live Database - VERIFIED)"]
    
    if evaluation:
        # Get pass/fail counts
        passes = sum(1 for letter in 'ABCDEFGHIJ' if evaluation.get(f"grade_{letter.lower()}") == 'PASS')
        
        report.append(f"**Current Score**: {passes}/10")
        report.append(f"**Evaluation Time**: {datetime.now().isoformat()}Z")
        report.append("")
        
        # Show all letters with metrics
        for letter in 'ABCDEFGHIJ':
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅" if grade == "PASS" else "❌"
            metric_str = f" metric={metric}" if metric is not None else " metric=null"
            
            # Add ANOMALY flag for B metrics > 105%
            anomaly = ""
            if letter == 'B' and metric and float(metric) > 105:
                anomaly = " [ANOMALY >105%]"
            
            report.append(f"  {letter}: {status_icon}{metric_str}{anomaly}")
    else:
        report.append("❌ Failed to retrieve metrics")
    
    return "\n".join(report)

def main():
    print("🎯 SHARD 19: BREVARD + DUVAL Gold Standard Session")
    print("📅 Run 19 - Autonomous 6-hour session")
    print("🚢 Ship-to-main mandate: Direct commits only")
    print(f"⏰ Started: {datetime.now().isoformat()}Z")
    print()
    
    print(f"🔗 Supabase URL: {SUPABASE_URL}")
    print(f"🔑 API Key present: {'Yes' if SUPABASE_KEY else 'No'}")
    print()
    
    # Test connection first
    if not test_connection():
        print("❌ Cannot proceed without database connection")
        print("Per CLAUDE.md: Never invent numbers - must verify against live DB")
        return
    
    print("📊 LIVE METRICS VERIFICATION (per Verification Protocol)")
    print("="*60)
    
    all_metrics = {}
    all_priorities = {}
    
    for county in ASSIGNED_COUNTIES:
        print(f"\n🔍 Evaluating {county}...")
        
        # Get live evaluation per issue mandate
        evaluation = evaluate_county_live(county)
        
        if evaluation:
            # Analyze priorities
            priorities, metrics = analyze_metrics(county, evaluation)
            all_metrics[county] = metrics
            all_priorities[county] = priorities
            
            # Display results
            print(format_county_report(county, evaluation))
            
            print(f"\n📋 SPRINT PRIORITIES for {county.upper()}:")
            if priorities:
                for priority in priorities:
                    print(f"   {priority}")
            else:
                print("   ✅ All criteria passing")
        else:
            print(f"❌ Failed to evaluate {county}")
    
    print("\n" + "="*60)
    print("📊 SESSION SUMMARY")
    print("="*60)
    
    total_passes = 0
    total_possible = 0
    
    for county in ASSIGNED_COUNTIES:
        if county in all_metrics:
            county_passes = sum(1 for letter, data in all_metrics[county].items() if data['grade'] == 'PASS')
            total_passes += county_passes
            total_possible += 10
            print(f"{county}: {county_passes}/10 letters passing")
        else:
            print(f"{county}: FAILED to retrieve metrics")
    
    print(f"\nOVERALL: {total_passes}/{total_possible} criteria passing")
    
    # Next steps based on sprint orders
    print(f"\n🎯 NEXT ACTIONS (per Issue Sprint Orders):")
    has_work = False
    
    for county, priorities in all_priorities.items():
        if priorities:
            has_work = True
            print(f"\n{county.upper()}:")
            for priority in priorities:
                print(f"  • {priority}")
    
    if not has_work:
        print("✅ Both counties at target metrics - focus on certification")
    
    # Save results for verification
    results = {
        "timestamp": datetime.now().isoformat() + "Z",
        "session": "shard19-run19",
        "counties": ASSIGNED_COUNTIES,
        "metrics": all_metrics,
        "priorities": all_priorities,
        "verification": "LIVE DATABASE QUERY - VERIFIED"
    }
    
    with open("shard19_live_verification.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved: shard19_live_verification.json")
    print("Per HONESTY PROTOCOL: VERIFIED metrics from live database queries above")
    
    return results

if __name__ == "__main__":
    main()