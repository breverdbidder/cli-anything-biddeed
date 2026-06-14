#!/usr/bin/env python3
"""
SHARD-2 MASTER COORDINATOR
Gold Standard autonomous session coordinator for SHIP-TO-MAIN execution

Orchestrates high-leverage improvements across brevard, sarasota, jackson, st_lucie, holmes
Dispatch ID: 464969f4-742c-4182-8aad-5727210bef66

PRIORITY ORDER (per brief):
1. Brevard B Reconciliation (134.1% anomaly blocking certification)
2. J Generator (universal 0% blocker across all counties)  
3. C/D Parity fixes (frozen numerators vs growing denominators)
4. Verification and certification protocol

Usage:
  python scripts/shard2_master_coordinator.py --execute
  python scripts/shard2_master_coordinator.py --verify-only
"""
import os
import sys
import subprocess
import json
import httpx
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-2 configuration
SHARD_ID = "SHARD-2"
DISPATCH_ID = "464969f4-742c-4182-8aad-5727210bef66"
TARGET_COUNTIES = ['brevard', 'sarasota', 'jackson', 'st_lucie', 'holmes']
SESSION_START = datetime.now(timezone.utc)

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def log_session_banner():
    """Display session banner with key information"""
    elapsed = datetime.now(timezone.utc) - SESSION_START
    elapsed_hours = elapsed.total_seconds() / 3600
    
    print("=" * 70)
    print("🚀 GOLD STANDARD SHARD-2 AUTONOMOUS SESSION")
    print(f"   Dispatch ID: {DISPATCH_ID}")
    print(f"   Counties: {', '.join(TARGET_COUNTIES)}")
    print(f"   Budget: 6 hours (ship-to-main mandate)")
    print(f"   Elapsed: {elapsed_hours:.1f}h")
    print(f"   Session: {SESSION_START.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 70)

def run_script(script_path: str, description: str) -> bool:
    """Run a Python script and return success status"""
    log(f"🔧 Executing: {description}")
    log(f"   Script: {script_path}")
    
    try:
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
        
        if result.returncode == 0:
            log(f"✅ {description} completed successfully")
            if result.stdout:
                log(f"   Output: {result.stdout[-500:]}")  # Last 500 chars
            return True
        else:
            log(f"❌ {description} failed (exit code {result.returncode})", "ERROR")
            if result.stderr:
                log(f"   Error: {result.stderr[-500:]}", "ERROR")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"⏰ {description} timed out after 30 minutes", "ERROR")
        return False
    except Exception as e:
        log(f"❌ Error executing {description}: {e}", "ERROR")
        return False

def verify_database_connection() -> bool:
    """Test database connection before starting"""
    try:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        
        response = client.get(f"{SUPABASE_URL}/rest/v1/audit_log", headers=headers, params={"limit": "1"})
        
        if response.status_code == 200:
            log("✅ Supabase connection verified")
            return True
        else:
            log(f"❌ Database connection failed: {response.status_code}", "ERROR")
            return False
            
    except Exception as e:
        log(f"❌ Database connection error: {e}", "ERROR")
        return False

def get_baseline_metrics() -> Dict[str, Dict]:
    """Get baseline metrics for all counties before improvements"""
    log("📊 Collecting baseline metrics")
    baseline = {}
    
    for county in TARGET_COUNTIES:
        try:
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            }
            
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug": county}
            )
            
            if response.status_code == 200:
                result = response.json()
                baseline[county] = result
                
                # Parse pass count
                pass_count = 0
                if isinstance(result, list):
                    pass_count = sum(1 for row in result if isinstance(row, dict) and row.get('pass'))
                
                log(f"   {county.upper()}: {pass_count}/10 PASS")
            else:
                log(f"⚠️ Could not get baseline for {county}: {response.status_code}")
                baseline[county] = None
                
        except Exception as e:
            log(f"⚠️ Error getting baseline for {county}: {e}")
            baseline[county] = None
    
    return baseline

