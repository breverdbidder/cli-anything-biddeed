#!/usr/bin/env python3
"""
SHARD-3 Gold Standard Campaign - Autonomous Session
Counties: broward, alachua, lee, st_lucie, jefferson

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

# Supabase configuration (following shard6 pattern)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-3 target counties (from briefing)
SHARD3_COUNTIES = ['broward', 'alachua', 'lee', 'st_lucie', 'jefferson']

# County scores from briefing (run 30 metrics)
CURRENT_METRICS = {
    'broward': {'score': '2/10', 'pass_letters': ['A', 'H'], 'critical_issues': ['B=null', 'F=2.5%', 'C=19.4%', 'D=47.7%']},
    'alachua': {'score': '1/10', 'pass_letters': ['A'], 'critical_issues': ['H=433.0h', 'B=null', 'C=10.9%', 'E=77.4%']},
    'lee': {'score': '1/10', 'pass_letters': ['A'], 'critical_issues': ['H=89.0h', 'B=null', 'C=12.2%', 'E=78.5%']}, 
    'st_lucie': {'score': '1/10', 'pass_letters': ['A'], 'critical_issues': ['H=130.7h', 'B=null', 'C=19.8%', 'E=51.1%']},
    'jefferson': {'score': '0/10', 'pass_letters': [], 'critical_issues': ['A=0 (no data)', 'All letters fail']}
}

client = httpx.Client(timeout=120)

def test_connection() -> bool:
    """Test Supabase connection"""
    try:
        response = client.get(f"{BASE}/fl_counties?limit=1", headers=HEADERS)
        if response.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error(f"❌ Database connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def run_county_evaluation(county: str) -> Dict:
    """Run pencil_dod_evaluate_county function for a single county"""
    logger.info(f"Evaluating county: {county}")
    
    try:
        # Try different parameter formats the function might accept
        for param_name in ['county_slug_arg', 'county_param', 'county_name', 'county']:
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
    """Get current status for all SHARD-3 counties"""
    status = {}
    
    for county in SHARD3_COUNTIES:
        logger.info(f"Getting status for {county}...")
        status[county] = run_county_evaluation(county)
        
    return status

def print_status_report(status: Dict):
    """Print formatted status report with letter-by-letter breakdown"""
    print("\n" + "="*50)
    print("SHARD-3 GOLD STANDARD STATUS REPORT")
    print("="*50)
    
    for county, data in status.items():
        print(f"\n{county.upper()}:")
        
        if 'error' in data:
            print(f"  ❌ ERROR: {data['error']}")
            print(f"  Expected from briefing: {CURRENT_METRICS.get(county, {}).get('score', 'unknown')}")
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
        print(f"  Briefing data: {CURRENT_METRICS.get(county, {})}")

def analyze_priorities(status: Dict) -> List[str]:
    """Analyze status and return prioritized list of actions based on briefing directives"""
    priorities = []
    
    # From briefing: Brevard B+F Priority Directive
    # Also mentions criterion-parallel pivot: fix criteria fleet-wide
    
    for county, data in status.items():
        if 'error' in data:
            priorities.append(f"FIX: {county} - Database connection/evaluation failed")
            continue
            
        if 'letters' not in data:
            priorities.append(f"FIX: {county} - No letter evaluation data")
            continue
            
        letters = data['letters']
        
        # Critical three letters from briefing: B, I, J
        critical_letters = ['B', 'I', 'J']
        for letter in critical_letters:
            if letters.get(f'grade_{letter.lower()}') == 'FAIL':
                metric = letters.get(f'metric_{letter.lower()}', 'null')
                detail = letters.get(f'detail_{letter.lower()}', '')
                priorities.append(f"CRITICAL: {county} letter {letter} - {detail} (metric={metric})")
        
        # From briefing: B is critical priority (verified outcomes >=95%)
        if letters.get('grade_b') == 'FAIL':
            priorities.append(f"BREVARD B+F PRIORITY: {county} letter B - Independent verified outcomes needed")
        
        # From briefing: F is tier1 sold-amount >=95% 
        if letters.get('grade_f') == 'FAIL':
            priorities.append(f"BREVARD B+F PRIORITY: {county} letter F - Tier1 sold amounts needed")
        
        # Check A-lane (dual-product coverage) - foundational
        if letters.get('grade_a') == 'FAIL':
            metric = letters.get('metric_a', '0')
            priorities.append(f"FOUNDATIONAL: {county} letter A - Coverage only {metric} (need dual-product)")
        
        # Check E-lane (parcel linkage) - enables other metrics
        if letters.get('grade_e') == 'FAIL':
            metric = letters.get('metric_e', '0')
            priorities.append(f"ENABLER: {county} letter E - Parcel linkage {metric}% (need >=95%)")
        
        # Check H-lane (freshness) - operational health
        if letters.get('grade_h') == 'FAIL':
            metric = letters.get('metric_h', 'unknown')
            priorities.append(f"FRESHNESS: {county} letter H - Data staleness {metric}h (SLA 48h)")
            
    return priorities

def identify_quick_wins(status: Dict) -> List[str]:
    """Identify quick wins based on briefing analysis"""
    quick_wins = []
    
    # From briefing analysis:
    # - Jefferson 0/10: likely missing from scraper config
    # - A-lane failures: dual-product coverage setup
    # - H-lane failures: scraper scheduling issues
    
    for county, data in status.items():
        if county == 'jefferson' and ('error' in data or data.get('pass_count', 0) == 0):
            quick_wins.append(f"SETUP: {county} - Add to scraper configuration (missing county)")
        
        if 'letters' in data:
            letters = data['letters']
            
            # A-lane quick fixes
            if letters.get('grade_a') == 'FAIL':
                quick_wins.append(f"CONFIG: {county} - Configure dual-product lanes in pipeline.counties")
            
            # H-lane quick fixes  
            if letters.get('grade_h') == 'FAIL':
                quick_wins.append(f"CRON: {county} - Fix scraper scheduling for freshness")
    
    return quick_wins

def main():
    """Main execution function"""
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        # Just get and display current status
        if not test_connection():
            sys.exit(1)
        status = get_shard_status()
        print_status_report(status)
        return
        
    logger.info("🎯 SHARD-3 Gold Standard Campaign Starting...")
    logger.info("Counties: broward, alachua, lee, st_lucie, jefferson")
    logger.info("Budget: 6 hours autonomous")
    logger.info("Ship-to-main mandate: Push directly to main")
    logger.info(f"Started: {datetime.now(timezone.utc).isoformat()}")
    
    # Test connection first
    if not test_connection():
        logger.error("Database connection failed. Cannot proceed.")
        sys.exit(1)
    
    # Get initial status
    logger.info("Getting baseline status for all counties...")
    initial_status = get_shard_status()
    print_status_report(initial_status)
    
    # Analyze priorities
    logger.info("Analyzing priorities based on briefing directives...")
    priorities = analyze_priorities(initial_status)
    
    # Identify quick wins
    quick_wins = identify_quick_wins(initial_status)
    
    print(f"\n{'='*50}")
    print("PRIORITY ACTION ITEMS")
    print("="*50)
    for i, priority in enumerate(priorities, 1):
        print(f"{i}. {priority}")
    
    if quick_wins:
        print(f"\n{'='*30}")
        print("QUICK WINS")
        print("="*30)
        for i, win in enumerate(quick_wins, 1):
            print(f"{i}. {win}")
    
    print(f"\n{'='*50}")
    print("BRIEFING KEY DIRECTIVES")
    print("="*50)
    print("1. SHIP-TO-MAIN MANDATE: Commit directly to main, no PRs")
    print("2. BREVARD B+F PRIORITY: Focus on verified outcomes + tier1 sold amounts")  
    print("3. CRITERION-PARALLEL: Fix criteria fleet-wide, not counties serially")
    print("4. PARALLEL-FLEET RULES: Only touch assigned counties, avoid conflicts")
    print("5. VERIFICATION PROTOCOL: Use pencil_dod_evaluate_county to verify improvements")
    
    logger.info("Status analysis complete. Ready for implementation phase.")
    logger.info("Next: Run with implementation flags to execute fixes...")

if __name__ == "__main__":
    main()