#!/usr/bin/env python3
"""
SHARD-10 Master Execution Coordinator
Gold Standard Campaign - Autonomous 6-hour session

Counties: leon, bay, okeechobee, franklin, union
Priority: Foundation → High-Impact → Infrastructure

This master coordinator orchestrates the complete SHARD-10 autonomous campaign
by executing all priority scripts in the correct sequence.

Usage:
  python scripts/shard10_master_coordinator.py
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

SHARD10_COUNTIES = ['leon', 'bay', 'okeechobee', 'franklin', 'union']
COUNTY_NUMBERS = {
    'leon': 47,
    'bay': 13, 
    'okeechobee': 57,
    'franklin': 29,
    'union': 73
}

class SHARD10MasterCoordinator:
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.results = {
            "session_info": {
                "start_time": self.session_start.isoformat(),
                "shard": "SHARD-10",
                "counties": SHARD10_COUNTIES,
                "county_numbers": COUNTY_NUMBERS,
                "priority_phases": [
                    "Phase 1: Foundation (Franklin/Union data ingestion)",
                    "Phase 2: High-Impact (Bay E-linkage, J Generator, C/D Parity)",  
                    "Phase 3: Infrastructure (B Outcomes, Leon E-linkage)"
                ],
                "session_budget": "6 hours",
                "ship_to_main": True
            },
            "phase_executions": {},
            "sql_verification_evidence": [],
            "county_metrics_before": {},
            "county_metrics_after": {},
            "certification_status": "PENDING"
        }
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def execute_script(self, phase_name, script_path, timeout=1800):
        """Execute a script and capture results"""
        self.log(f"🚀 Executing {phase_name}: {script_path}")
        
        try:
            # Check if script exists
            if not os.path.exists(script_path):
                error_result = {
                    "phase": phase_name,
                    "status": "ERROR", 
                    "error": f"Script not found: {script_path}",
                    "execution_time": 0
                }
                self.log(f"❌ {phase_name} script not found", "ERROR")
                return error_result
            
            start_time = datetime.now()
            
            # Execute the script
            result = subprocess.run([
                sys.executable, script_path
            ], capture_output=True, text=True, timeout=timeout)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            execution_result = {
                "phase": phase_name,
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
                self.log(f"✅ {phase_name} completed successfully ({execution_time:.1f}s)")
            else:
                self.log(f"❌ {phase_name} failed with code {result.returncode}", "ERROR")
                
            return execution_result
            
        except subprocess.TimeoutExpired:
            self.log(f"⏱️ {phase_name} timed out after {timeout}s", "ERROR")
            return {
                "phase": phase_name,
                "status": "TIMEOUT",
                "error": f"Execution timeout after {timeout}s",
                "execution_time": timeout
            }
        except Exception as e:
            self.log(f"❌ {phase_name} execution error: {e}", "ERROR")
            return {
                "phase": phase_name,
                "status": "ERROR",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": 0
            }
    
    def execute_county_verification(self, county):
        """Execute verification for a specific county"""
        self.log(f"🔍 Verifying {county} county metrics")
        
        # This would be the verification call - framework for future implementation
        verification_result = {
            "county": county,
            "co_no": COUNTY_NUMBERS.get(county),
            "verification_approach": "pencil_dod_evaluate_county SQL function",
            "status": "FRAMEWORK_READY",
            "requires": "Database connection with SUPABASE_SERVICE_KEY"
        }
        
        return verification_result
    
    def execute_phase_1_foundation(self):
        """Phase 1: Foundation - Ingest franklin and union county data"""
        self.log("🏗️ PHASE 1: FOUNDATION - Franklin/Union Data Ingestion")
        
        phase_results = {
            "phase": "Phase 1: Foundation",
            "description": "Ingest data for franklin (co_no=29) and union (co_no=73)",
            "expected_impact": "Enable letter A for both counties, unlock all other letters",
            "executions": {}
        }
        
        # Franklin county ingestion
        franklin_result = self.execute_script(
            "Franklin County Ingestion",
            "scripts/ingest_county.py --county 29 --full",
            timeout=2400  # 40 minutes for full ingestion
        )
        phase_results["executions"]["franklin_ingestion"] = franklin_result
        
        # Union county ingestion  
        union_result = self.execute_script(
            "Union County Ingestion", 
            "scripts/ingest_county.py --county 73 --full",
            timeout=2400  # 40 minutes for full ingestion
        )
        phase_results["executions"]["union_ingestion"] = union_result
        
        # Verification
        franklin_verify = self.execute_county_verification("franklin")
        union_verify = self.execute_county_verification("union")
        
        phase_results["verifications"] = {
            "franklin": franklin_verify,
            "union": union_verify
        }
        
        return phase_results
    
    def execute_phase_2_high_impact(self):
        """Phase 2: High-Impact fixes for existing data counties"""
        self.log("⚡ PHASE 2: HIGH-IMPACT - Bay E-linkage, J Generator, C/D Parity")
        
        phase_results = {
            "phase": "Phase 2: High-Impact", 
            "description": "Address highest-leverage failing letters",
            "expected_impact": "Bay 1→4+ letters, J pipeline all 5 counties, C/D parity improvements",
            "executions": {}
        }
        
        # Bay E-linkage improvement (close to passing at 81.3%)
        bay_linkage_result = self.execute_script(
            "Bay E-linkage Improvement",
            "scripts/shard10_bay_parcel_linkage.py",  # To be created
            timeout=1800
        )
        phase_results["executions"]["bay_e_linkage"] = bay_linkage_result
        
        # J Generator - bid_decisions pipeline (fleet-wide)
        j_generator_result = self.execute_script(
            "J Generator Pipeline",
            "scripts/shard10_j_generator.py",  # To be created
            timeout=2400
        )
        phase_results["executions"]["j_generator"] = j_generator_result
        
        # C/D Parity improvements
        parity_result = self.execute_script(
            "C/D Parity Fixes",
            "scripts/shard10_cd_parity_fix.py",  # To be created
            timeout=1800
        )
        phase_results["executions"]["cd_parity"] = parity_result
        
        return phase_results
    
    def execute_phase_3_infrastructure(self):
        """Phase 3: Infrastructure - B outcomes, Leon E-linkage"""
        self.log("🏗️ PHASE 3: INFRASTRUCTURE - B Outcomes, Leon E-linkage")
        
        phase_results = {
            "phase": "Phase 3: Infrastructure",
            "description": "Build verified outcomes and address major linkage gaps", 
            "expected_impact": "B letter improvements, Leon E from 6.7% to 85%+",
            "executions": {}
        }
        
        # B Verified outcomes
        b_outcomes_result = self.execute_script(
            "B Verified Outcomes",
            "scripts/shard10_b_reconciliation.py",  # To be created
            timeout=2400
        )
        phase_results["executions"]["b_outcomes"] = b_outcomes_result
        
        # Leon E-linkage major improvement
        leon_linkage_result = self.execute_script(
            "Leon E-linkage Major Improvement", 
            "scripts/shard10_leon_parcel_linkage.py",  # To be created
            timeout=2400
        )
        phase_results["executions"]["leon_e_linkage"] = leon_linkage_result
        
        return phase_results
    
    def execute_final_verification(self):
        """Execute final verification across all counties"""
        self.log("🔍 FINAL VERIFICATION - All Counties")
        
        final_verification = {
            "verification_start": datetime.now(timezone.utc).isoformat(),
            "approach": "pencil_dod_evaluate_county for each county",
            "counties": {}
        }
        
        for county in SHARD10_COUNTIES:
            county_verification = self.execute_county_verification(county)
            final_verification["counties"][county] = county_verification
        
        return final_verification
    
    def execute_autonomous_session(self):
        """Execute the complete SHARD-10 autonomous session"""
        self.log("🎯 STARTING SHARD-10 AUTONOMOUS GOLD STANDARD SESSION")
        self.log(f"Counties: {', '.join(SHARD10_COUNTIES)}")
        self.log(f"Session budget: 6 hours")
        
        try:
            # Phase 1: Foundation
            phase1_result = self.execute_phase_1_foundation()
            self.results["phase_executions"]["phase_1"] = phase1_result
            
            # Phase 2: High-Impact 
            phase2_result = self.execute_phase_2_high_impact()
            self.results["phase_executions"]["phase_2"] = phase2_result
            
            # Phase 3: Infrastructure
            phase3_result = self.execute_phase_3_infrastructure()
            self.results["phase_executions"]["phase_3"] = phase3_result
            
            # Final verification
            final_verification = self.execute_final_verification()
            self.results["final_verification"] = final_verification
            
            # Calculate session summary
            session_end = datetime.now(timezone.utc)
            session_duration = (session_end - self.session_start).total_seconds()
            
            self.results["session_summary"] = {
                "end_time": session_end.isoformat(),
                "duration_seconds": session_duration,
                "duration_hours": session_duration / 3600,
                "phases_completed": len(self.results["phase_executions"]),
                "ship_to_main_mandate": "All changes committed directly to main branch",
                "verification_protocol": "SQL proof required for each letter improvement claim"
            }
            
            self.log(f"✅ SHARD-10 SESSION COMPLETED - Duration: {session_duration/3600:.1f} hours")
            
        except Exception as e:
            self.log(f"❌ SHARD-10 SESSION FAILED: {e}", "ERROR")
            self.results["session_error"] = {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return self.results

def main():
    coordinator = SHARD10MasterCoordinator()
    results = coordinator.execute_autonomous_session()
    
    # Output results
    print("\n" + "="*60)
    print("SHARD-10 SESSION RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    # Save results to file
    results_file = f"shard10_session_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to: {results_file}")

if __name__ == "__main__":
    main()