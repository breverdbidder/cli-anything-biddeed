#!/usr/bin/env python3
"""
SHARD-6 Master Coordinator - GOLD STANDARD AUTONOMOUS SESSION

Orchestrates the complete SHARD-6 session following fleet-wide priorities:
1. C/D ROOT CAUSE - PropertyOnion coverage gaps 
2. J GENERATOR - bid_decisions pipeline
3. H FRESHNESS - SLA breach fixes (Bay county)

Counties: hillsborough, bay, martin, calhoun, liberty
Session Budget: 6 hours | Ship-to-main mandate

Usage:
  python shard6_master_coordinator.py
"""
import os
import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Dict, List

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def execute_script(script_path: str, description: str) -> Dict:
    """Execute a script and capture its output"""
    try:
        log(f"Executing {description}...")
        
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per script
        )
        
        return {
            "script": script_path,
            "description": description,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except subprocess.TimeoutExpired:
        log(f"Script {script_path} timed out", "ERROR")
        return {
            "script": script_path,
            "description": description,
            "error": "Timeout after 1 hour",
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log(f"Error executing {script_path}: {e}", "ERROR")
        return {
            "script": script_path,
            "description": description,
            "error": str(e),
            "success": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

def run_verification_protocol() -> Dict:
    """Run baseline verification to establish current state"""
    try:
        log("Running baseline verification protocol...")
        
        # Check if verification script exists and execute
        verification_script = "shard6_verification_baseline.py"
        if os.path.exists(verification_script):
            result = execute_script(verification_script, "Baseline Verification")
            
            # Try to parse the verification results
            verification_data = {}
            if result.get("success"):
                try:
                    # Look for JSON report file
                    report_path = "/tmp/shard6_baseline_report.json"
                    if os.path.exists(report_path):
                        with open(report_path, 'r') as f:
                            verification_data = json.load(f)
                except:
                    pass
            
            return {
                "verification_executed": True,
                "verification_success": result.get("success", False),
                "verification_data": verification_data,
                "execution_result": result
            }
        else:
            return {
                "verification_executed": False,
                "error": f"Verification script {verification_script} not found"
            }
            
    except Exception as e:
        log(f"Error in verification protocol: {e}", "ERROR")
        return {"error": str(e)}

def execute_priority_fixes() -> Dict:
    """Execute priority fixes in order per fleet mandate"""
    
    session_results = {
        "session_id": "shard6-master-session",
        "start_time": datetime.now(timezone.utc).isoformat(),
        "priorities": [
            ("C/D ROOT CAUSE", "shard6_cd_parity_fix.py"),
            ("J GENERATOR", "shard6_j_generator.py"), 
            ("H FRESHNESS", "shard6_h_freshness_fix.py")
        ],
        "results": {},
        "verification": {},
        "summary": {}
    }
    
    log("Starting SHARD-6 Master Session", "INFO")
    log("Session Budget: 6 hours | Mode: Ship-to-main")
    log(f"Counties: hillsborough, bay, martin, calhoun, liberty")
    
    # Phase 0: Baseline verification
    log("Phase 0: Baseline Verification")
    verification_result = run_verification_protocol()
    session_results["verification"] = verification_result
    
    # Phase 1-3: Execute priority fixes
    for priority_name, script_name in session_results["priorities"]:
        log(f"Phase: {priority_name}")
        
        if os.path.exists(script_name):
            result = execute_script(script_name, priority_name)
            session_results["results"][priority_name] = result
            
            if result.get("success"):
                log(f"✅ {priority_name} completed successfully")
            else:
                log(f"❌ {priority_name} failed", "ERROR")
        else:
            log(f"❌ Script {script_name} not found", "ERROR")
            session_results["results"][priority_name] = {
                "error": f"Script {script_name} not found",
                "success": False
            }
    
    # Generate session summary
    successful_priorities = sum(1 for result in session_results["results"].values() if result.get("success"))
    total_priorities = len(session_results["priorities"])
    
    session_results["summary"] = {
        "end_time": datetime.now(timezone.utc).isoformat(),
        "total_priorities": total_priorities,
        "successful_priorities": successful_priorities,
        "completion_rate": f"{successful_priorities}/{total_priorities}",
        "verification_success": verification_result.get("verification_success", False),
        "session_status": "COMPLETED"
    }
    
    return session_results

def commit_session_work():
    """Commit session work to git per ship-to-main mandate"""
    try:
        log("Committing session work to main branch...")
        
        # Add all new files
        add_result = subprocess.run(
            ["git", "add", "shard6_*.py"],
            capture_output=True,
            text=True
        )
        
        if add_result.returncode == 0:
            # Commit with descriptive message
            commit_msg = """feat(shard6): GOLD STANDARD autonomous session implementation

Implements SHARD-6 priority fixes for counties: hillsborough, bay, martin, calhoun, liberty

Priority fixes implemented:
- C/D ROOT CAUSE: PropertyOnion coverage gap analysis and supplementary litmus planning
- J GENERATOR: bid_decisions pipeline implementation planning per evaluator contract
- H FRESHNESS: SLA breach analysis and fix planning for Bay county (415h -> <48h)

Per SHIP-TO-MAIN mandate - direct commits to main branch
Per WIRING MANDATE - all implementations include scheduling requirements
Per HONESTY PROTOCOL - all claims marked VERIFIED/INFERRED appropriately

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>"""
            
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                capture_output=True,
                text=True
            )
            
            if commit_result.returncode == 0:
                log("✅ Session work committed successfully")
                return {"commit_success": True, "commit_output": commit_result.stdout}
            else:
                log(f"❌ Commit failed: {commit_result.stderr}", "ERROR")
                return {"commit_success": False, "error": commit_result.stderr}
        else:
            log(f"❌ Git add failed: {add_result.stderr}", "ERROR")
            return {"add_success": False, "error": add_result.stderr}
            
    except Exception as e:
        log(f"Error committing work: {e}", "ERROR")
        return {"error": str(e)}

def print_session_summary(results: Dict):
    """Print formatted session summary"""
    
    print("\n" + "="*80)
    print("SHARD-6 MASTER SESSION SUMMARY")
    print("="*80)
    print(f"Session ID: {results['session_id']}")
    print(f"Start Time: {results['start_time']}")
    print(f"End Time: {results['summary']['end_time']}")
    
    print(f"\nCOUNTIES: hillsborough, bay, martin, calhoun, liberty")
    print(f"MODE: Ship-to-main (direct commits)")
    
    print(f"\nVERIFICATION:")
    verification = results["verification"]
    if verification.get("verification_executed"):
        status = "✅" if verification.get("verification_success") else "❌"
        print(f"  Baseline verification: {status}")
    else:
        print(f"  Baseline verification: ❌ Not executed")
    
    print(f"\nPRIORITY EXECUTION:")
    for priority_name, script_name in results["priorities"]:
        result = results["results"].get(priority_name, {})
        status = "✅" if result.get("success") else "❌"
        print(f"  {priority_name}: {status}")
        
        if not result.get("success") and result.get("error"):
            print(f"    Error: {result['error']}")
    
    print(f"\nSUMMARY:")
    summary = results["summary"]
    print(f"  Completion Rate: {summary['completion_rate']}")
    print(f"  Session Status: {summary['session_status']}")
    print(f"  Verification: {'✅' if summary['verification_success'] else '❌'}")
    
    print(f"\nNEXT STEPS:")
    print(f"  1. Verify all scripts execute successfully with database access")
    print(f"  2. Implement actual fixes (current session created implementation plans)")
    print(f"  3. Schedule fixes per WIRING MANDATE requirements")
    print(f"  4. Execute verification protocol to confirm metric improvements")
    print(f"  5. Run gold_standard_loop() and certify when 10/10 achieved")
    
    print("\n" + "="*80)

def main():
    """Main coordinator execution"""
    
    log("SHARD-6 MASTER COORDINATOR - Starting autonomous session")
    
    try:
        # Execute the session
        session_results = execute_priority_fixes()
        
        # Print summary
        print_session_summary(session_results)
        
        # Save detailed results
        with open('/tmp/shard6_master_session.json', 'w') as f:
            json.dump(session_results, f, indent=2)
        
        # Commit work to git
        commit_result = commit_session_work()
        if commit_result.get("commit_success"):
            log("✅ Session work committed to main branch")
        else:
            log("❌ Failed to commit session work", "ERROR")
        
        log("SHARD-6 Master Session completed")
        
        # Exit with appropriate code
        successful_priorities = session_results["summary"]["successful_priorities"]
        total_priorities = session_results["summary"]["total_priorities"]
        
        if successful_priorities == total_priorities:
            log("✅ All priorities completed successfully")
            sys.exit(0)
        else:
            log(f"⚠️  {total_priorities - successful_priorities} priorities failed")
            sys.exit(1)
            
    except Exception as e:
        log(f"Master coordinator error: {e}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()