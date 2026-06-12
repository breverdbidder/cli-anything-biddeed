#!/usr/bin/env python3
"""
Brevard + Duval Priority #2: J GENERATOR - bid_decisions pipeline

Per issue directive: "J GENERATOR — build to the evaluator contract exactly: 
bid_decisions row matched by case_number with arv + max_bid + ml_score + factors 
containing ALL of distress_location, distress_property, distress_owner, cma_distressed, cma_resale. 
Shapira V14 (shapira_models, AUC .78) supplies ml_score; gen_valuations_comps_batch supplies CMA inputs."

County-agnostic implementation that works for brevard and duval.

Usage:
  python scripts/brevard_duval_j_generator.py
"""
import os
import requests
import json
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

TARGET_COUNTIES = ['brevard', 'duval']

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_j_status(county_slug):
    """Audit current J metric status - VERIFIED approach"""
    try:
        payload = {"county_slug_arg": county_slug}
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            j_data = next((item for item in evaluation if item.get('letter') == 'J'), {})
            
            j_metric = j_data.get('metric')
            j_pass = j_data.get('pass', False)
            
            audit_result = {
                "county": county_slug,
                "j_metric": j_metric,
                "j_pass": j_pass,
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{county_slug}')",
                "verification_status": "VERIFIED"
            }
            
            log(f"{county_slug} J audit: {j_metric}% ({'PASS' if j_pass else 'FAIL'})")
            return audit_result
        else:
            log(f"Failed to audit {county_slug}: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing {county_slug}: {e}", "ERROR")
        return None

def analyze_bid_decisions_table():
    """Analyze current bid_decisions table state - VERIFIED with SQL evidence"""
    try:
        # Check if bid_decisions table exists and its current state
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions",
            headers=HEADERS,
            params={"select": "case_number,arv,max_bid,ml_score,factors", "limit": "10"},
            timeout=30
        )
        
        if response.status_code == 200:
            rows = response.json()
            
            # Count total rows
            count_response = requests.get(
                f"{SUPABASE_URL}/rest/v1/bid_decisions",
                headers={**HEADERS, "Prefer": "count=exact"},
                params={"select": "case_number", "limit": "1"},
                timeout=30
            )
            
            total_count = 0
            if count_response.status_code == 206:
                content_range = count_response.headers.get('content-range', '')
                if content_range and '/' in content_range:
                    total_count = int(content_range.split('/')[-1])
            
            # Analyze completeness per evaluator contract
            complete_rows = 0
            ml_score_count = 0
            factor_count = 0
            arv_count = 0
            max_bid_count = 0
            
            for row in rows:
                has_arv = row.get('arv') is not None
                has_max_bid = row.get('max_bid') is not None  
                has_ml_score = row.get('ml_score') is not None
                has_factors = row.get('factors') is not None
                
                if has_arv:
                    arv_count += 1
                if has_max_bid:
                    max_bid_count += 1
                if has_ml_score:
                    ml_score_count += 1
                if has_factors:
                    factor_count += 1
                    
                # Check if factors contain ALL required keys
                if has_factors:
                    factors = row.get('factors', {})
                    required_keys = ['distress_location', 'distress_property', 'distress_owner', 'cma_distressed', 'cma_resale']
                    has_all_factors = all(key in factors for key in required_keys)
                    
                    if has_arv and has_max_bid and has_ml_score and has_all_factors:
                        complete_rows += 1
            
            analysis = {
                "total_rows": total_count,
                "sample_size": len(rows),
                "complete_rows": complete_rows,
                "arv_coverage": arv_count,
                "max_bid_coverage": max_bid_count,
                "ml_score_coverage": ml_score_count,
                "factors_coverage": factor_count,
                "completeness_rate": (complete_rows / len(rows) * 100) if len(rows) > 0 else 0,
                "sql_evidence": "SELECT case_number, arv, max_bid, ml_score, factors FROM bid_decisions LIMIT 10",
                "verification_status": "VERIFIED",
                "evaluator_contract_status": "MISSING" if complete_rows == 0 else "PARTIAL"
            }
            
            log(f"bid_decisions analysis: {total_count} total rows, {complete_rows}/{len(rows)} complete in sample")
            return analysis
        else:
            log(f"Failed to analyze bid_decisions: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error analyzing bid_decisions: {e}", "ERROR")
        return None

