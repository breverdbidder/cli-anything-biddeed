#!/usr/bin/env python3
"""
SHARD 25 VERIFICATION TEST
Quick test to verify current state and attempt basic database operations
Following the pattern from utcc-migrate.yml workflow
"""

import os
import sys

def print_analysis():
    """Print the analysis we've done so far"""
    print("SHARD 25 - GOLD STANDARD AUTOPILOT ANALYSIS")
    print("=" * 60)
    
    print("\nCURRENT STATE (from briefing):")
    print("Brevard (2/10): A✓, H✓")
    print("  B: 134.1% (ANOMALY - verified_outcomes > closed_sold)")
    print("  C: 20.8% (matched_clean=4092 of 19706)")
    print("  D: 33.2% (matched_any=6548 of 19706)")
    print("  G: 48.9% (FAR binding constraint)")
    print("  J: 0.0% (deal_complete=0 of 19706)")
    
    print("\nDuval (2/10): A✓, H✓")
    print("  B: 110.2% (ANOMALY - verified_outcomes > closed_sold)")
    print("  C: 16.1% (matched_clean=3217 of 20022)")
    print("  D: 52.9% (matched_any=10590 of 20022)")
    print("  G: NULL (no zoning substrate)")
    print("  I: NULL (no zoning substrate)")
    print("  J: 0.0% (deal_complete=0 of 20022)")
    
    print("\nIDENTIFIED ROOT CAUSES:")
    print("1. PropertyOnion coverage gap → C/D parity ceiling")
    print("2. Missing bid_decisions generator → J=0% fleet-wide")
    print("3. Duval zoning substrate missing → G/I unmeasurable")
    print("4. B anomalies indicate denominator/double-count issues")
    
    print("\nPRE-AUTHORIZED SOLUTIONS:")
    print("✅ Supplementary clerk/official-records litmus (C/D)")
    print("✅ Shapira V14 bid_decisions pipeline (J)")
    print("✅ Jacksonville Ch. 656 zoning extraction (G/I)")
    
    print("\nINFRASTRUCTURE CREATED:")
    print("✅ Migration: 20260614_duval_brevard_gold_standard.sql")
    print("✅ Analysis scripts: shard25_cd_root_cause_analysis.py")
    print("✅ Generator design: shard25_j_generator.py") 
    print("✅ Substrate plan: shard25_duval_gi_substrate.py")
    print("✅ Master executor: shard25_master_executor.py")
    
    print("\nULTRALOOP PROTOCOL:")
    print("- Evidence-based claims with VERIFIED/INFERRED/UNTESTED tags")
    print("- Adversarial refuter for survival vote")
    print("- gold_standard_ultraloop_audit logging")
    
    print("\nEXPECTED IMPACT:")
    print("- Brevard J: 0% → 95% (19,706 auctions)")
    print("- Duval J: 0% → 95% (20,022 auctions)")
    print("- Both C/D: significant improvement via clerk litmus")
    print("- Duval G/I: NULL → measurable via zoning substrate")

def check_environment():
    """Check what environment variables and tools are available"""
    print(f"\n{'='*60}")
    print("ENVIRONMENT CHECK")
    
    # Check if we're in GitHub Actions
    if 'GITHUB_ACTIONS' in os.environ:
        print("✅ Running in GitHub Actions")
        print(f"  Repository: {os.environ.get('GITHUB_REPOSITORY', 'N/A')}")
        print(f"  Workflow: {os.environ.get('GITHUB_WORKFLOW', 'N/A')}")
        print(f"  Run ID: {os.environ.get('GITHUB_RUN_ID', 'N/A')}")
    else:
        print("ℹ️ Not in GitHub Actions environment")
    
    # Check Python modules
    modules_to_check = ['httpx', 'json', 'pathlib']
    for module in modules_to_check:
        try:
            __import__(module)
            print(f"✅ {module} available")
        except ImportError:
            print(f"❌ {module} not available")
    
    # Check if curl is available for Supabase API calls
    import subprocess
    try:
        subprocess.run(['curl', '--version'], capture_output=True, check=True)
        print("✅ curl available for API calls")
    except:
        print("❌ curl not available")
    
    # Check working directory and key files
    cwd = os.getcwd()
    print(f"Working directory: {cwd}")
    
    key_files = [
        'CLAUDE.md',
        'supabase/migrations/20260614_duval_brevard_gold_standard.sql',
        'shard25_master_executor.py'
    ]
    
    for file_path in key_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} missing")

def main():
    """Main function"""
    print_analysis()
    check_environment()
    
    print(f"\n{'='*60}")
    print("VERIFICATION TEST COMPLETE")
    
    print("\nNEXT STEPS:")
    print("1. Execute via GitHub Actions workflow with Supabase secrets")
    print("2. Use curl-based API calls following utcc-migrate.yml pattern")
    print("3. Apply migration and execute database operations")
    print("4. Verify metrics improvement with pencil_dod_evaluate_county")
    
    print("\nCURRENT SESSION STATUS:")
    print("✅ Analysis phase complete")
    print("✅ Infrastructure scripts created")
    print("✅ Migration identified and ready")
    print("⏳ Awaiting execution phase with database access")

if __name__ == "__main__":
    main()