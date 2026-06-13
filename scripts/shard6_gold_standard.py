#!/usr/bin/env python3
"""
SHARD-6 Gold Standard Campaign - Autonomous Session
Counties: escambia, suwannee, martin, calhoun, liberty

Ship directly to main. 6-hour budget. Priority fixes for highest-leverage metrics.
"""

import os
import sys
import json
import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration (following shard2_verification_protocol.py pattern)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-6 target counties
SHARD6_COUNTIES = ['escambia', 'suwannee', 'martin', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def run_county_evaluation(county: str) -> Dict:
    """Run pencil_dod_evaluate_county function for a single county"""
    logger.info(f"Evaluating county: {county}")
    
    try:
        # Try different parameter formats the function might accept
        for param_name in ['county_param', 'county_slug_arg', 'county_name', 'county']:
            try:
                response = client.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county",
                    headers=HEADERS,
                    json={param_name: county},
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ {county} evaluation successful with param {param_name}")
                    
                    # Parse the result into a structured format
                    evaluation = {
                        'county': county,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'raw_result': result
                    }
                    
                    # Convert list of letter results to structured format
                    if isinstance(result, list):
                        letters = {}
                        pass_count = 0
                        for row in result:
                            if isinstance(row, dict):
                                letter = row.get('letter', '').upper()
                                is_pass = row.get('pass', False)
                                letters[f'grade_{letter.lower()}'] = 'PASS' if is_pass else 'FAIL'
                                letters[f'metric_{letter.lower()}'] = row.get('metric')
                                letters[f'detail_{letter.lower()}'] = row.get('detail')
                                letters[f'threshold_{letter.lower()}'] = row.get('threshold')
                                if is_pass:
                                    pass_count += 1
                        
                        evaluation['letters'] = letters
                        evaluation['pass_count'] = pass_count
                        evaluation['total_letters'] = len([k for k in letters.keys() if k.startswith('grade_')])
                    
                    return evaluation
                    
            except Exception as e:
                logger.debug(f"Parameter {param_name} failed: {e}")
                continue
        
        logger.error(f"❌ All parameter formats failed for {county}")
        return {'county': county, 'error': 'All parameter formats failed', 'timestamp': datetime.now(timezone.utc).isoformat()}
        
    except Exception as e:
        logger.error(f"❌ County evaluation failed for {county}: {e}")
        return {'county': county, 'error': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()}

def get_shard_status() -> Dict:
    """Get current status for all SHARD-6 counties"""
    status = {}
    
    for county in SHARD6_COUNTIES:
        logger.info(f"Getting status for {county}...")
        status[county] = run_county_evaluation(county)
        
    return status

def print_status_report(status: Dict):
    """Print formatted status report with letter-by-letter breakdown"""
    print("\n" + "="*50)
    print("SHARD-6 GOLD STANDARD STATUS REPORT")
    print("="*50)
    
    for county, data in status.items():
        print(f"\n{county.upper()}:")
        
        if 'error' in data:
            print(f"  ❌ ERROR: {data['error']}")
            continue
            
        if 'letters' in data:
            print(f"  Score: {data.get('pass_count', 0)}/{data.get('total_letters', 10)}")
            print("  Letter breakdown:")
            
            letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
            for letter in letters:
                letter_lower = letter.lower()
                grade = data['letters'].get(f'grade_{letter_lower}', 'UNKNOWN')
                metric = data['letters'].get(f'metric_{letter_lower}', 'null')
                detail = data['letters'].get(f'detail_{letter_lower}', '')
                
                status_emoji = "✅" if grade == "PASS" else "❌" if grade == "FAIL" else "❓"
                print(f"    {letter} {status_emoji} {grade} metric={metric} [{detail}]")
        
        print(f"  Timestamp: {data.get('timestamp', 'unknown')}")

def analyze_priorities(status: Dict) -> List[str]:
    """Analyze status and return prioritized list of actions"""
    priorities = []
    
    for county, data in status.items():
        if 'error' in data:
            priorities.append(f"FIX: {county} - Database connection/evaluation failed")
            continue
            
        if 'letters' not in data:
            priorities.append(f"FIX: {county} - No letter evaluation data")
            continue
            
        letters = data['letters']
        
        # Check critical failures (B, I, J as mentioned in brief)
        critical_letters = ['B', 'I', 'J']
        for letter in critical_letters:
            if letters.get(f'grade_{letter.lower()}') == 'FAIL':
                metric = letters.get(f'metric_{letter.lower()}', 'null')
                detail = letters.get(f'detail_{letter.lower()}', '')
                priorities.append(f"CRITICAL: {county} letter {letter} - {detail} (metric={metric})")
        
        # Check A-lane (dual-product coverage) 
        if letters.get('grade_a') == 'FAIL':
            metric = letters.get('metric_a', '0')
            priorities.append(f"HIGH: {county} letter A - Coverage only {metric} (need dual-product)")
        
        # Check E-lane (parcel linkage)
        if letters.get('grade_e') == 'FAIL':
            metric = letters.get('metric_e', '0')
            priorities.append(f"HIGH: {county} letter E - Parcel linkage {metric}% (need >=95%)")
            
    return priorities

def configure_missing_counties():
    """Configure calhoun and liberty counties that are missing from pipeline"""
    # Check cairn_multi_county_scraper.py for missing counties
    logger.info("Configuring missing counties (calhoun, liberty)...")
    
    # Based on analysis, calhoun and liberty are missing from COUNTY_URLS
    missing_configs = {
        'calhoun': ('realforeclose', 'https://calhoun.realforeclose.com'),
        'liberty': ('realforeclose', 'https://liberty.realforeclose.com')  # Need to verify this URL
    }
    
    # TODO: Add to cairn_multi_county_scraper.py
    logger.info(f"Need to add to COUNTY_URLS: {missing_configs}")
    return missing_configs

def main():
    """Main execution function"""
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # Just get and display current status
        status = get_shard_status()
        print_status_report(status)
        return
        
    logger.info("SHARD-6 Gold Standard Campaign Starting...")
    logger.info("Counties: escambia, suwannee, martin, calhoun, liberty")
    logger.info("Budget: 6 hours autonomous")
    logger.info(f"Started: {datetime.now(timezone.utc).isoformat()}")
    
    # Get initial status
    logger.info("Getting baseline status for all counties...")
    initial_status = get_shard_status()
    print_status_report(initial_status)
    
    # Analyze priorities
    logger.info("Analyzing priorities...")
    priorities = analyze_priorities(initial_status)
    
    print(f"\n{'='*50}")
    print("PRIORITY ACTION ITEMS")
    print("="*50)
    for i, priority in enumerate(priorities, 1):
        print(f"{i}. {priority}")
    
    # Configure missing counties
    missing_configs = configure_missing_counties()
    
    logger.info("Status analysis complete. Ready for implementation phase.")

if __name__ == "__main__":
    main()