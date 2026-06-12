#!/usr/bin/env python3
"""
SHARD-19 ULTRALOOP Verification Protocol
Implements adversarial verification per issue brief directives

ULTRALOOP Protocol (per 2026-06-12 brief):
1. FAN-OUT-AND-SYNTHESIZE: Subagent per failing letter per county
2. ADVERSARIAL SURVIVAL VOTE: Independent refuter for each claim  
3. FIX = LOOP-UNTIL-DONE: Against live gold_standard_county_status
4. SAVE WORKFLOWS: Reusable artifacts for resumable execution

Usage:
  python scripts/shard19_ultraloop_verification.py
"""
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

class ULTRALOOPVerification:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.results = {
            "session_info": {
                "protocol": "ULTRALOOP", 
                "start_time": self.start_time.isoformat(),
                "counties": SHARD19_COUNTIES,
                "objective": "Adversarial verification per issue brief"
            },
            "fan_out_audits": {},
            "adversarial_votes": {},
            "survival_results": {},
            "verification_evidence": []
        }

    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")

    def fan_out_letter_audits(self):
        """Phase 1: Fan out subagent per failing letter per county"""
        self.log("🔄 ULTRALOOP Phase 1: Fan-out letter audits")
        
        # Target letters per county from issue brief
        target_letters = {
            "charlotte": ["B", "C", "E", "F", "G", "I", "J"],  # 3/10 passing
            "citrus": ["B", "C", "D", "F", "G", "I", "J"],    # 3/10 passing  
            "broward": ["B", "C", "D", "E", "F", "G", "I", "J"]  # 2/10 passing
        }
        
        fan_out_audits = {}
        
        for county in SHARD19_COUNTIES:
            county_audits = {}
            
            for letter in target_letters[county]:
                # Isolated context audit per letter
                letter_audit = {
                    "letter": letter,
                    "county": county,
                    "audit_goal": f"Measure Letter {letter} against pencil_dod_criteria from live tables",
                    "context": "ISOLATED - one focused goal only",
                    "required_evidence": "SQL query output with Honesty Protocol markers",
                    "claims_to_verify": self.get_letter_claims(letter, county),
                    "audit_status": "FRAMEWORK_READY"
                }
                
                county_audits[letter] = letter_audit
            
            fan_out_audits[county] = county_audits
        
        self.results["fan_out_audits"] = fan_out_audits
        self.log("✅ Fan-out audits configured")
        return fan_out_audits

    def get_letter_claims(self, letter, county):
        """Get specific claims to verify for each letter"""
        
        claims_map = {
            "B": [
                "Independent verified outcomes data source exists",
                "Verified outcomes table populated with clerk records",
                "B metric >95% via independent source (not PropertyOnion)"
            ],
            "C": [
                "Parity clean rate >95% with supplementary litmus",
                "Case number normalization applied", 
                "Supplementary clerk sources integrated"
            ],
            "D": [
                "Parity any rate >95% with enhanced matching",
                "Address normalization implemented",
                "Fuzzy matching with splink applied"
            ],
            "E": [
                "Parcel linkage >95% via county appraiser ArcGIS",
                "Parcel IDs populated in multi_county_auctions",
                "Similarity scoring enhanced"
            ],
            "F": [
                "Tier1 sold amounts verified via independent sources",
                "Winning bid data from clerk records",
                "F metric >95% via tier1 promotion"
            ],
            "G": [
                "Zoning districts populated for all jurisdictions",
                "Zone standards with density/FAR/parking values", 
                "v_zoning_gold_standard_kpi_v3 returns data"
            ],
            "I": [
                "Property cards enriched with address/geo/value/zoned parcel",
                "I metric >95% via v_zoning_gold_standard_card",
                "Parcel linkage dependency satisfied (E)"
            ],
            "J": [
                "bid_decisions table populated with complete records",
                "Shapira V14 ml_score pipeline functional",
                "Triangle factors + CMA data complete per evaluator contract"
            ]
        }
        
        return claims_map.get(letter, [f"Letter {letter} claims need definition"])

    def execute_adversarial_votes(self):
        """Phase 2: Adversarial survival vote per claim"""
        self.log("⚔️ ULTRALOOP Phase 2: Adversarial survival votes")
        
        adversarial_votes = {}
        
        for county, audits in self.results["fan_out_audits"].items():
            county_votes = {}
            
            for letter, audit in audits.items():
                letter_votes = {}
                
                for claim in audit["claims_to_verify"]:
                    # Independent refuter subagent per claim
                    refuter_analysis = {
                        "claim": claim,
                        "refuter_goal": "Break claim with evidence", 
                        "refuter_approach": "Independent subagent - isolated context",
                        "evidence_requirement": "SQL query contradicting claim",
                        "methodology": "Find denominator mismatches, double-counting, ghost-success, stale source",
                        "survival_threshold": "Claim ships ONLY if refutation attempts fail",
                        "refutation_evidence": self.generate_refutation_analysis(claim, letter, county),
                        "survived": self.determine_survival(claim, letter, county)
                    }
                    
                    letter_votes[claim] = refuter_analysis
                
                county_votes[letter] = letter_votes
            
            adversarial_votes[county] = county_votes
        
        self.results["adversarial_votes"] = adversarial_votes
        self.log("✅ Adversarial votes executed")
        return adversarial_votes

    def generate_refutation_analysis(self, claim, letter, county):
        """Generate refutation analysis for a claim"""
        
        # Framework refutation patterns based on issue brief examples
        refutation_patterns = {
            "Independent verified outcomes": {
                "potential_breaks": [
                    "PropertyOnion-derived data_source (HARD FAIL per canon)",
                    "Zero rows in verified outcomes table",
                    "No clerk source integration"
                ],
                "sql_tests": [
                    "SELECT count(*) FROM foreclosure_outcomes_{county}",
                    "SELECT DISTINCT data_source FROM foreclosure_outcomes_{county}",
                    "CHECK: No PropertyOnion-derived sources"
                ]
            },
            "Parity": {
                "potential_breaks": [
                    "B>100% anomaly (verified=8547 > closed_sold=6373 pattern)",
                    "Denominator/source mismatch",
                    "PropertyOnion still sole litmus (no supplementary)"
                ],
                "sql_tests": [
                    "SELECT verified_outcomes, closed_sold FROM gold_standard_county_status WHERE county_slug='{county}'",
                    "CHECK: Ratio anomalies indicate double-count or scope mismatch"
                ]
            },
            "Zoning substrate": {
                "potential_breaks": [
                    "Zero districts in zoning_districts table",
                    "NULL density/FAR values in zone_standards", 
                    "v_zoning_gold_standard_kpi_v3 returns empty"
                ],
                "sql_tests": [
                    "SELECT count(*) FROM zoning_districts zd JOIN jurisdictions j ON zd.jurisdiction_id = j.id WHERE j.county = '{county.title()}'",
                    "SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county_slug = '{county}'"
                ]
            }
        }
        
        # Pattern matching for refutation
        for pattern_key, pattern in refutation_patterns.items():
            if any(keyword in claim.lower() for keyword in pattern_key.lower().split()):
                return {
                    "matched_pattern": pattern_key,
                    "potential_breaks": pattern["potential_breaks"],
                    "sql_tests": [sql.format(county=county) for sql in pattern["sql_tests"]],
                    "analysis_status": "FRAMEWORK_READY"
                }
        
        # Default refutation framework
        return {
            "matched_pattern": "generic",
            "potential_breaks": ["Implementation not complete", "No live data verification"],
            "sql_tests": [f"-- Framework test needed for: {claim}"],
            "analysis_status": "NEEDS_SPECIFIC_IMPLEMENTATION"
        }

    def determine_survival(self, claim, letter, county):
        """Determine if claim survives refutation"""
        
        # Per issue brief: Claims ship ONLY if refutation attempts fail
        # Currently all claims are framework-only, so survival = false (honest assessment)
        
        survival_analysis = {
            "survived": False,  # Honest: framework only, no live implementation
            "reason": "Framework implementation only - no live database verification",
            "evidence_level": "UNTESTED",
            "honesty_marker": "FRAMEWORK_READY - requires live execution for survival",
            "certification_blocker": True
        }
        
        return survival_analysis

    def log_ultraloop_audit_entries(self):
        """Log entries to gold_standard_ultraloop_audit table (framework)"""
        self.log("📝 Logging ULTRALOOP audit entries")
        
        audit_entries = []
        
        for county, votes in self.results["adversarial_votes"].items():
            for letter, letter_votes in votes.items():
                for claim, analysis in letter_votes.items():
                    
                    entry = {
                        "dispatch_id": "536a7475-ed3b-45bc-a5cd-e79e1ec74765",  # From issue brief
                        "ultraloop_mode": "framework",  # vs "native" 
                        "county_slug": county,
                        "letter": letter,
                        "claim": claim,
                        "refuter_evidence": analysis["refutation_evidence"],
                        "survived": analysis["survived"]["survived"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    
                    audit_entries.append(entry)
        
        self.results["audit_entries"] = audit_entries
        self.log(f"✅ {len(audit_entries)} ULTRALOOP audit entries prepared")
        
        return audit_entries

    def save_reusable_workflows(self):
        """Phase 4: Save workflows as reusable artifacts"""
        self.log("💾 Saving reusable ULTRALOOP workflows")
        
        # Create .claude/ workflow artifacts for resumable execution
        claude_dir = project_root / ".claude"
        workflow_dir = claude_dir / "workflows" / "ultraloop"
        
        try:
            workflow_dir.mkdir(parents=True, exist_ok=True)
            
            # Save workflow definitions
            workflow_artifacts = {
                "fan_out_config.json": self.results["fan_out_audits"],
                "adversarial_vote_patterns.json": {
                    "refutation_patterns": "See generate_refutation_analysis method",
                    "survival_thresholds": "100% survival required for certification"
                },
                "audit_entry_template.json": {
                    "schema": "dispatch_id, ultraloop_mode, county_slug, letter, claim, refuter_evidence, survived",
                    "table": "gold_standard_ultraloop_audit"
                }
            }
            
            saved_workflows = []
            for filename, data in workflow_artifacts.items():
                workflow_file = workflow_dir / filename
                
                with open(workflow_file, "w") as f:
                    json.dump(data, f, indent=2, default=str)
                
                saved_workflows.append(str(workflow_file))
                self.log(f"✅ Workflow saved: {workflow_file}")
            
            self.results["saved_workflows"] = saved_workflows
            
        except Exception as e:
            self.log(f"❌ Workflow saving failed: {e}", "ERROR")
            self.results["saved_workflows"] = []

    def execute_ultraloop_protocol(self):
        """Execute complete ULTRALOOP verification protocol"""
        self.log("🚀 SHARD-19 ULTRALOOP Verification Protocol Starting")
        
        # Phase 1: Fan-out audits
        fan_out_results = self.fan_out_letter_audits()
        
        # Phase 2: Adversarial votes
        adversarial_results = self.execute_adversarial_votes()
        
        # Phase 3: Log audit entries
        audit_entries = self.log_ultraloop_audit_entries()
        
        # Phase 4: Save workflows
        self.save_reusable_workflows()
        
        # Summary
        survival_summary = self.generate_survival_summary()
        
        self.results["protocol_summary"] = {
            "total_claims_tested": sum(len(votes) for county_votes in adversarial_results.values() for letter_votes in county_votes.values() for votes in letter_votes.values()),
            "survived_claims": sum(1 for county_votes in adversarial_results.values() for letter_votes in county_votes.values() for votes in letter_votes.values() for analysis in votes.values() if analysis["survived"]["survived"]),
            "certification_status": "BLOCKED" if any(not analysis["survived"]["survived"] for county_votes in adversarial_results.values() for letter_votes in county_votes.values() for votes in letter_votes.values() for analysis in votes.values()) else "READY",
            "blocking_reason": "Framework implementation only - requires live execution",
            "next_steps": [
                "1. Apply database migrations to live Supabase",
                "2. Execute scrapers to populate data",
                "3. Re-run ULTRALOOP with live data verification",
                "4. Achieve 100% claim survival for certification"
            ]
        }
        
        return self.results

    def generate_survival_summary(self):
        """Generate survival summary per county and letter"""
        
        survival_summary = {}
        
        for county, votes in self.results["adversarial_votes"].items():
            county_summary = {}
            
            for letter, letter_votes in votes.items():
                total_claims = len(letter_votes)
                survived_claims = sum(1 for analysis in letter_votes.values() if analysis["survived"]["survived"])
                
                county_summary[letter] = {
                    "total_claims": total_claims,
                    "survived_claims": survived_claims,
                    "survival_rate": (survived_claims / total_claims * 100) if total_claims > 0 else 0,
                    "certification_ready": survived_claims == total_claims
                }
            
            survival_summary[county] = county_summary
        
        self.results["survival_summary"] = survival_summary
        return survival_summary

def main():
    """Main execution for SHARD-19 ULTRALOOP verification"""
    verifier = ULTRALOOPVerification()
    
    try:
        results = verifier.execute_ultraloop_protocol()
        
        # Session completion
        session_end = datetime.now(timezone.utc) 
        session_duration = (session_end - verifier.start_time).total_seconds()
        
        results["session_info"]["end_time"] = session_end.isoformat()
        results["session_info"]["duration_seconds"] = session_duration
        
        # Final results
        print("\n" + "="*80)
        print("SHARD-19 ULTRALOOP VERIFICATION PROTOCOL")
        print("="*80)
        print(json.dumps(results, indent=2, default=str))
        
        verifier.log(f"✅ ULTRALOOP protocol complete ({session_duration:.1f}s)")
        verifier.log(f"🎯 Certification Status: {results['protocol_summary']['certification_status']}")
        
        # Return based on certification readiness
        certification_ready = results['protocol_summary']['certification_status'] == "READY"
        return 0 if certification_ready else 1
        
    except Exception as e:
        verifier.log(f"❌ CRITICAL ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())