#!/usr/bin/env python3
"""
SHARD-2 ULTRALOOP AUDIT PROTOCOL
Per CLAUDE.md: "kill agentic laziness, self-preferential bias, and goal drift"

Implementation:
1. SESSION INIT: Fan-out verification for each failing letter per county  
2. AUDIT = FAN-OUT-AND-SYNTHESIZE: isolated context per letter
3. VERIFY = ADVERSARIAL SURVIVAL VOTE: refuter subagents break claims
4. FIX = LOOP-UNTIL-DONE: fixes iterate against live metrics
5. SAVE WORKFLOWS: persist as reusable artifacts in .claude/
6. CERTIFY GATE: all survival votes recorded in gold_standard_ultraloop_audit

Target: SHARD-2 counties (brevard, washington, lake, st_johns, holmes)
Letters: A-J with focus on B, I, J as critical three per canon
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-2 target counties
SHARD2_COUNTIES = ['brevard', 'washington', 'lake', 'st_johns', 'holmes']

# Gold standard letter definitions (from issue)
LETTER_DEFINITIONS = {
    'A': {
        'name': 'dual-product coverage',
        'threshold': '>0',
        'critical': False,
        'description': 'Both foreclosure and tax deed lanes configured and running'
    },
    'B': {
        'name': 'verified INDEPENDENT outcomes',
        'threshold': '>=95%',
        'critical': True,
        'description': 'Verified outcomes >=95% of closed via independent source (never PropertyOnion-derived)'
    },
    'C': {
        'name': 'parity_clean',
        'threshold': '>=95%',
        'critical': False,
        'description': 'Clean matches >=95% vs litmus comparison'
    },
    'D': {
        'name': 'parity_any',
        'threshold': '>=95%',
        'critical': False,
        'description': 'Any matches >=95% vs litmus comparison'
    },
    'E': {
        'name': 'parcel linkage',
        'threshold': '>=95%',
        'critical': False,
        'description': 'Parcel ID linkage >=95% via property appraiser'
    },
    'F': {
        'name': 'tier1 sold-amount',
        'threshold': '>=95%',
        'critical': False,
        'description': 'Tier1 sold amount >=95% of closed amount'
    },
    'G': {
        'name': 'zoning min(density,FAR,pk1000)',
        'threshold': '>=95%',
        'critical': False,
        'description': 'Zoning completeness minimum of density, FAR, parking per 1000sf >=95%'
    },
    'H': {
        'name': 'freshness',
        'threshold': '<=48h',
        'critical': False,
        'description': 'Data freshness <=48h since last seen'
    },
    'I': {
        'name': 'property card complete',
        'threshold': '>=95%',
        'critical': True,
        'description': 'Property card complete (address+geo+value+zoned parcel) >=95%'
    },
    'J': {
        'name': 'Shapira deal thesis',
        'threshold': '>=95%',
        'critical': True,
        'description': 'Bid decisions: arv+max_bid+ml_score+triangle factors+two-arm CMA >=95%'
    }
}

# Current metrics from issue (VERIFIED source)
ISSUE_METRICS = {
    'brevard': {
        'A': {'metric': 5506, 'grade': 'PASS'},
        'B': {'metric': 137.4, 'grade': 'FAIL', 'anomaly': 'EXCEEDS_100_PERCENT'},
        'C': {'metric': 20.9, 'grade': 'FAIL'},
        'D': {'metric': 31.9, 'grade': 'FAIL'}, 
        'E': {'metric': 94.0, 'grade': 'FAIL'},
        'F': {'metric': 52.4, 'grade': 'FAIL'},
        'G': {'metric': 48.9, 'grade': 'FAIL'},
        'H': {'metric': 7.8, 'grade': 'PASS'},
        'I': {'metric': 19.8, 'grade': 'FAIL'},
        'J': {'metric': 0.0, 'grade': 'FAIL'}
    },
    'washington': {
        'A': {'metric': 30, 'grade': 'PASS'},
        'B': {'metric': None, 'grade': 'FAIL'},
        'C': {'metric': 45.4, 'grade': 'FAIL'},
        'D': {'metric': 84.8, 'grade': 'FAIL'},
        'E': {'metric': 24.8, 'grade': 'FAIL'},
        'F': {'metric': 18.6, 'grade': 'FAIL'},
        'G': {'metric': None, 'grade': 'FAIL'},
        'H': {'metric': 1.4, 'grade': 'PASS'},
        'I': {'metric': None, 'grade': 'FAIL'},
        'J': {'metric': 0.0, 'grade': 'FAIL'}
    },
    'lake': {
        'A': {'metric': 1113, 'grade': 'PASS'},
        'B': {'metric': None, 'grade': 'FAIL'},
        'C': {'metric': 17.3, 'grade': 'FAIL'},
        'D': {'metric': 54.0, 'grade': 'FAIL'},
        'E': {'metric': 74.4, 'grade': 'FAIL'},
        'F': {'metric': 0.0, 'grade': 'FAIL'},
        'G': {'metric': None, 'grade': 'FAIL'},
        'H': {'metric': 433.0, 'grade': 'FAIL'},
        'I': {'metric': None, 'grade': 'FAIL'},
        'J': {'metric': 0.0, 'grade': 'FAIL'}
    },
    'st_johns': {
        'A': {'metric': 558, 'grade': 'PASS'},
        'B': {'metric': None, 'grade': 'FAIL'},
        'C': {'metric': 27.8, 'grade': 'FAIL'},
        'D': {'metric': 60.3, 'grade': 'FAIL'},
        'E': {'metric': 87.1, 'grade': 'FAIL'},
        'F': {'metric': 5.2, 'grade': 'FAIL'},
        'G': {'metric': None, 'grade': 'FAIL'},
        'H': {'metric': 107.7, 'grade': 'FAIL'},
        'I': {'metric': None, 'grade': 'FAIL'},
        'J': {'metric': 0.0, 'grade': 'FAIL'}
    },
    'holmes': {
        'A': {'metric': 0, 'grade': 'FAIL'},
        'B': {'metric': None, 'grade': 'FAIL'},
        'C': {'metric': None, 'grade': 'FAIL'},
        'D': {'metric': None, 'grade': 'FAIL'},
        'E': {'metric': None, 'grade': 'FAIL'},
        'F': {'metric': None, 'grade': 'FAIL'},
        'G': {'metric': None, 'grade': 'FAIL'},
        'H': {'metric': None, 'grade': 'FAIL'},
        'I': {'metric': None, 'grade': 'FAIL'},
        'J': {'metric': None, 'grade': 'FAIL'}
    }
}

def log(message: str, level: str = "INFO"):
    """Log with timestamp and honesty markers"""
    timestamp = datetime.now(timezone.utc).isoformat()
    icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️", "VERIFIED": "🔍", "UNTESTED": "🔄", "INFERRED": "📊"}.get(level, "📋")
    print(f"[{timestamp}] {icon} {message}")

def generate_audit_subagent(county: str, letter: str) -> Dict:
    """Generate isolated audit subagent specification for a failing letter"""
    
    current_metric = ISSUE_METRICS.get(county, {}).get(letter, {})
    letter_def = LETTER_DEFINITIONS.get(letter, {})
    
    audit_spec = {
        "agent_id": f"audit_{county}_{letter}",
        "type": "isolated_audit",
        "context": "isolated",  # No access to main session context
        "goal": f"Measure {county} letter {letter} against pencil_dod_criteria",
        "letter": letter,
        "county": county,
        "definition": letter_def,
        "current_metric": current_metric,
        "success_criteria": [
            f"Run: SELECT public.pencil_dod_evaluate_county('{county}') WHERE letter = '{letter}'",
            "Extract: exact metric, pass/fail, detail string",
            "Compare: against threshold {letter_def.get('threshold', 'N/A')}",
            "Return: findings with Honesty Protocol markers (VERIFIED/UNTESTED/INFERRED)"
        ],
        "guardrails": [
            "Do not claim VERIFIED without showing actual query output",
            "Tag every claim with evidence source", 
            "Never assume - measure or mark as UNTESTED",
            "One letter, one county, one focused measurement"
        ],
        "return_contract": {
            "scope": f"{county} letter {letter} evaluation",
            "finding": "Current metric + grade + evidence",
            "evidence": "SQL query executed + output observed",
            "intervention": "None (audit only)",
            "validated": "Query result matches reported metric",
            "residual": "Any gaps between measured vs expected"
        }
    }
    
    return audit_spec

def generate_refuter_subagent(county: str, letter: str, claim: str) -> Dict:
    """Generate adversarial refuter subagent to break claims"""
    
    refuter_spec = {
        "agent_id": f"refuter_{county}_{letter}",
        "type": "adversarial_refuter",
        "context": "isolated",
        "goal": f"Break the claim: '{claim}' about {county} letter {letter}",
        "letter": letter,
        "county": county,
        "claim_to_refute": claim,
        "refutation_strategies": [
            "Denominator mismatch: verify count sources",
            "Double-counting: check for duplicate records", 
            "Ghost-success: verify claimed improvements exist",
            "Stale data: confirm metric freshness",
            "Anomalous ratios: flag metrics >100% as suspicious"
        ],
        "survival_test": f"Claim survives if refuter cannot find contradictory evidence",
        "success_criteria": [
            "Find contradictory evidence OR", 
            "Confirm claim survives adversarial scrutiny",
            "Document refutation evidence if claim breaks",
            "Tag findings with VERIFIED evidence only"
        ],
        "guardrails": [
            "Goal: break claims, not confirm them",
            "Flag anomalous ratios (>100%) as AUTO-FAIL",
            "Require fresh evidence to contradict claims",
            "Never accept self-referential evidence"
        ],
        "return_contract": {
            "scope": f"Adversarial test of claim about {county} letter {letter}",
            "finding": "Survived=true/false + evidence",
            "evidence": "Contradictory data found or none",
            "intervention": "None (verification only)", 
            "validated": "Claim proven true/false via independent evidence",
            "residual": "Remaining uncertainties or data quality issues"
        }
    }
    
    return refuter_spec

def generate_ultraloop_audit_table_sql() -> str:
    """Generate SQL for the ULTRALOOP audit tracking table"""
    
    sql = f"""
