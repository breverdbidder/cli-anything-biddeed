#!/usr/bin/env python3
"""
BREVARD & DUVAL VERIFICATION PROTOCOL
Gold Standard Autopilot Session baseline and progress verification

Based on shard12_verification_protocol.py but adapted for brevard/duval counties
per the Gold Standard Autopilot issue requirements.
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

# Supabase configuration from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Target counties for this session
TARGET_COUNTIES = ['brevard', 'duval']

# Client with extended timeout for verification queries
client = httpx.Client(timeout=120)

def run_county_evaluation(county: str) -> Dict:
    """Run pencil_dod_evaluate_county function for a single county"""
    logger.info(f"Evaluating county: {county}")
    
    try:
        # Try different parameter formats the function might accept
        for param_name in ['county_slug_arg', 'county_name', 'county']:
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
                    
                    return evaluation
                    
            except Exception as e:
                logger.debug(f"Param {param_name} failed: {e}")
                continue
        
        # If RPC calls fail, return error
        logger.warning(f"❌ RPC evaluation failed for {county}")
        
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': 'rpc_evaluation_failed'
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to evaluate {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e)
        }

def generate_verification_block(evaluations: Dict) -> str:
    """Generate SQL VERIFICATION block for issue comment"""
    
    timestamp_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    
    verification_block = f"""
### SQL VERIFICATION

Timestamp: {timestamp_utc}

**County Evaluation Queries:**
```sql
-- Set unlimited timeout for heavy queries
SET statement_timeout = 0;

-- Evaluate BREVARD & DUVAL counties
SELECT public.pencil_dod_evaluate_county('brevard');
SELECT public.pencil_dod_evaluate_county('duval');
```

**Verification Results:**
"""
    
    for county in TARGET_COUNTIES:
        evaluation = evaluations.get(county, {})
        
        if evaluation.get('error'):
            verification_block += f"""
**{county.upper()}**: ❌ EVALUATION_FAILED
Error: {evaluation.get('error')}
Timestamp: {evaluation.get('timestamp', 'Unknown')}
"""
        elif evaluation.get('letters'):
            letters = evaluation['letters']
            pass_count = evaluation.get('pass_count', 0)
            verification_block += f"""
**{county.upper()}**: ✅ EVALUATION_SUCCESS  
- Pass count: {pass_count}/10
- Letter A: {letters.get('grade_a', 'UNKNOWN')} (metric: {letters.get('metric_a', 'N/A')})
- Letter B: {letters.get('grade_b', 'UNKNOWN')} (metric: {letters.get('metric_b', 'N/A')})
- Letter C: {letters.get('grade_c', 'UNKNOWN')} (metric: {letters.get('metric_c', 'N/A')})
- Letter D: {letters.get('grade_d', 'UNKNOWN')} (metric: {letters.get('metric_d', 'N/A')})
- Letter E: {letters.get('grade_e', 'UNKNOWN')} (metric: {letters.get('metric_e', 'N/A')})
- Letter F: {letters.get('grade_f', 'UNKNOWN')} (metric: {letters.get('metric_f', 'N/A')})
- Letter G: {letters.get('grade_g', 'UNKNOWN')} (metric: {letters.get('metric_g', 'N/A')})
- Letter H: {letters.get('grade_h', 'UNKNOWN')} (metric: {letters.get('metric_h', 'N/A')})
- Letter I: {letters.get('grade_i', 'UNKNOWN')} (metric: {letters.get('metric_i', 'N/A')})
- Letter J: {letters.get('grade_j', 'UNKNOWN')} (metric: {letters.get('metric_j', 'N/A')})
- Timestamp: {evaluation.get('timestamp', 'Unknown')}
"""
        else:
            verification_block += f"""
**{county.upper()}**: ❓ UNKNOWN_STATUS
No valid evaluation data available
Timestamp: {evaluation.get('timestamp', 'Unknown')}
"""
    
    return verification_block

def main():
    """Execute BREVARD & DUVAL verification protocol"""
    logger.info("🔍 BREVARD & DUVAL GOLD STANDARD VERIFICATION")
    logger.info("Baseline assessment for autopilot session")
    
    # Check for required environment
    if not SUPABASE_KEY:
        logger.error("❌ No SUPABASE_KEY found in environment")
        return {'protocol_success': False, 'error': 'missing_supabase_key'}
    
    protocol_start = time.time()
    
    try:
        # Test connection
        logger.info("Testing database connection...")
        test_response = client.get(f"{BASE}/fl_counties?select=count&limit=1", headers=HEADERS)
        if test_response.status_code != 200:
            logger.error(f"❌ Database connection failed: {test_response.status_code}")
            return {'protocol_success': False, 'error': 'connection_failed'}
        
        logger.info("✅ Database connection successful")
        
        # Individual county evaluations
        logger.info("\n📊 COUNTY EVALUATIONS")
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
                
                # Show critical letters status
                letters = evaluation.get('letters', {})
                critical_letters = ['b', 'i', 'j']  # B, I, J are critical per issue
                for letter in critical_letters:
                    grade = letters.get(f'grade_{letter}', 'UNKNOWN')
                    metric = letters.get(f'metric_{letter}', 'N/A')
                    logger.info(f"    Letter {letter.upper()}: {grade} ({metric})")
            else:
                logger.info(f"⚠️ {county}: Partial evaluation completed")
        
        # Generate verification block
        logger.info("\n📋 GENERATING SQL VERIFICATION EVIDENCE")
        verification_block = generate_verification_block(county_evaluations)
        
        # Protocol completion summary
        elapsed = time.time() - protocol_start
        
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION PROTOCOL COMPLETION REPORT")
        logger.info("="*60)
        logger.info(f"⏱️ Protocol time: {elapsed:.1f} seconds")
        
        # Summary of county evaluations
        evaluated_count = sum(1 for eval in county_evaluations.values() if not eval.get('error'))
        logger.info(f"📊 Counties evaluated: {evaluated_count}/{len(TARGET_COUNTIES)}")
        
        # Print verification block for issue comment
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION EVIDENCE FOR ISSUE COMMENT:")
        logger.info("="*60)
        print(verification_block)  # Print for easy copy-paste
        
        # Final protocol status
        protocol_success = evaluated_count >= len(TARGET_COUNTIES)
        
        if protocol_success:
            logger.info("\n✅ VERIFICATION PROTOCOL: COMPLETED")
        else:
            logger.info("\n⚠️ VERIFICATION PROTOCOL: PARTIAL COMPLETION")
        
        return {
            'protocol_success': protocol_success,
            'county_evaluations': county_evaluations,
            'verification_block': verification_block,
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
    success = result.get('protocol_success', False)
    print(f"\nProtocol result: {'SUCCESS' if success else 'FAILED'}")
    sys.exit(0 if success else 1)