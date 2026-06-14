#!/usr/bin/env python3
"""
GOLD STANDARD ULTRALOOP COORDINATOR
Implements corrected approach after ULTRALOOP adversarial verification

ISSUE: #7724 GOLD STANDARD AUTOPILOT-BD
STATUS: Post-refutation remediation phase

This coordinator:
1. Logs ULTRALOOP audit findings to gold_standard_ultraloop_audit table
2. Implements schema fixes for missing tables
3. Executes corrected implementations that address refutation flaws
4. Provides SQL verification evidence per SHIP GATE requirements

Usage:
  python scripts/gold_standard_ultraloop_coordinator.py --mode audit-log
  python scripts/gold_standard_ultraloop_coordinator.py --mode schema-fix  
  python scripts/gold_standard_ultraloop_coordinator.py --mode execute
"""
import os
import sys
import json
import argparse
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# ULTRALOOP audit findings from refuters
ULTRALOOP_FINDINGS = [
    {
        "county_slug": "brevard",
        "letter": "C",
        "claim": "C/D parity fix will improve C=20.9% → 35-40% via clerk records",
        "refuter_evidence": {
            "critical_flaws": [
                "Implementation never executes SQL (designs only)",
                "Brevard clerk access unproven (uses mock data)",
                "Missing required tables and migrations",
                "Improvement estimates lack foundation"
            ],
            "verdict": "REFUTED - cannot deliver promised improvements"
        },
        "survived": False
    },
    {
        "county_slug": "brevard", 
        "letter": "D",
        "claim": "C/D parity fix will improve D=34.0% → 75-85% via clerk records",
        "refuter_evidence": {
            "critical_flaws": [
                "Same as C - design-only implementation", 
                "Case number matching logic unvalidated",
                "33% denominator growth claim unverified",
                "SQL syntax assumes non-existent tables"
            ],
            "verdict": "REFUTED - false positive risk due to flawed matching"
        },
        "survived": False
    },
    {
        "county_slug": "duval",
        "letter": "G", 
        "claim": "G+I substrate will make G measurable (null → 45-65%)",
        "refuter_evidence": {
            "critical_flaws": [
                "Required tables (zoning_districts, parcel_zones) DO NOT EXIST",
                "G evaluation function hardcoded FALSE regardless of data",
                "Spatial SQL uses wrong column names (geometry vs geom)",
                "COJ GIS accessibility assumptions untested"
            ],
            "verdict": "REFUTED - substrate completion ≠ measurability"
        },
        "survived": False
    },
    {
        "county_slug": "duval",
        "letter": "I",
        "claim": "G+I substrate will make I measurable (null → 35-55%)",
        "refuter_evidence": {
            "critical_flaws": [
                "Same substrate dependencies as G",
                "I evaluation function hardcoded FALSE",
                "Property completeness logic not implemented",
                "Jurisdiction ID assumptions unvalidated" 
            ],
            "verdict": "REFUTED - evaluation logic missing regardless of substrate"
        },
        "survived": False
    },
    {
        "county_slug": "brevard",
        "letter": "J",
        "claim": "J generator will improve J=0.0 → 85% via bid_decisions pipeline", 
        "refuter_evidence": {
            "critical_flaws": [
                "Shapira V14 ML inference is fake (hardcoded IF/THEN rules)",
                "Mathematical errors in Shapira formula (double-subtraction)",
                "SQL syntax errors and undefined table references",
                "Factor generation uses undefined variables"
            ],
            "verdict": "REFUTED - pipeline would generate zero valid records"
        },
        "survived": False
    },
    {
        "county_slug": "duval",
        "letter": "J",
        "claim": "J generator will improve J=0.0 → 82% via bid_decisions pipeline",
        "refuter_evidence": {
            "critical_flaws": [
                "Same implementation flaws as brevard",
                "Data coverage assumptions unvalidated", 
                "JOIN dependency failures likely",
                "80%+ estimates mathematically impossible with identified flaws"
            ],
            "verdict": "REFUTED - implementation cannot execute successfully"
        },
        "survived": False
    }
]

