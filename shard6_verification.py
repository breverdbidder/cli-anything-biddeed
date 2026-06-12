#!/usr/bin/env python3
"""
SHARD-6 VERIFICATION PROTOCOL  
Counties: highlands, st_johns, hendry, calhoun, liberty
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

# SHARD-6 target counties
TARGET_COUNTIES = ['highlands', 'st_johns', 'hendry', 'calhoun', 'liberty']

client = httpx.Client(timeout=120)

def run_county_evaluation(county: str) -> Dict:
    """Run pencil_dod_evaluate_county function for a single county"""
    logger.info(f"Evaluating county: {county}")
    
    try:
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": county},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"✅ {county} evaluation successful")
            
            # Parse the result into a structured format
            evaluation = {
                'county': county,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'raw_result': result
            }
            
            # Convert list of letter results to structured format
            if isinstance(result, list):
                letters = {}
                for row in result:
                    if isinstance(row, dict):
                        letter = row.get('letter', '').upper()
                        if letter != 'ERROR':
                            letters[f'grade_{letter.lower()}'] = 'PASS' if row.get('pass') else 'FAIL'
                            letters[f'metric_{letter.lower()}'] = row.get('metric')
                            letters[f'detail_{letter.lower()}'] = row.get('detail')
                            letters[f'threshold_{letter.lower()}'] = row.get('threshold')
                        else:
                            evaluation['error'] = row.get('detail', 'Unknown error')
                            return evaluation
                
                evaluation['letters'] = letters
                evaluation['pass_count'] = sum(1 for k, v in letters.items() if k.startswith('grade_') and v == 'PASS')
            
            return evaluation
            
    except Exception as e:
        logger.error(f"❌ Failed to evaluate {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e),
            'evaluation_method': 'failed'
        }

def generate_verification_summary(evaluations: Dict) -> str:
    """Generate summary for the GitHub comment"""
    
    timestamp_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    summary = f"""
### SHARD-6 COUNTY STATUS VERIFICATION

**Timestamp:** {timestamp_utc}

"""
    
    total_passed = 0
    total_evaluated = 0
    
    for county in TARGET_COUNTIES:
        evaluation = evaluations.get(county, {})
        
        if evaluation.get('error'):
            summary += f"**{county.upper()}**: ❌ EVALUATION_FAILED - {evaluation.get('error')}\n"
        elif evaluation.get('letters'):
            letters = evaluation['letters']
            pass_count = evaluation.get('pass_count', 0)
            total_passed += pass_count
            total_evaluated += 10  # 10 letters per county
            
            # Show status for key letters
            letter_status = []
            for letter in ['a', 'b', 'e', 'h', 'i', 'j']:
                grade = letters.get(f'grade_{letter}', 'UNKNOWN')
                metric = letters.get(f'metric_{letter}', 'N/A')
                detail = letters.get(f'detail_{letter}', '')
                letter_status.append(f"{letter.upper()}: {grade} ({metric}) [{detail}]")
            
            summary += f"**{county.upper()}**: {pass_count}/10 passed\n"
            for status in letter_status:
                summary += f"  - {status}\n"
            summary += "\n"
        else:
            summary += f"**{county.upper()}**: ❓ UNKNOWN_STATUS\n"
    
    summary += f"\n**FLEET TOTAL**: {total_passed}/{total_evaluated} letters passed\n"
    
    return summary

def main():
    """Execute SHARD-6 verification"""
    logger.info("🔍 SHARD-6 VERIFICATION PROTOCOL")
    
    if not SUPABASE_KEY:
        logger.error("❌ SUPABASE_KEY not found in environment")
        sys.exit(1)
    
    protocol_start = time.time()
    
    try:
        # Test connection first
        test_response = client.get(f"{BASE}/fl_counties?select=count&limit=1", headers=HEADERS)
        if test_response.status_code != 200:
            logger.error("❌ Database connection failed")
            sys.exit(1)
        logger.info("✅ Database connection verified")
        
        # Individual county evaluations
        logger.info("\n📊 Evaluating SHARD-6 counties...")
        county_evaluations = {}
        
        for county in TARGET_COUNTIES:
            logger.info(f"\n--- Evaluating {county} ---")
            evaluation = run_county_evaluation(county)
            county_evaluations[county] = evaluation
            
            # Log immediate results
            if evaluation.get('error'):
                logger.warning(f"❌ {county}: Evaluation failed - {evaluation['error']}")
            elif evaluation.get('pass_count') is not None:
                pass_count = evaluation['pass_count']
                logger.info(f"✅ {county}: {pass_count}/10 letters passing")
            else:
                logger.info(f"⚠️ {county}: Partial evaluation completed")
        
        # Generate summary
        verification_summary = generate_verification_summary(county_evaluations)
        
        # Protocol completion
        elapsed = time.time() - protocol_start
        
        logger.info("\n" + "="*60)
        logger.info("SHARD-6 VERIFICATION COMPLETE")
        logger.info("="*60)
        logger.info(f"⏱️ Protocol time: {elapsed:.1f} seconds")
        
        # Print summary for GitHub comment
        print(verification_summary)
        
        return {
            'protocol_success': True,
            'county_evaluations': county_evaluations,
            'verification_summary': verification_summary,
            'elapsed_time': elapsed
        }
        
    except Exception as e:
        logger.error(f"❌ Verification protocol failed: {e}")
        return {
            'protocol_success': False,
            'error': str(e),
            'elapsed_time': time.time() - protocol_start
        }
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get('protocol_success') else 1)