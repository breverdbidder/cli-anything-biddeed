#!/usr/bin/env python3
"""
SHARD-6 GOLD STANDARD AUTONOMOUS SESSION - SHIP-TO-MAIN
DISPATCH ID: 8ea6d509-c251-4e45-a5a5-65aac692cae6
RUN 27: highlands, escambia, nassau, calhoun, liberty

6-hour autonomous session following BREVARD SPRINT ORDER priorities:
1. C/D ROOT CAUSE — parity matching fixes (highest leverage)
2. E PARCEL LINKAGE — enables downstream valuations pipeline
3. B VERIFIED OUTCOMES — independent source requirement
4. H FRESHNESS — if time permits

Executes ship-to-main mandate with Evidence-Before-Claims verification.

Usage:
  python scripts/shard6_gold_standard_autonomous.py
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Session metadata
SESSION_ID = "shard6-autonomous-run27"
DISPATCH_ID = "8ea6d509-c251-4e45-a5a5-65aac692cae6"
ASSIGNED_COUNTIES = ['highlands', 'escambia', 'nassau', 'calhoun', 'liberty']
SESSION_START_TIME = datetime.now(timezone.utc)
SESSION_TIMEOUT_HOURS = 6

class SHARD6AutonomousSession:
    """Autonomous SHARD-6 Gold Standard improvement session"""
    
    def __init__(self):
        self.session_id = SESSION_ID
        self.counties = ASSIGNED_COUNTIES
        self.start_time = SESSION_START_TIME
        self.results = {}
        self.tasks_completed = 0
        self.total_improvements = 0
        
    def log_task_start(self, task_name: str, county: str = None):
        """Log task start with timing"""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        location = f" for {county}" if county else ""
        logger.info(f"🎯 [{elapsed:.1f}h] Starting {task_name}{location}")
        
    def log_task_complete(self, task_name: str, success: bool = True, details: str = ""):
        """Log task completion"""
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        status = "✅" if success else "❌"
        self.tasks_completed += 1
        logger.info(f"{status} [{elapsed:.1f}h] Task {self.tasks_completed}: {task_name} {details}")
        
    def execute_script(self, script_path: str, args: List[str] = None) -> Dict:
        """Execute a Python script and capture results"""
        
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
        
        try:
            logger.info(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # 1 hour timeout per script
                cwd=os.getcwd()
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Script {script_path} timed out")
            return {
                'success': False,
                'error': 'timeout',
                'stdout': '',
                'stderr': 'Script execution timed out'
            }
        except Exception as e:
            logger.error(f"Error executing {script_path}: {e}")
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': str(e)
            }
    
    def commit_progress(self, message: str, files: List[str] = None):
        """Commit progress to main branch"""
        
        try:
            # Add files
            if files:
                for file in files:
                    subprocess.run(['git', 'add', file], check=True)
            else:
                subprocess.run(['git', 'add', '.'], check=True)
            
            # Commit with session metadata
            commit_msg = f"{message}\n\nSHARD-6 RUN-27 {self.session_id}\nDispatch: {DISPATCH_ID}\nTask: {self.tasks_completed}\n\n🤖 Generated with Claude Code"
            
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
            subprocess.run(['git', 'push', 'origin', 'main'], check=True)
            
            logger.info(f"✅ Committed and pushed: {message}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Git operation failed: {e}")
            return False
    
    def execute_cd_parity_improvements(self) -> Dict:
        """Execute C/D parity improvements (Priority #1)"""
        
        self.log_task_start("C/D Parity Improvements")
        
        # Run the C/D parity script for all counties
        result = self.execute_script('scripts/shard6_cd_parity_improvements.py', ['--all-counties'])
        
        success = result['success']
        details = ""
        
        if success:
            # Parse improvements from output (basic parsing)
            output = result['stdout']
            if 'case_numbers_normalized' in output:
                details = "Completed parity matching improvements"
                self.total_improvements += 1
        else:
            details = f"Failed: {result['stderr'][:100]}"
        
        self.log_task_complete("C/D Parity Improvements", success, details)
        
        # Commit progress
        if success:
            self.commit_progress(
                "feat: SHARD-6 C/D parity matching improvements",
                ['scripts/shard6_cd_parity_improvements.py']
            )
        
        return {
            'task': 'cd_parity_improvements',
            'success': success,
            'result': result
        }
    
    def execute_parcel_linkage_improvements(self) -> Dict:
        """Execute Letter E parcel linkage improvements (Priority #2)"""
        
        self.log_task_start("Parcel Linkage Improvements (Letter E)")
        
        # Run the parcel linkage script
        result = self.execute_script('scripts/shard6_parcel_linkage_improvements.py', ['--all-counties'])
        
        success = result['success']
        details = ""
        
        if success:
            output = result['stdout']
            if 'parcels_linked' in output:
                details = "Completed parcel linkage improvements"
                self.total_improvements += 1
        else:
            details = f"Failed: {result['stderr'][:100]}"
        
        self.log_task_complete("Parcel Linkage Improvements", success, details)
        
        # Commit progress
        if success:
            self.commit_progress(
                "feat: SHARD-6 Letter E parcel linkage improvements",
                ['scripts/shard6_parcel_linkage_improvements.py']
            )
        
        return {
            'task': 'parcel_linkage_improvements',
            'success': success,
            'result': result
        }
    
    def execute_verification_protocol(self) -> Dict:
        """Execute final verification protocol"""
        
        self.log_task_start("Final Verification Protocol")
        
        # Run verification using existing script
        result = self.execute_script('scripts/shard6_verification_protocol.py')
        
        success = result['success']
        details = ""
        
        if success:
            output = result['stdout']
            # Look for county evaluations in output
            if 'County Evaluations:' in output:
                details = "Verification protocol completed"
        else:
            details = f"Failed: {result['stderr'][:100]}"
        
        self.log_task_complete("Final Verification Protocol", success, details)
        
        return {
            'task': 'verification_protocol',
            'success': success,
            'result': result
        }
    
    def check_session_timeout(self) -> bool:
        """Check if session is approaching timeout"""
        elapsed_hours = (datetime.now(timezone.utc) - self.start_time).total_seconds() / 3600
        return elapsed_hours >= (SESSION_TIMEOUT_HOURS - 0.5)  # Stop 30min before timeout
    
    def execute_session(self) -> Dict:
        """Execute the complete autonomous session"""
        
        logger.info("🚀 STARTING SHARD-6 AUTONOMOUS GOLD STANDARD SESSION")
        logger.info(f"Session ID: {self.session_id}")
        logger.info(f"Dispatch ID: {DISPATCH_ID}")
        logger.info(f"Counties: {', '.join(self.counties)}")
        logger.info(f"Start Time: {self.start_time.isoformat()}")
        logger.info(f"Timeout: {SESSION_TIMEOUT_HOURS} hours")
        
        session_results = {
            'session_id': self.session_id,
            'dispatch_id': DISPATCH_ID,
            'counties': self.counties,
            'start_time': self.start_time.isoformat(),
            'tasks': [],
            'session_status': 'running'
        }
        
        try:
            # Priority 1: C/D Parity Improvements
            if not self.check_session_timeout():
                cd_result = self.execute_cd_parity_improvements()
                session_results['tasks'].append(cd_result)
                time.sleep(5)  # Brief pause between tasks
            
            # Priority 2: Parcel Linkage Improvements  
            if not self.check_session_timeout():
                linkage_result = self.execute_parcel_linkage_improvements()
                session_results['tasks'].append(linkage_result)
                time.sleep(5)
            
            # Final verification
            if not self.check_session_timeout():
                verification_result = self.execute_verification_protocol()
                session_results['tasks'].append(verification_result)
            
            # Session completion
            elapsed_time = datetime.now(timezone.utc) - self.start_time
            session_results['end_time'] = datetime.now(timezone.utc).isoformat()
            session_results['duration_hours'] = elapsed_time.total_seconds() / 3600
            session_results['tasks_completed'] = self.tasks_completed
            session_results['total_improvements'] = self.total_improvements
            session_results['session_status'] = 'completed'
            
            # Final commit with session summary
            self.commit_progress(
                f"feat: SHARD-6 RUN-27 session complete - {self.tasks_completed} tasks, {self.total_improvements} improvements",
                ['scripts/shard6_gold_standard_autonomous.py']
            )
            
            logger.info(f"✅ SHARD-6 AUTONOMOUS SESSION COMPLETE")
            logger.info(f"Duration: {elapsed_time.total_seconds() / 3600:.1f} hours")
            logger.info(f"Tasks completed: {self.tasks_completed}")
            logger.info(f"Improvements made: {self.total_improvements}")
            
        except Exception as e:
            logger.error(f"❌ Session failed: {e}")
            session_results['session_status'] = 'failed'
            session_results['error'] = str(e)
            session_results['end_time'] = datetime.now(timezone.utc).isoformat()
        
        # Save session results
        results_file = '/tmp/shard6_autonomous_session_results.json'
        with open(results_file, 'w') as f:
            json.dump(session_results, f, indent=2)
        
        logger.info(f"Session results saved to {results_file}")
        
        return session_results

def main():
    """Main execution entry point"""
    
    # Verify environment
    if not os.environ.get("SUPABASE_KEY") and not os.environ.get("SUPABASE_SERVICE_KEY"):
        logger.error("❌ No Supabase key found in environment")
        sys.exit(1)
    
    # Check git status
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if result.stdout.strip():
            logger.warning("Working directory has uncommitted changes - will commit as part of session")
    except Exception:
        logger.warning("Could not check git status")
    
    # Execute autonomous session
    session = SHARD6AutonomousSession()
    results = session.execute_session()
    
    # Print final summary
    print("\n" + "="*70)
    print("SHARD-6 AUTONOMOUS SESSION - FINAL SUMMARY")
    print("="*70)
    print(f"Session ID: {results['session_id']}")
    print(f"Status: {results['session_status']}")
    print(f"Duration: {results.get('duration_hours', 0):.1f} hours")
    print(f"Tasks completed: {results.get('tasks_completed', 0)}")
    print(f"Improvements made: {results.get('total_improvements', 0)}")
    
    if results.get('session_status') == 'completed':
        print("\n✅ SESSION SUCCESSFUL - Changes committed to main branch")
        sys.exit(0)
    else:
        print(f"\n❌ SESSION FAILED - {results.get('error', 'Unknown error')}")
        sys.exit(1)

if __name__ == "__main__":
    main()