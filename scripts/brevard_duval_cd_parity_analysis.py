#!/usr/bin/env python3
"""
Brevard & Duval C/D Parity Root Cause Analysis
Implements pre-authorized clerk/official-records litmus adoption per session brief

Background:
- Brevard C=20.9, D=34.0 (numerators frozen ~4.1K/6.6K while denominator grew 33%)
- Duval C=16.1, D=52.9 (worse than brevard, same pattern)
- Root cause: PropertyOnion coverage gap vs actual closed auctions
- Pre-authorized solution: Adopt clerk/official-records as supplementary litmus
"""
import os
import sys
import json
import requests
from datetime import datetime, timezone

# Database configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

class CDParityAnalysis:
    def __init__(self):
        self.findings = {}
        self.evidence = []
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
    
    def query_db(self, query, description):
        """Execute SQL query and log evidence"""
        try:
            # For complex queries, we need to use RPC or direct SQL execution
            # This is a template - actual implementation would use appropriate endpoint
            self.log(f"🔍 {description}")
            self.log(f"SQL: {query}")
            
            # Store evidence for ULTRALOOP audit
            evidence = {
                "description": description,
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "UNTESTED"  # Honesty protocol - marking as untested until DB access available
            }
            self.evidence.append(evidence)
            
            self.log("⏳ Query logged for execution when DB access available")
            return None
            
        except Exception as e:
            self.log(f"❌ Error: {e}", "ERROR")
            return None
    
    def analyze_brevard_cd_gap(self):
        """Analyze Brevard C/D parity gaps"""
        self.log("🔍 Analyzing Brevard C/D Parity Gap...")
        
        # Query 1: Count matched vs total auctions
        brevard_counts_query = """
        SELECT 
            county_slug,
            COUNT(*) as total_auctions,
            COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_clean,
            COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) as matched_any,
            ROUND(100.0 * COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) / COUNT(*), 2) as pct_clean,
            ROUND(100.0 * COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) / COUNT(*), 2) as pct_any
        FROM multi_county_auctions 
        WHERE county_slug = 'brevard'
          AND created_at >= '2024-01-01'  -- Recent data
        GROUP BY county_slug;
        """
        
        self.query_db(brevard_counts_query, "Brevard C/D current parity counts")
        
        # Query 2: PropertyOnion vs actual closed auction counts  
        brevard_source_analysis = """
        SELECT 
            data_source,
            COUNT(*) as auction_count,
            COUNT(CASE WHEN auction_status = 'closed' THEN 1 END) as closed_count,
            COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_count
        FROM multi_county_auctions 
        WHERE county_slug = 'brevard'
          AND created_at >= '2024-01-01'
        GROUP BY data_source
        ORDER BY auction_count DESC;
        """
        
        self.query_db(brevard_source_analysis, "Brevard data source breakdown vs PropertyOnion coverage")
        
        # Query 3: Identify unmatched closed auctions (gap candidates)
        brevard_gap_analysis = """
        SELECT 
            case_number,
            auction_date,
            auction_status,
            parity_status,
            data_source,
            property_address
        FROM multi_county_auctions 
        WHERE county_slug = 'brevard'
          AND auction_status = 'closed'
          AND parity_status IS NULL OR parity_status NOT IN ('matched_clean', 'matched_divergent')
        ORDER BY auction_date DESC
        LIMIT 100;
        """
        
        self.query_db(brevard_gap_analysis, "Brevard unmatched closed auctions (C/D gap candidates)")
        
        self.findings['brevard'] = {
            "current_metrics": {"C": 20.9, "D": 34.0},
            "hypothesis": "PropertyOnion coverage gap - numerators frozen while denominator grew",
            "evidence_status": "UNTESTED - queries prepared for DB access"
        }
    
    def analyze_duval_cd_gap(self):
        """Analyze Duval C/D parity gaps"""
        self.log("🔍 Analyzing Duval C/D Parity Gap...")
        
        # Query 1: Count matched vs total auctions
        duval_counts_query = """
        SELECT 
            county_slug,
            COUNT(*) as total_auctions,
            COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_clean,
            COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) as matched_any,
            ROUND(100.0 * COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) / COUNT(*), 2) as pct_clean,
            ROUND(100.0 * COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) / COUNT(*), 2) as pct_any
        FROM multi_county_auctions 
        WHERE county_slug = 'duval'
          AND created_at >= '2024-01-01'
        GROUP BY county_slug;
        """
        
        self.query_db(duval_counts_query, "Duval C/D current parity counts")
        
        # Query 2: PropertyOnion ID analysis (per session brief - 8,979 of 9,336 carry PO-xxxxxx)
        duval_po_analysis = """
        SELECT 
            CASE 
                WHEN case_number LIKE 'PO-%' THEN 'PropertyOnion_ID'
                WHEN case_number ~ '^[0-9]{2}-[0-9]+' THEN 'Court_Format'
                ELSE 'Other_Format'
            END as case_number_format,
            COUNT(*) as count,
            COUNT(CASE WHEN auction_status = 'closed' THEN 1 END) as closed,
            COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as matched_clean,
            COUNT(CASE WHEN parcel_id IS NOT NULL THEN 1 END) as has_parcel_id
        FROM multi_county_auctions 
        WHERE county_slug = 'duval'
          AND created_at >= '2024-01-01'
        GROUP BY 1
        ORDER BY count DESC;
        """
        
        self.query_db(duval_po_analysis, "Duval PropertyOnion ID format analysis (PO-xxxxxx vs court format)")
        
        # Query 3: Parcel ID repair candidates
        duval_repair_candidates = """
        SELECT 
            case_number,
            auction_date,
            auction_status,
            parity_status,
            parcel_id,
            property_address
        FROM multi_county_auctions 
        WHERE county_slug = 'duval'
          AND case_number LIKE 'PO-%'
          AND parcel_id IS NOT NULL
          AND auction_status = 'closed'
        ORDER BY auction_date DESC
        LIMIT 50;
        """
        
        self.query_db(duval_repair_candidates, "Duval PO→court case number repair candidates")
        
        self.findings['duval'] = {
            "current_metrics": {"C": 16.1, "D": 52.9},
            "hypothesis": "PropertyOnion IDs can never match official records - worse than Brevard",
            "po_id_issue": "8,979 of 9,336 closed rows carry PO-xxxxxx case numbers",
            "repair_strategy": "PO→court case_number via Duval clerk tax-deed file lookup by parcel_id+sale date",
            "evidence_status": "UNTESTED - queries prepared for DB access"
        }
    
    def design_clerk_records_integration(self):
        """Design clerk/official records integration per pre-authorization"""
        self.log("🏗️ Designing Clerk Records Integration...")
        
        integration_plan = {
            "brevard": {
                "source": "Brevard Clerk courthouse foreclosure calendar",
                "endpoint": "UNTESTED - need to verify Brevard AcclaimWeb endpoint", 
                "approach": "Port Duval Acclaim pipeline to Brevard",
                "data_types": ["Certificates of Title", "Sale amounts", "Case numbers"],
                "match_strategy": "case_number to multi_county_auctions (source_platform=clerk_brevard)",
                "benefits": "Moves B and F together (one pipeline)"
            },
            "duval": {
                "source": "Duval clerk tax-deed records",
                "current_infrastructure": "AcclaimWeb pipeline exists, needs enhancement",
                "repair_strategy": "PO→court case_number lookup via parcel_id+sale_date",
                "data_available": "18,156 PO rows have parcel_id for lookup",
                "implementation": "Enhance existing Duval clerk record matching"
            },
            "shared_benefits": {
                "independent_source": "Clerk records are independent of PropertyOnion",
                "b_letter_fix": "Independent verified outcomes",
                "cd_parity_fix": "Official case numbers enable proper matching",
                "f_letter_bonus": "Sale amounts from official records"
            }
        }
        
        self.findings['integration_plan'] = integration_plan
        self.log("✅ Clerk records integration plan documented")
    
    def generate_implementation_roadmap(self):
        """Generate implementation roadmap for C/D fixes"""
        self.log("📋 Generating Implementation Roadmap...")
        
        roadmap = {
            "phase_1_verification": {
                "brevard": [
                    "Execute brevard_counts_query to confirm current C/D metrics",
                    "Execute brevard_source_analysis to confirm PropertyOnion coverage gap", 
                    "Execute brevard_gap_analysis to identify unmatched closed auctions"
                ],
                "duval": [
                    "Execute duval_counts_query to confirm current C/D metrics",
                    "Execute duval_po_analysis to confirm PO-xxxxxx issue scope",
                    "Execute duval_repair_candidates to identify high-value repair targets"
                ]
            },
            "phase_2_implementation": {
                "brevard": [
                    "Verify Brevard AcclaimWeb endpoint availability",
                    "Port Duval acclaim_* functions to Brevard (county parameterization)",
                    "Backfill last 24 months Certificates of Title",
                    "Match CT case numbers to multi_county_auctions"
                ],
                "duval": [
                    "Enhance existing Duval acclaim pipeline",
                    "Implement PO→court case_number repair via parcel_id lookup",
                    "Backfill repaired case numbers to enable parity matching"
                ]
            },
            "phase_3_verification": {
                "success_criteria": [
                    "Brevard C ≥95% (from 20.9%)",
                    "Brevard D ≥95% (from 34.0%)", 
                    "Duval C ≥95% (from 16.1%)",
                    "Duval D ≥95% (from 52.9%)"
                ],
                "verification_method": "pencil_dod_evaluate_county() before/after comparison"
            }
        }
        
        self.findings['roadmap'] = roadmap
        self.log("✅ Implementation roadmap complete")
    
    def export_findings(self):
        """Export findings for ULTRALOOP audit"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"brevard_duval_cd_parity_analysis_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                "counties": ["brevard", "duval"],
                "findings": self.findings,
                "evidence_queries": self.evidence,
                "honesty_protocol": "All queries marked UNTESTED pending DB access",
                "preauth_status": "Clerk/official-records adoption pre-authorized per session brief"
            }, f, indent=2)
        
        self.log(f"✅ Analysis exported to {filename}")
        return filename

def main():
    analysis = CDParityAnalysis()
    
    analysis.log("🚀 Starting Brevard & Duval C/D Parity Root Cause Analysis")
    
    # Analyze both counties
    analysis.analyze_brevard_cd_gap()
    analysis.analyze_duval_cd_gap()
    
    # Design integration solution
    analysis.design_clerk_records_integration()
    
    # Generate implementation roadmap
    analysis.generate_implementation_roadmap()
    
    # Export findings
    filename = analysis.export_findings()
    
    analysis.log("✅ C/D Parity Analysis Complete")
    analysis.log(f"📁 Results: {filename}")

if __name__ == "__main__":
    main()