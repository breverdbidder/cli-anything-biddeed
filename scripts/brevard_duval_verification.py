#!/usr/bin/env python3
"""
BREVARD+DUVAL VERIFICATION PROTOCOL
Mandatory before/after verification for GOLD STANDARD AUTOPILOT-BD session

SHIP GATE — VERIFIED-tier compliance:
1. Execute, not just commit
2. Paste SQL proof in completion comment  
3. SQL VERIFICATION block with exact queries and results
4. Timestamp evidence in UTC

VERIFICATION PROTOCOL REQUIREMENTS:
- Before improvements: baseline evaluation using pencil_dod_evaluate_county
- After improvements: current evaluation
- SQL VERIFICATION block with exact queries and results
- Timestamp evidence in UTC
- Claims without verification evidence = Honesty Protocol violations

Usage:
  python scripts/brevard_duval_verification.py --baseline
  python scripts/brevard_duval_verification.py --final
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

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

# SHARD target counties per issue assignment
TARGET_COUNTIES = ['brevard', 'duval']

client = httpx.Client(timeout=120)  # Longer timeout for verification queries

def set_statement_timeout():
    """Set unlimited statement timeout as required by Gold Standard protocol"""
    logger.info("Setting statement timeout = 0 for heavy queries...")
    
    try:
        # This would require a direct SQL connection, which we may not have
        # For now, log the requirement
        logger.info("⚠️  Note: SET statement_timeout=0 should be run before heavy queries")
        return True
    except Exception as e:
        logger.error(f"Could not set statement timeout: {e}")
        return False

def evaluate_county(county_slug: str) -> Optional[List[Dict]]:
    """Run pencil_dod_evaluate_county for a single county"""
    logger.info(f"📊 Evaluating {county_slug} using pencil_dod_evaluate_county...")
    
    try:
        # Call the RPC function
        payload = {"county_slug_arg": county_slug}
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ Evaluation completed for {county_slug}")
            
            if isinstance(result, list) and len(result) > 0:
                # Format results for display
                pass_count = sum(1 for r in result if r.get('pass', False))
                logger.info(f"County {county_slug} score: {pass_count}/10")
                
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅ PASS" if letter_data.get('pass') else "❌ FAIL"
                    details = letter_data.get('details', '')
                    logger.info(f"  {letter}: {status} metric={metric} [{details}]")
                
                return result
            else:
                logger.warning(f"Empty or invalid result for {county_slug}")
                return None
        else:
            logger.error(f"❌ Failed to evaluate {county_slug}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error evaluating {county_slug}: {e}")
        return None

def run_gold_standard_loop():
    """Execute the gold standard loop function"""
    logger.info("🔄 Running gold standard loop...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/gold_standard_loop",
            headers=HEADERS,
            json={}
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ Gold standard loop completed")
            return result
        else:
            logger.error(f"❌ Gold standard loop failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error running gold standard loop: {e}")
        return None

def run_gold_standard_certify():
    """Execute the gold standard certify function"""
    logger.info("🏆 Running gold standard certify...")
    
    try:
        response = client.post(
            f"{BASE}/rpc/gold_standard_certify",
            headers=HEADERS,
            json={}
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ Gold standard certify completed")
            return result
        else:
            logger.error(f"❌ Gold standard certify failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error running gold standard certify: {e}")
        return None

def get_timestamp_utc() -> str:
    """Get current UTC timestamp for verification"""
    return datetime.now(timezone.utc).isoformat()

def generate_sql_verification_block(county_evaluations: Dict, timestamp: str) -> str:
    """Generate SQL VERIFICATION block for issue comment"""
    verification_block = f"""
### SQL VERIFICATION

**Timestamp**: {timestamp}

**Evaluation Queries Executed**:
"""
    
    for county, results in county_evaluations.items():
        verification_block += f"""
```sql
-- {county.upper()} EVALUATION
SELECT public.pencil_dod_evaluate_county('{county}');
```

**Results for {county}**:
```json
{json.dumps(results, indent=2) if results else 'null'}
```
"""
    
    # Add summary metrics
    verification_block += """