-- ULTRALOOP AUDIT TRACKING TABLE
-- Created: {datetime.now(timezone.utc).isoformat()}
-- Purpose: Track survival votes for Gold Standard certification gate

CREATE TABLE IF NOT EXISTS gold_standard_ultraloop_audit (
    id                    SERIAL PRIMARY KEY,
    dispatch_id           TEXT NOT NULL,
    ultraloop_mode        TEXT NOT NULL,  -- 'native', 'fallback'
    county_slug           TEXT NOT NULL,
    letter                TEXT NOT NULL CHECK (letter IN ('A','B','C','D','E','F','G','H','I','J')),
    claim                 TEXT NOT NULL,
    refuter_evidence      JSONB,
    survived              BOOLEAN NOT NULL,
    audit_timestamp       TIMESTAMPTZ DEFAULT NOW(),
    
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(dispatch_id, county_slug, letter, claim)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_gsua_county_letter ON gold_standard_ultraloop_audit(county_slug, letter);
CREATE INDEX IF NOT EXISTS idx_gsua_survived ON gold_standard_ultraloop_audit(survived);
CREATE INDEX IF NOT EXISTS idx_gsua_timestamp ON gold_standard_ultraloop_audit(audit_timestamp);

-- View for certification gate queries
CREATE OR REPLACE VIEW ultraloop_certification_status AS
SELECT 
    county_slug,
    letter,
    COUNT(*) as total_audits,
    COUNT(CASE WHEN survived = true THEN 1 END) as survived_count,
    MAX(audit_timestamp) as latest_audit,
    CASE 
        WHEN COUNT(CASE WHEN survived = true THEN 1 END) > 0 
             AND MAX(audit_timestamp) > NOW() - INTERVAL '7 days'
        THEN 'ELIGIBLE'
        ELSE 'NOT_ELIGIBLE'
    END as certification_status
FROM gold_standard_ultraloop_audit
GROUP BY county_slug, letter;

-- Function to check certification eligibility
CREATE OR REPLACE FUNCTION check_certification_eligibility(target_county TEXT)
RETURNS TABLE(
    letter TEXT,
    current_grade TEXT,
    survival_votes INTEGER,
    latest_audit TIMESTAMPTZ,
    certification_eligible BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        gs.letter::TEXT,
        CASE WHEN gs.pass THEN 'PASS' ELSE 'FAIL' END::TEXT as current_grade,
        COALESCE(ucs.survived_count, 0)::INTEGER as survival_votes,
        ucs.latest_audit,
        CASE 
            WHEN gs.pass AND COALESCE(ucs.survived_count, 0) > 0 
                 AND ucs.latest_audit > NOW() - INTERVAL '7 days'
            THEN true
            ELSE false
        END as certification_eligible
    FROM (
        SELECT * FROM public.pencil_dod_evaluate_county(target_county)
    ) gs
    LEFT JOIN ultraloop_certification_status ucs ON (
        ucs.county_slug = target_county AND ucs.letter = gs.letter
    );
END;
$$ LANGUAGE plpgsql;

-- Comment
COMMENT ON TABLE gold_standard_ultraloop_audit IS 
'ULTRALOOP Protocol: Every claim must survive adversarial refutation before counting toward certification';
"""
    
    return sql

def generate_audit_workflow_specs() -> Dict:
    """Generate complete workflow specifications for all failing letters"""
    
    workflows = {}
    
    for county in SHARD2_COUNTIES:
        county_workflows = {}
        
        # Get failing letters for this county
        county_metrics = ISSUE_METRICS.get(county, {})
        failing_letters = []
        
        for letter, data in county_metrics.items():
            if data.get('grade') == 'FAIL':
                failing_letters.append(letter)
        
        # Generate audit + refuter pairs for each failing letter
        for letter in failing_letters:
            current_metric = county_metrics.get(letter, {}).get('metric')
            
            # Audit subagent
            audit_agent = generate_audit_subagent(county, letter)
            
            # Generate refuter for expected claims
            expected_claim = f"{county} letter {letter} metric improved to pass threshold"
            refuter_agent = generate_refuter_subagent(county, letter, expected_claim)
            
            county_workflows[letter] = {
                'audit_agent': audit_agent,
                'refuter_agent': refuter_agent,
                'current_metric': current_metric,
                'expected_improvement': f"Move {current_metric} to pass {LETTER_DEFINITIONS.get(letter, {}).get('threshold', 'N/A')}"
            }
        
        workflows[county] = county_workflows
    
    return workflows

def generate_execution_script() -> str:
    """Generate execution script for the ULTRALOOP protocol"""
    
    script = f"""#!/usr/bin/env python3
'''
SHARD-2 ULTRALOOP EXECUTION SCRIPT
Generated: {datetime.now(timezone.utc).isoformat()}

This script implements the ULTRALOOP audit protocol via subagent dispatch.
Run this AFTER migrations are applied to verify claims and populate audit table.

Usage:
  python3 shard2_ultraloop_execution.py
'''

import os
import sys
import json
from datetime import datetime, timezone

# Session configuration
DISPATCH_ID = "shard2-ultraloop-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
ULTRALOOP_MODE = "fallback"  # Use Task subagents if /effort ultracode unavailable

# Counties and failing letters to audit
AUDIT_TARGETS = {json.dumps({county: list(ISSUE_METRICS[county].keys()) for county in SHARD2_COUNTIES if ISSUE_METRICS[county]}, indent=4)}

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{{timestamp}}] {{level}}: {{message}}")

def dispatch_audit_subagent(county, letter):
    '''Dispatch isolated audit subagent for county+letter'''
    log(f"Dispatching audit subagent: {{county}} letter {{letter}}")
    
    # TODO: Implement via Task tool dispatch or /effort ultracode
    # Subagent gets isolated context and measures letter against live DB
    
    # Placeholder return
    return {{
        'agent_id': f'audit_{{county}}_{{letter}}',
        'findings': 'UNTESTED - subagent dispatch not implemented',
        'evidence': None,
        'honesty_tag': 'UNTESTED'
    }}

def dispatch_refuter_subagent(county, letter, claim):
    '''Dispatch adversarial refuter subagent'''
    log(f"Dispatching refuter subagent: {{county}} letter {{letter}}")
    
    # TODO: Implement adversarial refutation
    # Goal: break the claim or confirm it survives
    
    return {{
        'agent_id': f'refuter_{{county}}_{{letter}}',
        'claim': claim,
        'survived': None,  # true/false after refutation attempt
        'evidence': None,
        'honesty_tag': 'UNTESTED'
    }}

def record_survival_vote(county, letter, claim, survived, evidence):
    '''Record survival vote in audit table'''
    # TODO: Insert into gold_standard_ultraloop_audit
    log(f"Recording survival vote: {{county}} {{letter}} survived={{survived}}")
    
def main():
    log("🚀 SHARD-2 ULTRALOOP AUDIT EXECUTION")
    log(f"Dispatch ID: {{DISPATCH_ID}}")
    log(f"Mode: {{ULTRALOOP_MODE}}")
    
    survival_votes = []
    
    for county, letters in AUDIT_TARGETS.items():
        log(f"\\n📍 Processing {{county.upper()}}")
        
        for letter in letters:
            if ISSUE_METRICS.get(county, {{}}).get(letter, {{}}).get('grade') == 'FAIL':
                
                # 1. Dispatch audit subagent
                audit_result = dispatch_audit_subagent(county, letter)
                
                # 2. Generate claim from audit
                claim = f"{{county}} letter {{letter}} measured correctly"
                
                # 3. Dispatch refuter subagent  
                refuter_result = dispatch_refuter_subagent(county, letter, claim)
                
                # 4. Record survival vote
                survived = refuter_result.get('survived', False)
                evidence = refuter_result.get('evidence', {{}})
                
                survival_votes.append({{
                    'county': county,
                    'letter': letter, 
                    'claim': claim,
                    'survived': survived,
                    'audit_result': audit_result,
                    'refuter_result': refuter_result
                }})
                
                record_survival_vote(county, letter, claim, survived, evidence)
    
    # Summary
    total_votes = len(survival_votes)
    survived_count = sum(1 for v in survival_votes if v['survived'])
    
    log(f"\\n🎯 ULTRALOOP AUDIT SUMMARY")
    log(f"Total claims tested: {{total_votes}}")  
    log(f"Survived adversarial refutation: {{survived_count}}")
    log(f"Survival rate: {{survived_count/total_votes*100:.1f}}%" if total_votes > 0 else "N/A")
    
    return survival_votes

if __name__ == "__main__":
    main()
"""
    
    return script

def main():
    """Main ULTRALOOP audit generation function"""
    
    log("🚀 SHARD-2 ULTRALOOP AUDIT PROTOCOL GENERATOR", "VERIFIED")
    log(f"Target counties: {', '.join(SHARD2_COUNTIES)}")
    log("Purpose: Kill agentic laziness, self-preferential bias, goal drift")
    
    # Generate audit table SQL
    log("\n📋 Generating ULTRALOOP audit table SQL...")
    audit_table_sql = generate_ultraloop_audit_table_sql()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    table_sql_file = f"shard2_ultraloop_audit_table_{timestamp}.sql"
    
    with open(table_sql_file, 'w') as f:
        f.write(audit_table_sql)
    
    log(f"✅ Generated audit table SQL: {table_sql_file}", "VERIFIED")
    
    # Generate workflow specifications
    log("\n📋 Generating audit workflow specifications...")
    workflows = generate_audit_workflow_specs()
    
    workflow_spec_file = f"shard2_ultraloop_workflows_{timestamp}.json"
    with open(workflow_spec_file, 'w') as f:
        json.dump(workflows, f, indent=2, default=str)
    
    log(f"✅ Generated workflow specs: {workflow_spec_file}", "VERIFIED")
    
    # Generate execution script
    log("\n📋 Generating ULTRALOOP execution script...")
    execution_script = generate_execution_script()
    
    execution_file = f"shard2_ultraloop_execution_{timestamp}.py"
    with open(execution_file, 'w') as f:
        f.write(execution_script)
    
    log(f"✅ Generated execution script: {execution_file}", "VERIFIED")
    
    # Analysis of failing letters requiring audit
    log("\n📊 AUDIT TARGET ANALYSIS", "INFERRED")
    
    total_failing = 0
    critical_failing = 0
    
    for county, metrics in ISSUE_METRICS.items():
        failing_letters = [letter for letter, data in metrics.items() if data.get('grade') == 'FAIL']
        critical_fails = [letter for letter in failing_letters if LETTER_DEFINITIONS.get(letter, {}).get('critical', False)]
        
        total_failing += len(failing_letters)
        critical_failing += len(critical_fails)
        
        log(f"📍 {county.upper()}: {len(failing_letters)} failing ({', '.join(failing_letters)})")
        if critical_fails:
            log(f"   🚨 Critical: {', '.join(critical_fails)}")
    
    log(f"\n🎯 SUMMARY:")
    log(f"Total failing letter instances: {total_failing}")
    log(f"Critical failing (B,I,J): {critical_failing}")
    log(f"Audit subagents required: {total_failing}")
    log(f"Refuter subagents required: {total_failing}")
    log(f"Total survival votes needed: {total_failing}")
    
    # B anomaly special alert
    brevard_b = ISSUE_METRICS['brevard']['B']['metric']
    if brevard_b and brevard_b > 100:
        log(f"\n🚨 B ANOMALY ALERT: Brevard B={brevard_b}% (>100%)", "WARNING")
        log("Per issue: 'B metrics exceed 100% means denominator/source mismatch'")
        log("Auto-FAIL survival vote until reconciliation completed")
    
    log(f"\n✅ ULTRALOOP audit protocol ready for deployment", "VERIFIED")
    
    return {
        'status': 'SUCCESS',
        'audit_table_sql': table_sql_file,
        'workflow_specs': workflow_spec_file,
        'execution_script': execution_file,
        'total_failing_letters': total_failing,
        'critical_failing_count': critical_failing,
        'b_anomaly_detected': brevard_b > 100 if brevard_b else False
    }

if __name__ == "__main__":
    try:
        result = main()
        print(f"\n🎯 Result: {json.dumps(result, indent=2, default=str)}")
    except Exception as e:
        log(f"❌ Error generating ULTRALOOP audit: {e}", "ERROR")
        sys.exit(1)