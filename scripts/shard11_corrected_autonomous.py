#!/usr/bin/env python3
"""
SHARD-11 Gold Standard Autonomous Campaign - CORRECTED COUNTIES
Counties: manatee, clay, pasco, gadsden, wakulla

Based on issue #7682 assignment, correcting from previous scripts that used wrong counties.
Implements evidence-before-claims protocol and ship-to-main mandate.

Usage:
  python scripts/shard11_corrected_autonomous.py
"""
import os
import requests
import json
import time
from datetime import datetime, timezone

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# CORRECTED SHARD-11 counties from issue #7682
SHARD11_COUNTIES = ['manatee', 'clay', 'pasco', 'gadsden', 'wakulla']

# Brevard Sprint Order priorities (highest to lowest leverage)
PRIORITY_ORDER = [
    "C_D_ROOT_CAUSE",     # C/D parity audit - all counties failing
    "J_GENERATOR",        # bid_decisions pipeline - 0% across board  
    "G_HIT_LIST",         # zone_standards backfill
    "B_RECONCILIATION"    # verified_outcomes anomaly fixes
]

class SHARD11CorrectedCampaign:
    def __init__(self):
        self.session_start = datetime.now(timezone.utc)
        self.results = {}
        self.verification_evidence = []
        self.commits_made = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def test_connection(self):
        """Test Supabase connection - VERIFIED approach"""
        try:
            if not SUPABASE_KEY:
                self.log("❌ No SUPABASE_KEY in environment", "ERROR") 
                return False
                
            response = requests.get(
                f"{BASE}/multi_county_auctions", 
                headers=HEADERS, 
                params={"select": "count", "limit": "1"}, 
                timeout=10
            )
            
            if response.status_code == 200:
                self.log("✅ Supabase connection successful")
                return True
            else:
                self.log(f"❌ Connection failed: {response.status_code}", "ERROR")
                self.log(f"Response: {response.text[:200]}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Connection error: {e}", "ERROR")
            return False
    
    def get_county_evaluation(self, county):
        """Get current evaluation for a county - VERIFIED with SQL evidence"""
        try:
            # Try different parameter formats that exist in the codebase
            for param_key in ["county_slug_arg", "county_name"]:
                payload = {param_key: county}
                response = requests.post(
                    f"{BASE}/rpc/pencil_dod_evaluate_county", 
                    headers=HEADERS, 
                    json=payload,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Store verification evidence
                    evidence = {
                        "query": f"SELECT public.pencil_dod_evaluate_county('{county}')",
                        "parameter_used": param_key,
                        "result": result,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "status": "VERIFIED"
                    }
                    self.verification_evidence.append(evidence)
                    
                    self.log(f"✅ Evaluated {county} using parameter '{param_key}'")
                    return result
                    
                self.log(f"⚠️ Parameter '{param_key}' failed for {county}: {response.status_code}")
            
            # If both approaches fail, log the error
            self.log(f"❌ All parameter formats failed for {county}", "ERROR")
            return None
                
        except Exception as e:
            self.log(f"❌ Error evaluating {county}: {e}", "ERROR")
            return None
    
    def analyze_failing_letters(self, county, evaluation):
        """Analyze failing letters and determine priority - INFERRED from evaluation"""
        if not evaluation:
            return {
                "priority": "BASIC_SETUP", 
                "failing_letters": ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
                "reason": "No evaluation data - likely missing basic auction ingestion"
            }
            
        failing_letters = []
        
        # Handle different response formats
        if isinstance(evaluation, list):
            # Format: list of letter objects
            for letter_data in evaluation:
                letter = letter_data.get('letter')
                passes = letter_data.get('pass', False) or letter_data.get('grade') == 'PASS'
                if not passes:
                    failing_letters.append(letter)
        else:
            # Format: single object with grade fields
            for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
                grade_field = f"grade_{letter.lower()}"
                if evaluation.get(grade_field) != "PASS":
                    failing_letters.append(letter)
        
        # Determine priority based on Brevard Sprint Order
        if 'C' in failing_letters or 'D' in failing_letters:
            return {
                "priority": "C_D_ROOT_CAUSE", 
                "failing_letters": failing_letters,
                "reason": "Parity audit needed - PropertyOnion coverage issue"
            }
        elif 'J' in failing_letters:
            return {
                "priority": "J_GENERATOR", 
                "failing_letters": failing_letters,
                "reason": "bid_decisions pipeline missing - 0% deal completion"
            }
        elif 'G' in failing_letters:
            return {
                "priority": "G_HIT_LIST", 
                "failing_letters": failing_letters,
                "reason": "Zone standards NULL values need ordinance text extraction"
            }
        elif 'B' in failing_letters:
            return {
                "priority": "B_RECONCILIATION", 
                "failing_letters": failing_letters,
                "reason": "verified_outcomes > closed_sold anomaly (>100% ratio)"
            }
        else:
            return {
                "priority": "MAINTENANCE", 
                "failing_letters": failing_letters,
                "reason": "Minor fixes or already passing"
            }
    
    def execute_c_d_root_cause(self, counties_needing_fix):
        """Execute C/D parity audit and PropertyOnion supplementary litmus - UNTESTED"""
        self.log("🔍 Executing C/D ROOT CAUSE: PropertyOnion coverage vs parity audit")
        
        # Framework for implementing the pre-authorized supplementary litmus
        implementation_plan = {
            "status": "FRAMEWORK_READY",
            "evidence_required": "VERIFIED",
            "next_steps": [
                "Audit PropertyOnion source coverage vs our matcher results",
                "Document evidence of PropertyOnion coverage gaps",
                "Implement clerk/official-records as supplementary litmus source", 
                "Backfill missing matches using official records",
                "Re-run parity evaluation to verify C/D metric improvements"
            ],
            "counties_affected": counties_needing_fix,
            "authorization": "Pre-authorized by Ariel 2026-06-12 - no re-approval needed"
        }
        
        self.log("📋 C/D implementation plan prepared")
        return implementation_plan
    
    def execute_j_generator(self, counties_needing_fix):
        """Execute J generator - bid_decisions pipeline - UNTESTED"""
        self.log("🎯 Executing J GENERATOR: bid_decisions pipeline")
        
        implementation_plan = {
            "status": "FRAMEWORK_READY", 
            "evidence_required": "VERIFIED",
            "next_steps": [
                "Build bid_decisions table populator to evaluator contract",
                "Integrate Shapira V14 ml_score (shapira_models, AUC .78)",
                "Connect gen_valuations_comps_batch for CMA inputs",
                "Implement required fields: arv + max_bid + ml_score + factors",
                "Ensure factors contain: distress_location, distress_property, distress_owner, cma_distressed, cma_resale",
                "Match by case_number to multi_county_auctions",
                "Re-run evaluation to verify J metric moves from 0%"
            ],
            "counties_affected": counties_needing_fix,
            "contract": "Evaluator expects bid_decisions row matched by case_number with ALL required fields"
        }
        
        self.log("📋 J generator implementation plan prepared")
        return implementation_plan
    
    def ship_to_main_commit(self, changes_summary):
        """Commit changes directly to main - following ship-to-main mandate"""
        try:
            # This would be where we commit the actual implementation
            # For now, tracking the framework and evidence preparation
            commit_message = f"""
Gold Standard SHARD-11: {changes_summary}

Counties: {', '.join(SHARD11_COUNTIES)}
Session: {self.session_start.isoformat()}

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
""".strip()
            
            # Add to commit tracking
            self.commits_made.append({
                "message": commit_message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "changes": changes_summary,
                "status": "PLANNED"  # Would be "EXECUTED" when actually committed
            })
            
            self.log(f"📝 Planned commit: {changes_summary}")
            return True
            
        except Exception as e:
            self.log(f"❌ Commit planning error: {e}", "ERROR")
            return False
    
    def run_campaign(self):
        """Execute the corrected SHARD-11 campaign"""
        self.log("🚀 SHARD-11 Gold Standard Campaign - CORRECTED COUNTIES")
        self.log(f"Counties: {', '.join(SHARD11_COUNTIES)}")
        self.log(f"Session start: {self.session_start.isoformat()}")
        
        # PHASE 1: Database Connection (Evidence-Before-Claims)
        if not self.test_connection():
            self.log("❌ Campaign aborted - no database connection", "ERROR")
            return {"status": "FAILED", "reason": "NO_DATABASE_CONNECTION"}
        
        # PHASE 2: County Verification (VERIFIED approach)
        self.log("📊 PHASE 2: County Verification with SQL Evidence")
        county_evaluations = {}
        
        for county in SHARD11_COUNTIES:
            self.log(f"Evaluating {county}...")
            evaluation = self.get_county_evaluation(county)
            county_evaluations[county] = evaluation
            
            if evaluation:
                # Extract score from evaluation
                if isinstance(evaluation, list) and len(evaluation) > 0:
                    pass_count = sum(1 for item in evaluation if item.get('pass') or item.get('grade') == 'PASS')
                    self.log(f"✅ {county}: {pass_count}/10 letters passing")
                else:
                    self.log(f"✅ {county}: evaluation completed (format: {type(evaluation)})")
            else:
                self.log(f"❌ {county}: evaluation failed")
        
        # PHASE 3: Priority Analysis (INFERRED from data)
        self.log("🎯 PHASE 3: Priority Analysis per Brevard Sprint Order")
        priority_analysis = {}
        
        for county, evaluation in county_evaluations.items():
            analysis = self.analyze_failing_letters(county, evaluation)
            priority_analysis[county] = analysis
            self.log(f"{county}: {analysis['priority']} - {analysis['reason']}")
        
        # PHASE 4: Implementation Planning (UNTESTED - Framework only)
        self.log("⚙️ PHASE 4: Implementation Framework")
        implementation_plans = {}
        
        # Group counties by priority
        priorities_grouped = {}
        for county, analysis in priority_analysis.items():
            priority = analysis['priority']
            if priority not in priorities_grouped:
                priorities_grouped[priority] = []
            priorities_grouped[priority].append(county)
        
        # Execute by priority order
        for priority in PRIORITY_ORDER:
            if priority in priorities_grouped:
                counties = priorities_grouped[priority]
                self.log(f"🔧 Processing {priority} for counties: {', '.join(counties)}")
                
                if priority == "C_D_ROOT_CAUSE":
                    plan = self.execute_c_d_root_cause(counties)
                elif priority == "J_GENERATOR":
                    plan = self.execute_j_generator(counties)
                else:
                    plan = {"status": "FRAMEWORK_PENDING", "counties": counties}
                
                implementation_plans[priority] = plan
                
                # Ship framework to main
                self.ship_to_main_commit(f"{priority} framework for {len(counties)} counties")
        
        # PHASE 5: Final Results
        campaign_results = {
            "session_info": {
                "start": self.session_start.isoformat(),
                "end": datetime.now(timezone.utc).isoformat(),
                "counties": SHARD11_COUNTIES,
                "status": "FRAMEWORK_COMPLETE"
            },
            "verification_evidence": self.verification_evidence,
            "county_evaluations": county_evaluations, 
            "priority_analysis": priority_analysis,
            "implementation_plans": implementation_plans,
            "commits_planned": self.commits_made,
            "next_session_priorities": [
                "Execute C/D parity audit with PropertyOnion evidence",
                "Implement J generator bid_decisions pipeline",
                "Run verification protocol to confirm metric movements",
                "Complete ULTRALOOP audit for all claims"
            ]
        }
        
        self.log("✅ SHARD-11 Campaign Framework Complete")
        self.log(f"📊 Evidence collected: {len(self.verification_evidence)} SQL verifications")
        self.log(f"📋 Implementation plans: {len(implementation_plans)} priorities identified")
        
        return campaign_results

def main():
    """Main entry point"""
    campaign = SHARD11CorrectedCampaign()
    results = campaign.run_campaign()
    
    # Save results for analysis
    output_file = "/tmp/shard11_corrected_campaign_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print("\n" + "="*80)
    print("SHARD-11 CORRECTED CAMPAIGN RESULTS")
    print("="*80)
    print(json.dumps(results, indent=2, default=str))
    
    return results

if __name__ == "__main__":
    main()