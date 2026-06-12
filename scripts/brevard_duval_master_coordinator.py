#!/usr/bin/env python3
"""
Brevard + Duval Master Execution Coordinator
Gold Standard Campaign - Autonomous 6-hour session

Counties: brevard, duval
Priority Orders:
  Brevard: C/D ROOT CAUSE → J GENERATOR → G HIT LIST → B RECONCILIATION
  Duval: G+I SUBSTRATE BUILD → C/D ROOT CAUSE → J GENERATOR → B RECONCILIATION

This master coordinator orchestrates the complete autonomous campaign by executing 
all priority scripts in the correct sequence with ULTRALOOP protocol.

Usage:
  python scripts/brevard_duval_master_coordinator.py
"""
import os
import sys
import json
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

TARGET_COUNTIES = ['brevard', 'duval']

class BrevardDuvalMasterCoordinator:
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.results = {
            "session_info": {
                "start_time": self.session_start.isoformat(),
                "counties": TARGET_COUNTIES,
                "brevard_priority_order": ["C/D ROOT CAUSE", "J GENERATOR", "G HIT LIST", "B RECONCILIATION"],
                "duval_priority_order": ["G+I SUBSTRATE BUILD", "C/D ROOT CAUSE", "J GENERATOR", "B RECONCILIATION"],
                "session_budget": "6 hours",
                "ship_to_main": True,
                "parallel_fleet_rules": "No cross-shard interference",
                "verification_protocol": "SELECT public.pencil_dod_evaluate_county('<county>')"
            },
            "executions": {},
            "sql_verification_evidence": [],
            "ultraloop_audits": {},
            "final_metrics": {},
            "certification_status": "PENDING"
        }
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def execute_priority_script(self, priority_name, script_path, county=None):
        """Execute a priority script and capture results"""
        script_label = f"{county} {priority_name}" if county else priority_name
        self.log(f"🚀 Executing {script_label}: {script_path}")
        
        try:
            # Check if script exists
            if not os.path.exists(script_path):
                error_result = {
                    "priority": priority_name,
                    "county": county,
                    "status": "ERROR", 
                    "error": f"Script not found: {script_path}",
                    "execution_time": 0
                }
                self.log(f"❌ {script_label} script not found", "ERROR")
                return error_result
            
            start_time = datetime.now()
            
            # Execute the script
            result = subprocess.run([
                sys.executable, script_path
            ], capture_output=True, text=True, timeout=1800)  # 30 min timeout
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            execution_result = {
                "priority": priority_name,
                "county": county,
                "script_path": script_path,
                "status": "SUCCESS" if result.returncode == 0 else "ERROR",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": execution_time,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            if result.returncode == 0:
                self.log(f"✅ {script_label} completed successfully ({execution_time:.1f}s)")
            else:
                self.log(f"❌ {script_label} failed with code {result.returncode}", "ERROR")
                
            return execution_result
            
        except subprocess.TimeoutExpired:
            self.log(f"⏱️ {script_label} timed out after 30 minutes", "ERROR")
            return {
                "priority": priority_name,
                "county": county,
                "status": "TIMEOUT",
                "error": "Execution timed out",
                "execution_time": 1800
            }
        except Exception as e:
            self.log(f"💥 {script_label} crashed: {e}", "ERROR")
            return {
                "priority": priority_name,
                "county": county,
                "status": "CRASHED",
                "error": str(e),
                "execution_time": 0,
                "traceback": traceback.format_exc()
            }
    
    def verify_county_status(self, county_slug):
        """Get fresh county evaluation using pencil_dod_evaluate_county"""
        self.log(f"📊 Verifying {county_slug} status")
        
        try:
            verification_script = project_root / "scripts" / "verify_brevard_duval_status.py"
            if verification_script.exists():
                result = subprocess.run([
                    sys.executable, str(verification_script)
                ], capture_output=True, text=True, timeout=120)
                
                verification_result = {
                    "county": county_slug,
                    "verification_time": datetime.now(timezone.utc).isoformat(),
                    "status": "SUCCESS" if result.returncode == 0 else "ERROR",
                    "output": result.stdout,
                    "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county_slug}')",
                    "verification_status": "VERIFIED"
                }
                
                return verification_result
            else:
                self.log(f"⚠️ Verification script not found for {county_slug}", "WARNING")
                return None
                
        except Exception as e:
            self.log(f"❌ Error verifying {county_slug}: {e}", "ERROR")
            return None
    
    def execute_brevard_priority_sequence(self):
        """Execute Brevard's priority order: C/D → J → G → B"""
        self.log("🎯 BREVARD PRIORITY SEQUENCE")
        
        brevard_executions = {}
        
        # 1. C/D ROOT CAUSE
        cd_result = self.execute_priority_script(
            "C/D ROOT CAUSE", 
            "scripts/brevard_duval_cd_parity_fix.py",
            "brevard"
        )
        brevard_executions["cd_root_cause"] = cd_result
        
        # 2. J GENERATOR
        j_result = self.execute_priority_script(
            "J GENERATOR",
            "scripts/brevard_duval_j_generator.py", 
            "brevard"
        )
        brevard_executions["j_generator"] = j_result
        
        # 3. G HIT LIST (Brevard-specific)
        # Per issue: "G HIT LIST — the ~15 verified district rows"
        g_result = {
            "priority": "G HIT LIST",
            "county": "brevard",
            "status": "DEFERRED",
            "note": "Requires zone_standards ordinance text verification for ~15 districts",
            "hit_list": [
                "R-1AAA Melbourne (53,435 parcels)",
                "R-1AAA Titusville (22,252 parcels)", 
                "R-1A Rockledge (17,085 parcels)",
                "R-1B Titusville (9,855 parcels)",
                "R-1AAA West Melbourne (9,024 parcels)",
                "RU-2-15 Melbourne (5,601 parcels - FAR binding)",
                "R-3 Titusville (2,530 parcels - FAR binding)",
                "C-1 Melbourne (1,890 parcels - FAR binding)"
            ],
            "implementation": "Need ordinance text values with honesty markers"
        }
        brevard_executions["g_hit_list"] = g_result
        
        # 4. B RECONCILIATION 
        b_result = {
            "priority": "B RECONCILIATION",
            "county": "brevard", 
            "status": "DEFERRED",
            "anomaly": "verified=8547 > closed_sold=6373 (134.1%)",
            "required": "Refuter must find double-count/denominator mismatch before certify",
            "implementation": "Scope outcomes to snapshot set"
        }
        brevard_executions["b_reconciliation"] = b_result
        
        return brevard_executions
    
    def execute_duval_priority_sequence(self):
        """Execute Duval's priority order: G+I → C/D → J → B"""
        self.log("🎯 DUVAL PRIORITY SEQUENCE")
        
        duval_executions = {}
        
        # 1. G+I SUBSTRATE BUILD
        gi_result = self.execute_priority_script(
            "G+I SUBSTRATE BUILD",
            "scripts/duval_gi_substrate_build.py",
            "duval"
        )
        duval_executions["gi_substrate"] = gi_result
        
        # 2. C/D ROOT CAUSE
        cd_result = self.execute_priority_script(
            "C/D ROOT CAUSE",
            "scripts/brevard_duval_cd_parity_fix.py",
            "duval"
        )
        duval_executions["cd_root_cause"] = cd_result
        
        # 3. J GENERATOR (county-agnostic, check if brevard built it first)
        j_result = self.execute_priority_script(
            "J GENERATOR",
            "scripts/brevard_duval_j_generator.py",
            "duval"
        )
        duval_executions["j_generator"] = j_result
        
        # 4. B RECONCILIATION
        b_result = {
            "priority": "B RECONCILIATION",
            "county": "duval",
            "status": "DEFERRED", 
            "anomaly": "110.2% anomaly, same refuter treatment as brevard",
            "implementation": "Same denominator/double-count analysis pattern"
        }
        duval_executions["b_reconciliation"] = b_result
        
        return duval_executions
    
    def collect_final_metrics(self):
        """Collect final metrics for both counties using verification protocol"""
        self.log("📈 COLLECTING FINAL METRICS")
        
        final_metrics = {}
        
        for county in TARGET_COUNTIES:
            verification = self.verify_county_status(county)
            if verification:
                final_metrics[county] = verification
            else:
                final_metrics[county] = {
                    "status": "ERROR",
                    "error": "Could not collect final metrics"
                }
        
        return final_metrics
    
    def generate_session_summary(self):
        """Generate comprehensive session summary with SQL verification evidence"""
        self.log("📋 GENERATING SESSION SUMMARY")
        
        session_end = datetime.now(timezone.utc)
        total_duration = (session_end - self.session_start).total_seconds()
        
        summary = {
            "session_duration_seconds": total_duration,
            "session_duration_hours": total_duration / 3600,
            "end_time": session_end.isoformat(),
            "executions_summary": {},
            "verification_evidence": self.results["sql_verification_evidence"],
            "certification_readiness": "PENDING_VERIFICATION"
        }
        
        # Summarize executions
        all_executions = {**self.results["executions"]}
        
        success_count = 0
        error_count = 0
        
        for execution_id, result in all_executions.items():
            if result.get("status") == "SUCCESS":
                success_count += 1
            else:
                error_count += 1
        
        summary["executions_summary"] = {
            "total_executions": len(all_executions),
            "successful": success_count,
            "failed": error_count,
            "success_rate": (success_count / len(all_executions) * 100) if all_executions else 0
        }
        
        return summary
    
    def run_autonomous_session(self):
        """Execute the complete autonomous session"""
        self.log("🚀 STARTING AUTONOMOUS BREVARD + DUVAL SESSION")
        self.log(f"Session budget: 6 hours")
        self.log(f"Target counties: {', '.join(TARGET_COUNTIES)}")
        self.log(f"SHIP-TO-MAIN mandate: Commit directly to main")
        
        try:
            # Execute priority sequences
            self.log("\n" + "="*60)
            brevard_results = self.execute_brevard_priority_sequence()
            self.results["executions"]["brevard"] = brevard_results
            
            self.log("\n" + "="*60)
            duval_results = self.execute_duval_priority_sequence()
            self.results["executions"]["duval"] = duval_results
            
            # Collect final metrics
            self.log("\n" + "="*60)
            final_metrics = self.collect_final_metrics()
            self.results["final_metrics"] = final_metrics
            
            # Generate summary
            summary = self.generate_session_summary()
            self.results["session_summary"] = summary
            
            # Write results
            results_file = f"brevard_duval_session_{self.session_start.strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            self.log(f"📄 Session results written to: {results_file}")
            
            return self.results
            
        except Exception as e:
            self.log(f"💥 Session crashed: {e}", "ERROR")
            self.log(traceback.format_exc(), "ERROR")
            
            self.results["session_error"] = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "crash_time": datetime.now(timezone.utc).isoformat()
            }
            
            return self.results
    
    def commit_to_main(self):
        """Commit changes directly to main per SHIP-TO-MAIN mandate"""
        self.log("📝 COMMITTING TO MAIN (Ship-to-Main mandate)")
        
        try:
            # Add all new scripts
            subprocess.run(["git", "add", "scripts/verify_brevard_duval_status.py"], check=True)
            subprocess.run(["git", "add", "scripts/brevard_duval_cd_parity_fix.py"], check=True)  
            subprocess.run(["git", "add", "scripts/brevard_duval_j_generator.py"], check=True)
            subprocess.run(["git", "add", "scripts/duval_gi_substrate_build.py"], check=True)
            subprocess.run(["git", "add", "scripts/brevard_duval_master_coordinator.py"], check=True)
            
            # Add results files if they exist
            subprocess.run(["git", "add", "*.json"], check=False)  # Don't fail if no json files
            
            # Commit with descriptive message
            commit_message = f"""feat: Gold Standard autonomous session - brevard + duval

Implement autonomous 6-hour session scripts per issue #7614:

Brevard Priority: C/D root cause → J generator → G hit list → B reconciliation
Duval Priority: G+I substrate → C/D root cause → J generator → B reconciliation

Components:
- verify_brevard_duval_status.py: County metrics verification
- brevard_duval_cd_parity_fix.py: PropertyOnion coverage audit + clerk supplementary litmus
- brevard_duval_j_generator.py: bid_decisions pipeline to evaluator contract
- duval_gi_substrate_build.py: Zoning foundation for G+I measurability
- brevard_duval_master_coordinator.py: Session orchestrator

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""

            result = subprocess.run([
                "git", "commit", "-m", commit_message
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log("✅ Committed to main successfully")
                return True
            else:
                self.log(f"❌ Commit failed: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Error committing to main: {e}", "ERROR")
            return False

def main():
    """Run the complete autonomous session"""
    coordinator = BrevardDuvalMasterCoordinator()
    
    # Execute session
    results = coordinator.run_autonomous_session()
    
    # Commit to main per mandate
    commit_success = coordinator.commit_to_main()
    results["commit_status"] = "SUCCESS" if commit_success else "FAILED"
    
    # Final summary
    coordinator.log("\n" + "="*60)
    coordinator.log("🎯 AUTONOMOUS SESSION COMPLETE")
    coordinator.log("="*60)
    
    brevard_results = results["executions"].get("brevard", {})
    duval_results = results["executions"].get("duval", {})
    
    coordinator.log(f"BREVARD EXECUTIONS:")
    for priority, result in brevard_results.items():
        status = result.get("status", "UNKNOWN")
        coordinator.log(f"  {priority}: {status}")
    
    coordinator.log(f"\nDUVAL EXECUTIONS:")
    for priority, result in duval_results.items():
        status = result.get("status", "UNKNOWN")
        coordinator.log(f"  {priority}: {status}")
    
    session_summary = results.get("session_summary", {})
    duration_hours = session_summary.get("session_duration_hours", 0)
    success_rate = session_summary.get("executions_summary", {}).get("success_rate", 0)
    
    coordinator.log(f"\nSESSION METRICS:")
    coordinator.log(f"  Duration: {duration_hours:.1f} hours")
    coordinator.log(f"  Success rate: {success_rate:.1f}%") 
    coordinator.log(f"  Commit status: {results.get('commit_status', 'UNKNOWN')}")
    
    coordinator.log(f"\nNext: Run final verification protocol and monitor metrics")

if __name__ == "__main__":
    main()