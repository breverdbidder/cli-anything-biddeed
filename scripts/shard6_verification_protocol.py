#!/usr/bin/env python3
"""
SHARD-6 Verification Protocol
Execute verification queries and confirm metrics moved per SHIP GATE requirements

Must show SQL proof that improvements were delivered to live database
Following NEVER-LIE and Evidence-Before-Claims protocols
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
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

SHARD6_COUNTIES = ['escambia', 'suwannee', 'martin', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def execute_verification_query(county: str) -> Dict:
    """Execute pencil_dod_evaluate_county and return raw results"""
    
    logger.info(f"Executing verification query for {county}...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_param": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Verification successful for {county}")
            return {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'success',
                'raw_result': result
            }
        else:
            logger.error(f"❌ Verification failed for {county}: {response.status_code}")
            return {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'failed',
                'error': f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.error(f"❌ Error executing verification for {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'error',
            'error': str(e)
        }

def parse_evaluation_result(raw_result: List[Dict]) -> Dict:
    """Parse evaluation result into structured letter grades"""
    
    letters = {}
    pass_count = 0
    
    if not isinstance(raw_result, list):
        return {'error': 'Invalid result format', 'raw': raw_result}
    
    for row in raw_result:
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
        'letters': letters,
        'pass_count': pass_count,
        'total_letters': len(letters),
        'score': f"{pass_count}/{len(letters)}"
    }

def check_source_coverage(county: str) -> Dict:
    """Verify that county is configured in cairn scraper"""
    
    logger.info(f"Checking source coverage for {county}...")
    
    try:
        # Read cairn_multi_county_scraper.py to verify county is configured
        script_path = "scripts/cairn_multi_county_scraper.py"
        with open(script_path, 'r') as f:
            content = f.read()
        
        if f"'{county}'" in content:
            logger.info(f"✅ {county} found in COUNTY_SOURCES")
            return {'county': county, 'configured': True, 'source': 'cairn_multi_county_scraper'}
        else:
            logger.warning(f"❌ {county} NOT found in COUNTY_SOURCES")
            return {'county': county, 'configured': False, 'source': None}
            
    except Exception as e:
        logger.error(f"Error checking source coverage for {county}: {e}")
        return {'county': county, 'error': str(e)}

def verify_database_connections() -> Dict:
    """Test basic database connectivity"""
    
    logger.info("Testing database connectivity...")
    
    try:
        # Test a simple query
        response = client.get(f"{BASE}/multi_county_auctions", headers=HEADERS, params={'limit': 1})
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Database connection successful")
            return {
                'status': 'success',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'test_query': 'multi_county_auctions LIMIT 1',
                'rows_returned': len(result) if isinstance(result, list) else 0
            }
        else:
            logger.error(f"❌ Database connection failed: {response.status_code}")
            return {
                'status': 'failed',
                'error': f"HTTP {response.status_code}",
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Database connection error: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

def generate_verification_report() -> Dict:
    """Generate comprehensive verification report for SHARD-6"""
    
    logger.info("Generating SHARD-6 verification report...")
    
    report = {
        'session_id': 'shard6-verification',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'database_connection': None,
        'source_coverage': {},
        'county_evaluations': {},
        'summary': {}
    }
    
    # Test database connectivity
    report['database_connection'] = verify_database_connections()
    
    # Check source coverage for each county
    for county in SHARD6_COUNTIES:
        report['source_coverage'][county] = check_source_coverage(county)
    
    # Execute county evaluations
    total_pass = 0
    total_counties = len(SHARD6_COUNTIES)
    
    for county in SHARD6_COUNTIES:
        verification = execute_verification_query(county)
        
        if verification.get('status') == 'success':
            parsed = parse_evaluation_result(verification['raw_result'])
            verification['parsed'] = parsed
            total_pass += parsed.get('pass_count', 0)
        
        report['county_evaluations'][county] = verification
    
    # Generate summary
    report['summary'] = {
        'total_counties': total_counties,
        'counties_with_data': sum(1 for v in report['county_evaluations'].values() if v.get('status') == 'success'),
        'counties_configured': sum(1 for v in report['source_coverage'].values() if v.get('configured', False)),
        'database_connected': report['database_connection'].get('status') == 'success'
    }
    
    return report

def print_verification_report(report: Dict):
    """Print formatted verification report"""
    
    print("\n" + "="*60)
    print("SHARD-6 VERIFICATION PROTOCOL REPORT")
    print("="*60)
    print(f"Timestamp: {report['timestamp']}")
    print(f"Session ID: {report['session_id']}")
    
    # Database connection
    print(f"\nDatabase Connection:")
    db_status = report['database_connection'].get('status', 'unknown')
    print(f"  Status: {'✅ SUCCESS' if db_status == 'success' else '❌ FAILED'}")
    if db_status == 'failed':
        print(f"  Error: {report['database_connection'].get('error', 'Unknown')}")
    
    # Source coverage
    print(f"\nSource Coverage (A-lane):")
    for county, coverage in report['source_coverage'].items():
        configured = coverage.get('configured', False)
        print(f"  {county}: {'✅ CONFIGURED' if configured else '❌ MISSING'}")
    
    # County evaluations
    print(f"\nCounty Evaluations:")
    for county, evaluation in report['county_evaluations'].items():
        status = evaluation.get('status', 'unknown')
        if status == 'success':
            parsed = evaluation.get('parsed', {})
            score = parsed.get('score', 'unknown')
            print(f"  {county}: {score} {'✅' if status == 'success' else '❌'}")
            
            # Show individual letter grades
            letters = parsed.get('letters', {})
            for letter in 'ABCDEFGHIJ':
                if letter in letters:
                    letter_info = letters[letter]
                    pass_status = '✅' if letter_info['pass'] else '❌'
                    metric = letter_info['metric']
                    print(f"    {letter}: {pass_status} metric={metric}")
        else:
            print(f"  {county}: ❌ ERROR - {evaluation.get('error', 'Unknown')}")
    
    # Summary
    print(f"\nSummary:")
    summary = report['summary']
    print(f"  Total counties: {summary['total_counties']}")
    print(f"  Counties with data: {summary['counties_with_data']}")
    print(f"  Counties configured: {summary['counties_configured']}")
    print(f"  Database connected: {'✅' if summary['database_connected'] else '❌'}")

def main():
    """Main verification function"""
    logger.info("SHARD-6 Verification Protocol - Evidence-Before-Claims")
    
    if len(sys.argv) > 1:
        county = sys.argv[1]
        if county in SHARD6_COUNTIES:
            # Verify single county
            verification = execute_verification_query(county)
            print(json.dumps(verification, indent=2))
        else:
            logger.error(f"County {county} not in SHARD-6 assignment")
            sys.exit(1)
    else:
        # Generate full report
        report = generate_verification_report()
        print_verification_report(report)
        
        # Save report for debugging
        with open('/tmp/shard6_verification_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info("Verification report saved to /tmp/shard6_verification_report.json")

if __name__ == "__main__":
    main()