#!/usr/bin/env python3
"""
SHARD-12 J GENERATOR - BID DECISIONS PIPELINE
Fleet-wide criterion fix: J=0 → J=95% for all counties

ROOT CAUSE (from brief):
"J=0 fleet-wide because bid_decisions has zero qualifying case-number matches: 
the deal-triangle (arv+max_bid+ml_score+factors) pipeline is not writing."

SOLUTION:
Build to evaluator contract exactly: bid_decisions row matched by case_number 
with arv + max_bid + ml_score + factors containing ALL of:
- distress_location, distress_property, distress_owner, cma_distressed, cma_resale

INPUTS:
- Shapira V14 (shapira_models, AUC .78) supplies ml_score
- gen_valuations_comps_batch supplies CMA inputs

TARGET: County-agnostic, affects marion+collier+pinellas+glades (all SHARD-12)
EXPECTED IMPACT: 4 counties × 95 points = 380 total points
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    logger.warning("⚠️ No SUPABASE_KEY - running in analysis mode only")
    ANALYSIS_ONLY = True
else:
    ANALYSIS_ONLY = False

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
} if SUPABASE_KEY else {}

TARGET_COUNTIES = ['marion', 'collier', 'pinellas', 'glades']

def analyze_bid_decisions_gap():
    """Analyze current bid_decisions state and gap"""
    analysis = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'gap_analysis': {},
        'requirements': {
            'evaluator_contract': [
                'arv (after repair value)',
                'max_bid (maximum bid amount)', 
                'ml_score (from Shapira V14)',
                'factors containing ALL of:',
                '  - distress_location',
                '  - distress_property', 
                '  - distress_owner',
                '  - cma_distressed',
                '  - cma_resale'
            ],
            'data_sources': [
                'shapira_models (AUC .78) for ml_score',
                'gen_valuations_comps_batch for CMA inputs',
                'multi_county_auctions for case_number matching'
            ]
        },
        'pipeline_design': {
            'input_tables': [
                'multi_county_auctions',
                'shapira_models', 
                'valuations_comps (via gen_valuations_comps_batch)',
                'parcel_data (for property characteristics)'
            ],
            'output_table': 'bid_decisions',
            'matching_key': 'case_number',
            'required_fields': [
                'case_number',
                'county', 
                'arv',
                'max_bid',
                'ml_score',
                'factors (jsonb containing all 5 factor keys)'
            ]
        }
    }
    
    if ANALYSIS_ONLY:
        analysis['current_state'] = 'analysis_only_no_db_access'
        analysis['gap_analysis'] = {
            'bid_decisions_count': 'unknown_requires_db',
            'counties_affected': TARGET_COUNTIES,
            'expected_impact': f'{len(TARGET_COUNTIES)} counties × 95 points = {len(TARGET_COUNTIES) * 95} points'
        }
    else:
        # Would query actual state here
        pass
        
    return analysis

def design_bid_decisions_pipeline():
    """Design the bid_decisions generation pipeline"""
    
    pipeline = {
        'name': 'bid_decisions_generator',
        'description': 'Generate bid_decisions records for Shapira deal thesis criterion J',
        'phases': [
            {
                'phase': 1,
                'name': 'arv_calculation',
                'description': 'Calculate after repair value from parcel data and comps',
                'sql_pattern': '''
                    -- Calculate ARV using established methodology
                    WITH property_base AS (
                        SELECT 
                            case_number,
                            county,
                            parcel_id,
                            -- Property characteristics for ARV calc
                            COALESCE(assessed_value, market_value) as base_value,
                            square_footage,
                            lot_size_acres,
                            year_built,
                            property_type
                        FROM multi_county_auctions mca
                        LEFT JOIN parcel_data pd ON mca.parcel_id = pd.parcel_id
                        WHERE mca.county IN ('marion', 'collier', 'pinellas', 'glades')
                        AND mca.case_number IS NOT NULL
                        AND mca.case_number != ''
                    )
                    SELECT 
                        case_number,
                        county,
                        -- ARV calculation methodology (to be refined)
                        CASE 
                            WHEN base_value > 0 THEN base_value * 1.15  -- 15% repair premium
                            ELSE NULL 
                        END as arv
                    FROM property_base;
                '''
            },
            {
                'phase': 2,
                'name': 'max_bid_calculation', 
                'description': 'Calculate maximum bid using Shapira methodology',
                'sql_pattern': '''
                    -- Apply Shapira formula: (ARV×70%)-Repairs-$10K-MIN($25K,15%×ARV)
                    WITH arv_base AS (
                        -- Previous phase output
                    )
                    SELECT 
                        case_number,
                        county,
                        arv,
                        GREATEST(0, 
                            (arv * 0.70) - 
                            COALESCE(estimated_repairs, arv * 0.10) - 
                            10000 - 
                            LEAST(25000, arv * 0.15)
                        ) as max_bid
                    FROM arv_base;
                '''
            },
            {
                'phase': 3,
                'name': 'ml_score_integration',
                'description': 'Integrate Shapira V14 ML scores',
                'sql_pattern': '''
                    -- Join with shapira_models for ML predictions
                    SELECT 
                        bd.case_number,
                        bd.county,
                        bd.arv,
                        bd.max_bid,
                        sm.score as ml_score,
                        sm.confidence,
                        sm.model_version
                    FROM bid_decisions_temp bd
                    LEFT JOIN shapira_models sm ON (
                        sm.case_number = bd.case_number OR
                        (sm.parcel_id = bd.parcel_id AND sm.county = bd.county)
                    )
                    WHERE sm.model_version = 'V14'
                    AND sm.score IS NOT NULL;
                '''
            },
            {
                'phase': 4,
                'name': 'factors_compilation',
                'description': 'Compile all required factor keys from CMA batch',
                'sql_pattern': '''
                    -- Build factors JSONB with all 5 required keys
                    SELECT 
                        bd.*,
                        jsonb_build_object(
                            'distress_location', dl.score,
                            'distress_property', dp.score, 
                            'distress_owner', do_score.score,
                            'cma_distressed', vc.distressed_avg,
                            'cma_resale', vc.resale_avg
                        ) as factors
                    FROM bid_decisions_temp bd
                    LEFT JOIN distress_location_scores dl ON dl.case_number = bd.case_number
                    LEFT JOIN distress_property_scores dp ON dp.case_number = bd.case_number  
                    LEFT JOIN distress_owner_scores do_score ON do_score.case_number = bd.case_number
                    LEFT JOIN valuations_comps vc ON vc.case_number = bd.case_number;
                '''
            },
            {
                'phase': 5,
                'name': 'final_assembly',
                'description': 'Final bid_decisions record assembly',
                'sql_pattern': '''
                    INSERT INTO bid_decisions (
                        case_number, county, created_at,
                        arv, max_bid, ml_score, factors,
                        data_source, pipeline_version
                    )
                    SELECT 
                        case_number,
                        county,
                        NOW(),
                        arv,
                        max_bid,
                        ml_score,
                        factors,
                        'shard12_j_generator:v1',
                        '2026-06-13'
                    FROM bid_decisions_complete
                    WHERE 
                        arv IS NOT NULL AND
                        max_bid IS NOT NULL AND
                        ml_score IS NOT NULL AND
                        factors ? 'distress_location' AND
                        factors ? 'distress_property' AND
                        factors ? 'distress_owner' AND
                        factors ? 'cma_distressed' AND
                        factors ? 'cma_resale';
                '''
            }
        ],
        'dependencies': {
            'existing_tables': [
                'multi_county_auctions',
                'parcel_data',
                'shapira_models', 
                'valuations_comps',
                'distress_location_scores',
                'distress_property_scores',
                'distress_owner_scores'
            ],
            'missing_tables': [],  # To be filled by dependency check
            'data_quality_requirements': [
                'case_number NOT NULL and not empty',
                'county IN target counties',
                'Shapira V14 models available',
                'gen_valuations_comps_batch has run recently'
            ]
        },
        'validation': {
            'success_criteria': [
                'bid_decisions rows inserted > 0',
                'All 5 factor keys present in factors JSONB',
                'ml_score from Shapira V14 only',
                'case_number matches multi_county_auctions'
            ],
            'quality_checks': [
                'max_bid > 0 (positive bidding amounts)',
                'arv > max_bid (sensible spread)',
                'ml_score between 0 and 1',
                'factors JSONB well-formed'
            ]
        }
    }
    
    return pipeline

def estimate_impact():
    """Estimate impact of J generator on SHARD-12 counties"""
    
    impact_estimate = {
        'criteria_improvement': {
            'letter_J': {
                'before': '0.0% for all target counties',
                'after': '95%+ (if pipeline successful)',
                'point_gain_per_county': 95,
                'total_counties': len(TARGET_COUNTIES),
                'total_point_gain': len(TARGET_COUNTIES) * 95
            }
        },
        'qualification_impact': {
            'marion': {'current': '2/10', 'potential': '3/10', 'gain': '+1 letter'},
            'collier': {'current': '1/10', 'potential': '2/10', 'gain': '+1 letter'},
            'pinellas': {'current': '1/10', 'potential': '2/10', 'gain': '+1 letter'},
            'glades': {'current': '0/10', 'potential': '1/10', 'gain': '+1 letter (if A-lane setup)'}
        },
        'fleet_impact': {
            'description': 'Single highest-leverage intervention for SHARD-12',
            'counties_affected': 4,
            'criterion_parallel_value': 'Fixes J across entire fleet simultaneously',
            'dependency_enables': 'None - J is independent per brief'
        },
        'implementation_complexity': {
            'level': 'high',
            'key_challenges': [
                'Shapira V14 model integration',
                'CMA data from gen_valuations_comps_batch',
                'Factor compilation from multiple tables',
                'Data quality validation across all inputs'
            ],
            'estimated_time': '2-3 hours development + testing',
            'testing_required': 'Essential - financial calculations'
        }
    }
    
    return impact_estimate

def generate_implementation_checklist():
    """Generate implementation checklist for execution"""
    
    checklist = {
        'pre_implementation': [
            '[ ] Verify shapira_models table exists and has V14 records',
            '[ ] Verify gen_valuations_comps_batch has run recently',
            '[ ] Check multi_county_auctions for target counties case_numbers',
            '[ ] Verify bid_decisions table schema matches requirements',
            '[ ] Check dependency tables (distress_*_scores) exist'
        ],
        'implementation': [
            '[ ] Create temporary staging tables for each phase',
            '[ ] Implement Phase 1: ARV calculation',
            '[ ] Implement Phase 2: Max bid calculation',  
            '[ ] Implement Phase 3: ML score integration',
            '[ ] Implement Phase 4: Factors compilation',
            '[ ] Implement Phase 5: Final assembly and validation'
        ],
        'testing': [
            '[ ] Test with 10-20 sample case_numbers from each county',
            '[ ] Validate ARV calculations against known good values',
            '[ ] Verify max_bid follows Shapira methodology exactly',
            '[ ] Confirm all 5 factor keys present in output',
            '[ ] Check ml_score values are sensible (0-1 range)',
            '[ ] Validate case_number matching works correctly'
        ],
        'deployment': [
            '[ ] Run full pipeline on all target counties',
            '[ ] Monitor for errors and data quality issues',
            '[ ] Verify bid_decisions count > 0 for each county',
            '[ ] Run pencil_dod_evaluate_county to confirm J improvement',
            '[ ] Document any edge cases or data quality issues'
        ],
        'verification': [
            '[ ] SELECT count(*) FROM bid_decisions WHERE county IN target_counties',
            '[ ] SELECT pencil_dod_evaluate_county for each county - confirm J PASS',
            '[ ] Validate factors JSONB structure on sample records',
            '[ ] Check data_source = shard12_j_generator:v1',
            '[ ] Confirm no duplicate case_numbers in output'
        ],
        'commit_ship': [
            '[ ] Commit pipeline scripts to main',
            '[ ] Commit any new migration files',
            '[ ] Document pipeline in SHARD-12 session notes',
            '[ ] Update TODO.md with J generator completion',
            '[ ] Run final verification and capture SQL evidence'
        ]
    }
    
    return checklist

def main():
    """Execute J generator analysis and design"""
    logger.info("🎯 SHARD-12 J GENERATOR - HIGHEST LEVERAGE CRITERION FIX")
    
    try:
        # Analysis
        logger.info("📊 Analyzing bid_decisions gap...")
        gap_analysis = analyze_bid_decisions_gap()
        
        # Design  
        logger.info("🔧 Designing pipeline architecture...")
        pipeline_design = design_bid_decisions_pipeline()
        
        # Impact estimation
        logger.info("📈 Estimating impact...")
        impact = estimate_impact()
        
        # Implementation checklist
        logger.info("✅ Generating implementation checklist...")
        checklist = generate_implementation_checklist()
        
        # Summary report
        logger.info("\n" + "="*60)
        logger.info("J GENERATOR DESIGN COMPLETE")
        logger.info("="*60)
        
        print(f"\n🎯 IMPACT SUMMARY:")
        print(f"Current J status: 0.0% all target counties")
        print(f"Target J status: 95%+ all target counties") 
        print(f"Point gain: {impact['criteria_improvement']['letter_J']['total_point_gain']} points total")
        print(f"Counties affected: {len(TARGET_COUNTIES)}")
        
        print(f"\n🔧 IMPLEMENTATION:")
        print(f"Pipeline phases: {len(pipeline_design['phases'])}")
        print(f"Key dependencies: Shapira V14, gen_valuations_comps_batch")
        print(f"Complexity: {impact['implementation_complexity']['level']}")
        print(f"Est. time: {impact['implementation_complexity']['estimated_time']}")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"1. Complete pre-implementation checklist")
        print(f"2. Build and test pipeline phases")
        print(f"3. Deploy to production") 
        print(f"4. Verify J letter improvement")
        print(f"5. Ship to main per SHIP-TO-MAIN mandate")
        
        # Save full design
        full_design = {
            'gap_analysis': gap_analysis,
            'pipeline_design': pipeline_design,
            'impact_estimate': impact,
            'implementation_checklist': checklist,
            'generated_at': datetime.now(timezone.utc).isoformat()
        }
        
        with open('shard12_j_generator_design.json', 'w') as f:
            json.dump(full_design, f, indent=2, default=str)
            
        logger.info("💾 Full design saved to shard12_j_generator_design.json")
        logger.info("✅ J GENERATOR DESIGN READY FOR IMPLEMENTATION")
        
        return full_design
        
    except Exception as e:
        logger.error(f"❌ J generator design failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)