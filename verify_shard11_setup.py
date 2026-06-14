#!/usr/bin/env python3
"""
SHARD-11 Setup Verification
Verify the session setup and database configuration without requiring live DB access

Usage:
  python verify_shard11_setup.py
"""
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# SHARD-11 counties from issue #7745
SHARD11_COUNTIES = ['sarasota', 'hillsborough', 'pinellas', 'gadsden', 'wakulla']

def check_environment():
    """Check environment configuration"""
    print("🔧 Environment Configuration Check")
    
    config_status = {
        "supabase_url": os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co"),
        "supabase_key_available": bool(os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")),
        "db_password_available": bool(os.environ.get("SUPABASE_DB_PASSWORD")),
        "working_directory": str(Path.cwd()),
        "project_root": str(Path(__file__).parent),
        "session_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    print(f"   SUPABASE_URL: {config_status['supabase_url']}")
    print(f"   SUPABASE_KEY available: {config_status['supabase_key_available']}")
    print(f"   DB_PASSWORD available: {config_status['db_password_available']}")
    print(f"   Working directory: {config_status['working_directory']}")
    
    return config_status

def check_script_files():
    """Check if required scripts and files exist"""
    print("\n📂 Script Files Check")
    
    required_files = [
        "scripts/shard11_gold_standard_session.py",
        "scripts/shard11_session_test.py", 
        "CLAUDE.md",
        "TODO.md"
    ]
    
    file_status = {}
    for file_path in required_files:
        full_path = Path(__file__).parent / file_path
        exists = full_path.exists()
        file_status[file_path] = {
            "exists": exists,
            "path": str(full_path),
            "size": full_path.stat().st_size if exists else 0
        }
        
        status = "✅" if exists else "❌"
        print(f"   {status} {file_path}")
        
    return file_status

def validate_county_configuration():
    """Validate county configuration against issue requirements"""
    print("\n🗺️ County Configuration Validation")
    
    # Expected metrics from issue #7745
    expected_metrics = {
        'sarasota': {'score': '2/10', 'passing': ['A', 'H']},
        'hillsborough': {'score': '1/10', 'passing': ['A']},
        'pinellas': {'score': '1/10', 'passing': ['A']},
        'gadsden': {'score': '0/10', 'passing': []},
        'wakulla': {'score': '0/10', 'passing': []}
    }
    
    print(f"   Target counties: {', '.join(SHARD11_COUNTIES)}")
    
    for county in SHARD11_COUNTIES:
        metrics = expected_metrics[county]
        passing_letters = ', '.join(metrics['passing']) if metrics['passing'] else 'None'
        print(f"   🎯 {county}: {metrics['score']} - Passing: {passing_letters}")
    
    return expected_metrics

def validate_priority_order():
    """Validate priority execution order per Brevard Sprint Order"""
    print("\n📋 Priority Order Validation")
    
    priorities = [
        {
            "order": 1,
            "name": "C/D ROOT CAUSE", 
            "description": "Parity audit + supplementary litmus",
            "approach": "PropertyOnion coverage gap analysis"
        },
        {
            "order": 2, 
            "name": "J GENERATOR",
            "description": "bid_decisions pipeline",
            "approach": "arv + max_bid + ml_score + factors"
        },
        {
            "order": 3,
            "name": "G HIT LIST", 
            "description": "zone_standards backfill",
            "approach": "Ordinance-text values with honesty markers"
        },
        {
            "order": 4,
            "name": "B RECONCILIATION",
            "description": "verified_outcomes anomaly fix", 
            "approach": "Resolve >100% metrics anomaly"
        }
    ]
    
    for priority in priorities:
        print(f"   {priority['order']}. {priority['name']}")
        print(f"      {priority['description']}")
        print(f"      Approach: {priority['approach']}")
    
    return priorities

def generate_session_plan():
    """Generate the complete session execution plan"""
    print("\n🎯 Session Execution Plan")
    
    plan = {
        "session_metadata": {
            "shard": "SHARD-11", 
            "issue": "#7745",
            "counties": SHARD11_COUNTIES,
            "ship_to_main": True,
            "ultraloop_protocol": True,
            "budget": "6 hours"
        },
        "execution_phases": [
            {
                "phase": 1,
                "name": "Database Connectivity Test",
                "script": "scripts/shard11_session_test.py",
                "purpose": "Verify database access and get baseline metrics"
            },
            {
                "phase": 2,
                "name": "Priority Fixes Execution",
                "script": "scripts/shard11_gold_standard_session.py", 
                "purpose": "Execute C/D, J, G, B fixes in Brevard Sprint Order"
            },
            {
                "phase": 3,
                "name": "ULTRALOOP Verification", 
                "script": "Built into main session",
                "purpose": "Adversarial verification with survival votes"
            },
            {
                "phase": 4,
                "name": "Final Metrics & Certification",
                "script": "pencil_dod_evaluate_county() calls",
                "purpose": "Verify improvements and determine certification status"
            }
        ],
        "success_criteria": [
            "All priority scripts execute successfully",
            "ULTRALOOP verification passes with survived=true rows",
            "Final metrics show improvement vs baseline",
            "All changes committed to main branch"
        ]
    }
    
    for phase in plan["execution_phases"]:
        print(f"   Phase {phase['phase']}: {phase['name']}")
        print(f"      Script: {phase['script']}")
        print(f"      Purpose: {phase['purpose']}")
    
    return plan

def main():
    """Main verification"""
    print("="*80)
    print("SHARD-11 GOLD STANDARD SESSION - SETUP VERIFICATION")
    print("Issue #7745 - sarasota, hillsborough, pinellas, gadsden, wakulla")
    print("="*80)
    
    # Run all checks
    env_config = check_environment()
    file_status = check_script_files() 
    county_config = validate_county_configuration()
    priority_order = validate_priority_order()
    session_plan = generate_session_plan()
    
    # Generate verification report
    verification_report = {
        "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        "environment_config": env_config,
        "file_status": file_status,
        "county_configuration": county_config,
        "priority_order": priority_order, 
        "session_plan": session_plan,
        "verification_status": "COMPLETE"
    }
    
    # Check overall readiness
    db_ready = env_config["supabase_key_available"]
    scripts_ready = all(status["exists"] for status in file_status.values())
    
    overall_status = "READY" if (db_ready and scripts_ready) else "BLOCKED"
    blocking_factors = []
    
    if not db_ready:
        blocking_factors.append("Database credentials not available")
    if not scripts_ready:
        blocking_factors.append("Required script files missing")
    
    print(f"\n" + "="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print(f"Overall Status: {overall_status}")
    
    if blocking_factors:
        print("Blocking Factors:")
        for factor in blocking_factors:
            print(f"   ❌ {factor}")
    else:
        print("✅ All verification checks passed")
        print("✅ Ready to execute Gold Standard session")
    
    print(f"\nNext step: Run scripts/shard11_gold_standard_session.py")
    
    # Save verification report
    report_file = "/tmp/shard11_verification_report.json"
    try:
        with open(report_file, "w") as f:
            json.dump(verification_report, f, indent=2, default=str)
        print(f"📄 Verification report saved to {report_file}")
    except Exception as e:
        print(f"⚠️ Could not save verification report: {e}")
    
    return verification_report

if __name__ == "__main__":
    main()