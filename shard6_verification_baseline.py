#!/usr/bin/env python3
"""
SHARD-6 Baseline Verification Script
Assigned counties: hillsborough, bay, martin, calhoun, liberty

Per SHIP GATE requirements and HONESTY PROTOCOL - all claims must be VERIFIED
Execute pencil_dod_evaluate_county for each county and report exact metrics
"""

import os
import sys
import json
import httpx
import logging
from typing import Dict, List
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("No SUPABASE_KEY found in environment")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-6 assigned counties from issue briefing
SHARD6_COUNTIES = ['hillsborough', 'bay', 'martin', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def test_database_connection() -> bool:
    """Test basic database connectivity"""
    try:
        response = client.get(f"{BASE}/fl_counties", headers=HEADERS, params={'limit': 1})
        if response.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error(f"❌ Database connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return False

def evaluate_county(county: str) -> Dict:
    """Execute pencil_dod_evaluate_county for a single county"""
    
    logger.info(f"Evaluating {county}...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_param": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse the result into structured format
            letters = {}
            pass_count = 0
            
            if isinstance(result, list):
                for row in result:
                    if isinstance(row, dict):
                        letter = row.get('letter', '').upper()
                        is_pass = row.get('pass', False)
                        metric = row.get('metric')
                        detail = row.get('detail', '')
                        threshold = row.get('threshold')
                        
                        letters[letter] = {
                            'pass': is_pass,
                            'metric': metric,
                            'detail': detail,
                            'threshold': threshold
                        }
                        
                        if is_pass:
                            pass_count += 1
            
            return {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'success',
                'score': f"{pass_count}/10",
                'pass_count': pass_count,
                'letters': letters,
                'raw_result': result
            }
        else:
            logger.error(f"❌ Failed to evaluate {county}: {response.status_code}")
            return {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'failed',
                'error': f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.error(f"❌ Error evaluating {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'error',
            'error': str(e)
        }

def get_county_auction_counts() -> Dict:
    """Get current auction counts for each county"""
    
    logger.info("Getting auction counts...")
    
    try:
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                'select': 'county',
                'county': f'in.({",".join(SHARD6_COUNTIES)})',
                'limit': 100000  # Get all records to count
            }
        )
        
        if response.status_code == 200:
            results = response.json()
            counts = {}
            for county in SHARD6_COUNTIES:
                counts[county] = sum(1 for r in results if r.get('county') == county)
            return counts
        else:
            logger.error(f"Failed to get auction counts: {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"Error getting auction counts: {e}")
        return {}

def generate_baseline_report() -> Dict:
    """Generate baseline verification report for SHARD-6"""
    
    report = {
        'session_id': 'shard6-baseline',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'assigned_counties': SHARD6_COUNTIES,
        'database_connection': test_database_connection(),
        'auction_counts': get_county_auction_counts(),
        'evaluations': {}
    }
    
    # Evaluate each county
    for county in SHARD6_COUNTIES:
        evaluation = evaluate_county(county)
        report['evaluations'][county] = evaluation
    
    return report

def print_baseline_report(report: Dict):
    """Print formatted baseline report"""
    
    print("\n" + "="*70)
    print("SHARD-6 BASELINE VERIFICATION REPORT")
    print("="*70)
    print(f"Session: {report['session_id']}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Database Connected: {'✅' if report['database_connection'] else '❌'}")
    
    print(f"\nAuction Counts:")
    for county, count in report['auction_counts'].items():
        print(f"  {county}: {count:,} auctions")
    
    print(f"\nCounty Evaluations:")
    print("-" * 70)
    
    for county in SHARD6_COUNTIES:
        evaluation = report['evaluations'][county]
        status = evaluation.get('status')
        
        if status == 'success':
            score = evaluation.get('score', 'N/A')
            print(f"\n{county.upper()} ({score})")
            
            letters = evaluation.get('letters', {})
            for letter in 'ABCDEFGHIJ':
                if letter in letters:
                    letter_data = letters[letter]
                    pass_emoji = '✅' if letter_data['pass'] else '❌'
                    metric = letter_data['metric']
                    detail = letter_data['detail']
                    print(f"  {letter}: {pass_emoji} metric={metric} [{detail}]")
        else:
            print(f"\n{county.upper()}: ❌ {evaluation.get('error', 'Unknown error')}")
    
    print("\n" + "="*70)

def main():
    """Main execution"""
    
    if len(sys.argv) > 1:
        county = sys.argv[1].lower()
        if county in SHARD6_COUNTIES:
            # Single county evaluation
            evaluation = evaluate_county(county)
            print(json.dumps(evaluation, indent=2))
        else:
            print(f"Error: {county} not in assigned counties {SHARD6_COUNTIES}")
            sys.exit(1)
    else:
        # Full baseline report
        report = generate_baseline_report()
        print_baseline_report(report)
        
        # Save for reference
        with open('/tmp/shard6_baseline_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nBaseline report saved to /tmp/shard6_baseline_report.json")

if __name__ == "__main__":
    main()