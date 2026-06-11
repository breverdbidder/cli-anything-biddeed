#!/usr/bin/env python3
"""
SHARD-11 VERIFICATION PROTOCOL
Mandatory before/after verification for autonomous Gold Standard session

PROTOCOL REQUIREMENTS:
- After each fix: SELECT public.pencil_dod_evaluate_county('<county>');
- Before session end: SET statement_timeout=0; SELECT public.gold_standard_loop();
- Closing summary MUST paste literal before/after JSON for each county
- Claims without verification evidence = Honesty Protocol violations

SHARD-11 COUNTIES: orange, baker, miami_dade, gadsden, wakulla
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

# Supabase configuration - using CLAUDE.md specified values
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.error("SUPABASE_KEY not found in environment variables")
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# SHARD-11 target counties
SHARD11_COUNTIES = ['orange', 'baker', 'miami_dade', 'gadsden', 'wakulla']

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
            
            # Convert to letter grade format
            if isinstance(result, list):
                letters = {}
                pass_count = 0
                for row in result:
                    if isinstance(row, dict):
                        letter = row.get('letter', '').upper()
                        is_pass = row.get('pass', False)
                        letters[f'grade_{letter.lower()}'] = 'PASS' if is_pass else 'FAIL'
                        letters[f'metric_{letter.lower()}'] = row.get('metric')
                        letters[f'detail_{letter.lower()}'] = row.get('detail', '')
                        if is_pass:
                            pass_count += 1
                
                evaluation['letters'] = letters
                evaluation['pass_count'] = pass_count
            
            return evaluation
            
    except Exception as e:
        logger.error(f"❌ Failed to evaluate {county}: {e}")
        return {
            'county': county,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'error': str(e),
            'evaluation_method': 'failed'
        }

def get_baseline_metrics() -> Dict:
    """Get baseline metrics for all SHARD-11 counties"""
    logger.info("🔍 Collecting baseline metrics for SHARD-11 counties...")
    
    baseline = {}
    baseline_start = time.time()
    
    for county in SHARD11_COUNTIES:
        logger.info(f"\n--- Baseline for {county} ---")
        evaluation = run_county_evaluation(county)
        baseline[county] = evaluation
        
        if evaluation.get('error'):
            logger.warning(f"❌ {county}: Baseline failed - {evaluation['error']}")
        elif evaluation.get('pass_count') is not None:
            pass_count = evaluation['pass_count']
            logger.info(f"📊 {county}: {pass_count}/10 letters passing")
        else:
            logger.info(f"⚠️ {county}: Partial baseline collected")
    
    baseline['collection_time'] = time.time() - baseline_start
    baseline['timestamp'] = datetime.now(timezone.utc).isoformat()
    
    return baseline

def analyze_priority_targets(baseline: Dict) -> List[tuple]:
    """Analyze baseline to identify highest-priority work"""
    priorities = []
    
    logger.info("\n🎯 ANALYZING PRIORITY TARGETS...")
    
    for county in SHARD11_COUNTIES:
        county_data = baseline.get(county, {})
        
        if county_data.get('error'):
            logger.warning(f"{county}: Baseline evaluation failed - skipping priority analysis")
            continue
            
        letters = county_data.get('letters', {})
        pass_count = county_data.get('pass_count', 0)
        
        # Calculate priority score based on:
        # 1. Current pass count (lower = higher priority)
        # 2. Critical letters B, I, J status
        # 3. Expected impact/leverage
        
        priority_score = 0
        
        # Base score from pass count (10 - pass_count)
        priority_score += (10 - pass_count) * 10
        
        # Critical letter bonuses
        if letters.get('grade_b') == 'FAIL':
            priority_score += 50  # Verified outcomes critical
        if letters.get('grade_i') == 'FAIL':
            priority_score += 40  # Property card completion
        if letters.get('grade_j') == 'FAIL':
            priority_score += 30  # Deal completion
        if letters.get('grade_e') == 'FAIL':
            priority_score += 25  # Parcel linkage feeds other letters
        
        # Letter H (freshness) failure is high priority for active counties
        if letters.get('grade_h') == 'FAIL':
            h_detail = letters.get('detail_h', '')
            if 'hours since last_seen' in h_detail:
                try:
                    hours = float(h_detail.split('=')[1].split()[0])
                    if hours > 48:
                        priority_score += 20
                except:
                    priority_score += 15
        
        priorities.append((county, priority_score, pass_count, {
            'B': letters.get('grade_b', 'UNKNOWN'),
            'E': letters.get('grade_e', 'UNKNOWN'), 
            'H': letters.get('grade_h', 'UNKNOWN'),
            'I': letters.get('grade_i', 'UNKNOWN'),
            'J': letters.get('grade_j', 'UNKNOWN')
        }))
    
    # Sort by priority score (highest first)
    priorities.sort(key=lambda x: x[1], reverse=True)
    
    logger.info("\n📋 PRIORITY RANKING:")
    for i, (county, score, passes, critical) in enumerate(priorities, 1):
        logger.info(f"{i}. {county}: score={score} passes={passes}/10 critical={critical}")
    
    return priorities

def generate_work_plan(priorities: List[tuple]) -> Dict:
    """Generate concrete work plan based on priority analysis"""
    
    logger.info("\n📝 GENERATING WORK PLAN...")
    
    work_plan = {
        'session_start': datetime.now(timezone.utc).isoformat(),
        'priorities': priorities,
        'planned_tasks': [],
        'estimated_hours': 0
    }
    
    for county, score, passes, critical in priorities[:3]:  # Top 3 priorities
        county_tasks = []
        
        if critical['H'] == 'FAIL':
            county_tasks.append({
                'letter': 'H',
                'task': 'Configure/fix data refresh pipeline',
                'estimated_hours': 0.5,
                'leverage': 'Enables other metrics'
            })
        
        if critical['E'] == 'FAIL':
            county_tasks.append({
                'letter': 'E', 
                'task': 'Implement parcel linkage via ArcGIS FeatureServer',
                'estimated_hours': 1.5,
                'leverage': 'Feeds C/D parity and enables other workflows'
            })
        
        if critical['B'] == 'FAIL':
            county_tasks.append({
                'letter': 'B',
                'task': 'Build independent verified outcomes scraper',
                'estimated_hours': 2.0,
                'leverage': 'Core validation requirement'
            })
        
        if critical['I'] == 'FAIL':
            county_tasks.append({
                'letter': 'I',
                'task': 'Extend property card enrichment pipeline',
                'estimated_hours': 1.0,
                'leverage': 'Completes property data foundation'
            })
        
        if critical['J'] == 'FAIL':
            county_tasks.append({
                'letter': 'J',
                'task': 'Wire Shapira Formula deal completion pipeline',
                'estimated_hours': 1.0,
                'leverage': 'Final deal metrics'
            })
        
        county_plan = {
            'county': county,
            'priority_score': score,
            'current_passes': passes,
            'tasks': county_tasks,
            'estimated_hours': sum(task['estimated_hours'] for task in county_tasks)
        }
        
        work_plan['planned_tasks'].append(county_plan)
        work_plan['estimated_hours'] += county_plan['estimated_hours']
    
    logger.info(f"📊 Total planned work: {work_plan['estimated_hours']} hours across {len(work_plan['planned_tasks'])} counties")
    
    return work_plan

def main():
    """Execute SHARD-11 baseline evaluation and work planning"""
    logger.info("🚀 SHARD-11 AUTONOMOUS SESSION INITIALIZATION")
    logger.info(f"Target counties: {', '.join(SHARD11_COUNTIES)}")
    
    try:
        # Step 1: Collect baseline metrics
        logger.info("\n" + "="*60)
        logger.info("STEP 1: BASELINE EVALUATION")
        logger.info("="*60)
        
        baseline = get_baseline_metrics()
        
        # Step 2: Analyze priorities
        logger.info("\n" + "="*60)
        logger.info("STEP 2: PRIORITY ANALYSIS") 
        logger.info("="*60)
        
        priorities = analyze_priority_targets(baseline)
        
        # Step 3: Generate work plan
        logger.info("\n" + "="*60)
        logger.info("STEP 3: WORK PLAN GENERATION")
        logger.info("="*60)
        
        work_plan = generate_work_plan(priorities)
        
        # Save baseline and plan for session tracking
        session_data = {
            'session_id': f"shard11_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            'baseline': baseline,
            'work_plan': work_plan,
            'priorities': priorities
        }
        
        # Write session data
        with open('/tmp/shard11_session.json', 'w') as f:
            json.dump(session_data, f, indent=2)
        
        logger.info(f"\n✅ Session initialized - baseline collected for {len(baseline) - 2} counties")
        logger.info(f"📋 Work plan ready - {work_plan['estimated_hours']} hours planned")
        logger.info("🔄 Ready to begin implementation phase")
        
        return session_data
        
    except Exception as e:
        logger.error(f"❌ Session initialization failed: {e}")
        return None
    
    finally:
        client.close()

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)