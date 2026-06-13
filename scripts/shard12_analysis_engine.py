#!/usr/bin/env python3
"""
SHARD-12 ANALYSIS ENGINE
Criterion-focused analysis for marion, collier, pinellas, glades

ANALYSIS FRAMEWORK:
1. Letter-by-letter dependency analysis 
2. High-leverage intervention identification
3. Criterion-parallel fix prioritization per 2026-06-12 directive

TARGET LETTERS BY COUNTY (from brief):
- marion: Focus on C/D (9.6%/55.1%), B reconciliation, J generator
- collier: Focus on H (562.4h), C/D (17.3%/59.2%), F bootstrap (0.0%)
- pinellas: Focus on H (82.7h), C/D (11.8%/39.2%), F bootstrap (2.4%)  
- glades: Full A-lane bootstrap (0/10 letters)

DEPENDENCY CHAIN (from brief):
I <= E by construction (card requires parcel_id)
I requires parcel_id IN v_zoning_gold_standard_card with zone_code
Order: E linkage -> G zoning load -> I follows largely for free
J is independent of G
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CountyMetrics:
    """County letter metrics from brief"""
    county: str
    pass_count: int
    letters: Dict[str, any]
    
    def __post_init__(self):
        # Parse letter status from metrics string
        # Format examples: "A✓ H✓ | B FAIL | C 9.6% | D 55.1%"
        self.letter_status = {}
        self.bottlenecks = []
        self.high_leverage = []

# Current metrics from Loop Run 22 brief
COUNTY_DATA = {
    'marion': {
        'pass_count': 2,
        'letters': {
            'A': {'status': 'PASS', 'metric': '3021', 'detail': 'fc=3489 td=3021'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=1981'},
            'C': {'status': 'FAIL', 'metric': 9.6, 'detail': 'matched_clean=628 of 6510'},
            'D': {'status': 'FAIL', 'metric': 55.1, 'detail': 'matched_any=3588 of 6510'},
            'E': {'status': 'FAIL', 'metric': 67.6, 'detail': 'parcel_linked=4403 of 6510'},
            'F': {'status': 'FAIL', 'metric': 8.6, 'detail': 'tier1_sold=170 closed_sold=1981'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'PASS', 'metric': 41.0, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=775 auctions=6510'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 6510 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'collier': {
        'pass_count': 1,
        'letters': {
            'A': {'status': 'PASS', 'metric': '559', 'detail': 'fc=1111 td=559'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=610'},
            'C': {'status': 'FAIL', 'metric': 17.3, 'detail': 'matched_clean=289 of 1670'},
            'D': {'status': 'FAIL', 'metric': 59.2, 'detail': 'matched_any=988 of 1670'},
            'E': {'status': 'FAIL', 'metric': 64.8, 'detail': 'parcel_linked=1082 of 1670'},
            'F': {'status': 'FAIL', 'metric': 0.0, 'detail': 'tier1_sold=0 closed_sold=610'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 562.4, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=224 auctions=1670'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 1670 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'pinellas': {
        'pass_count': 1,
        'letters': {
            'A': {'status': 'PASS', 'metric': '4438', 'detail': 'fc=10048 td=4438'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=5724'},
            'C': {'status': 'FAIL', 'metric': 11.8, 'detail': 'matched_clean=1703 of 14486'},
            'D': {'status': 'FAIL', 'metric': 39.2, 'detail': 'matched_any=5684 of 14486'},
            'E': {'status': 'FAIL', 'metric': 77.4, 'detail': 'parcel_linked=11213 of 14486'},
            'F': {'status': 'FAIL', 'metric': 2.4, 'detail': 'tier1_sold=136 closed_sold=5724'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 82.7, 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=1096 auctions=14486'},
            'J': {'status': 'FAIL', 'metric': 0.0, 'detail': 'deal_complete=0 of 14486 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    },
    'glades': {
        'pass_count': 0,
        'letters': {
            'A': {'status': 'FAIL', 'metric': 0, 'detail': 'fc=0 td=0'},
            'B': {'status': 'FAIL', 'metric': 'null', 'detail': 'verified=0 closed_sold=0'},
            'C': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_clean=0 of 0'},
            'D': {'status': 'FAIL', 'metric': 'null', 'detail': 'matched_any=0 of 0'},
            'E': {'status': 'FAIL', 'metric': 'null', 'detail': 'parcel_linked=0 of 0'},
            'F': {'status': 'FAIL', 'metric': 'null', 'detail': 'tier1_sold=0 closed_sold=0'},
            'G': {'status': 'FAIL', 'metric': 'null', 'detail': 'density= far= pk1000='},
            'H': {'status': 'FAIL', 'metric': 'null', 'detail': 'hours since last_seen (SLA 48h)'},
            'I': {'status': 'FAIL', 'metric': 'null', 'detail': 'zoned_complete_parcels=0 field_complete_parcels=0 auctions=0'},
            'J': {'status': 'FAIL', 'metric': 'null', 'detail': 'deal_complete=0 of 0 (triangle + two-arm CMA + ml_score + max_bid)'}
        }
    }
}

class LetterAnalyzer:
    """Analyze letter performance and dependencies"""
    
    def __init__(self):
        self.dependency_chain = {
            'I': ['E'],  # I requires E (parcel linkage)
            'G': ['zoning_load'],  # G requires zoning data loaded
            'I_complete': ['E', 'G'],  # I fully depends on both E and G
            'J': []  # J is independent per brief
        }
        
    def analyze_county(self, county: str) -> Dict:
        """Comprehensive county analysis"""
        if county not in COUNTY_DATA:
            return {'error': f'No data for county {county}'}
            
        data = COUNTY_DATA[county]
        letters = data['letters']
        
        analysis = {
            'county': county,
            'current_score': f"{data['pass_count']}/10",
            'bottlenecks': self._identify_bottlenecks(letters),
            'high_leverage': self._identify_high_leverage(county, letters),
            'quick_wins': self._identify_quick_wins(letters),
            'blockers': self._identify_blockers(letters),
            'criterion_focus': self._criterion_analysis(county, letters)
        }
        
        return analysis
    
    def _identify_bottlenecks(self, letters: Dict) -> List[str]:
        """Identify letters blocking the most other letters"""
        bottlenecks = []
        
        # E blocks I by dependency chain
        if letters['E']['status'] == 'FAIL':
            bottlenecks.append('E_blocks_I')
            
        # G blocks I completion (zoning required)
        if letters['G']['status'] == 'FAIL':
            bottlenecks.append('G_blocks_I') 
            
        # B anomaly blocks certification
        if letters['B']['status'] == 'FAIL' or letters['B']['metric'] == 'null':
            bottlenecks.append('B_verification_missing')
            
        return bottlenecks
        
    def _identify_high_leverage(self, county: str, letters: Dict) -> List[Dict]:
        """Identify highest-leverage interventions"""
        leverage_opportunities = []
        
        # J generator - 0→95 is single largest point block (per brief)
        if letters['J']['metric'] == 0.0:
            leverage_opportunities.append({
                'letter': 'J',
                'intervention': 'bid_decisions_generator',
                'potential_gain': '95 points',
                'complexity': 'high',
                'dependencies': ['Shapira V14', 'gen_valuations_comps_batch'],
                'county_agnostic': True
            })
        
        # C/D parity fixes - frozen numerators while denominator grew
        c_metric = letters['C']['metric']
        d_metric = letters['D']['metric']
        if isinstance(c_metric, (int, float)) and c_metric < 95:
            leverage_opportunities.append({
                'letter': 'C/D',
                'intervention': 'propertyonion_supplementary_litmus',
                'potential_gain': f'{95 - c_metric:.1f} + {95 - d_metric:.1f} points',
                'complexity': 'medium',
                'pre_authorized': True,
                'evidence': 'frozen_numerators_growing_denominator'
            })
        
        # H freshness (collier/pinellas specific)
        if county in ['collier', 'pinellas']:
            h_metric = letters['H']['metric']
            if isinstance(h_metric, (int, float)) and h_metric > 48:
                leverage_opportunities.append({
                    'letter': 'H',
                    'intervention': 'freshness_pipeline_fix',
                    'potential_gain': '95 points',
                    'complexity': 'medium',
                    'urgency': 'high' if h_metric > 500 else 'medium'
                })
        
        # Glades full bootstrap
        if county == 'glades' and letters['A']['metric'] == 0:
            leverage_opportunities.append({
                'letter': 'A_bootstrap',
                'intervention': 'full_a_lane_setup',
                'potential_gain': 'all 10 letters',
                'complexity': 'high',
                'priority': 'foundational'
            })
            
        return leverage_opportunities
        
    def _identify_quick_wins(self, letters: Dict) -> List[Dict]:
        """Identify quick wins - letters close to passing"""
        quick_wins = []
        
        for letter, data in letters.items():
            metric = data['metric']
            if isinstance(metric, (int, float)) and 85 <= metric < 95:
                quick_wins.append({
                    'letter': letter,
                    'current': metric,
                    'gap_to_pass': 95 - metric,
                    'intervention': f'incremental_{letter.lower()}_improvement'
                })
                
        return quick_wins
        
    def _identify_blockers(self, letters: Dict) -> List[Dict]:
        """Identify hard blockers requiring fundamental fixes"""
        blockers = []
        
        for letter, data in letters.items():
            if data['metric'] == 'null' or data['metric'] == 0:
                blockers.append({
                    'letter': letter,
                    'type': 'null_metric' if data['metric'] == 'null' else 'zero_metric',
                    'detail': data['detail'],
                    'requires': 'fundamental_pipeline_build'
                })
                
        return blockers
        
    def _criterion_analysis(self, county: str, letters: Dict) -> Dict:
        """Criterion-parallel analysis per 2026-06-12 directive"""
        
        # Fleet-wide criteria that need fixing across all counties
        fleet_wide_issues = []
        
        # J=0 fleet-wide (per brief)
        if letters['J']['metric'] == 0.0:
            fleet_wide_issues.append('J_generator_missing')
            
        # G NULL for all non-brevard counties
        if letters['G']['metric'] == 'null':
            fleet_wide_issues.append('G_zoning_data_missing')
            
        # I NULL dependent on G
        if letters['I']['metric'] == 'null':
            fleet_wide_issues.append('I_property_cards_blocked_by_G')
            
        county_specific = []
        
        # County-specific patterns
        if county in ['collier', 'pinellas'] and letters['H']['status'] == 'FAIL':
            county_specific.append('H_freshness_pipeline_stale')
            
        if county == 'glades' and letters['A']['metric'] == 0:
            county_specific.append('A_lane_bootstrap_required')
            
        return {
            'fleet_wide_fixes_needed': fleet_wide_issues,
            'county_specific_fixes': county_specific,
            'criterion_parallel_priority': self._prioritize_criterion_parallel(fleet_wide_issues)
        }
        
    def _prioritize_criterion_parallel(self, fleet_issues: List[str]) -> List[str]:
        """Prioritize criterion fixes per brief directive"""
        priority_order = []
        
        # J has highest leverage (0→95 single largest point block)
        if 'J_generator_missing' in fleet_issues:
            priority_order.append('J_generator_build')
            
        # G/I are coupled - G data loads enable I
        if 'G_zoning_data_missing' in fleet_issues:
            priority_order.append('G_zoning_substrate_build')
            
        if 'I_property_cards_blocked_by_G' in fleet_issues:
            priority_order.append('I_property_cards_post_G')
            
        return priority_order

def generate_execution_plan() -> Dict:
    """Generate execution plan for SHARD-12"""
    analyzer = LetterAnalyzer()
    
    execution_plan = {
        'session_start': datetime.now(timezone.utc).isoformat(),
        'strategy': 'criterion_parallel_pivot_2026_06_12',
        'target_counties': list(COUNTY_DATA.keys()),
        'county_analyses': {},
        'fleet_wide_fixes': [],
        'execution_order': [],
        'estimated_impact': {}
    }
    
    # Analyze each county
    for county in COUNTY_DATA.keys():
        analysis = analyzer.analyze_county(county)
        execution_plan['county_analyses'][county] = analysis
        
        # Collect fleet-wide fixes
        for fix in analysis['criterion_focus']['fleet_wide_fixes_needed']:
            if fix not in execution_plan['fleet_wide_fixes']:
                execution_plan['fleet_wide_fixes'].append(fix)
    
    # Prioritize execution order per criterion-parallel strategy
    if 'J_generator_missing' in execution_plan['fleet_wide_fixes']:
        execution_plan['execution_order'].append({
            'phase': 1,
            'type': 'criterion_fleet_wide',
            'target': 'J_generator_build',
            'impact': 'all_counties_0_to_95_J',
            'complexity': 'high',
            'county_agnostic': True
        })
    
    if 'G_zoning_data_missing' in execution_plan['fleet_wide_fixes']:
        execution_plan['execution_order'].append({
            'phase': 2, 
            'type': 'criterion_fleet_wide',
            'target': 'G_I_substrate_build',
            'impact': 'enables_G_and_I_for_all',
            'complexity': 'high',
            'dependencies': ['zoning_districts_load', 'parcel_zones_spatial']
        })
    
    # County-specific high-leverage items
    execution_plan['execution_order'].append({
        'phase': 3,
        'type': 'county_specific_high_leverage', 
        'targets': [
            'glades_A_bootstrap',
            'collier_pinellas_H_freshness',
            'cd_parity_supplementary_litmus'
        ]
    })
    
    # Estimate total impact
    total_potential_gain = 0
    for county_analysis in execution_plan['county_analyses'].values():
        for opportunity in county_analysis['high_leverage']:
            if 'potential_gain' in opportunity:
                gain_str = opportunity['potential_gain']
                # Extract numeric value from strings like "95 points"
                import re
                numbers = re.findall(r'\d+(?:\.\d+)?', gain_str)
                if numbers:
                    total_potential_gain += float(numbers[0])
    
    execution_plan['estimated_impact'] = {
        'total_potential_points': total_potential_gain,
        'counties_affected': len(COUNTY_DATA),
        'criterion_leverage': 'high_J_and_GI_fleet_wide'
    }
    
    return execution_plan

def main():
    """Execute analysis and generate execution plan"""
    logger.info("🔍 SHARD-12 CRITERION-PARALLEL ANALYSIS")
    
    try:
        plan = generate_execution_plan()
        
        logger.info("📊 ANALYSIS COMPLETE")
        logger.info("="*60)
        
        # Summary
        print(f"\n📋 EXECUTION PLAN SUMMARY")
        print(f"Strategy: {plan['strategy']}")
        print(f"Counties: {', '.join(plan['target_counties'])}")
        print(f"Fleet-wide fixes needed: {len(plan['fleet_wide_fixes'])}")
        print(f"Estimated total impact: {plan['estimated_impact']['total_potential_points']:.1f} points")
        
        print(f"\n🎯 HIGH-LEVERAGE OPPORTUNITIES:")
        
        for i, phase in enumerate(plan['execution_order'], 1):
            print(f"\nPhase {i}: {phase['type'].replace('_', ' ').title()}")
            if 'target' in phase:
                print(f"  Target: {phase['target']}")
                print(f"  Impact: {phase['impact']}")
                print(f"  Complexity: {phase.get('complexity', 'unknown')}")
            else:
                print(f"  Targets: {', '.join(phase.get('targets', []))}")
        
        print(f"\n📊 COUNTY-SPECIFIC ANALYSIS:")
        for county, analysis in plan['county_analyses'].items():
            print(f"\n{county.upper()} ({analysis['current_score']}):")
            print(f"  Bottlenecks: {', '.join(analysis['bottlenecks'])}")
            print(f"  High-leverage ops: {len(analysis['high_leverage'])}")
            print(f"  Quick wins: {len(analysis['quick_wins'])}")
            print(f"  Blockers: {len(analysis['blockers'])}")
        
        # Save plan for execution scripts
        with open('shard12_execution_plan.json', 'w') as f:
            json.dump(plan, f, indent=2, default=str)
            
        logger.info("✅ Execution plan saved to shard12_execution_plan.json")
        
        return plan
        
    except Exception as e:
        logger.error(f"❌ Analysis failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
    exit_code = 0 if result else 1
    exit(exit_code)