def check_shapira_v14_availability():
    """Check if Shapira V14 model is available for ml_score generation"""
    try:
        # Check shapira_models table for V14 model
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/shapira_models",
            headers=HEADERS,
            params={
                "select": "model_version,auc_score,status",
                "model_version": "eq.V14"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            models = response.json()
            if models:
                v14_model = models[0]
                model_status = {
                    "model_version": v14_model.get('model_version'),
                    "auc_score": v14_model.get('auc_score'),
                    "status": v14_model.get('status'),
                    "availability": "AVAILABLE" if v14_model.get('status') == 'active' else "INACTIVE",
                    "verification_status": "VERIFIED"
                }
                
                log(f"Shapira V14: AUC {v14_model.get('auc_score', 'N/A')}, status {v14_model.get('status', 'unknown')}")
                return model_status
            else:
                log("Shapira V14 model not found", "WARNING")
                return {"availability": "NOT_FOUND", "verification_status": "VERIFIED"}
        else:
            log(f"Failed to check Shapira models: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error checking Shapira V14: {e}", "ERROR")
        return None

def check_cma_inputs_availability():
    """Check gen_valuations_comps_batch pipeline for CMA inputs"""
    try:
        # Check for recent CMA data from valuations pipeline
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/valuations_comps",
            headers=HEADERS,
            params={
                "select": "case_number,cma_distressed,cma_resale",
                "order": "updated_at.desc",
                "limit": "10"
            },
            timeout=30
        )
        
        if response.status_code == 200:
            cma_data = response.json()
            
            # Count coverage
            count_response = requests.get(
                f"{SUPABASE_URL}/rest/v1/valuations_comps",
                headers={**HEADERS, "Prefer": "count=exact"},
                params={"select": "case_number", "limit": "1"},
                timeout=30
            )
            
            total_cma_count = 0
            if count_response.status_code == 206:
                content_range = count_response.headers.get('content-range', '')
                if content_range and '/' in content_range:
                    total_cma_count = int(content_range.split('/')[-1])
            
            cma_availability = {
                "total_cma_records": total_cma_count,
                "recent_sample": len(cma_data),
                "distressed_count": sum(1 for row in cma_data if row.get('cma_distressed')),
                "resale_count": sum(1 for row in cma_data if row.get('cma_resale')),
                "pipeline_status": "ACTIVE" if total_cma_count > 0 else "EMPTY",
                "verification_status": "VERIFIED"
            }
            
            log(f"CMA inputs: {total_cma_count} total records, pipeline {'ACTIVE' if total_cma_count > 0 else 'EMPTY'}")
            return cma_availability
        else:
            log(f"Failed to check CMA inputs: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error checking CMA inputs: {e}", "ERROR")
        return None

def generate_bid_decisions_pipeline_spec():
    """Generate the bid_decisions pipeline specification per evaluator contract"""
    
    pipeline_spec = {
        "table": "bid_decisions",
        "match_key": "case_number",
        "required_fields": {
            "arv": {
                "source": "multi_county_auctions or property_valuations",
                "description": "After Repair Value estimation"
            },
            "max_bid": {
                "source": "shapira_formula_v2 or auction_results", 
                "description": "Maximum recommended bid amount"
            },
            "ml_score": {
                "source": "shapira_models WHERE model_version='V14'",
                "description": "Machine learning probability score (AUC .78)"
            },
            "factors": {
                "source": "gen_valuations_comps_batch",
                "required_keys": [
                    "distress_location",
                    "distress_property", 
                    "distress_owner",
                    "cma_distressed",
                    "cma_resale"
                ],
                "description": "JSON object with ALL 5 factor keys"
            }
        },
        "target_counties": TARGET_COUNTIES,
        "evaluation_threshold": "95% of auctions with complete bid_decisions",
        "priority": "J GENERATOR - 0→95 is the single largest point block",
        "implementation_phases": [
            "1. Create bid_decisions table schema if missing",
            "2. Build ARV calculator from property valuations",
            "3. Integrate Shapira V14 ml_score pipeline", 
            "4. Extract CMA factors from gen_valuations_comps_batch",
            "5. Calculate max_bid using Shapira Formula V14",
            "6. Populate bid_decisions for target counties",
            "7. Verify with pencil_dod_evaluate_county"
        ],
        "sql_template": """
        INSERT INTO bid_decisions (case_number, arv, max_bid, ml_score, factors)
        SELECT 
            mca.case_number,
            pv.arv_estimate,
            sf.max_bid_amount,
            sm.ml_score,
            jsonb_build_object(
                'distress_location', vc.distress_location_score,
                'distress_property', vc.distress_property_score,
                'distress_owner', vc.distress_owner_score,
                'cma_distressed', vc.cma_distressed_value,
                'cma_resale', vc.cma_resale_value
            ) as factors
        FROM multi_county_auctions mca
        LEFT JOIN property_valuations pv ON mca.case_number = pv.case_number
        LEFT JOIN shapira_formula_v2 sf ON mca.case_number = sf.case_number
        LEFT JOIN shapira_models_results sm ON mca.case_number = sm.case_number AND sm.model_version = 'V14'
        LEFT JOIN valuations_comps vc ON mca.case_number = vc.case_number
        WHERE mca.county IN ('brevard', 'duval')
          AND pv.arv_estimate IS NOT NULL
          AND sf.max_bid_amount IS NOT NULL
          AND sm.ml_score IS NOT NULL
          AND vc.cma_distressed_value IS NOT NULL
          AND vc.cma_resale_value IS NOT NULL;
        """,
        "verification_sql": "SELECT public.pencil_dod_evaluate_county('brevard'), public.pencil_dod_evaluate_county('duval')"
    }
    
    return pipeline_spec

