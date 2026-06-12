#!/usr/bin/env python3
"""
CCB Gold Standard Autonomous Session Coordinator
Handles Charlotte, Citrus, Broward autonomous 6-hour Gold Standard improvements

Implements CRITERION-PARALLEL PIVOT strategy per brief:
- B: Verified outcomes (highest leverage)
- J: Deal generator (high leverage) 
- E: Parcel linkage (charlotte/broward priority)
- C/D: Parity fixes
- Ship directly to main per SHIP-TO-MAIN MANDATE

Usage:
  python scripts/ccb_gold_standard_autonomous.py

Target counties: charlotte (3/10), citrus (3/10), broward (2/10)
"""

import os
import sys
import subprocess
import requests
import json
import time
from datetime import datetime, timedelta
import logging

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target counties from issue brief
TARGET_COUNTIES = ['charlotte', 'citrus', 'broward']

def test_connection():
    """Test Supabase connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Supabase connection successful")
            return True
        else:
            logger.error(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def get_county_baseline(county):
    """Get baseline evaluation for a county using pencil_dod_evaluate_county"""
    try:
        payload = {"county_name": county}
        response = requests.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to get baseline for {county}: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting baseline for {county}: {e}")
        return None

def run_script(script_path, args=[]):
    """Execute a script and return success status"""
    try:
        cmd = ["python", script_path] + args
        logger.info(f"🚀 Executing: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"✅ {script_path} completed successfully")
            logger.debug(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"❌ {script_path} failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {script_path} timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error running {script_path}: {e}")
        return False

def generate_verification_report(county, baseline, final):
    """Generate verification report comparing baseline vs final metrics"""
    if not baseline or not final:
        return f"❌ {county}: Missing evaluation data"
    
    report = [f"\n=== {county.upper()} VERIFICATION ==="]
    
    improvements = []
    for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
        base_grade = baseline.get(f"grade_{letter.lower()}", 'UNKNOWN')
        final_grade = final.get(f"grade_{letter.lower()}", 'UNKNOWN')
        
        base_metric = baseline.get(f"metric_{letter.lower()}")
        final_metric = final.get(f"metric_{letter.lower()}")
        
        status = "→"
        if base_grade != final_grade:
            if final_grade == "PASS":
                status = "✅ IMPROVED"
                improvements.append(letter)
            elif base_grade == "PASS":
                status = "❌ REGRESSED"
        
        base_str = f"{base_grade}"
        if base_metric is not None:
            base_str += f" ({base_metric})"
            
        final_str = f"{final_grade}"
        if final_metric is not None:
            final_str += f" ({final_metric})"
        
        report.append(f"  {letter}: {base_str} {status} {final_str}")
    
    if improvements:
        report.append(f"\n🎯 IMPROVEMENTS: {', '.join(improvements)}")
    
    return "\n".join(report)

def commit_and_push_changes():
    """Commit changes to main branch per SHIP-TO-MAIN MANDATE"""
    try:
        # Add all new/modified files
        subprocess.run(["git", "add", "."], check=True)
        
        # Check if there are changes to commit
        result = subprocess.run(["git", "diff", "--staged", "--quiet"], capture_output=True)
        if result.returncode == 0:
            logger.info("📝 No changes to commit")
            return True
        
        # Commit with descriptive message
        commit_msg = f"""feat: CCB Gold Standard autonomous improvements

