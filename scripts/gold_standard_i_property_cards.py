#!/usr/bin/env python3
"""
Gold Standard Letter I: Property Card Complete Implementation  
Builds property card completion pipeline for I letter requirements.

Letter I requirement: >=95% property card complete
Property card complete = address + geo + value + zoned parcel

Dependencies per brief:
- I <= E by construction (card requires parcel_id)
- I requires parcel_id IN v_zoning_gold_standard_card with zone_code
- Order: E linkage -> G zoning load -> I follows largely for free

Counties: charlotte, citrus, broward (SHARD-19)
"""
import os
import requests
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

class PropertyCardBuilder:
    """Build I letter property card completion pipeline"""
    
    def __init__(self, county: str):
        self.county = county.lower()
        self.session_start = datetime.now(timezone.utc)
        self.results = {}
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"[{timestamp}] {level}: {self.county.upper()} - {message}")
    
    def analyze_property_card_requirements(self) -> Dict:
        """Analyze property card complete requirements - INFERRED from brief"""
        
        self.log("🏠 Analyzing property card complete requirements...")
        
        requirements = {
            "definition": "Property card complete = address + geo + value + zoned parcel",
            "components": {
                "address": {
                    "fields": ["street_address", "city", "state", "zip_code"],
                    "source": "County property appraiser records",
                    "quality": "Standardized, geocodable addresses"
                },
                "geo": {
                    "fields": ["latitude", "longitude", "parcel_geometry"],
                    "source": "County GIS parcel boundaries", 
                    "quality": "Accurate spatial coordinates"
                },
                "value": {
                    "fields": ["assessed_value", "market_value", "land_value", "improvement_value"],
                    "source": "County property appraiser valuations",
                    "quality": "Current tax year assessments"
                },
                "zoned_parcel": {
                    "fields": ["zone_code", "zoning_district", "permitted_uses"],
                    "source": "v_zoning_gold_standard_card with zone_code",
                    "quality": "Complete zoning classification"
                }
            },
            "dependencies": [
                "E letter: parcel_id linkage (prerequisite)",
                "G letter: zoning data load (prerequisite)",
                "County appraiser API/scraping capability",
                "GIS parcel boundary access"
            ],
            "canonical_threshold": ">=95% property cards complete",
            "honesty_marker": "INFERRED from brief - actual property card schema UNTESTED"
        }
        
        self.log("📋 Property card requirements analyzed")
        self.log(f"   Components: {len(requirements['components'])} required sections")
        self.log(f"   Dependencies: {len(requirements['dependencies'])} prerequisites")
        
        return requirements
    
    def analyze_dependency_status(self) -> Dict:
        """Analyze E and G letter dependency status for county"""
        
        self.log("🔗 Analyzing dependency status (E linkage + G zoning)...")
        
        # Based on brief metrics for county
        brief_metrics = {
            'charlotte': {'E_metric': 43.8, 'G_metric': 'null'},
            'citrus': {'E_metric': 95.3, 'G_metric': 'null'},  # E PASS
            'broward': {'E_metric': 20.6, 'G_metric': 'null'}
        }
        
        county_metrics = brief_metrics.get(self.county, {})
        e_metric = county_metrics.get('E_metric')
        g_metric = county_metrics.get('G_metric')
        
        dependency_status = {
            "E_parcel_linkage": {
                "current_metric": e_metric,
                "status": "PASS" if e_metric and e_metric >= 95.0 else "FAIL",
                "required_for_I": "parcel_id linkage enables property lookups",
                "county_specific": f"{e_metric}% parcel linkage" if e_metric else "No linkage data"
            },
            "G_zoning_data": {
                "current_metric": g_metric,
                "status": "FAIL" if g_metric == 'null' else "UNKNOWN",
                "required_for_I": "zone_code enables v_zoning_gold_standard_card lookup",
                "county_specific": "No zoning data loaded" if g_metric == 'null' else f"Metric: {g_metric}"
            },
            "I_readiness": "BLOCKED" if (not e_metric or e_metric < 95.0) or g_metric == 'null' else "READY"
        }
        
        self.log(f"📊 Dependency analysis:")
        self.log(f"   E (parcel linkage): {dependency_status['E_parcel_linkage']['status']} ({e_metric}%)")
        self.log(f"   G (zoning data): {dependency_status['G_zoning_data']['status']}")
        self.log(f"   I readiness: {dependency_status['I_readiness']}")
        
        return dependency_status
    
    def get_county_appraiser_config(self) -> Dict:
        """Get county property appraiser configuration - INFERRED from patterns"""
        
        appraiser_configs = {
            'charlotte': {
                'appraiser_url': 'https://www.ccappraiser.com',  # INFERRED
                'search_endpoint': '/property-search',
                'api_pattern': 'REST API or scraping interface',
                'data_source': 'charlotte_appraiser:PROPERTY_V1'
            },
            'citrus': {
                'appraiser_url': 'https://www.citruspa.org',  # INFERRED
                'search_endpoint': '/property-search', 
                'api_pattern': 'REST API or scraping interface',
                'data_source': 'citrus_appraiser:PROPERTY_V1'
            },
            'broward': {
                'appraiser_url': 'https://web.bcpa.net',  # INFERRED
                'search_endpoint': '/property-search',
                'api_pattern': 'REST API or scraping interface', 
                'data_source': 'broward_appraiser:PROPERTY_V1'
            }
        }
        
        config = appraiser_configs.get(self.county, {})
        
        self.log(f"🏛️ County appraiser config:")
        self.log(f"   URL: {config.get('appraiser_url', 'UNKNOWN')}")
        self.log(f"   Data source: {config.get('data_source', 'UNKNOWN')}")
        
        return config
    
    def get_county_gis_config(self) -> Dict:
        """Get county GIS configuration for parcel boundaries"""
        
        # Based on brief patterns and county GIS discovery
        gis_configs = {
            'charlotte': {
                'gis_url': 'https://gis.charlotte.fl.gov',  # INFERRED
                'arcgis_rest': '/arcgis/rest/services/',
                'parcel_layer': 'Parcels/MapServer',
                'geometry_field': 'SHAPE'
            },
            'citrus': {
                'gis_url': 'https://gis.citrus.fl.gov',  # INFERRED  
                'arcgis_rest': '/arcgis/rest/services/',
                'parcel_layer': 'Parcels/MapServer',
                'geometry_field': 'SHAPE'
            },
            'broward': {
                'gis_url': 'https://gis.broward.org',  # INFERRED
                'arcgis_rest': '/arcgis/rest/services/',
                'parcel_layer': 'Parcels/MapServer', 
                'geometry_field': 'SHAPE'
            }
        }
        
        config = gis_configs.get(self.county, {})
        
        self.log(f"🗺️ County GIS config:")
        self.log(f"   URL: {config.get('gis_url', 'UNKNOWN')}")
        self.log(f"   Parcel layer: {config.get('parcel_layer', 'UNKNOWN')}")
        
        return config
    
    def define_enrichment_pipeline(self) -> Dict:
        """Define address/geo/value enrichment pipeline"""
        
        self.log("🔧 Defining property card enrichment pipeline...")
        
        pipeline = {
            "input_source": "multi_county_auctions with parcel_id linkage (E prerequisite)",
            "enrichment_stages": {
                "stage_1_address": {
                    "source": "County property appraiser records",
                    "method": "Parcel ID lookup → standardized address",
                    "output_fields": ["street_address", "city", "state", "zip_code"],
                    "quality_check": "Address standardization + geocoding validation"
                },
                "stage_2_geo": {
                    "source": "County GIS parcel boundaries",
                    "method": "Parcel ID → parcel geometry + centroid coordinates",
                    "output_fields": ["latitude", "longitude", "parcel_geometry"],
                    "quality_check": "Spatial coordinate validation"
                },
                "stage_3_value": {
                    "source": "County property appraiser valuations",
                    "method": "Parcel ID → current tax assessments", 
                    "output_fields": ["assessed_value", "market_value", "land_value", "improvement_value"],
                    "quality_check": "Current tax year validation"
                },
                "stage_4_zoning": {
                    "source": "v_zoning_gold_standard_card (G prerequisite)",
                    "method": "Parcel ID → zoning classification",
                    "output_fields": ["zone_code", "zoning_district", "permitted_uses"],
                    "quality_check": "Complete zoning data validation"
                }
            },
            "output_table": "property_cards_complete OR enhanced multi_county_auctions",
            "completion_criteria": "All 4 stages successful for >=95% of auctions",
            "processing_approach": "Batch processing by county with error handling"
        }
        
        self.log("📋 Enrichment pipeline defined")
        self.log(f"   Stages: {len(pipeline['enrichment_stages'])}")
        self.log(f"   Target: {pipeline['completion_criteria']}")
        
        return pipeline
    
    def estimate_county_workload(self) -> Dict:
        """Estimate property card completion workload for county"""
        
        # Based on brief metrics
        county_data = {
            'charlotte': {'auctions': 8106, 'field_complete': 1423, 'zoned_complete': 0},
            'citrus': {'auctions': 5512, 'field_complete': 1473, 'zoned_complete': 0},
            'broward': {'auctions': 30109, 'field_complete': 737, 'zoned_complete': 0}
        }
        
        data = county_data.get(self.county, {})
        total_auctions = data.get('auctions', 0)
        current_field_complete = data.get('field_complete', 0)
        current_zoned_complete = data.get('zoned_complete', 0)
        
        target_complete = int(total_auctions * 0.95)  # 95% canon threshold
        gap = target_complete - current_zoned_complete
        
        workload = {
            "total_auctions": total_auctions,
            "current_field_complete": current_field_complete,
            "current_zoned_complete": current_zoned_complete,
            "target_complete": target_complete,
            "completion_gap": gap,
            "workload_estimate": f"{gap:,} properties need complete cards",
            "completion_rate": f"{(current_zoned_complete / total_auctions * 100):.1f}%" if total_auctions > 0 else "0%"
        }
        
        self.log(f"📊 Workload estimate:")
        self.log(f"   Total auctions: {total_auctions:,}")
        self.log(f"   Current complete: {current_zoned_complete:,} ({workload['completion_rate']})")
        self.log(f"   Target complete: {target_complete:,}")
        self.log(f"   Gap: {gap:,} properties")
        
        return workload
    
    def build_property_card_pipeline(self) -> Dict:
        """Build complete property card pipeline for county"""
        
        self.log(f"🔧 Building Letter I property card pipeline for {self.county}")
        
        # Component analysis
        requirements = self.analyze_property_card_requirements()
        dependencies = self.analyze_dependency_status()
        appraiser_config = self.get_county_appraiser_config()
        gis_config = self.get_county_gis_config()
        enrichment_pipeline = self.define_enrichment_pipeline()
        workload = self.estimate_county_workload()
        
        # Complete pipeline
        pipeline = {
            "county": self.county,
            "session_timestamp": self.session_start.isoformat(),
            "requirements": requirements,
            "dependency_status": dependencies,
            "data_sources": {
                "appraiser_config": appraiser_config,
                "gis_config": gis_config
            },
            "enrichment_pipeline": enrichment_pipeline,
            "workload_estimate": workload,
            "implementation_steps": [
                "1. PREREQUISITE CHECK: Verify E >= 95% (parcel linkage)",
                "2. PREREQUISITE CHECK: Verify G data loaded (zoning)",
                "3. Discover county appraiser API/scraping capability",
                "4. Discover county GIS parcel boundary access",
                "5. Build address enrichment (stage 1)",
                "6. Build geo enrichment (stage 2)",  
                "7. Build value enrichment (stage 3)",
                "8. Build zoning enrichment (stage 4)",
                "9. Batch process all county auctions",
                "10. Verify I metric via pencil_dod_evaluate_county"
            ],
            "blocking_conditions": [
                f"E metric < 95% ({dependencies['E_parcel_linkage']['current_metric']}%)",
                f"G data not loaded ({dependencies['G_zoning_data']['current_metric']})"
            ] if dependencies['I_readiness'] == 'BLOCKED' else [],
            "canon_requirement": ">=95% property cards complete (address + geo + value + zoned)",
            "honesty_marker": "FRAMEWORK_READY - dependencies BLOCKING, implementation pending"
        }
        
        pipeline_status = "READY" if dependencies['I_readiness'] == 'READY' else "BLOCKED"
        
        self.log(f"✅ Letter I pipeline built")
        self.log(f"   Status: {pipeline_status}")
        self.log(f"   Target: {workload['target_complete']:,} complete cards")
        self.log(f"   Gap: {workload['completion_gap']:,} properties")
        
        return pipeline