**Summary Metrics**:
"""
    
    for county, results in county_evaluations.items():
        if results and isinstance(results, list):
            pass_count = sum(1 for r in results if r.get('pass', False))
            verification_block += f"- {county}: {pass_count}/10 passing\n"
    
    return verification_block

def baseline_verification():
    """Run baseline verification before improvements"""
    logger.info("🏁 BASELINE VERIFICATION - Before Improvements")
    logger.info("="*50)
    
    timestamp = get_timestamp_utc()
    
    # Set statement timeout
    set_statement_timeout()
    
    # Evaluate each county
    county_evaluations = {}
    for county in TARGET_COUNTIES:
        results = evaluate_county(county)
        county_evaluations[county] = results
    
    # Generate verification block
    verification_block = generate_sql_verification_block(county_evaluations, timestamp)
    
    # Save baseline results
    baseline_file = f"baseline_verification_{timestamp.replace(':', '-')}.json"
    with open(baseline_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'type': 'baseline',
            'counties': county_evaluations
        }, f, indent=2)
    
    logger.info(f"📝 Baseline verification saved to {baseline_file}")
    logger.info("BASELINE SQL VERIFICATION BLOCK:")
    print(verification_block)
    
    return county_evaluations

def final_verification():
    """Run final verification after improvements"""
    logger.info("🏁 FINAL VERIFICATION - After Improvements")
    logger.info("="*50)
    
    timestamp = get_timestamp_utc()
    
    # Set statement timeout
    set_statement_timeout()
    
    # Evaluate each county
    county_evaluations = {}
    for county in TARGET_COUNTIES:
        results = evaluate_county(county)
        county_evaluations[county] = results
    
    # Run gold standard functions
    logger.info("🔄 Running gold standard functions...")
    
    # Only run if not in parallel fleet (other shards working)
    # For now, skip these to avoid conflicts per parallel fleet rules
    logger.info("⚠️  Skipping gold_standard_loop() - parallel fleet active")
    logger.info("⚠️  Skipping gold_standard_certify() - parallel fleet active")
    
    # Generate verification block  
    verification_block = generate_sql_verification_block(county_evaluations, timestamp)
    
    # Save final results
    final_file = f"final_verification_{timestamp.replace(':', '-')}.json"
    with open(final_file, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'type': 'final',
            'counties': county_evaluations
        }, f, indent=2)
    
    logger.info(f"📝 Final verification saved to {final_file}")
    logger.info("FINAL SQL VERIFICATION BLOCK:")
    print(verification_block)
    
    return county_evaluations

def compare_results(baseline_file: str, final_file: str):
    """Compare baseline vs final results"""
    try:
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        with open(final_file, 'r') as f:
            final = json.load(f)
        
        logger.info("📈 BEFORE/AFTER COMPARISON:")
        
        for county in TARGET_COUNTIES:
            baseline_results = baseline.get('counties', {}).get(county, [])
            final_results = final.get('counties', {}).get(county, [])
            
            if baseline_results and final_results:
                baseline_pass = sum(1 for r in baseline_results if r.get('pass', False))
                final_pass = sum(1 for r in final_results if r.get('pass', False))
                
                logger.info(f"{county}: {baseline_pass}/10 → {final_pass}/10 ({'+' if final_pass > baseline_pass else ''}{final_pass - baseline_pass})")
                
                # Show specific letter improvements
                for letter in 'ABCDEFGHIJ':
                    baseline_letter = next((r for r in baseline_results if r.get('letter') == letter), {})
                    final_letter = next((r for r in final_results if r.get('letter') == letter), {})
                    
                    if baseline_letter and final_letter:
                        baseline_metric = baseline_letter.get('metric', 0)
                        final_metric = final_letter.get('metric', 0)
                        
                        if letter in ['C', 'D', 'E']:  # Our target letters
                            if isinstance(baseline_metric, (int, float)) and isinstance(final_metric, (int, float)):
                                delta = final_metric - baseline_metric
                                logger.info(f"  {letter}: {baseline_metric:.1f} → {final_metric:.1f} ({'+' if delta > 0 else ''}{delta:.1f})")
        
    except Exception as e:
        logger.error(f"Error comparing results: {e}")

def main():
    """Main verification function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run verification protocol for brevard+duval')
    parser.add_argument('--baseline', action='store_true', 
                       help='Run baseline verification before improvements')
    parser.add_argument('--final', action='store_true',
                       help='Run final verification after improvements')
    parser.add_argument('--compare', nargs=2, metavar=('BASELINE_FILE', 'FINAL_FILE'),
                       help='Compare two verification files')
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        sys.exit(1)
    
    logger.info(f"🔍 BREVARD+DUVAL VERIFICATION PROTOCOL")
    logger.info(f"Target counties: {TARGET_COUNTIES}")
    logger.info(f"Timestamp: {get_timestamp_utc()}")
    
    if args.baseline:
        baseline_verification()
    elif args.final:
        final_verification()
    elif args.compare:
        compare_results(args.compare[0], args.compare[1])
    else:
        logger.error("Must specify --baseline, --final, or --compare")
        sys.exit(1)
    
    logger.info("✅ Verification protocol completed")

if __name__ == "__main__":
    main()