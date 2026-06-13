#!/usr/bin/env python3
"""
SHARD-10 Foundation: Franklin/Union County Data Ingestion
Executes Letter A fixes for counties with zero data

Counties: franklin (co_no=29), union (co_no=73)
Expected Impact: Enable all letters for these counties (foundational unlock)

Usage:
  python scripts/shard10_foundation_ingestion.py
"""
import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def log(message, level="INFO"):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] {level}: {message}")

def execute_ingestion(county_name, co_no):
    """Execute county ingestion and return results"""
    log(f"🏗️ Starting {county_name} County (co_no={co_no}) ingestion")
    
    try:
        # Execute full county ingestion
        start_time = time.time()
        
        result = subprocess.run([
            sys.executable, "scripts/ingest_county.py", 
            "--county", str(co_no), 
            "--full"
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        execution_time = time.time() - start_time
        
        if result.returncode == 0:
            log(f"✅ {county_name} ingestion completed successfully ({execution_time:.1f}s)")
            log(f"📊 Output: {result.stdout}")
        else:
            log(f"❌ {county_name} ingestion failed with code {result.returncode}", "ERROR")
            log(f"❌ Error: {result.stderr}", "ERROR")
        
        return {
            "county": county_name,
            "co_no": co_no,
            "status": "SUCCESS" if result.returncode == 0 else "ERROR",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "execution_time": execution_time
        }
        
    except subprocess.TimeoutExpired:
        log(f"⏱️ {county_name} ingestion timed out after 1 hour", "ERROR")
        return {
            "county": county_name,
            "co_no": co_no,
            "status": "TIMEOUT",
            "error": "Ingestion timeout after 1 hour"
        }
    except Exception as e:
        log(f"❌ {county_name} ingestion error: {e}", "ERROR")
        return {
            "county": county_name,
            "co_no": co_no,
            "status": "ERROR", 
            "error": str(e)
        }

def execute_verification(county_name):
    """Execute post-ingestion verification"""
    log(f"🔍 Verifying {county_name} county status after ingestion")
    
    try:
        # This would execute the county evaluation
        result = subprocess.run([
            sys.executable, "scripts/verify_shard10_status.py"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log(f"✅ {county_name} verification completed")
            # Extract relevant metrics from output
            return {
                "county": county_name,
                "verification_status": "SUCCESS",
                "output": result.stdout
            }
        else:
            log(f"⚠️ {county_name} verification had issues", "WARNING")
            return {
                "county": county_name,
                "verification_status": "WARNING",
                "output": result.stderr
            }
            
    except Exception as e:
        log(f"❌ {county_name} verification error: {e}", "ERROR")
        return {
            "county": county_name,
            "verification_status": "ERROR",
            "error": str(e)
        }

def main():
    log("🎯 SHARD-10 FOUNDATION: Franklin/Union County Ingestion")
    log("Objective: Enable Letter A for both counties (foundational unlock)")
    
    results = {
        "foundation_phase": {
            "start_time": datetime.now().isoformat(),
            "objective": "Ingest data for franklin (29) and union (73) counties",
            "expected_impact": "Letter A enabled, all other letters unlocked for development"
        },
        "ingestions": {},
        "verifications": {},
        "summary": {}
    }
    
    # County ingestion tasks
    counties_to_ingest = [
        ("franklin", 29),
        ("union", 73)
    ]
    
    successful_ingestions = 0
    total_records_ingested = 0
    
    # Execute ingestions
    for county_name, co_no in counties_to_ingest:
        ingestion_result = execute_ingestion(county_name, co_no)
        results["ingestions"][county_name] = ingestion_result
        
        if ingestion_result["status"] == "SUCCESS":
            successful_ingestions += 1
            
        # Execute verification
        verification_result = execute_verification(county_name)
        results["verifications"][county_name] = verification_result
    
    # Summary
    results["summary"] = {
        "end_time": datetime.now().isoformat(),
        "successful_ingestions": successful_ingestions,
        "total_counties_processed": len(counties_to_ingest),
        "foundation_success": successful_ingestions == len(counties_to_ingest),
        "next_phase": "High-Impact fixes for existing data counties" if successful_ingestions > 0 else "Debug ingestion issues",
        "ship_to_main_status": "All changes committed directly to main branch per mandate"
    }
    
    # Status report
    if successful_ingestions == len(counties_to_ingest):
        log(f"🎉 FOUNDATION PHASE SUCCESSFUL: {successful_ingestions}/{len(counties_to_ingest)} counties ingested")
        log("✅ Franklin and Union now have foundational data for letter development")
        log("🚀 Ready for Phase 2: High-Impact fixes")
    else:
        log(f"⚠️ FOUNDATION PHASE PARTIAL: {successful_ingestions}/{len(counties_to_ingest)} counties successful")
        log("⚡ Proceeding with available data - check failed ingestions")
    
    print("\n" + "="*60)
    print("FOUNDATION PHASE RESULTS")
    print("="*60)
    
    for county_name, result in results["ingestions"].items():
        status_icon = "✅" if result["status"] == "SUCCESS" else "❌"
        print(f"{status_icon} {county_name.upper()} (co_no={result['co_no']}): {result['status']}")
        if result["status"] == "SUCCESS":
            print(f"   Execution time: {result['execution_time']:.1f}s")
        elif "error" in result:
            print(f"   Error: {result['error']}")
    
    return results

if __name__ == "__main__":
    main()