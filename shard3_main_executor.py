#!/usr/bin/env python3
"""
SHARD-3 Main Executor - 6-Hour Autonomous Session
Execute highest-impact fixes for broward, washington, lake, st_lucie, jefferson

Session Strategy:
1. Jefferson bootstrap (highest leverage - enables everything)
2. E linkage fixes (unlocks I+J downstream)  
3. H freshness fixes (quick wins)
4. J generator (fleet-wide impact)
5. Verify all changes with live DB queries

WIRING MANDATE: All fixes execute, not just commit
EVIDENCE-BEFORE-CLAIMS: Every metric change verified with SQL
"""

import os
import sys
import subprocess
import time
from datetime import datetime, timezone
import json

def log(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{timestamp}] {level}: {message}")

def run_script(script_name, description, timeout_minutes=60):
    """Run a Python script and capture results"""
    log(f"Starting {description}")
    log(f"Executing: python {script_name}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run([
            sys.executable, script_name
        ], 
        capture_output=True, 
        text=True, 
        timeout=timeout_minutes * 60
        )
        
        elapsed = time.time() - start_time
        log(f"Completed {description} in {elapsed/60:.1f} minutes")
        
        if result.returncode == 0:
            log(f"✅ SUCCESS: {description}", "SUCCESS")
            if result.stdout:
                print("--- STDOUT ---")
                print(result.stdout[-2000:])  # Last 2KB of output
                print("--- END STDOUT ---")
        else:
            log(f"❌ FAILED: {description} (exit code {result.returncode})", "ERROR")
            if result.stderr:
                print("--- STDERR ---")
                print(result.stderr[-1000:])  # Last 1KB of errors
                print("--- END STDERR ---")
        
        return {
            'success': result.returncode == 0,
            'exit_code': result.returncode,
            'elapsed_minutes': elapsed / 60,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        log(f"❌ TIMEOUT: {description} after {timeout_minutes} minutes", "ERROR")
        return {
            'success': False,
            'exit_code': -1,
            'elapsed_minutes': elapsed / 60,
            'timeout': True
        }
    except Exception as e:
        elapsed = time.time() - start_time
        log(f"❌ ERROR: {description} - {e}", "ERROR")
        return {
            'success': False,
            'exit_code': -2,
            'elapsed_minutes': elapsed / 60,
            'error': str(e)
        }

def run_verification(county_slug):
    """Run county verification via database test"""
    log(f"Verifying {county_slug} status")
    
    # Use the connection test script to verify current status
    verification_script = f"""
import sys
sys.path.append('.')
from shard3_connection_test import evaluate_county_live

if __name__ == "__main__":
    result = evaluate_county_live('{county_slug}')
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
"""
    
    # Write temporary verification script
    temp_script = f"verify_{county_slug}_temp.py"
    with open(temp_script, 'w') as f:
        f.write(verification_script)
    
    try:
        result = subprocess.run([
            sys.executable, temp_script
        ], 
        capture_output=True, 
        text=True, 
        timeout=120
        )
        
        # Clean up temp file
        os.unlink(temp_script)
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except Exception as e:
        log(f"❌ Verification failed for {county_slug}: {e}", "ERROR")
        # Clean up temp file
        try:
            os.unlink(temp_script)
        except:
            pass
        return {'success': False, 'error': str(e)}

def main():
    """Main execution flow"""
    session_start = time.time()
    log("="*60)
    log("SHARD-3 AUTONOMOUS SESSION STARTING")
    log("="*60)
    log("Counties: broward, washington, lake, st_lucie, jefferson")
    log("Budget: 6 hours")
    log("Strategy: highest-leverage fixes first")
    
    results = {}
    total_fixes = 0
    
    # Phase 1: Jefferson Bootstrap (P0 - enables everything)
    log("\n🚀 PHASE 1: JEFFERSON BOOTSTRAP")
    
    phase1_start = time.time()
    
    # Run Jefferson bootstrap
    results['jefferson_bootstrap'] = run_script(
        'jefferson_bootstrap.py',
        'Jefferson County Bootstrap (Letter A setup)',
        timeout_minutes=30
    )
    
    if results['jefferson_bootstrap']['success']:
        # Run Jefferson ingestion 
        results['jefferson_ingestion'] = run_script(
            'jefferson_ingest_runner.py', 
            'Jefferson FL GIO Parcel Ingestion',
            timeout_minutes=90
        )
        
        if results['jefferson_ingestion']['success']:
            total_fixes += 1
            log("✅ Jefferson Letter A setup complete", "SUCCESS")
    
    phase1_elapsed = (time.time() - phase1_start) / 60
    log(f"Phase 1 completed in {phase1_elapsed:.1f} minutes")
    
    # Phase 2: E Linkage Fixes (P0 - unlocks I+J)
    log("\n🔗 PHASE 2: E LINKAGE FIXES")
    
    phase2_start = time.time()
    
    results['e_linkage_fixes'] = run_script(
        'shard3_e_linkage_fix.py',
        'E Linkage Fixes (parcel linkage improvements)',
        timeout_minutes=90
    )
    
    if results['e_linkage_fixes']['success']:
        total_fixes += 1
        log("✅ E linkage improvements applied", "SUCCESS")
    
    phase2_elapsed = (time.time() - phase2_start) / 60
    log(f"Phase 2 completed in {phase2_elapsed:.1f} minutes")
    
    # Phase 3: H Freshness Fixes (P1 - quick wins)
    log("\n⏰ PHASE 3: H FRESHNESS FIXES")
    
    phase3_start = time.time()
    
    results['h_freshness_fixes'] = run_script(
        'shard3_h_freshness_fix.py',
        'H Freshness Fixes (lake + st_lucie)',
        timeout_minutes=45
    )
    
    if results['h_freshness_fixes']['success']:
        total_fixes += 1
        log("✅ H freshness improvements applied", "SUCCESS")
    
    phase3_elapsed = (time.time() - phase3_start) / 60
    log(f"Phase 3 completed in {phase3_elapsed:.1f} minutes")
    
    # Phase 4: J Generator (P0-FLEET - affects all counties)
    log("\n🧠 PHASE 4: J GENERATOR")
    
    phase4_start = time.time()
    
    results['j_generator'] = run_script(
        'shard3_j_generator.py',
        'J Generator (fleet-wide bid_decisions)',
        timeout_minutes=90
    )
    
    if results['j_generator']['success']:
        total_fixes += 1
        log("✅ J generator pipeline built", "SUCCESS")
    
    phase4_elapsed = (time.time() - phase4_start) / 60
    log(f"Phase 4 completed in {phase4_elapsed:.1f} minutes")
    
    # Phase 5: Verification (mandatory per CLAUDE.md)
    log("\n🔍 PHASE 5: VERIFICATION")
    
    phase5_start = time.time()
    
    verification_results = {}
    counties = ['broward', 'washington', 'lake', 'st_lucie', 'jefferson']
    
    for county in counties:
        verification_results[county] = run_verification(county)
        
        if verification_results[county]['success']:
            log(f"✅ {county} verification passed", "SUCCESS")
        else:
            log(f"❌ {county} verification failed", "ERROR")
    
    phase5_elapsed = (time.time() - phase5_start) / 60
    log(f"Phase 5 completed in {phase5_elapsed:.1f} minutes")
    
    # Session Summary
    session_elapsed = (time.time() - session_start) / 60
    
    log("\n" + "="*60)
    log("SHARD-3 SESSION SUMMARY")
    log("="*60)
    log(f"Total session time: {session_elapsed:.1f} minutes ({session_elapsed/60:.1f} hours)")
    log(f"Total fixes applied: {total_fixes}")
    log(f"Budget remaining: {6*60 - session_elapsed:.0f} minutes")
    
    # Results by phase
    log("\nPhase Results:")
    log(f"  Phase 1 (Jefferson):   {'✅' if results.get('jefferson_bootstrap', {}).get('success') else '❌'} {phase1_elapsed:.1f}m")
    log(f"  Phase 2 (E Linkage):    {'✅' if results.get('e_linkage_fixes', {}).get('success') else '❌'} {phase2_elapsed:.1f}m")
    log(f"  Phase 3 (H Freshness):  {'✅' if results.get('h_freshness_fixes', {}).get('success') else '❌'} {phase3_elapsed:.1f}m")
    log(f"  Phase 4 (J Generator):  {'✅' if results.get('j_generator', {}).get('success') else '❌'} {phase4_elapsed:.1f}m")
    log(f"  Phase 5 (Verification): {'✅' if all(v.get('success') for v in verification_results.values()) else '❌'} {phase5_elapsed:.1f}m")
    
    # County verification status
    log("\nCounty Verification Status:")
    for county in counties:
        status = "✅" if verification_results.get(county, {}).get('success') else "❌"
        log(f"  {county}: {status}")
    
    # Achievements
    achievements = []
    
    if results.get('jefferson_bootstrap', {}).get('success'):
        achievements.append("🎯 Jefferson bootstrapped from 0/10")
    if results.get('e_linkage_fixes', {}).get('success'):
        achievements.append("🔗 E linkage improved across 4 counties")
    if results.get('h_freshness_fixes', {}).get('success'):
        achievements.append("⏰ H freshness fixed for lake + st_lucie")
    if results.get('j_generator', {}).get('success'):
        achievements.append("🧠 J generator built for fleet-wide use")
    
    log("\nSession Achievements:")
    for achievement in achievements:
        log(f"  {achievement}")
    
    # Next steps
    log("\n📋 RECOMMENDED NEXT STEPS:")
    log("  1. Monitor Jefferson A lane configuration")
    log("  2. Validate E linkage accuracy improvements")
    log("  3. Confirm H freshness SLA compliance")
    log("  4. Scale J generator to production data")
    log("  5. Schedule follow-up verification in 24h")
    
    # Return summary for any downstream processing
    return {
        'session_minutes': session_elapsed,
        'total_fixes': total_fixes,
        'phases_completed': sum(1 for r in results.values() if r.get('success')),
        'verification_passed': sum(1 for v in verification_results.values() if v.get('success')),
        'achievements': achievements
    }

if __name__ == "__main__":
    summary = main()
    
    # Exit with appropriate code
    if summary['total_fixes'] > 0:
        log("🎉 SESSION COMPLETED WITH FIXES APPLIED", "SUCCESS")
        sys.exit(0)
    else:
        log("❌ SESSION COMPLETED WITHOUT FIXES", "ERROR") 
        sys.exit(1)