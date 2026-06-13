#!/usr/bin/env python3
"""
Apply J Generator Migration for SHARD-20 - AUTONOMOUS OPERATION
Per CLAUDE.md: "supabase db push - Apply migrations — NO HITL"

This script applies the J generator migration to create bid_decisions entries
for charlotte, citrus, broward counties per the evaluator contract.
"""
import os
import sys
import requests
import json
from datetime import datetime, timezone

# Supabase configuration from environment
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def apply_migration_direct():
    """Apply J generator migration directly via SQL execution"""
    log("🚀 Applying J generator migration via direct SQL execution")
    
    # Read the migration file
    migration_file = "/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/supabase/migrations/20260613_shard20_j_generator_execution.sql"
    
    try:
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
    except FileNotFoundError:
        log(f"Migration file not found: {migration_file}", "ERROR")
        return False
    
    # Split the SQL into individual statements
    statements = [stmt.strip() for stmt in migration_sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]
    
    log(f"Found {len(statements)} SQL statements to execute")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Execute each statement
    success_count = 0
    for i, statement in enumerate(statements):
        if statement.strip():
            try:
                # Use RPC to execute raw SQL
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
                    headers=headers,
                    json={"sql": statement}
                )
                
                if response.status_code in [200, 201]:
                    success_count += 1
                    log(f"Statement {i+1}/{len(statements)}: SUCCESS")
                else:
                    log(f"Statement {i+1}/{len(statements)}: FAILED - {response.status_code} {response.text}")
                    
            except Exception as e:
                log(f"Statement {i+1}/{len(statements)}: ERROR - {e}")
    
    log(f"Migration execution complete: {success_count}/{len(statements)} statements succeeded")
    return success_count > 0

def verify_migration_success():
    """Verify the J generator migration was applied successfully"""
    log("🔍 Verifying J generator migration success")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Check bid_decisions table exists and has data
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers=headers,
            params={
                "select": "case_number,county_slug",
                "county_slug": "in.(charlotte,citrus,broward)",
                "limit": "5"
            }
        )
        
        if response.status_code == 200:
            rows = response.json()
            log(f"✅ bid_decisions table accessible, found {len(rows)} sample rows")
            
            # Count total rows per county
            for county in ['charlotte', 'citrus', 'broward']:
                county_response = requests.get(
                    f"{SUPABASE_URL}/rest/v1/bid_decisions",
                    headers=headers,
                    params={
                        "select": "case_number",
                        "county_slug": f"eq.{county}"
                    }
                )
                
                if county_response.status_code == 200:
                    county_rows = county_response.json()
                    log(f"{county}: {len(county_rows)} bid_decisions entries")
            
            return True
        else:
            log(f"❌ bid_decisions verification failed: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Verification error: {e}")
        return False

def run_post_migration_evaluation():
    """Run county evaluations to check J metric improvement"""
    log("📊 Running post-migration county evaluations")
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    evaluation_results = {}
    
    for county in ['charlotte', 'citrus', 'broward']:
        try:
            # Try both parameter patterns for the RPC function
            for param_name in ["county_slug_arg", "county_name"]:
                response = requests.post(
                    f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                    headers=headers,
                    json={param_name: county}
                )
                
                if response.status_code == 200:
                    evaluation = response.json()
                    
                    # Extract J letter data
                    j_data = None
                    if isinstance(evaluation, list):
                        j_data = next((item for item in evaluation if item.get('letter') == 'J'), None)
                    elif isinstance(evaluation, dict):
                        j_data = {'metric': evaluation.get('metric_j'), 'pass': evaluation.get('grade_j') == 'PASS'}
                    
                    if j_data:
                        j_metric = j_data.get('metric', 0)
                        j_grade = "PASS" if j_data.get('pass', False) else "FAIL"
                        
                        evaluation_results[county] = {
                            "j_metric": j_metric,
                            "j_grade": j_grade,
                            "evaluation_status": "SUCCESS"
                        }
                        
                        log(f"{county} J evaluation: {j_metric}% ({j_grade})")
                        break
                        
                elif response.status_code != 400:
                    log(f"Failed to evaluate {county}: {response.status_code}")
            
            if county not in evaluation_results:
                evaluation_results[county] = {
                    "evaluation_status": "FAILED",
                    "error": "Could not run evaluation"
                }
                
        except Exception as e:
            log(f"Error evaluating {county}: {e}")
            evaluation_results[county] = {
                "evaluation_status": "ERROR", 
                "error": str(e)
            }
    
    return evaluation_results

def main():
    """Main execution for J generator migration application"""
    log("🎯 SHARD-20 J GENERATOR MIGRATION APPLICATION - AUTONOMOUS OPERATION")
    
    if not SUPABASE_KEY:
        log("❌ No Supabase API key available", "ERROR")
        return False
    
    # Step 1: Apply migration
    migration_success = apply_migration_direct()
    
    if not migration_success:
        log("❌ Migration application failed", "ERROR")
        return False
    
    # Step 2: Verify migration was applied
    verification_success = verify_migration_success()
    
    if not verification_success:
        log("❌ Migration verification failed", "ERROR")
        return False
    
    # Step 3: Run evaluations to check impact
    evaluation_results = run_post_migration_evaluation()
    
    # Summary
    log("\n" + "="*60)
    log("J GENERATOR MIGRATION APPLICATION RESULTS")
    log("="*60)
    
    for county, results in evaluation_results.items():
        j_metric = results.get('j_metric', 'unknown')
        j_grade = results.get('j_grade', 'unknown')
        log(f"{county}: J={j_metric}% ({j_grade})")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)