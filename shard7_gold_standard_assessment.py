#!/usr/bin/env python3
"""
SHARD-7 Gold Standard Assessment and Implementation
Counties: highlands, volusia, miami_dade, columbia, madison

Focus order per brief:
1. columbia & madison (0/10) - complete bootstrapping needed
2. miami_dade (1/10) - needs scraper setup and data pipeline  
3. volusia & highlands (2/10) - optimize existing failing letters

Letters to target: B, C, D, E, F, G, I, J (A and H are mostly passing)
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

try:
    import httpx
    print("✅ Using httpx for HTTP client")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Database configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not SUPABASE_KEY:
    print("❌ SUPABASE_KEY environment variable required")
    sys.exit(1)

# SHARD-7 Counties (ONLY work on these, never touch other shards)
SHARD7_COUNTIES = {
    'columbia': {'co_no': 18, 'priority': 1, 'current_passes': 0, 'target_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
    'madison': {'co_no': 44, 'priority': 1, 'current_passes': 0, 'target_letters': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
    'miami_dade': {'co_no': 13, 'priority': 2, 'current_passes': 1, 'target_letters': ['B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']},
    'volusia': {'co_no': 67, 'priority': 3, 'current_passes': 2, 'target_letters': ['B', 'C', 'D', 'E', 'F', 'G', 'I', 'J']},
    'highlands': {'co_no': 35, 'priority': 3, 'current_passes': 2, 'target_letters': ['B', 'C', 'D', 'E', 'F', 'G', 'I', 'J']}
}

def get_headers():
    """Get Supabase API headers"""
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection() -> bool:
    """Test Supabase connection"""
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=get_headers())
            if r.status_code == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Connection failed: {r.status_code} - {r.text}")
                return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county(county_slug: str) -> Optional[List[Dict]]:
    """Evaluate county using pencil_dod_evaluate_county function"""
    try:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=get_headers(),
                json={"county_slug_arg": county_slug}
            )
            
            if r.status_code == 200:
                return r.json()
            else:
                print(f"❌ Failed to evaluate {county_slug}: {r.status_code} - {r.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def check_county_data_status(county_slug: str, co_no: int) -> Dict:
    """Check basic data availability for a county"""
    status = {
        'county_slug': county_slug,
        'co_no': co_no,
        'multi_county_auctions': 0,
        'sample_properties': 0,
        'tax_deed_outcomes': 0,
        'foreclosure_outcomes': 0,
        'parcel_zones': 0,
        'zoning_districts': 0,
        'has_pipeline_config': False
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # Check multi_county_auctions
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county_slug=eq.{county_slug}&select=count",
                headers=get_headers()
            )
            if r.status_code == 200:
                result = r.json()
                status['multi_county_auctions'] = len(result) if isinstance(result, list) else 0
                
            # Check sample_properties 
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/sample_properties?county_slug=eq.{county_slug}&select=count",
                headers=get_headers()
            )
            if r.status_code == 200:
                result = r.json()
                status['sample_properties'] = len(result) if isinstance(result, list) else 0
                
            # Check verified outcomes
            for table in ['tax_deed_outcomes', 'foreclosure_outcomes']:
                r = client.get(
                    f"{SUPABASE_URL}/rest/v1/{table}?county_slug=eq.{county_slug}&select=count",
                    headers=get_headers()
                )
                if r.status_code == 200:
                    result = r.json()
                    status[table] = len(result) if isinstance(result, list) else 0
                    
            # Check zoning data
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/parcel_zones?county_slug=eq.{county_slug}&select=count",
                headers=get_headers()
            )
            if r.status_code == 200:
                result = r.json()
                status['parcel_zones'] = len(result) if isinstance(result, list) else 0
                
            # Check pipeline configuration
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/pipeline_counties?county_slug=eq.{county_slug}&select=*",
                headers=get_headers()
            )
            if r.status_code == 200:
                result = r.json()
                status['has_pipeline_config'] = len(result) > 0 if isinstance(result, list) else False
                
    except Exception as e:
        print(f"❌ Error checking data status for {county_slug}: {e}")
        
    return status

def get_county_co_no(county_slug: str) -> Optional[int]:
    """Get the FL county number for a county slug"""
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/fl_counties?name=eq.{county_slug.replace('_', ' ').title()}&select=co_no",
                headers=get_headers()
            )
            
            if r.status_code == 200:
                result = r.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('co_no')
                    
    except Exception as e:
        print(f"❌ Error getting co_no for {county_slug}: {e}")
    
    return None

def main():
    """Main assessment function"""
    print("=== SHARD-7 GOLD STANDARD ASSESSMENT ===")
    print(f"Target counties: {', '.join(SHARD7_COUNTIES.keys())}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print()
    
    if not test_connection():
        print("Database connection failed. Exiting.")
        return
    
    county_evaluations = {}
    county_data_status = {}
    
    print("\n=== COUNTY EVALUATIONS (VERIFIED) ===")
    
    for county_slug in SHARD7_COUNTIES.keys():
        print(f"\n--- {county_slug.upper()} ---")
        county_info = SHARD7_COUNTIES[county_slug]
        co_no = county_info['co_no']
        
        # Get current evaluation
        evaluation = evaluate_county(county_slug)
        county_evaluations[county_slug] = evaluation
        
        # Get data status
        data_status = check_county_data_status(county_slug, co_no)
        county_data_status[county_slug] = data_status
        
        if evaluation:
            pass_count = sum(1 for item in evaluation if item.get('pass', False))
            print(f"Current score: {pass_count}/10 letters passing")
            
            # Show failing letters
            failing_letters = [item for item in evaluation if not item.get('pass', False)]
            if failing_letters:
                print("Failing letters:")
                for item in failing_letters:
                    letter = item.get('letter', '?')
                    metric = item.get('metric', 'null')
                    print(f"  {letter}: FAIL (metric={metric})")
        else:
            print("❌ Could not evaluate county")
            
        # Show data availability 
        print(f"Data status:")
        print(f"  Auctions: {data_status['multi_county_auctions']:,}")
        print(f"  Properties: {data_status['sample_properties']:,}")
        print(f"  Outcomes: TD={data_status['tax_deed_outcomes']}, FC={data_status['foreclosure_outcomes']}")
        print(f"  Zoning: parcels={data_status['parcel_zones']:,}, districts={data_status['zoning_districts']}")
        print(f"  Pipeline config: {data_status['has_pipeline_config']}")
    
    print("\n=== PRIORITY ANALYSIS ===")
    
    # Prioritize work based on current status
    work_queue = []
    
    for county_slug, evaluation in county_evaluations.items():
        if not evaluation:
            continue
            
        county_info = SHARD7_COUNTIES[county_slug]
        data_status = county_data_status[county_slug]
        
        pass_count = sum(1 for item in evaluation if item.get('pass', False))
        
        # Prioritize 0/10 counties first (complete bootstrap needed)
        if pass_count == 0:
            work_queue.append({
                'county': county_slug,
                'priority': 1,
                'action': 'BOOTSTRAP',
                'reason': 'Zero letters passing - needs complete setup',
                'letters_needed': 10,
                'data_available': data_status['multi_county_auctions'] > 0
            })
        # Then 1-3/10 counties (need major fixes)
        elif pass_count <= 3:
            work_queue.append({
                'county': county_slug,
                'priority': 2, 
                'action': 'MAJOR_FIXES',
                'reason': f'Only {pass_count}/10 passing - needs significant work',
                'letters_needed': 10 - pass_count,
                'data_available': data_status['multi_county_auctions'] > 0
            })
        # Then other counties (optimization)
        else:
            work_queue.append({
                'county': county_slug,
                'priority': 3,
                'action': 'OPTIMIZE', 
                'reason': f'{pass_count}/10 passing - needs optimization',
                'letters_needed': 10 - pass_count,
                'data_available': data_status['multi_county_auctions'] > 0
            })
    
    # Sort by priority
    work_queue.sort(key=lambda x: (x['priority'], -x['letters_needed']))
    
    print("\nWork queue (priority order):")
    for item in work_queue:
        status = "✅" if item['data_available'] else "❌"
        print(f"  {item['county']}: {item['action']} - {item['reason']} {status}")
    
    # Write assessment results
    assessment_file = f"shard7_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(assessment_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'shard': 'SHARD-7',
            'counties': list(SHARD7_COUNTIES.keys()),
            'evaluations': county_evaluations,
            'data_status': county_data_status,
            'work_queue': work_queue
        }, f, indent=2, default=str)
    
    print(f"\nAssessment saved to: {assessment_file}")
    
    return work_queue

if __name__ == "__main__":
    main()