class UltraloopCoordinator:
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.dispatch_id = "8a3c4642-b4e2-430b-a5ad-c561d464bb73"  # From issue brief
        self.results = {
            "session_start": self.session_start.isoformat(),
            "dispatch_id": self.dispatch_id,
            "mode": None,
            "ultraloop_mode": "fallback",  # Using Task subagents, not native ultracode
            "audit_logged": False,
            "schema_fixed": False,
            "execution_results": {},
            "sql_verification_evidence": []
        }
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def log_ultraloop_audit_findings(self) -> Dict:
        """Log ULTRALOOP audit findings to database - HONESTY PROTOCOL: VERIFIED"""
        self.log("📝 Logging ULTRALOOP audit findings to database...")
        
        logged_count = 0
        errors = []
        
        for finding in ULTRALOOP_FINDINGS:
            try:
                audit_record = {
                    "dispatch_id": self.dispatch_id,
                    "ultraloop_mode": "fallback",
                    "county_slug": finding["county_slug"],
                    "letter": finding["letter"],
                    "claim": finding["claim"],
                    "refuter_evidence": finding["refuter_evidence"],
                    "survived": finding["survived"],
                    "created_at": self.session_start.isoformat()
                }
                
                response = requests.post(
                    f"{BASE}/gold_standard_ultraloop_audit",
                    headers=HEADERS,
                    json=audit_record,
                    timeout=20
                )
                
                if response.status_code in [200, 201]:
                    logged_count += 1
                    self.log(f"✅ Logged {finding['county_slug']} {finding['letter']} audit finding")
                else:
                    error_msg = f"Failed to log {finding['county_slug']} {finding['letter']}: {response.status_code}"
                    errors.append(error_msg)
                    self.log(error_msg, "ERROR")
                    
            except Exception as e:
                error_msg = f"Exception logging {finding['county_slug']} {finding['letter']}: {e}"
                errors.append(error_msg)
                self.log(error_msg, "ERROR")
        
        return {
            "logged_count": logged_count,
            "total_findings": len(ULTRALOOP_FINDINGS),
            "errors": errors,
            "success": logged_count == len(ULTRALOOP_FINDINGS) and len(errors) == 0
        }
    
    def apply_schema_fixes(self) -> Dict:
        """Apply schema fixes to address missing tables - HONESTY PROTOCOL: DESIGNED"""
        self.log("🔧 Applying schema fixes for missing tables...")
        
        # Read the migration file
        migration_path = Path(__file__).parent.parent / "migrations" / "20260614_gold_standard_schema_fixes.sql"
        
        if not migration_path.exists():
            return {"error": f"Migration file not found: {migration_path}"}
        
        try:
            with open(migration_path, 'r') as f:
                migration_sql = f.read()
                
            schema_fixes = {
                "migration_file": str(migration_path),
                "sql_length": len(migration_sql),
                "tables_created": [
                    "zoning_districts",
                    "parcel_zones", 
                    "brevard_clerk_parity_records",
                    "gold_standard_ultraloop_audit"
                ],
                "functions_updated": ["pencil_dod_evaluate_county_fixed"],
                "status": "PREPARED",
                "note": "Migration designed but requires Supabase execution"
            }
            
            self.log(f"✅ Schema fixes prepared: {len(schema_fixes['tables_created'])} tables")
            
            return schema_fixes
            
        except Exception as e:
            return {"error": f"Schema fix preparation failed: {e}"}
    
    def validate_current_metrics(self) -> Dict:
        """Get current verified metrics for brevard and duval - HONESTY PROTOCOL: VERIFIED"""
        self.log("📊 Validating current metrics for brevard and duval...")
        
        metrics = {"brevard": {}, "duval": {}, "sql_queries": []}
        
        for county in ["brevard", "duval"]:
            try:
                payload = {"county_name": county}
                response = requests.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county", 
                    headers=HEADERS, 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    evaluation = response.json()
                    metrics[county] = {
                        "c_metric": evaluation.get("metric_c"),
                        "d_metric": evaluation.get("metric_d"),
                        "g_metric": evaluation.get("metric_g"),
                        "i_metric": evaluation.get("metric_i"),
                        "j_metric": evaluation.get("metric_j"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    metrics["sql_queries"].append({
                        "query": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                        "result": evaluation,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    self.log(f"✅ {county} current metrics VERIFIED")
                    
                else:
                    metrics[county] = {"error": f"Evaluation failed: {response.status_code}"}
                    
            except Exception as e:
                metrics[county] = {"error": str(e)}
                
        return metrics
    
    def run_mode_audit_log(self) -> Dict:
        """Log ULTRALOOP findings to audit table"""
        self.log("📝 Running AUDIT-LOG mode...")
        
        # Validate database connection
        if not SUPABASE_KEY:
            return {"error": "No SUPABASE_KEY in environment"}
            
        try:
            response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
            if response.status_code != 200:
                return {"error": f"Database connection failed: {response.status_code}"}
        except Exception as e:
            return {"error": f"Database connection error: {e}"}
        
        # Log ULTRALOOP findings
        audit_result = self.log_ultraloop_audit_findings()
        
        return {
            "mode": "AUDIT-LOG",
            "audit_logging": audit_result,
            "findings_summary": {
                "total_claims_tested": len(ULTRALOOP_FINDINGS),
                "survived": 0,
                "refuted": len(ULTRALOOP_FINDINGS),
                "survival_rate": "0% - all implementations failed adversarial testing"
            }
        }
    
    def run_mode_schema_fix(self) -> Dict:
        """Apply schema fixes for missing dependencies"""
        self.log("🔧 Running SCHEMA-FIX mode...")
        
        schema_result = self.apply_schema_fixes()
        current_metrics = self.validate_current_metrics()
        
        return {
            "mode": "SCHEMA-FIX",
            "schema_fixes": schema_result,
            "current_metrics": current_metrics,
            "remediation_status": "DESIGNED - requires Supabase migration execution"
        }
    
    def run_mode_execute(self) -> Dict:
        """Execute corrected implementations with proper validation"""
        self.log("🚀 Running EXECUTE mode...")
        
        # Validate prerequisites
        current_metrics = self.validate_current_metrics()
        
        execution_plan = {
            "phase_1_schema": "Apply 20260614_gold_standard_schema_fixes.sql migration",
            "phase_2_validation": "Validate table creation and data access",
            "phase_3_corrected_impl": "Execute j_generator_fixed.py with data validation",
            "phase_4_verification": "Measure actual improvements vs estimates",
            "blocking_dependencies": [
                "Supabase migration execution capability", 
                "Database schema fixes applied",
                "Data source validation completed"
            ]
        }
        
        return {
            "mode": "EXECUTE",
            "current_state": current_metrics,
            "execution_plan": execution_plan,
            "status": "BLOCKED - requires schema fixes before execution",
            "next_actions": [
                "Apply schema migration via Supabase CLI",
                "Validate table creation success",
                "Execute j_generator_fixed.py with real data validation",
                "Measure and report actual improvements with SQL proof"
            ]
        }


def main():
    parser = argparse.ArgumentParser(description="Gold Standard ULTRALOOP Coordinator")
    parser.add_argument("--mode", choices=["audit-log", "schema-fix", "execute"], 
                       default="audit-log", help="Operation mode")
    
    args = parser.parse_args()
    
    coordinator = UltraloopCoordinator()
    coordinator.results["mode"] = args.mode
    
    if args.mode == "audit-log":
        results = coordinator.run_mode_audit_log()
    elif args.mode == "schema-fix":
        results = coordinator.run_mode_schema_fix()
    elif args.mode == "execute":
        results = coordinator.run_mode_execute()
    else:
        results = {"error": "Invalid mode"}
    
    # Store results
    coordinator.results.update(results)
    
    # Output final results
    print("\n" + "="*60)
    print("GOLD STANDARD ULTRALOOP COORDINATOR - FINAL REPORT")
    print("="*60)
    print(json.dumps(coordinator.results, indent=2, default=str))
    
    return 0 if "error" not in results else 1


if __name__ == "__main__":
    exit(main())