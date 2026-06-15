#!/usr/bin/env python3
"""
SHARD-8 County Status Verification
Check current A-J letter grades for marion, collier, nassau, desoto, monroe

Usage:
  python scripts/verify_shard8_status.py
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

# Target counties for SHARD-8
SHARD8_COUNTIES = ['marion', 'collier', 'nassau', 'desoto', 'monroe']

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

def identify_priority_targets(county_data):
    """Identify highest priority counties and letters based on CRITERION-PARALLEL strategy"""
    
    # Aggregate failing letters across all counties
    failing_by_letter = {}
    county_scores = {}
    
    for county, data in county_data.items():
        evaluation = data.get('evaluation')
        if not evaluation:
            continue
            
        score = 0
        failing_letters = []
        
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            grade_field = f"grade_{letter.lower()}"
            if evaluation.get(grade_field) == 'PASS':
                score += 1
            else:
                failing_letters.append(letter)
                # Track which counties fail each letter
                if letter not in failing_by_letter:
                    failing_by_letter[letter] = []
                failing_by_letter[letter].append(county)
        
        county_scores[county] = {
            'score': score,
            'failing_letters': failing_letters
        }
    
    # Priority order based on BREVARD/DUVAL SPRINT ORDER
    letter_priorities = ['C', 'D', 'J', 'B', 'G', 'I', 'E', 'F']
    
    return {
        'by_letter': failing_by_letter,
        'by_county': county_scores,
        'priority_order': letter_priorities
    }

def get_briefing_baseline():
    """Return the briefing data as baseline for comparison"""
    return {
        'marion': {
            'score': 2,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 3021, 'detail': '[fc=3491 td=3021]'},
                'B': {'grade': 'FAIL', 'metric': None, 'detail': '[verified=0 closed_sold=1981]'},
                'C': {'grade': 'FAIL', 'metric': 9.6, 'detail': '[matched_clean=628 of 6512]'},
                'D': {'grade': 'FAIL', 'metric': 55.1, 'detail': '[matched_any=3588 of 6512]'},
                'E': {'grade': 'FAIL', 'metric': 67.6, 'detail': '[parcel_linked=4405 of 6512]'},
                'F': {'grade': 'FAIL', 'metric': 8.6, 'detail': '[tier1_sold=170 closed_sold=1981]'},
                'G': {'grade': 'FAIL', 'metric': None, 'detail': '[density= far= pk1000=]'},
                'H': {'grade': 'PASS', 'metric': 9.2, 'detail': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'detail': '[zoned_complete_parcels=0 field_complete_parcels=775 auctions=6512]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': '[deal_complete=0 of 6512 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'collier': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 559, 'detail': '[fc=1111 td=559]'},
                'B': {'grade': 'FAIL', 'metric': None, 'detail': '[verified=0 closed_sold=610]'},
                'C': {'grade': 'FAIL', 'metric': 17.3, 'detail': '[matched_clean=289 of 1670]'},
                'D': {'grade': 'FAIL', 'metric': 59.2, 'detail': '[matched_any=988 of 1670]'},
                'E': {'grade': 'FAIL', 'metric': 64.8, 'detail': '[parcel_linked=1082 of 1670]'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': '[tier1_sold=0 closed_sold=610]'},
                'G': {'grade': 'FAIL', 'metric': None, 'detail': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': 616.4, 'detail': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'detail': '[zoned_complete_parcels=0 field_complete_parcels=224 auctions=1670]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': '[deal_complete=0 of 1670 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'nassau': {
            'score': 1,
            'metrics': {
                'A': {'grade': 'PASS', 'metric': 194, 'detail': '[fc=293 td=194]'},
                'B': {'grade': 'FAIL', 'metric': None, 'detail': '[verified=0 closed_sold=208]'},
                'C': {'grade': 'FAIL', 'metric': 15.2, 'detail': '[matched_clean=74 of 487]'},
                'D': {'grade': 'FAIL', 'metric': 55.9, 'detail': '[matched_any=272 of 487]'},
                'E': {'grade': 'FAIL', 'metric': 80.3, 'detail': '[parcel_linked=391 of 487]'},
                'F': {'grade': 'FAIL', 'metric': 0.0, 'detail': '[tier1_sold=0 closed_sold=208]'},
                'G': {'grade': 'FAIL', 'metric': None, 'detail': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': 415.0, 'detail': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'detail': '[zoned_complete_parcels=0 field_complete_parcels=79 auctions=487]'},
                'J': {'grade': 'FAIL', 'metric': 0.0, 'detail': '[deal_complete=0 of 487 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'desoto': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'detail': '[fc=0 td=0]'},
                'B': {'grade': 'FAIL', 'metric': None, 'detail': '[verified=0 closed_sold=0]'},
                'C': {'grade': 'FAIL', 'metric': None, 'detail': '[matched_clean=0 of 0]'},
                'D': {'grade': 'FAIL', 'metric': None, 'detail': '[matched_any=0 of 0]'},
                'E': {'grade': 'FAIL', 'metric': None, 'detail': '[parcel_linked=0 of 0]'},
                'F': {'grade': 'FAIL', 'metric': None, 'detail': '[tier1_sold=0 closed_sold=0]'},
                'G': {'grade': 'FAIL', 'metric': None, 'detail': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': None, 'detail': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'detail': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
                'J': {'grade': 'FAIL', 'metric': None, 'detail': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        },
        'monroe': {
            'score': 0,
            'metrics': {
                'A': {'grade': 'FAIL', 'metric': 0, 'detail': '[fc=0 td=0]'},
                'B': {'grade': 'FAIL', 'metric': None, 'detail': '[verified=0 closed_sold=0]'},
                'C': {'grade': 'FAIL', 'metric': None, 'detail': '[matched_clean=0 of 0]'},
                'D': {'grade': 'FAIL', 'metric': None, 'detail': '[matched_any=0 of 0]'},
                'E': {'grade': 'FAIL', 'metric': None, 'detail': '[parcel_linked=0 of 0]'},
                'F': {'grade': 'FAIL', 'metric': None, 'detail': '[tier1_sold=0 closed_sold=0]'},
                'G': {'grade': 'FAIL', 'metric': None, 'detail': '[density= far= pk1000=]'},
                'H': {'grade': 'FAIL', 'metric': None, 'detail': '[hours since last_seen (SLA 48h)]'},
                'I': {'grade': 'FAIL', 'metric': None, 'detail': '[zoned_complete_parcels=0 field_complete_parcels=0 auctions=0]'},
                'J': {'grade': 'FAIL', 'metric': None, 'detail': '[deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)]'}
            }
        }
    }

def main():
    print("🔍 SHARD-8 County Status Verification")
    print(f"Target counties: {', '.join(SHARD8_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Print debug info about environment
    print(f"SUPABASE_URL: {SUPABASE_URL}")
    print(f"SUPABASE_KEY available: {'Yes' if SUPABASE_KEY else 'No'}")
    
    # Test connection first - if it fails, use briefing data
    has_db_access = test_connection()
    
    if not has_db_access:
        print("❌ Database connection failed. Using briefing baseline data for analysis...")
        briefing_data = get_briefing_baseline()
        
        print("\n" + "="*60)
        print("SHARD-8 BASELINE STATUS (from briefing)")
        print("="*60)
        
        # Convert briefing format to evaluation format for analysis
        county_data = {}
        for county, data in briefing_data.items():
            # Convert to evaluation-like format
            evaluation = {}
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                metric_info = data['metrics'][letter]
                evaluation[f"grade_{letter.lower()}"] = metric_info['grade']
                evaluation[f"metric_{letter.lower()}"] = metric_info['metric']
            
            county_data[county] = {
                'evaluation': evaluation,
                'status': {'total_score': data['score']}
            }
            
            # Print summary
            score = data['score']
            failing_count = sum(1 for letter_data in data['metrics'].values() if letter_data['grade'] == 'FAIL')
            passing_count = 10 - failing_count
            
            print(f"\n## {county.upper()}: {score}/10 ({passing_count} PASS, {failing_count} FAIL)")
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                letter_data = data['metrics'][letter]
                status = "✅" if letter_data['grade'] == 'PASS' else "❌"
                metric = letter_data['metric']
                detail = letter_data['detail']
                metric_str = f" {metric}" if metric is not None else " null"
                print(f"  {letter}: {status} {metric_str} {detail}")
        
    else:
        print("📊 Gathering live county evaluations...\n")
        
        # Collect data for each county
        county_data = {}
        for county in SHARD8_COUNTIES:
            print(f"Processing {county}...")
            
            # Get evaluation using function
            evaluation = get_county_evaluation(county)
            
            # Get status from table
            status = get_county_status_direct(county)
            
            county_data[county] = {
                'evaluation': evaluation,
                'status': status
            }
        
        # Generate live reports
        print("\n" + "="*60)
        print("SHARD-8 LIVE COUNTY STATUS")
        print("="*60)
        
        for county, data in county_data.items():
            evaluation = data.get('evaluation')
            status = data.get('status')
            
            print(format_county_report(county, evaluation, status))
    
    # Priority analysis using CRITERION-PARALLEL strategy
    priorities = identify_priority_targets(county_data)
    
    print(f"\n" + "="*60)
    print("CRITERION-PARALLEL ANALYSIS")
    print("="*60)
    
    print("\n📊 Failing Letters Across Shard:")
    for letter in priorities['priority_order']:
        counties = priorities['by_letter'].get(letter, [])
        if counties:
            impact = len(counties)
            print(f"**{letter}**: {', '.join(counties)} ({impact} counties)")
    
    print(f"\n📊 County Scores:")
    for county, data in priorities['by_county'].items():
        score = data['score']
        failing = data['failing_letters']
        print(f"**{county}**: {score}/10 - Failing: {', '.join(failing) if failing else 'None'}")
    
    # Action plan based on briefing priorities
    print(f"\n" + "="*60)
    print("SHARD-8 ACTION PLAN (CRITERION-PARALLEL PIVOT)")
    print("="*60)
    
    print("\n🎯 **Priority Order:**")
    print("1. **C/D ROOT CAUSE** - PropertyOnion coverage issue (C: all 3 active counties fail)")
    print("2. **J GENERATOR** - Build bid_decisions pipeline (fleet-wide 0.0%)")
    print("3. **A LANE SETUP** - Configure desoto/monroe lanes (both 0/10)")
    print("4. **B RECONCILIATION** - Independent verified outcomes (all fail)")
    print("5. **H FRESHNESS** - Fix collier/nassau staleness (>48h)")
    print("6. **G+I SUBSTRATE** - Zoning + property cards (all null)")
    print("7. **E LINKAGE** - Parcel mapping improvements")
    print("8. **F TIER1** - Automated promotion (working where data exists)")
    
    print("\n📝 **Recommended Session Focus:**")
    print("1. **HIGHEST IMPACT**: J generator - affects all 3 active counties")
    print("2. **QUICK WINS**: C/D parity - PropertyOnion supplementary litmus (pre-authorized)")
    print("3. **INFRASTRUCTURE**: A lane setup for desoto/monroe")
    print("4. **FRESHNESS**: H fixes for collier/nassau")
    print("5. **SUBSTRATE**: G/I only if time permits")
    
    print("\n⚡ **Immediate Actions:**")
    print("- Check existing J generator in codebase from other shards")
    print("- Implement clerk/official-records supplementary litmus for C/D")
    print("- Configure pipeline.counties for desoto/monroe")
    print("- Fix scraper scheduling for collier/nassau staleness")
    print("- All commits go directly to MAIN (ship-to-main mandate)")

if __name__ == "__main__":
    main()