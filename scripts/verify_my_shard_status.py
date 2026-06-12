#!/usr/bin/env python3
"""
My Shard County Status Verification - Run 19
Check current A-J letter grades for charlotte, citrus, broward

Usage:
  python scripts/verify_my_shard_status.py
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
    sys.exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

# My assigned counties for this session
MY_COUNTIES = ['charlotte', 'citrus', 'broward']

def test_connection():
    """Test Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function - try both parameter names
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_name": county}
        )
        
        if r.status_code == 200:
            return r.json()
        else:
            print(f"⚠️ Failed to evaluate {county}: {r.status_code} - {r.text}")
            # Try alternative parameter name
            r2 = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            
            if r2.status_code == 200:
                return r2.json()
            else:
                print(f"⚠️ Also failed with county_slug_arg: {r2.status_code} - {r2.text}")
                return None
            
    except Exception as e:
        print(f"⚠️ Error evaluating {county}: {e}")
        return None

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/gold_standard_county_status",
            headers=sb_headers(),
            params={
                "county": f"eq.{county}",
                "select": "*"
            }
        )
        
        if r.status_code == 200:
            data = r.json()
            return data[0] if data else None
        else:
            print(f"⚠️ Failed to get status for {county}: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️ Error getting status for {county}: {e}")
        return None

def format_county_report(county, evaluation, status):
    """Format a detailed county report"""
    report = [f"\n## {county.upper()} County Status"]
    
    if status:
        report.append(f"**Score**: {status.get('total_score', 'N/A')}/10")
        report.append(f"**Last Updated**: {status.get('updated_at', 'Unknown')}")
    
    if evaluation:
        report.append("\n### Letter Grades:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            metric_field = f"metric_{letter.lower()}"
            
            grade = evaluation.get(grade_field, 'UNKNOWN')
            metric = evaluation.get(metric_field)
            
            status_icon = "✅ PASS" if grade == "PASS" else "❌ FAIL"
            metric_str = f" (metric={metric})" if metric is not None else ""
            
            report.append(f"**{letter}**: {status_icon}{metric_str}")
        
        # Add raw evaluation data for reference
        report.append("\n### Raw Evaluation Data:")
        report.append(f"```json\n{json.dumps(evaluation, indent=2)}\n```")
    
    return "\n".join(report)

def identify_priority_actions(county_data):
    """Identify priority actions based on the brief's guidance"""
    actions = []
    
    # From the brief - priority targets based on current scores
    priority_order = [
        'charlotte',  # 3/10 but mentioned first
        'citrus',     # 3/10 
        'broward'     # 2/10 but largest scale
    ]
    
    for county in priority_order:
        data = county_data.get(county)
        if not data or not data.get('evaluation'):
            continue
            
        evaluation = data['evaluation']
        failing_letters = []
        critical_failing = []
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            if evaluation.get(grade_field) != 'PASS':
                failing_letters.append(letter)
                if letter in ['B', 'I', 'J']:  # Critical three
                    critical_failing.append(letter)
        
        actions.append({
            'county': county,
            'failing_letters': failing_letters,
            'critical_failing': critical_failing,
            'recommended_order': get_recommended_fix_order(county, failing_letters)
        })
    
    return actions

def get_recommended_fix_order(county, failing_letters):
    """Get recommended fix order based on the brief's playbooks"""
    # High leverage fixes from the brief
    leverage_order = {
        'B': 'Verified outcomes (clerk scraper) - enables F, builds trust',
        'C': 'Parity clean - data quality foundation',
        'D': 'Parity any - completeness validation', 
        'E': 'Parcel linkage - enables I, unlocks mapping',
        'F': 'Tier1 sold amounts - depends on B',
        'G': 'Zoning coverage - enables I, development upside',
        'I': 'Property cards - customer-visible output',
        'J': 'Deal thesis - the monetization'
    }
    
    # Filter to only failing letters and return in leverage order
    recommended = []
    for letter in ['B', 'E', 'C', 'D', 'G', 'I', 'F', 'J']:
        if letter in failing_letters:
            recommended.append({
                'letter': letter,
                'description': leverage_order.get(letter, 'Unknown'),
                'dependency': get_letter_dependencies(letter)
            })
    
    return recommended

def get_letter_dependencies(letter):
    """Get dependencies for each letter"""
    deps = {
        'A': 'None - foundational',
        'B': 'Requires clerk/official records access',
        'C': 'Requires PropertyOnion parity data',
        'D': 'Requires PropertyOnion parity data', 
        'E': 'Requires county GIS/appraiser parcel mapping',
        'F': 'Depends on B (verified outcomes)',
        'G': 'Requires zoning districts and standards data',
        'H': 'Requires active scraping pipeline',
        'I': 'Depends on E (parcel linkage) and G (zoning)',
        'J': 'Depends on all - final monetization layer'
    }
    return deps.get(letter, 'Unknown')

def main():
    print("🔍 My Shard County Status Verification - Run 19")
    print(f"Assigned counties: {', '.join(MY_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Check environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Need to configure environment variables.")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in MY_COUNTIES:
        print(f"Processing {county}...")
        
        # Get evaluation using function
        evaluation = get_county_evaluation(county)
        
        # Get status from table
        status = get_county_status_direct(county)
        
        county_data[county] = {
            'evaluation': evaluation,
            'status': status
        }
    
    # Generate reports
    print("\n" + "="*60)
    print("MY SHARD COUNTY STATUS REPORT")
    print("="*60)
    
    for county in MY_COUNTIES:  # Maintain order
        data = county_data[county]
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Priority analysis
    actions = identify_priority_actions(county_data)
    
    print(f"\n" + "="*60)
    print("PRIORITY ACTION PLAN")
    print("="*60)
    
    for action in actions:
        county = action['county']
        failing = action['failing_letters']
        critical = action['critical_failing']
        recommended = action['recommended_order']
        
        print(f"\n### {county.upper()} County")
        print(f"Failing letters: {', '.join(failing) if failing else 'None'}")
        if critical:
            print(f"🎯 Critical failing (B,I,J): {', '.join(critical)}")
        
        if recommended:
            print("\nRecommended fix order:")
            for i, fix in enumerate(recommended[:3], 1):  # Show top 3
                print(f"  {i}. {fix['letter']}: {fix['description']}")
                print(f"     Dependencies: {fix['dependency']}")
    
    print(f"\n" + "="*60)
    print("SHIP-TO-MAIN SESSION PLAN")
    print("="*60)
    print("1. Work highest-leverage failing letters first")
    print("2. Verify each fix with pencil_dod_evaluate_county")
    print("3. Commit directly to main branch (no PRs)")
    print("4. Execute verification protocol before close-out")
    print("5. Target 5.5h of work before session end")

if __name__ == "__main__":
    main()