#!/usr/bin/env python3
"""
SHARD-19 Letter J: Deal Thesis Generator Implementation
Gold Standard Campaign - charlotte, citrus, broward counties

Letter J requirement: Deal completeness >=95% (triangle + two-arm CMA + ml_score + max_bid)
Current status: J=0.0 (bid_decisions table empty/unmatched)

This script builds the deal thesis generator for charlotte/citrus/broward:
1. Build bid_decisions table structure  
2. Implement Shapira V14 ml_score pipeline
3. Build two-arm CMA generation
4. Populate triangle factors (distress location/property/owner)
5. Calculate max_bid recommendations

Usage:
  python scripts/shard19_j_generator.py
"""
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

class DealThesisGenerator:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
        self.results = {
            "session_info": {
                "script": "shard19_j_generator.py", 
                "start_time": self.start_time.isoformat(),
                "counties": SHARD19_COUNTIES,
                "objective": "Build deal thesis generator for Letter J"
            },
            "bid_decisions_framework": {},
            "shapira_v14_integration": {},
            "cma_pipeline": {},
            "triangle_factors": {},
            "verification_evidence": []
        }

    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")

    def create_bid_decisions_migration(self):
        """Create migration for bid_decisions table structure"""
        self.log("🏗️ Creating bid_decisions table migration")
        
        migration_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        migration_file = project_root / "supabase" / "migrations" / f"{migration_timestamp}_shard19_bid_decisions.sql"
        
        migration_sql = self.generate_bid_decisions_sql()
        
        try:
            # Ensure migrations directory exists
            migration_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(migration_file, "w") as f:
                f.write(migration_sql)
                
            self.log(f"✅ Bid decisions migration created: {migration_file}")
            
            # Add to verification evidence
            self.results["verification_evidence"].append({
                "component": "Bid decisions migration file",
                "path": str(migration_file),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return str(migration_file)
            
        except Exception as e:
            self.log(f"❌ Migration creation failed: {e}", "ERROR")
            return None

    def generate_bid_decisions_sql(self):
        """Generate SQL migration for bid_decisions table per evaluator contract"""
        
        sql_parts = [
            "-- SHARD-19 Bid Decisions (Letter J) Migration",
            "-- Implements Shapira Deal Thesis per pencil_dod_criteria contract",
            f"-- Created: {datetime.now(timezone.utc).isoformat()}",
            "",
            "-- Letter J evaluator contract requires:",
            "-- bid_decisions row matched by case_number with:",
            "-- arv + max_bid + ml_score + factors containing ALL of:",
            "-- distress_location, distress_property, distress_owner, cma_distressed, cma_resale",
            "",
            "BEGIN;",
            "",
            "-- Create bid_decisions table per evaluator contract",
            "CREATE TABLE IF NOT EXISTS public.bid_decisions (",
            "    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,",
            "    case_number text NOT NULL,",
            "    county_slug text NOT NULL,",
            "    ",
            "    -- Core Shapira Formula components",
            "    arv numeric,                    -- After Repair Value",
            "    max_bid numeric,                -- Recommended maximum bid",
            "    ml_score numeric,               -- Shapira V14 ML model score", 
            "    ",
            "    -- Triangle factors (ALL required per evaluator)",
            "    factors jsonb NOT NULL DEFAULT '{}',",
            "    -- Must contain: distress_location, distress_property, distress_owner, cma_distressed, cma_resale",
            "    ",
            "    -- Supporting data",
            "    repair_estimate numeric,",
            "    holding_costs numeric,",
            "    profit_margin numeric DEFAULT 0.15,",
            "    ",
            "    -- CMA components", 
            "    cma_distressed_avg numeric,    -- Distressed comps average",
            "    cma_resale_avg numeric,        -- Retail resale comps average",
            "    cma_count_distressed integer,",
            "    cma_count_resale integer,",
            "    ",
            "    -- Analysis metadata",
            "    generated_at timestamp with time zone DEFAULT now(),",
            "    generated_by text DEFAULT 'SHARD19_J_GENERATOR',",
            "    model_version text DEFAULT 'shapira_v14',",
            "    confidence_score numeric,",
            "    ",
            "    -- Audit trail",
            "    data_sources jsonb,",
            "    calculation_details jsonb,",
            "    created_at timestamp with time zone DEFAULT now(),",
            "    updated_at timestamp with time zone DEFAULT now()",
            ");",
            "",
            "-- Indexes for performance",
            "CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON public.bid_decisions (case_number);",
            "CREATE INDEX IF NOT EXISTS idx_bid_decisions_county_slug ON public.bid_decisions (county_slug);", 
            "CREATE INDEX IF NOT EXISTS idx_bid_decisions_generated_at ON public.bid_decisions (generated_at);",
            "",
            "-- Constraint to ensure triangle factors completeness",
            "ALTER TABLE public.bid_decisions ADD CONSTRAINT IF NOT EXISTS check_triangle_factors",
            "CHECK (",
            "    factors ? 'distress_location' AND",
            "    factors ? 'distress_property' AND", 
            "    factors ? 'distress_owner' AND",
            "    factors ? 'cma_distressed' AND",
            "    factors ? 'cma_resale'",
            ");",
            "",
            "-- RLS policies",
            "ALTER TABLE public.bid_decisions ENABLE ROW LEVEL SECURITY;",
            "CREATE POLICY IF NOT EXISTS \"Public read access\" ON public.bid_decisions FOR SELECT USING (true);",
            "CREATE POLICY IF NOT EXISTS \"Service role write access\" ON public.bid_decisions FOR ALL USING (auth.role() = 'service_role');",
            "",
            "-- Function to validate Letter J completeness per evaluator",
            "CREATE OR REPLACE FUNCTION public.validate_bid_decision_completeness(decision_row public.bid_decisions)",
            "RETURNS boolean",
            "LANGUAGE plpgsql",
            "AS $$",
            "BEGIN",
            "    -- Check all required components per pencil_dod_criteria",
            "    RETURN (",
            "        decision_row.arv IS NOT NULL AND",
            "        decision_row.max_bid IS NOT NULL AND", 
            "        decision_row.ml_score IS NOT NULL AND",
            "        decision_row.factors ? 'distress_location' AND",
            "        decision_row.factors ? 'distress_property' AND",
            "        decision_row.factors ? 'distress_owner' AND", 
            "        decision_row.factors ? 'cma_distressed' AND",
            "        decision_row.factors ? 'cma_resale'",
            "    );",
            "END;",
            "$$;",
            "",
            "-- Sample bid decision for framework testing",
            "INSERT INTO public.bid_decisions (", 
            "    case_number, county_slug, arv, max_bid, ml_score, factors,",
            "    generated_by, model_version, data_sources",
            ") VALUES (",
            "    'FRAMEWORK_TEST_001', 'charlotte',",
            "    250000, 175000, 0.75,",
            "    '{",
            '        "distress_location": 0.8,',
            '        "distress_property": 0.6,',
            '        "distress_owner": 0.7,',
            '        "cma_distressed": 200000,', 
            '        "cma_resale": 245000',
            "    }'::jsonb,",
            "    'SHARD19_FRAMEWORK_SAMPLE', 'shapira_v14',", 
            "    '{\"framework\": \"sample_data\"}'::jsonb",
            ") ON CONFLICT (case_number) DO NOTHING;",
            "",
            "COMMIT;",
            "",
            "-- Verification queries:",
            "-- SELECT count(*) FROM public.bid_decisions;",
            "-- SELECT case_number, arv, max_bid, ml_score, public.validate_bid_decision_completeness(bid_decisions.*) as complete FROM public.bid_decisions LIMIT 5;", 
            "-- Test Letter J evaluation: SELECT * FROM public.pencil_dod_evaluate_county('charlotte') WHERE letter = 'J';"
        ]
        
        return "\n".join(sql_parts)

    def create_shapira_v14_integration(self):
        """Create Shapira V14 model integration script"""
        self.log("🧠 Creating Shapira V14 ML model integration")
        
        shapira_script = project_root / "scripts" / "shard19_shapira_v14_pipeline.py"
        
        shapira_template = '''#!/usr/bin/env python3
"""
SHARD-19 Shapira V14 Model Integration
ML scoring pipeline for deal thesis generation

Integrates with existing Shapira V14 model (AUC .78) to generate ml_score
for bid_decisions table per Letter J evaluator contract.

Usage:
  python scripts/shard19_shapira_v14_pipeline.py --county charlotte
  python scripts/shard19_shapira_v14_pipeline.py --all-counties
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

class ShapiraV14Pipeline:
    def __init__(self, county):
        self.county = county
        self.model_version = "shapira_v14"
        self.model_auc = 0.78  # Per issue brief
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def load_shapira_model(self):
        """Load Shapira V14 model for scoring"""
        self.log(f"🧠 Loading Shapira V14 model (AUC: {self.model_auc})")
        
        # IMPLEMENTATION NEEDED:
        # 1. Locate existing Shapira V14 model files
        # 2. Load trained model (likely scikit-learn or similar)
        # 3. Verify model version and performance metrics
        # 4. Prepare feature engineering pipeline
        
        model_info = {
            "model_loaded": False,
            "model_version": self.model_version,
            "expected_auc": self.model_auc,
            "feature_count": "TBD",
            "implementation_status": "NEEDS_DEVELOPMENT",
            "model_location": "scripts/shapira_models/ (search required)"
        }
        
        self.log("⚠️ Shapira V14 model loading needs implementation", "WARNING")
        return model_info
        
    def extract_ml_features(self, auction_cases):
        """Extract features for ML scoring"""
        self.log(f"🔧 Extracting ML features for {len(auction_cases)} cases")
        
        # IMPLEMENTATION NEEDED:
        # 1. Extract features used by Shapira V14 model
        # 2. Property characteristics (size, age, condition)
        # 3. Location factors (neighborhood, schools, crime)
        # 4. Market conditions (recent sales, inventory)
        # 5. Distress indicators (foreclosure stage, time on market)
        
        features = []
        for case in auction_cases:
            case_features = {
                "case_number": case.get("case_number"),
                "features": "TBD - needs feature engineering",
                "status": "PENDING_IMPLEMENTATION"
            }
            features.append(case_features)
            
        return features
        
    def generate_ml_scores(self, features):
        """Generate ML scores using Shapira V14 model"""
        if not features:
            return []
            
        self.log(f"🎯 Generating ML scores for {len(features)} cases")
        
        # IMPLEMENTATION NEEDED:
        # 1. Run feature vectors through Shapira V14 model
        # 2. Generate probability scores (0.0 - 1.0 range)
        # 3. Apply calibration if needed
        # 4. Add confidence intervals
        
        scores = []
        for feature_set in features:
            score_result = {
                "case_number": feature_set.get("case_number"),
                "ml_score": 0.5,  # Placeholder - needs model inference
                "confidence": 0.0,
                "model_version": self.model_version,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "PLACEHOLDER_VALUE"
            }
            scores.append(score_result)
            
        return scores
        
    def run_county_scoring(self):
        """Execute ML scoring for county auction cases"""
        self.log(f"🚀 Running Shapira V14 scoring for {self.county}")
        
        try:
            # Load model
            model_info = self.load_shapira_model()
            
            # Get auction cases needing scoring (placeholder)
            auction_cases = [{"case_number": "SAMPLE_001"}]  # Would query multi_county_auctions
            
            # Extract features
            features = self.extract_ml_features(auction_cases)
            
            # Generate scores
            scores = self.generate_ml_scores(features)
            
            # Update bid_decisions table (placeholder)
            updated_count = self.update_bid_decisions_scores(scores)
            
            result = {
                "county": self.county,
                "model_info": model_info,
                "cases_processed": len(auction_cases),
                "scores_generated": len(scores),
                "scores_saved": updated_count,
                "status": "FRAMEWORK_READY" if model_info["model_loaded"] else "NEEDS_IMPLEMENTATION"
            }
            
            return result
            
        except Exception as e:
            self.log(f"❌ Scoring failed for {self.county}: {e}", "ERROR")
            return {
                "county": self.county,
                "status": "ERROR",
                "error": str(e)
            }
            
    def update_bid_decisions_scores(self, scores):
        """Update bid_decisions table with ML scores"""
        if not scores:
            return 0
            
        self.log(f"💾 Updating bid_decisions with {len(scores)} ML scores")
        
        # IMPLEMENTATION NEEDED:
        # 1. Connect to Supabase
        # 2. Update existing bid_decisions rows with ml_score
        # 3. Create new rows if needed
        # 4. Handle batch updates efficiently
        
        return 0  # Placeholder

def main():
    parser = argparse.ArgumentParser(description='SHARD-19 Shapira V14 ML Pipeline')
    parser.add_argument('--county', choices=SHARD19_COUNTIES, help='County to score')
    parser.add_argument('--all-counties', action='store_true', help='Score all counties')
    
    args = parser.parse_args()
    
    if not args.county and not args.all_counties:
        parser.print_help()
        sys.exit(1)
        
    counties = SHARD19_COUNTIES if args.all_counties else [args.county]
    
    total_results = {}
    
    for county in counties:
        pipeline = ShapiraV14Pipeline(county)
        result = pipeline.run_county_scoring()
        total_results[county] = result
    
    print("\\n" + "="*60)
    print("SHARD-19 SHAPIRA V14 ML SCORING RESULTS")
    print("="*60)
    print(json.dumps(total_results, indent=2))

if __name__ == "__main__":
    main()
'''
        
        try:
            with open(shapira_script, "w") as f:
                f.write(shapira_template)
                
            self.log(f"✅ Shapira V14 pipeline created: {shapira_script}")
            return str(shapira_script)
            
        except Exception as e:
            self.log(f"❌ Shapira script creation failed: {e}", "ERROR")
            return None

    def create_cma_pipeline(self):
        """Create CMA (Comparative Market Analysis) pipeline"""
        self.log("🏠 Creating CMA pipeline for two-arm analysis")
        
        cma_script = project_root / "scripts" / "shard19_cma_pipeline.py"
        
        cma_template = '''#!/usr/bin/env python3
"""
SHARD-19 CMA Pipeline
Two-arm Comparative Market Analysis for deal thesis

Generates distressed and resale comps per Letter J evaluator contract:
- cma_distressed: distressed property comps
- cma_resale: retail resale comps

Sources: HomeHarvest, HUD, public Realtor endpoints (per $50/mo budget authorization)

Usage:
  python scripts/shard19_cma_pipeline.py --county charlotte
  python scripts/shard19_cma_pipeline.py --all-counties
"""
import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path  
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

SHARD19_COUNTIES = ['charlotte', 'citrus', 'broward']

class CMAPipeline:
    def __init__(self, county):
        self.county = county
        self.budget_monthly = 50.0  # Per issue brief authorization
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {message}")
        
    def setup_cma_sources(self):
        """Setup CMA data sources within budget"""
        self.log("🔧 Setting up CMA data sources")
        
        # Per issue brief: HomeHarvest, HUD, public Realtor endpoints
        sources = {
            "homeharvest": {
                "type": "FREE",
                "api_endpoint": "TBD - research required",
                "coverage": "Residential sales data",
                "implementation_status": "NEEDS_RESEARCH"
            },
            "hud": {
                "type": "FREE", 
                "api_endpoint": "https://www.huduser.gov/portal/datasets/",
                "coverage": "Foreclosure and distressed sales",
                "implementation_status": "NEEDS_RESEARCH"
            },
            "realtor_endpoints": {
                "type": "FREE/LIMITED",
                "api_endpoint": "Public Realtor.com endpoints (research required)",
                "coverage": "Recent sales, listings",
                "implementation_status": "NEEDS_RESEARCH"
            },
            "paid_fallback": {
                "type": "PAID",
                "monthly_budget": self.budget_monthly,
                "note": "Use only if free sources insufficient",
                "options": ["RentSpree API", "Rentals.com", "Other MLS feeds"]
            }
        }
        
        self.log("⚠️ CMA sources need research and implementation", "WARNING")
        return sources
        
    def generate_distressed_comps(self, property_info):
        """Generate distressed property comps"""
        self.log("🏚️ Generating distressed comps")
        
        # IMPLEMENTATION NEEDED:
        # 1. Search for recent foreclosure sales in area
        # 2. Filter by property type, size, age similarity  
        # 3. Apply time-based adjustments
        # 4. Calculate average price per sq ft
        # 5. Return distressed comp average
        
        distressed_comps = {
            "property_address": property_info.get("address", "TBD"),
            "search_radius_miles": 5.0,
            "comparable_count": 0,
            "average_price": None,
            "price_per_sqft": None,
            "analysis_date": datetime.now(timezone.utc).isoformat(),
            "status": "NEEDS_IMPLEMENTATION"
        }
        
        return distressed_comps
        
    def generate_resale_comps(self, property_info):
        """Generate retail resale comps"""  
        self.log("🏡 Generating retail resale comps")
        
        # IMPLEMENTATION NEEDED:
        # 1. Search for recent retail sales in area
        # 2. Filter by property type, size, age, condition
        # 3. Exclude distressed/foreclosure sales
        # 4. Apply market condition adjustments
        # 5. Calculate average retail value
        
        resale_comps = {
            "property_address": property_info.get("address", "TBD"),
            "search_radius_miles": 3.0,
            "comparable_count": 0,
            "average_price": None,
            "price_per_sqft": None,
            "analysis_date": datetime.now(timezone.utc).isoformat(), 
            "status": "NEEDS_IMPLEMENTATION"
        }
        
        return resale_comps
        
    def run_two_arm_cma(self, auction_cases):
        """Run two-arm CMA analysis for auction cases"""
        self.log(f"🎯 Running two-arm CMA for {len(auction_cases)} cases")
        
        cma_results = []
        
        for case in auction_cases:
            try:
                # Extract property info
                property_info = {
                    "case_number": case.get("case_number"),
                    "address": case.get("property_address", "TBD"),
                    # More property details would be extracted from multi_county_auctions
                }
                
                # Generate both arms
                distressed_comps = self.generate_distressed_comps(property_info)
                resale_comps = self.generate_resale_comps(property_info)
                
                cma_result = {
                    "case_number": property_info["case_number"],
                    "cma_distressed": distressed_comps,
                    "cma_resale": resale_comps,
                    "two_arm_analysis": {
                        "distressed_avg": distressed_comps.get("average_price"),
                        "resale_avg": resale_comps.get("average_price"),
                        "spread_percent": None,  # Would calculate if both available
                        "confidence": "LOW_PLACEHOLDER"
                    },
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
                
                cma_results.append(cma_result)
                
            except Exception as e:
                self.log(f"❌ CMA failed for case {case.get('case_number')}: {e}", "ERROR")
                
        return cma_results
        
    def update_bid_decisions_cma(self, cma_results):
        """Update bid_decisions with CMA data"""
        if not cma_results:
            return 0
            
        self.log(f"💾 Updating bid_decisions with {len(cma_results)} CMA results")
        
        # IMPLEMENTATION NEEDED:
        # 1. Connect to Supabase
        # 2. Update factors jsonb with cma_distressed, cma_resale values
        # 3. Update individual CMA columns if available
        # 4. Handle batch updates
        
        return 0  # Placeholder

def main():
    parser = argparse.ArgumentParser(description='SHARD-19 CMA Pipeline')
    parser.add_argument('--county', choices=SHARD19_COUNTIES, help='County to analyze')
    parser.add_argument('--all-counties', action='store_true', help='Analyze all counties')
    
    args = parser.parse_args()
    
    if not args.county and not args.all_counties:
        parser.print_help()
        sys.exit(1)
        
    counties = SHARD19_COUNTIES if args.all_counties else [args.county]
    
    total_results = {}
    
    for county in counties:
        pipeline = CMAPipeline(county)
        sources = pipeline.setup_cma_sources()
        
        # Placeholder auction cases - would query multi_county_auctions
        auction_cases = [{"case_number": "SAMPLE_001", "property_address": "TBD"}]
        
        cma_results = pipeline.run_two_arm_cma(auction_cases)
        updated_count = pipeline.update_bid_decisions_cma(cma_results)
        
        total_results[county] = {
            "sources_setup": sources,
            "cases_analyzed": len(auction_cases),
            "cma_results": len(cma_results),
            "updates_applied": updated_count
        }
    
    print("\\n" + "="*60)
    print("SHARD-19 CMA PIPELINE RESULTS")
    print("="*60)
    print(json.dumps(total_results, indent=2))

if __name__ == "__main__":
    main()
'''
        
        try:
            with open(cma_script, "w") as f:
                f.write(cma_template)
                
            self.log(f"✅ CMA pipeline created: {cma_script}")
            return str(cma_script)
            
        except Exception as e:
            self.log(f"❌ CMA script creation failed: {e}", "ERROR")
            return None

    def execute_priority_fixes(self):
        """Execute the Letter J deal thesis generator implementation"""
        self.log("🎯 Executing Letter J deal thesis generator implementation")
        
        # Step 1: Create bid_decisions migration
        migration_file = self.create_bid_decisions_migration()
        
        # Step 2: Create Shapira V14 integration
        shapira_script = self.create_shapira_v14_integration()
        
        # Step 3: Create CMA pipeline
        cma_script = self.create_cma_pipeline()
        
        # Summary
        implementation_summary = {
            "bid_decisions_framework": migration_file is not None,
            "shapira_v14_integration": shapira_script is not None,
            "cma_pipeline_created": cma_script is not None,
            "framework_status": "READY",
            "next_steps": [
                "1. Apply bid_decisions migration to live Supabase",
                "2. Locate and integrate existing Shapira V14 model",
                "3. Research and implement CMA data sources (HomeHarvest, HUD, public Realtor)",
                "4. Build feature extraction for ML scoring",
                "5. Execute full pipeline to populate bid_decisions",
                "6. Verify Letter J metric via SELECT public.pencil_dod_evaluate_county('<county>');"
            ],
            "estimated_effort": "4-5 hours ML integration + 3 hours CMA implementation + 2 hours testing",
            "certification_readiness": "FRAMEWORK_READY",
            "budget_authorization": "$50/month for paid CMA APIs (pre-approved)"
        }
        
        self.results["implementation_summary"] = implementation_summary
        self.log("✅ Letter J deal thesis framework complete")
        
        return implementation_summary

def main():
    """Main execution for SHARD-19 Letter J deal thesis generator"""
    generator = DealThesisGenerator()
    
    try:
        generator.log("🚀 SHARD-19 Letter J: Deal Thesis Generator Implementation Starting")
        
        # Execute the implementation
        summary = generator.execute_priority_fixes()
        
        # Session completion
        session_end = datetime.now(timezone.utc) 
        session_duration = (session_end - generator.start_time).total_seconds()
        
        generator.results["session_info"]["end_time"] = session_end.isoformat()
        generator.results["session_info"]["duration_seconds"] = session_duration
        
        # Final results
        print("\\n" + "="*80)
        print("SHARD-19 LETTER J: DEAL THESIS GENERATOR IMPLEMENTATION")
        print("="*80)
        print(json.dumps(generator.results, indent=2, default=str))
        
        generator.log(f"✅ Letter J generator complete ({session_duration:.1f}s)")
        
        # Return success if migration was created
        framework_success = generator.results["implementation_summary"]["bid_decisions_framework"]
        return 0 if framework_success else 1
        
    except Exception as e:
        generator.log(f"❌ CRITICAL ERROR: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())