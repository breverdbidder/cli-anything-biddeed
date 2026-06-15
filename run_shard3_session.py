#!/usr/bin/env python3
"""
SHARD-3 Session Runner - Direct execution for autonomous session
Can be run locally or in GitHub Actions for immediate execution
"""

import os
import sys
import subprocess
import time
from datetime import datetime, timezone

def log(msg: str, level: str = "INFO"):
    """Timestamped logging"""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {level}: {msg}")

def check_environment():
    """Check required environment variables"""
    required_vars = ['SUPABASE_URL', 'SUPABASE_KEY']
    missing = [var for var in required_vars if not os.environ.get(var)]
    
    if missing:
        log(f"❌ Missing environment variables: {', '.join(missing)}", "ERROR")
        log("Set these before running:", "ERROR")
        for var in missing:
            log(f"  export {var}=<value>", "ERROR")
        return False
    
    log("✅ Environment variables confirmed")
    return True

def run_command(cmd: list, description: str):
    """Run a command and log output"""
    log(f"Running: {description}")
    log(f"Command: {' '.join(cmd)}")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=1800  # 30 min timeout per command
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            log(f"✅ {description} completed ({duration:.1f}s)")
            if result.stdout.strip():
                print("--- STDOUT ---")
                print(result.stdout)
                print("--- END STDOUT ---")
        else:
            log(f"❌ {description} failed ({duration:.1f}s)", "ERROR")
            if result.stderr.strip():
                print("--- STDERR ---")
                print(result.stderr)
                print("--- END STDERR ---")
            if result.stdout.strip():
                print("--- STDOUT ---")
                print(result.stdout)
                print("--- END STDOUT ---")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        log(f"❌ {description} timed out", "ERROR")
        return False
    except Exception as e:
        log(f"❌ {description} error: {e}", "ERROR")
        return False

def main():
    """Main execution"""
    log("🎯 SHARD-3 AUTONOMOUS SESSION RUNNER")
    log(f"Session start: {datetime.now(timezone.utc).isoformat()}")
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    session_id = f"shard3-{int(time.time())}"
    log(f"Session ID: {session_id}")
    
    # Step 1: Apply migration
    log("=== STEP 1: DATABASE MIGRATION ===")
    migration_success = run_command([
        'python3', '-c', '''
import httpx, os
with open("supabase/migrations/20260615_shard3_gold_standard_setup.sql", "r") as f:
    sql = f.read()
client = httpx.Client(timeout=60)
headers = {
    "apikey": os.environ["SUPABASE_KEY"],
    "Authorization": f"Bearer {os.environ[\\"SUPABASE_KEY\\"]}",
    "Content-Type": "application/json"
}
response = client.post(
    f"{os.environ[\\"SUPABASE_URL\\"]}/rest/v1/rpc/exec_sql",
    headers=headers,
    json={"query": sql}
)
print(f"Migration result: {response.status_code}")
if response.status_code != 200:
    print(f"Error: {response.text}")
    exit(1)
print("Migration applied successfully")
'''
    ], "Apply database migration")
    
    if not migration_success:
        log("❌ Migration failed - cannot proceed", "ERROR")
        sys.exit(1)
    
    # Step 2: Get baseline status
    log("=== STEP 2: BASELINE STATUS ===")
    baseline_success = run_command([
        'python3', 'scripts/shard3_gold_standard.py', 'status'
    ], "Get baseline county status")
    
    # Step 3: Run autonomous fixes
    log("=== STEP 3: AUTONOMOUS FIXES ===")
    fixes_success = run_command([
        'python3', 'scripts/shard3_autonomous_fixes.py'
    ], "Execute autonomous fixes")
    
    # Step 4: Verify improvements  
    log("=== STEP 4: VERIFICATION ===")
    verify_success = run_command([
        'python3', 'scripts/shard3_gold_standard.py', 'status'  
    ], "Verify improvements")
    
    # Summary
    log("=== SESSION SUMMARY ===")
    log(f"Session ID: {session_id}")
    log(f"Migration: {'✅' if migration_success else '❌'}")
    log(f"Baseline: {'✅' if baseline_success else '❌'}")
    log(f"Fixes: {'✅' if fixes_success else '❌'}")
    log(f"Verification: {'✅' if verify_success else '❌'}")
    
    overall_success = all([migration_success, fixes_success, verify_success])
    log(f"Overall: {'✅ SUCCESS' if overall_success else '❌ FAILED'}")
    log(f"Session end: {datetime.now(timezone.utc).isoformat()}")
    
    if overall_success:
        log("🎯 Shard-3 session completed successfully")
        log("Ready for ship-to-main per mandate")
    else:
        log("❌ Session failed - check logs above")
        sys.exit(1)

if __name__ == "__main__":
    main()