- Implemented Letter B verified outcomes scraper
- Added Letter J deal generator (Shapira V14 simulation)  
- Enhanced Letter E parcel linkage for charlotte/broward
- Target counties: charlotte, citrus, broward

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: breverdbidder <breverdbidder@users.noreply.github.com>"""

        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        
        # Push directly to main per SHIP-TO-MAIN MANDATE
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        logger.info("✅ Changes committed and pushed to main")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Git operation failed: {e}")
        return False

def main():
    logger.info("🚀 CCB Gold Standard Autonomous Session")
    logger.info(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    logger.info(f"Strategy: CRITERION-PARALLEL PIVOT (B→J→E→C/D)")
    logger.info(f"Mandate: SHIP-TO-MAIN (no PRs)")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test connection
    if not test_connection():
        logger.error("❌ Database connection failed")
        sys.exit(1)
    
    # Phase 1: Get baseline metrics
    logger.info("\n📊 Phase 1: Collecting baseline metrics")
    baselines = {}
    for county in TARGET_COUNTIES:
        baseline = get_county_baseline(county)
        baselines[county] = baseline
        if baseline:
            score = sum(1 for letter in ['a','b','c','d','e','f','g','h','i','j'] 
                       if baseline.get(f'grade_{letter}') == 'PASS')
            logger.info(f"  {county}: {score}/10 baseline")
    
    # Phase 2: Execute high-leverage fixes
    logger.info("\n⚡ Phase 2: Executing criterion fixes")
    
    # Letter B: Verified outcomes (highest leverage - all counties at 0%)
    logger.info("\n🎯 Letter B: Verified outcomes")
    b_success = run_script("ccb_verified_outcomes.py", ["--all"])
    
    # Letter J: Deal generator (high leverage - all counties at 0%)  
    logger.info("\n🎯 Letter J: Deal generator")
    j_success = run_script("ccb_deal_generator.py", ["--all"])
    
    # Letter E: Parcel linkage (charlotte/broward priority)
    logger.info("\n🎯 Letter E: Parcel linkage")
    e_success = run_script("ccb_parcel_linkage.py", ["--all"])
    
    # Phase 3: Verification protocol
    logger.info("\n📈 Phase 3: Verification protocol")
    
    # Wait for database updates to propagate
    time.sleep(10)
    
    # Get final metrics
    finals = {}
    for county in TARGET_COUNTIES:
        final = get_county_baseline(county)  # Same function, new results
        finals[county] = final
        if final:
            score = sum(1 for letter in ['a','b','c','d','e','f','g','h','i','j'] 
                       if final.get(f'grade_{letter}') == 'PASS')
            logger.info(f"  {county}: {score}/10 final")
    
    # Phase 4: Generate verification report
    logger.info("\n📋 Phase 4: Verification report")
    
    for county in TARGET_COUNTIES:
        report = generate_verification_report(county, baselines.get(county), finals.get(county))
        logger.info(report)
    
    # Phase 5: Ship to main
    logger.info("\n🚢 Phase 5: Ship to main")
    commit_success = commit_and_push_changes()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("CCB GOLD STANDARD SESSION COMPLETE")
    logger.info("="*60)
    
    successes = [
        f"Letter B: {'✅' if b_success else '❌'}",
        f"Letter J: {'✅' if j_success else '❌'}",
        f"Letter E: {'✅' if e_success else '❌'}",
        f"Ship-to-main: {'✅' if commit_success else '❌'}"
    ]
    
    for success in successes:
        logger.info(f"  {success}")
    
    # SQL verification queries for the issue
    logger.info("\n### SQL VERIFICATION")
    logger.info("```sql")
    logger.info("-- Timestamp: " + datetime.now().isoformat())
    logger.info("-- Database: mocerqjnksmhcjzxrewo.supabase.co")
    logger.info("")
    logger.info("-- Verify Letter B improvements")
    logger.info("SELECT county, COUNT(*) as verified_outcomes")
    logger.info("FROM foreclosure_outcomes") 
    logger.info("WHERE county IN ('charlotte', 'citrus', 'broward')")
    logger.info("  AND data_source LIKE 'clerk_%_official_records'")
    logger.info("GROUP BY county;")
    logger.info("")
    logger.info("-- Verify Letter J improvements")
    logger.info("SELECT county, COUNT(*) as bid_decisions")
    logger.info("FROM bid_decisions")
    logger.info("WHERE county IN ('charlotte', 'citrus', 'broward')")
    logger.info("  AND arv IS NOT NULL AND max_bid IS NOT NULL")
    logger.info("  AND ml_score IS NOT NULL AND factors IS NOT NULL")
    logger.info("GROUP BY county;")
    logger.info("")
    logger.info("-- Verify Letter E improvements")
    logger.info("SELECT county, COUNT(*) as total_auctions,")
    logger.info("       SUM(CASE WHEN parcel_id IS NOT NULL THEN 1 ELSE 0 END) as linked,")
    logger.info("       ROUND(100.0 * SUM(CASE WHEN parcel_id IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) as pct_linked")
    logger.info("FROM multi_county_auctions")
    logger.info("WHERE county IN ('charlotte', 'citrus', 'broward')")
    logger.info("GROUP BY county;")
    logger.info("```")
    
    all_success = all([b_success, j_success, e_success, commit_success])
    logger.info(f"\n🎯 Session status: {'✅ SUCCESS' if all_success else '❌ PARTIAL'}")
    
    return 0 if all_success else 1

if __name__ == "__main__":
    sys.exit(main())