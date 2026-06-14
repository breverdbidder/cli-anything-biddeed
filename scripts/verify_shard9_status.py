#!/usr/bin/env python3
"""
SHARD-9 County Status Verification
Check current A-J letter grades for palm_beach, hendry, orange, dixie, taylor

Usage:
  python scripts/verify_shard9_status.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Target counties for SHARD-9
SHARD9_COUNTIES = ['palm_beach', 'hendry', 'orange', 'dixie', 'taylor']

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

def get_county_evaluation(county):
    """Get evaluation for a specific county using pencil_dod_evaluate_county function"""
    try:
        # Use RPC call to the evaluation function
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

def get_county_status_direct(county):
    """Get county status directly from gold_standard_county_status table"""
    try:
        response = requests.get(
            f"{BASE}/gold_standard_county_status", 
            headers=HEADERS, 
            params={
                "county": f"eq.{county}",
                "select": "*"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data[0] if data else None
        else:
            print(f"⚠️ Failed to get status for {county}: {response.status_code}")
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
    
    return "\n".join(report)

def identify_highest_leverage_targets(county_data):
    """Identify highest leverage failing letters based on current status"""
    
    # Count county auctions to determine leverage
    auction_counts = {
        'palm_beach': 24000,  # From briefing
        'hendry': 62,         # From briefing  
        'orange': 16131,      # From briefing
        'dixie': 0,           # From briefing
        'taylor': 0           # From briefing
    }
    
    leverage_analysis = {}
    failing_by_letter = {}
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            continue
        
        auction_count = auction_counts.get(county, 0)
        failing_letters = []
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            if evaluation.get(grade_field) != 'PASS':
                failing_letters.append(letter)
                
                # Track which counties fail each letter with their auction counts
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append((county, auction_count))
        
        leverage_analysis[county] = {
            'auction_count': auction_count,
            'failing_letters': failing_letters
        }
    
    return {
        'by_letter': failing_by_letter,
        'by_county': leverage_analysis
    }

def main():
    print("🔍 SHARD-9 County Status Verification")
    print(f"Target counties: {', '.join(SHARD9_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first
    if not test_connection():
        print("❌ Database connection failed. Checking for environment variables...")
        print("Note: GitHub Actions should provide SUPABASE_KEY automatically")
        return
    
    print("📊 Gathering county evaluations...\n")
    
    # Collect data for each county
    county_data = {}
    for county in SHARD9_COUNTIES:
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
    print("SHARD-9 COUNTY STATUS REPORT")
    print("="*60)
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        status = data.get('status')
        
        print(format_county_report(county, evaluation, status))
    
    # Leverage analysis  
    leverage = identify_highest_leverage_targets(county_data)
    
    print(f"\n" + "="*60)
    print("LEVERAGE ANALYSIS")
    print("="*60)
    
    print("\n📊 Failing Letters by Total Auction Volume:")
    total_volume_by_letter = {}
    for letter, counties_data in leverage['by_letter'].items():
        total_volume = sum(auction_count for _, auction_count in counties_data)
        total_volume_by_letter[letter] = total_volume
        county_list = [f"{county}({count})" for county, count in counties_data]
        print(f"**{letter}**: {total_volume:,} auctions - {', '.join(county_list)}")
    
    # Sort by total volume for prioritization
    priority_letters = sorted(total_volume_by_letter.items(), key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 County Auction Volumes:")
    for county, data in leverage['by_county'].items():
        count = data['auction_count']
        failing = data['failing_letters']
        print(f"**{county}**: {count:,} auctions - Failing: {', '.join(failing) if failing else 'None'}")
    
    # Recommended action plan
    print(f"\n" + "="*60)
    print("RECOMMENDED ACTION PLAN")
    print("="*60)
    
    print("\n🎯 **High-Leverage Targets (by auction volume):**")
    for i, (letter, volume) in enumerate(priority_letters[:5]):
        counties = [county for county, _ in leverage['by_letter'][letter]]
        print(f"{i+1}. **Letter {letter}**: {volume:,} auctions across {', '.join(counties)}")
    
    print("\n📝 **Next Steps (following briefing priorities):**")
    print("1. **C/D Parity**: Fix matching for palm_beach (24K auctions) and orange (16K auctions)")
    print("2. **A Dual Coverage**: Set up lanes for dixie and taylor (currently 0 auctions)")  
    print("3. **E Linkage**: Connect parcels for palm_beach and orange")
    print("4. **J Generator**: Implement deal thesis pipeline (affects all counties)")
    print("5. **B/F Verified Outcomes**: Build independent data sources")
    print("6. Use ULTRALOOP verification for all fixes")
    print("7. Commit directly to main per SHIP-TO-MAIN mandate")

if __name__ == "__main__":
    main()