def build_all_counties():
    """Build I letter pipeline for all SHARD-19 counties"""
    
    counties = ['charlotte', 'citrus', 'broward']
    results = {}
    
    print("🚀 Building Letter I: Property Card Complete Pipeline") 
    print(f"Counties: {', '.join(counties)}")
    print("="*60)
    
    for county in counties:
        print(f"\n📍 Processing {county.upper()}")
        builder = PropertyCardBuilder(county)
        pipeline = builder.build_property_card_pipeline()
        results[county] = pipeline
        
        status = "READY" if pipeline['dependency_status']['I_readiness'] == 'READY' else "BLOCKED"
        print(f"✅ {county} pipeline: {status}")
    
    # Summary
    print("\n" + "="*60)
    print("LETTER I IMPLEMENTATION SUMMARY")
    print("="*60)
    
    total_gap = 0
    ready_counties = 0
    
    for county, pipeline in results.items():
        workload = pipeline['workload_estimate']
        gap = workload['completion_gap']
        status = "READY" if pipeline['dependency_status']['I_readiness'] == 'READY' else "BLOCKED"
        
        total_gap += gap
        if status == "READY":
            ready_counties += 1
        
        dependencies_met = len(pipeline['blocking_conditions']) == 0
        blocking = pipeline['blocking_conditions'] if not dependencies_met else ["None"]
        
        print(f"{county:>10}: {gap:,} gap | Status: {status}")
        if pipeline['blocking_conditions']:
            for block in pipeline['blocking_conditions']:
                print(f"           BLOCKED BY: {block}")
    
    print(f"{'TOTAL':>10}: {total_gap:,} properties need complete cards")
    print(f"{'READY':>10}: {ready_counties}/{len(counties)} counties")
    print(f"\nDependency order: E linkage -> G zoning -> I follows largely for free")
    print(f"Implementation approach: 4-stage enrichment (address + geo + value + zoning)")
    print(f"Status: FRAMEWORK_READY - dependencies must be resolved first")
    
    return results

if __name__ == "__main__":
    results = build_all_counties()
    
    # Save results
    with open("/tmp/letter_i_property_cards_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to: /tmp/letter_i_property_cards_results.json")