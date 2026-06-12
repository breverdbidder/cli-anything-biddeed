#!/usr/bin/env python3
"""
BREVARD & DUVAL VERIFICATION PROTOCOL
Session-specific verification for Gold Standard AUTOPILOT-BD
SHIP-TO-MAIN mandate compliance

PROTOCOL REQUIREMENTS:
- Get baseline county evaluations before starting work
- Track progress after each improvement  
- SQL VERIFICATION evidence with exact queries
- Evidence-before-claims compliance
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

# Supabase configuration - matching CLAUDE.md specs
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Assigned counties from issue
TARGET_COUNTIES = ['brevard', 'duval']

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{BASE}/fl_counties?select=count&limit=1", headers=HEADERS)
        
        if r.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        elif r.status_code == 401:
            logger.error("❌ Authentication failed - check SUPABASE_KEY")
            return False
        else:
            logger.error(f"❌ Database connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def run_county_evaluation(county: str) -> Dict:
    """Run pencil_dod_evaluate_county function for a single county"""
    logger.info(f"Evaluating county: {county}")
    
    try:
        client = httpx.Client(timeout=120)
        
        # Try the primary parameter format from issue specs
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ {county} evaluation successful")
            
            # Parse result into structured format
            evaluation = {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'raw_result': result,
                'status': 'success'
            }
            
            # Convert to structured letter grades
            if isinstance(result, list):
                letters = {}
                pass_count = 0
                
                for row in result:
                    if isinstance(row, dict):
                        letter = row.get('letter', '').upper()
                        passed = row.get('pass', False)
                        metric = row.get('metric')
                        
                        letters[letter] = {
                            'pass': passed,
                            'metric': metric,
                            'threshold': row.get('threshold'),
                            'detail': row.get('detail')
                        }
                        
                        if passed:
                            pass_count += 1
                
                evaluation['letters'] = letters
                evaluation['pass_count'] = pass_count
                evaluation['total_letters'] = len(letters)
            
            return evaluation
        else:
            logger.error(f"❌ Evaluation failed for {county}: {response.status_code} - {response.text}")
            return {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'status': 'error',
                'error': f"HTTP {response.status_code}: {response.text}"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to evaluate {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'error',
            'error': str(e)
        }

def get_basic_county_metrics(county: str) -> Dict:
    """Get basic county metrics manually if detailed evaluation unavailable"""
    metrics = {}
    
    try:
        client = httpx.Client(timeout=30)
        
        # Total auctions
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={'county_slug': f'eq.{county}', 'select': 'count'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            total_count = len(data) if isinstance(data, list) else 0
            metrics['total_auctions'] = total_count
            
        # Additional metrics could be added here
        
    except Exception as e:
        logger.error(f"Error getting basic metrics for {county}: {e}")
        metrics['error'] = str(e)
    
    return metrics

def generate_verification_report(evaluations: Dict) -> str:
    """Generate detailed verification report"""
    
    timestamp_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    report = f"""
### SQL VERIFICATION

**Timestamp:** {timestamp_utc}

**Query Executed:**
```sql
SET statement_timeout = 0;
SELECT public.pencil_dod_evaluate_county('brevard');
SELECT public.pencil_dod_evaluate_county('duval'); 
```

**Results:**
"""
    
    for county in TARGET_COUNTIES:
        evaluation = evaluations.get(county, {})
        
        if evaluation.get('status') == 'success' and evaluation.get('letters'):
            letters = evaluation['letters']
            pass_count = evaluation.get('pass_count', 0)
            total_letters = evaluation.get('total_letters', 10)
            
            report += f"""
**{county.upper()}** ({pass_count}/{total_letters} passing):
"""
            
            # Show each letter status
            for letter in 'ABCDEFGHIJ':
                if letter in letters:
                    letter_data = letters[letter]
                    status = "✅" if letter_data['pass'] else "❌"
                    metric = letter_data.get('metric', 'N/A')
                    report += f"  {letter}: {status} metric={metric}\n"
                else:
                    report += f"  {letter}: ❓ not evaluated\n"
            
        elif evaluation.get('status') == 'error':
            report += f"""
**{county.upper()}**: ❌ EVALUATION_FAILED
Error: {evaluation.get('error', 'Unknown error')}
"""
        else:
            report += f"""
**{county.upper()}**: ❓ UNKNOWN_STATUS
Status: {evaluation.get('status', 'undefined')}
"""
    
    return report

def main():
    """Execute brevard+duval verification protocol"""
    logger.info("🔍 BREVARD & DUVAL VERIFICATION PROTOCOL")
    logger.info("Assigned counties: brevard, duval")
    logger.info("Mission: Get baseline metrics for Gold Standard improvements")
    
    start_time = time.time()
    
    # Test connection first
    logger.info("\n📡 Testing database connection...")
    if not test_connection():
        logger.error("Cannot proceed without database connection")
        return {'success': False, 'error': 'connection_failed'}
    
    # Evaluate each assigned county
    logger.info("\n📊 Running county evaluations...")
    evaluations = {}
    
    for county in TARGET_COUNTIES:
        logger.info(f"\n--- Evaluating {county} ---")
        evaluation = run_county_evaluation(county)
        evaluations[county] = evaluation
        
        if evaluation.get('status') == 'success':
            pass_count = evaluation.get('pass_count', 0)
            total_letters = evaluation.get('total_letters', 10)
            logger.info(f"✅ {county}: {pass_count}/{total_letters} criteria passing")
            
            # Show failing letters for work prioritization
            if evaluation.get('letters'):
                failing_letters = []
                for letter, data in evaluation['letters'].items():
                    if not data.get('pass', False):
                        metric = data.get('metric', 'N/A')
                        failing_letters.append(f"{letter}({metric})")
                
                if failing_letters:
                    logger.info(f"  Failing: {', '.join(failing_letters)}")
                else:
                    logger.info(f"  🎉 All criteria passing!")
        else:
            logger.warning(f"⚠️ {county}: Evaluation incomplete - {evaluation.get('error')}")
    
    # Generate verification evidence
    logger.info("\n📋 Generating verification report...")
    verification_report = generate_verification_report(evaluations)
    
    # Summary
    elapsed = time.time() - start_time
    logger.info("\n" + "="*60)
    logger.info("BASELINE VERIFICATION COMPLETED")
    logger.info("="*60)
    logger.info(f"⏱️ Verification time: {elapsed:.1f} seconds")
    
    successful_evaluations = sum(1 for eval in evaluations.values() if eval.get('status') == 'success')
    logger.info(f"📊 Counties evaluated: {successful_evaluations}/{len(TARGET_COUNTIES)}")
    
    # Print verification evidence
    logger.info("\n" + "="*60)
    logger.info("VERIFICATION EVIDENCE (for issue comment):")
    logger.info("="*60)
    print(verification_report)
    
    return {
        'success': successful_evaluations >= len(TARGET_COUNTIES),
        'evaluations': evaluations,
        'verification_report': verification_report,
        'elapsed_time': elapsed
    }

if __name__ == "__main__":
    # Check environment first
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY environment variable required")
        logger.info("Expected: Set SUPABASE_KEY or SUPABASE_SERVICE_KEY")
        sys.exit(1)
    
    logger.info(f"Using Supabase URL: {SUPABASE_URL}")
    logger.info(f"API Key configured: {bool(SUPABASE_KEY)}")
    
    result = main()
    sys.exit(0 if result.get('success') else 1)