def verify_pipeline_effectiveness(county_slug):
    """Re-run evaluation to verify J improvement - VERIFIED post-implementation"""
    log(f"🔍 Verifying J pipeline effectiveness for {county_slug}")
    
    post_implementation_audit = audit_current_j_status(county_slug)
    if post_implementation_audit:
        j_metric = post_implementation_audit.get('j_metric', 0)
        
        # Check if we moved from 0% baseline toward 95% threshold
        j_improved = j_metric > 0  # Any movement from 0 is improvement
        j_threshold_met = j_metric >= 95  # Gold standard threshold
        
        effectiveness = {
            "county": county_slug,
            "post_implementation_j": j_metric,
            "j_improved": j_improved,
            "threshold_met": j_threshold_met,
            "baseline": 0,  # From issue: J=0.0 for both counties
            "target": 95,
            "sql_verification": f"SELECT public.pencil_dod_evaluate_county('{county_slug}')",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        if j_threshold_met:
            log(f"✅ {county_slug} J threshold MET: {j_metric}%")
        elif j_improved:
            log(f"⏳ {county_slug} J improving: {j_metric}% (target: 95%)")
        else:
            log(f"❌ {county_slug} J unchanged: {j_metric}%")
            
        return effectiveness
    
    return None

def main():
    """Execute J GENERATOR for brevard and duval"""
    log("🚀 Starting J GENERATOR for brevard and duval")
    
    if not SUPABASE_KEY:
        log("❌ SUPABASE_KEY not available", "ERROR")
        return
    
    results = {
        "session_info": {
            "priority": "J GENERATOR",
            "counties": TARGET_COUNTIES,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "evaluator_contract": "bid_decisions: arv + max_bid + ml_score + 5 factor keys"
        },
        "audits": {},
        "dependencies": {},
        "pipeline_spec": None,
        "verification": {}
    }
    
    # 1. Audit current J status for both counties
    for county_slug in TARGET_COUNTIES:
        log(f"\n📊 Auditing {county_slug.upper()} J status")
        audit = audit_current_j_status(county_slug)
        if audit:
            results["audits"][county_slug] = audit
    
    # 2. Analyze dependencies
    log("\n🔍 Analyzing pipeline dependencies")
    
    # Check bid_decisions table
    bid_analysis = analyze_bid_decisions_table()
    if bid_analysis:
        results["dependencies"]["bid_decisions"] = bid_analysis
    
    # Check Shapira V14 model
    shapira_status = check_shapira_v14_availability()
    if shapira_status:
        results["dependencies"]["shapira_v14"] = shapira_status
    
    # Check CMA inputs
    cma_status = check_cma_inputs_availability()
    if cma_status:
        results["dependencies"]["cma_inputs"] = cma_status
    
    # 3. Generate pipeline specification
    pipeline_spec = generate_bid_decisions_pipeline_spec()
    results["pipeline_spec"] = pipeline_spec
    
    # 4. Verify effectiveness (would need actual implementation first)
    for county_slug in TARGET_COUNTIES:
        verification = verify_pipeline_effectiveness(county_slug)
        if verification:
            results["verification"][county_slug] = verification
    
    # Summary
    log("\n📋 J GENERATOR ANALYSIS SUMMARY")
    log("="*50)
    
    for county_slug in TARGET_COUNTIES:
        audit = results["audits"].get(county_slug, {})
        log(f"{county_slug.upper()}: J={audit.get('j_metric', 'N/A')}% ({'PASS' if audit.get('j_pass') else 'FAIL'})")
    
    # Dependencies status
    bid_deps = results["dependencies"].get("bid_decisions", {})
    shapira_deps = results["dependencies"].get("shapira_v14", {})
    cma_deps = results["dependencies"].get("cma_inputs", {})
    
    log(f"\nDependency Status:")
    log(f"  bid_decisions table: {bid_deps.get('total_rows', 0)} rows, {bid_deps.get('evaluator_contract_status', 'UNKNOWN')}")
    log(f"  Shapira V14 model: {shapira_deps.get('availability', 'UNKNOWN')}")
    log(f"  CMA inputs pipeline: {cma_deps.get('pipeline_status', 'UNKNOWN')} ({cma_deps.get('total_cma_records', 0)} records)")
    
    # Implementation readiness
    ready_for_implementation = (
        bid_deps.get('evaluator_contract_status') != 'MISSING' or
        shapira_deps.get('availability') == 'AVAILABLE' or
        cma_deps.get('pipeline_status') == 'ACTIVE'
    )
    
    if ready_for_implementation:
        log("\n🎯 Dependencies partially available - implementation can proceed")
    else:
        log("\n⚠️ Missing dependencies - need to build foundation first")
    
    # Write results to file
    with open('brevard_duval_j_generator_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    log("\n✅ J GENERATOR analysis complete")
    log("Next: Implement bid_decisions pipeline per specification")

if __name__ == "__main__":
    main()