def execute_migration(migration_file: str) -> bool:
    """Execute Supabase migration"""
    if not os.path.exists(migration_file):
        log(f"⚠️ Migration file not found: {migration_file}")
        return True  # Don't block on missing migrations
    
    log(f"🔧 Applying migration: {migration_file}")
    
    # Try multiple migration methods
    migration_methods = [
        ["node", "migrations/run_migration.js", migration_file],
        ["supabase", "db", "push"]  # If supabase CLI is available
    ]
    
    for method in migration_methods:
        try:
            result = subprocess.run(method, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                log(f"✅ Migration applied successfully via {method[0]}")
                return True
        except Exception:
            continue
    
    log(f"⚠️ Could not apply migration via standard methods")
    return True  # Don't block session on migration issues

def priority_1_brevard_b_reconciliation() -> bool:
    """Priority 1: Fix Brevard B anomaly (134.1%)"""
    log("🎯 PRIORITY 1: Brevard B Reconciliation")
    return run_script("scripts/shard2_brevard_b_reconciliation.py", "Brevard B Anomaly Fix")

def priority_2_j_generator() -> bool:
    """Priority 2: Universal J Generator (0% → 95%)"""
    log("🎯 PRIORITY 2: J Generator (Universal 0% blocker)")
    
    # First apply bid_decisions migration
    migration_success = execute_migration("migrations/20260612_shard2_bid_decisions.sql")
    if not migration_success:
        log("⚠️ Migration may have failed, but continuing with J Generator")
    
    return run_script("scripts/shard2_j_generator.py", "Bid Decisions Pipeline")

def priority_3_cd_parity_fixes() -> bool:
    """Priority 3: C/D Parity fixes across all counties"""
    log("🎯 PRIORITY 3: C/D Parity Fixes (Supplementary Litmus)")
    return run_script("scripts/shard2_cd_parity_fix.py", "C/D Parity Supplementary Matching")

def run_verification_protocol() -> Dict[str, Dict]:
    """Run verification protocol to measure improvements"""
    log("🔍 Running post-improvement verification")
    
    return get_baseline_metrics()  # Same function, different context

def calculate_improvements(baseline: Dict, final: Dict) -> Dict:
    """Calculate improvements between baseline and final metrics"""
    improvements = {}
    
    for county in TARGET_COUNTIES:
        if county not in baseline or county not in final:
            continue
        
        base = baseline[county]
        fin = final[county]
        
        if not base or not fin:
            continue
        
        # Count passes
        base_passes = 0
        final_passes = 0
        
        if isinstance(base, list):
            base_passes = sum(1 for row in base if isinstance(row, dict) and row.get('pass'))
        if isinstance(fin, list):
            final_passes = sum(1 for row in fin if isinstance(row, dict) and row.get('pass'))
        
        improvements[county] = {
            'baseline_passes': base_passes,
            'final_passes': final_passes,
            'improvement': final_passes - base_passes
        }
    
    return improvements

def generate_session_report(baseline: Dict, final: Dict, improvements: Dict, execution_log: List[str]):
    """Generate comprehensive session report"""
    elapsed = datetime.now(timezone.utc) - SESSION_START
    elapsed_hours = elapsed.total_seconds() / 3600
    
    report = {
        'session_id': DISPATCH_ID,
        'shard': SHARD_ID,
        'counties': TARGET_COUNTIES,
        'start_time': SESSION_START.isoformat(),
        'end_time': datetime.now(timezone.utc).isoformat(),
        'elapsed_hours': elapsed_hours,
        'baseline_metrics': baseline,
        'final_metrics': final,
        'improvements': improvements,
        'execution_log': execution_log,
        'summary': {
            'total_counties': len(TARGET_COUNTIES),
            'counties_improved': len([c for c in improvements.values() if c['improvement'] > 0]),
            'total_point_gain': sum(c['improvement'] for c in improvements.values()),
            'success_rate': len([c for c in improvements.values() if c['improvement'] > 0]) / len(TARGET_COUNTIES) if TARGET_COUNTIES else 0
        }
    }
    
    log("📋 SESSION REPORT SUMMARY:")
    log(f"   Total elapsed: {elapsed_hours:.1f} hours")
    log(f"   Counties improved: {report['summary']['counties_improved']}/{report['summary']['total_counties']}")
    log(f"   Total point gain: +{report['summary']['total_point_gain']} letters")
    log(f"   Success rate: {report['summary']['success_rate']*100:.1f}%")
    
    return report

def execute_autonomous_session():
    """Execute the full autonomous session"""
    log_session_banner()
    
    execution_log = []
    
    # Pre-flight checks
    log("✈️ PRE-FLIGHT CHECKS")
    if not verify_database_connection():
        log("❌ Pre-flight failed: Database connection", "ERROR")
        return False
    
    # Baseline metrics
    baseline = get_baseline_metrics()
    execution_log.append("baseline_collection")
    
    # Priority execution sequence
    priorities = [
        ("brevard_b_reconciliation", priority_1_brevard_b_reconciliation),
        ("j_generator", priority_2_j_generator),
        ("cd_parity_fixes", priority_3_cd_parity_fixes)
    ]
    
    for priority_name, priority_func in priorities:
        success = priority_func()
        execution_log.append(f"{priority_name}:{'success' if success else 'failed'}")
        
        if not success:
            log(f"⚠️ Priority {priority_name} failed, continuing with session")
        
        # Brief pause between priorities
        time.sleep(5)
    
    # Post-improvement verification
    final = run_verification_protocol()
    execution_log.append("final_verification")
    
    # Calculate and report improvements
    improvements = calculate_improvements(baseline, final)
    report = generate_session_report(baseline, final, improvements, execution_log)
    
    # Save report
    with open(f"shard2_session_report_{DISPATCH_ID[:8]}.json", "w") as f:
        json.dump(report, f, indent=2)
    
    log(f"📄 Session report saved: shard2_session_report_{DISPATCH_ID[:8]}.json")
    
    return report['summary']['total_point_gain'] > 0

def verify_only_mode():
    """Run verification only (no improvements)"""
    log_session_banner()
    log("🔍 VERIFICATION-ONLY MODE")
    
    baseline = get_baseline_metrics()
    
    log("📊 CURRENT METRICS:")
    for county, result in baseline.items():
        if result:
            pass_count = 0
            if isinstance(result, list):
                pass_count = sum(1 for row in result if isinstance(row, dict) and row.get('pass'))
            log(f"   {county.upper()}: {pass_count}/10 PASS")
        else:
            log(f"   {county.upper()}: UNAVAILABLE")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="SHARD-2 Master Coordinator")
    parser.add_argument("--execute", action="store_true", help="Execute full autonomous session")
    parser.add_argument("--verify-only", action="store_true", help="Run verification only")
    
    args = parser.parse_args()
    
    try:
        if args.verify_only:
            verify_only_mode()
        elif args.execute:
            success = execute_autonomous_session()
            sys.exit(0 if success else 1)
        else:
            log("🎯 SHARD-2 Master Coordinator ready")
            log("Usage: --execute (full session) or --verify-only (metrics only)")
            
    except KeyboardInterrupt:
        log("⚠️ Session interrupted by user")
        sys.exit(130)
    except Exception as e:
        log(f"❌ Unexpected error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()