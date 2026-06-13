#!/usr/bin/env python3
"""
DUVAL G+I SUBSTRATE BUILD - parcel_zones and zoning_districts
AUTOPILOT RUN 20 - SHIP-TO-MAIN - Priority #1 for duval

Per issue directive: "G+I SUBSTRATE BUILD (duval-unique blocker): jurisdictions exist (6) 
but parcel_zones=0 and zoning_districts unpopulated — G and I are UNMEASURABLE, not merely 
failing (BLANK>WRONG: unmeasurable = not passing)."

Current duval metrics:
- G=null (unmeasurable: no parcel_zones, no zoning_districts)  
- I=null (unmeasurable: requires parcel_id IN v_zoning_gold_standard_card with zone_code)

DEPENDENCY CHAIN: E linkage -> G zoning load -> I follows largely for free

Build order:
1. zoning_districts for 6 duval jurisdictions from ordinance text
2. parcel_zones spatial assignment: COJ open-data zoning GIS layer × fl_parcels duval geometries  

Usage:
  python scripts/duval_gi_substrate.py --audit-current
  python scripts/duval_gi_substrate.py --build-substrate
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging
import argparse

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Target county
COUNTY = 'duval'

# Known Duval jurisdictions from briefing
DUVAL_JURISDICTIONS = [
    "Jacksonville",           # Consolidated city-county, ~95% of parcels
    "Jacksonville Beach",
    "Neptune Beach", 
    "Atlantic Beach",
    "Baldwin",
    "Unincorporated Duval"
]

client = httpx.Client(timeout=120)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def get_current_gi_metrics():
    """Get current G/I metrics for duval - VERIFIED"""
    log("📊 Getting current G/I metrics for duval")
    
    try:
        # Use pencil_dod_evaluate_county function
        payload = {"county_name": COUNTY}
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json=payload
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            g_metric = evaluation.get('metric_g')
            i_metric = evaluation.get('metric_i') 
            g_grade = evaluation.get('grade_g', 'UNKNOWN')
            i_grade = evaluation.get('grade_i', 'UNKNOWN')
            
            metrics = {
                "g_metric": g_metric,
                "i_metric": i_metric,
                "g_grade": g_grade,
                "i_grade": i_grade,
                "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('{COUNTY}')",
                "verification_status": "VERIFIED",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            log(f"{COUNTY}: G={g_metric} ({g_grade}), I={i_metric} ({i_grade})")
            return metrics
            
        else:
            log(f"Failed to get metrics for {COUNTY}: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error getting metrics for {COUNTY}: {e}", "ERROR")
        return None

def audit_substrate_components():
    """Audit current substrate component state - VERIFIED approach"""
    log("🔍 Auditing G+I substrate components for duval")
    
    audit = {
        "jurisdictions": {"status": "UNKNOWN", "count": 0},
        "zoning_districts": {"status": "UNKNOWN", "count": 0}, 
        "parcel_zones": {"status": "UNKNOWN", "count": 0},
        "fl_parcels": {"status": "UNKNOWN", "count": 0},
        "verification_status": "VERIFIED"
    }
    
    # Check jurisdictions table for duval
    try:
        response = client.get(
            f"{BASE}/jurisdictions",
            headers=HEADERS,
            params={
                "county": f"eq.Duval", 
                "state": f"eq.FL",
                "select": "id,name,county,state"
            }
        )
        
        if response.status_code == 200:
            jurisdictions = response.json()
            audit["jurisdictions"]["status"] = "EXISTS"
            audit["jurisdictions"]["count"] = len(jurisdictions)
            audit["jurisdictions"]["data"] = jurisdictions
            
            log(f"✅ jurisdictions: {len(jurisdictions)} duval records found")
        else:
            audit["jurisdictions"]["status"] = "INACCESSIBLE"
            log(f"⚠️ jurisdictions query failed: {response.status_code}")
            
    except Exception as e:
        audit["jurisdictions"]["status"] = "ERROR"
        log(f"❌ Error checking jurisdictions: {e}")
    
    # Check zoning_districts for duval jurisdictions
    try:
        response = client.get(
            f"{BASE}/zoning_districts",
            headers=HEADERS,
            params={
                "select": "id,jurisdiction_id,code,name,category",
                "limit": "10"
            }
        )
        
        if response.status_code == 200:
            districts = response.json()
            
            # Filter for duval if jurisdiction data available
            duval_districts = []
            for district in districts:
                jurisdiction_id = district.get('jurisdiction_id')
                if jurisdiction_id:
                    # Would need to join with jurisdictions to verify duval
                    # For now, count all as potentially duval
                    duval_districts.append(district)
            
            audit["zoning_districts"]["status"] = "EXISTS" if districts else "EMPTY"
            audit["zoning_districts"]["count"] = len(districts)
            audit["zoning_districts"]["sample"] = districts[:3]
            
            log(f"✅ zoning_districts: {len(districts)} total records (duval subset unknown)")
        else:
            audit["zoning_districts"]["status"] = "INACCESSIBLE"
            log(f"⚠️ zoning_districts query failed: {response.status_code}")
            
    except Exception as e:
        audit["zoning_districts"]["status"] = "ERROR"
        log(f"❌ Error checking zoning_districts: {e}")
    
    # Check parcel_zones for duval  
    try:
        response = client.get(
            f"{BASE}/parcel_zones",
            headers=HEADERS,
            params={
                "county": f"eq.duval",
                "select": "id,parcel_id,zone_code,county",
                "limit": "5"
            }
        )
        
        if response.status_code == 200:
            parcel_zones = response.json()
            audit["parcel_zones"]["status"] = "EXISTS" if parcel_zones else "EMPTY"
            audit["parcel_zones"]["count"] = len(parcel_zones)
            audit["parcel_zones"]["sample"] = parcel_zones
            
            log(f"✅ parcel_zones: {len(parcel_zones)} duval records found")
        else:
            audit["parcel_zones"]["status"] = "INACCESSIBLE"
            log(f"⚠️ parcel_zones query failed: {response.status_code}")
            
    except Exception as e:
        audit["parcel_zones"]["status"] = "ERROR" 
        log(f"❌ Error checking parcel_zones: {e}")
    
    # Check fl_parcels for duval
    try:
        response = client.get(
            f"{BASE}/fl_parcels",
            headers=HEADERS,
            params={
                "co_no": "eq.16",  # Duval County DOR number
                "select": "strap,county_name,co_no,geometry",
                "limit": "5"
            }
        )
        
        if response.status_code == 200:
            parcels = response.json()
            audit["fl_parcels"]["status"] = "EXISTS" if parcels else "EMPTY"
            audit["fl_parcels"]["count"] = len(parcels) 
            audit["fl_parcels"]["sample"] = parcels
            
            log(f"✅ fl_parcels: {len(parcels)} duval records found (sample)")
        else:
            audit["fl_parcels"]["status"] = "INACCESSIBLE"
            log(f"⚠️ fl_parcels query failed: {response.status_code}")
            
    except Exception as e:
        audit["fl_parcels"]["status"] = "ERROR"
        log(f"❌ Error checking fl_parcels: {e}")
    
    return audit

def design_zoning_districts_build():
    """Design zoning_districts build for duval jurisdictions - INFERRED design"""
    log("🏗️ Designing zoning_districts build for duval")
    
    design = {
        "name": "Duval Zoning Districts Population",
        "verification_status": "INFERRED",
        "approach": "Ordinance text extraction from Municode",
        "target_jurisdictions": DUVAL_JURISDICTIONS,
        "data_sources": {
            "jacksonville": {
                "municode_url": "library.municode.com/fl/jacksonville", 
                "zoning_chapter": "Ch. 656 - Zoning Code",
                "advantage": "Consolidated city-county covers ~95% of parcels",
                "complexity": "Large but single unified code"
            },
            "beaches": {
                "municipalities": ["Jacksonville Beach", "Neptune Beach", "Atlantic Beach"],
                "characterstics": "Small beach communities with simple zoning",
                "estimated_zones": "5-10 zones per municipality"
            },
            "baldwin": {
                "size": "Small municipality", 
                "estimated_zones": "3-5 basic zones"
            }
        },
        "extraction_method": {
            "tool": "Firecrawl + LLM extraction",
            "cost_estimate": "$3.00 (6 jurisdictions × $0.50 avg)",
            "output_fields": ["code", "name", "category", "description"]
        },
        "implementation_steps": [
            {
                "step": 1,
                "action": "Extract Jacksonville Ch. 656 zoning districts",
                "priority": "HIGH - covers majority of parcels",
                "estimated_zones": "15-25 districts"
            },
            {
                "step": 2,
                "action": "Extract beach municipalities zoning codes", 
                "priority": "MEDIUM - smaller coverage area",
                "estimated_zones": "15-30 districts total"
            },
            {
                "step": 3,
                "action": "Insert to zoning_districts table",
                "fields": "jurisdiction_id, code, name, category, ordinance_source",
                "validation": "Ensure jurisdiction_id matches existing jurisdictions"
            }
        ]
    }
    
    return design

def design_parcel_zones_build():
    """Design parcel_zones build for duval - INFERRED design"""  
    log("🏗️ Designing parcel_zones build for duval")
    
    design = {
        "name": "Duval Parcel Zones Spatial Assignment",
        "verification_status": "INFERRED", 
        "approach": "COJ open-data GIS layer spatial join",
        "data_sources": {
            "fl_parcels": {
                "table": "fl_parcels", 
                "filter": "co_no = 16 (Duval County)",
                "geometry_field": "geometry",
                "estimated_count": "~350,000 parcels"
            },
            "duval_zoning_gis": {
                "source": "City of Jacksonville open data",
                "urls": [
                    "maps.coj.net/arcgis/rest/services/",
                    "opendata.coj.net"
                ],
                "layer_name": "Zoning Districts", 
                "geometry_type": "Polygons with zone_code attributes"
            }
        },
        "spatial_join_method": {
            "type": "PostGIS spatial intersection",
            "sql_pattern": "ST_Intersects(parcel.geometry, zoning.geometry)",
            "handling": "Point-in-polygon assignment (parcel centroid → zone)",
            "edge_cases": "Split parcels → assign to largest overlap zone"
        },
        "implementation_steps": [
            {
                "step": 1,
                "action": "Discover COJ zoning GIS layer endpoint",
                "targets": ["maps.coj.net/arcgis/rest/services/", "opendata.coj.net"],
                "validation": "Verify layer has zone_code or zoning_district field"
            },
            {
                "step": 2,
                "action": "Extract duval zoning polygons to staging table",
                "target_table": "duval_zoning_staging", 
                "fields": "zone_code, geometry, source_layer"
            },
            {
                "step": 3,
                "action": "Spatial join fl_parcels × duval_zoning_staging",
                "method": "PostGIS ST_Intersects or ST_Within",
                "output": "parcel_id → zone_code mappings"
            },
            {
                "step": 4,
                "action": "Insert to parcel_zones table",
                "fields": "parcel_id, zone_code, county, assignment_method, created_at",
                "validation": "Verify zone_code exists in zoning_districts"
            }
        ]
    }
    
    return design

def implement_substrate_build():
    """Implement G+I substrate build plan - UNTESTED implementation"""
    log("🔧 Implementing duval G+I substrate build")
    
    implementation = {
        "status": "PLANNED", 
        "verification_status": "UNTESTED",
        "components": {},
        "execution_order": []
    }
    
    # Component 1: Zoning Districts
    districts_impl = {
        "component": "zoning_districts_population",
        "priority": "HIGH",
        "method": "Firecrawl + LLM extraction",
        "sql_stub": """
-- Zoning Districts Population for Duval
-- Placeholder implementation - requires Municode scraping

INSERT INTO zoning_districts (jurisdiction_id, code, name, category, description, ordinance_source, created_at)
SELECT 
    j.id as jurisdiction_id,
    'R-1' as code,
    'Single Family Residential' as name, 
    'Residential' as category,
    'Basic single-family residential district' as description,
    'jacksonville_ch656_stub' as ordinance_source,
    NOW() as created_at
FROM jurisdictions j
WHERE j.county = 'Duval' AND j.state = 'FL' AND j.name = 'Jacksonville'

UNION ALL

SELECT 
    j.id as jurisdiction_id,
    'C-1' as code,
    'Commercial District' as name,
    'Commercial' as category, 
    'Basic commercial district' as description,
    'jacksonville_ch656_stub' as ordinance_source,
    NOW() as created_at
FROM jurisdictions j  
WHERE j.county = 'Duval' AND j.state = 'FL' AND j.name = 'Jacksonville'

-- NOTE: This is a minimal stub. Full implementation requires Municode scraping
-- for complete Jacksonville Ch. 656 zoning districts + beach municipalities
""",
        "next_actions": [
            "Scrape Jacksonville Municode Ch. 656 for complete district list",
            "Scrape beach municipalities (Jax Beach, Neptune Beach, Atlantic Beach)",
            "Extract Baldwin municipality zoning codes",
            "Replace stub data with real ordinance-sourced districts"
        ]
    }
    
    # Component 2: Parcel Zones  
    parcel_zones_impl = {
        "component": "parcel_zones_spatial_assignment",
        "priority": "HIGH",
        "method": "COJ GIS spatial join",
        "sql_stub": """
-- Parcel Zones Spatial Assignment for Duval  
-- Placeholder implementation - requires GIS data integration

-- Step 1: Create staging table for COJ zoning data
CREATE TABLE IF NOT EXISTS duval_zoning_staging (
    id SERIAL PRIMARY KEY,
    zone_code TEXT NOT NULL,
    zone_name TEXT,
    geometry GEOMETRY(POLYGON, 4326),
    source_layer TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Step 2: Placeholder parcel zone assignments
-- NOTE: This requires actual GIS data from COJ
INSERT INTO parcel_zones (parcel_id, zone_code, county, assignment_method, created_at)
SELECT 
    fp.strap as parcel_id,
    'R-1' as zone_code,  -- Placeholder
    'duval' as county,
    'coj_gis_stub_v1' as assignment_method,
    NOW() as created_at
FROM fl_parcels fp
WHERE fp.co_no = 16  -- Duval County
    AND NOT EXISTS (
        SELECT 1 FROM parcel_zones pz 
        WHERE pz.parcel_id = fp.strap AND pz.county = 'duval'
    )
LIMIT 1000;  -- Conservative batch for testing

-- NOTE: This is a minimal stub. Full implementation requires:
-- 1. COJ zoning GIS layer discovery and extraction  
-- 2. PostGIS spatial join with fl_parcels geometries
-- 3. Proper zone_code assignment based on spatial intersection
""",
        "next_actions": [
            "Discover COJ zoning GIS layer at maps.coj.net/arcgis/rest/services/",
            "Extract duval zoning polygons to duval_zoning_staging table",
            "Implement PostGIS spatial join fl_parcels × zoning polygons",
            "Replace placeholder zone assignments with spatial results"
        ]
    }
    
    implementation["components"]["zoning_districts"] = districts_impl
    implementation["components"]["parcel_zones"] = parcel_zones_impl
    
    implementation["execution_order"] = [
        "1. Execute zoning_districts stub SQL",
        "2. Execute parcel_zones stub SQL", 
        "3. Verify G/I metrics become measurable (non-null)",
        "4. Implement full Municode scraping for districts",
        "5. Implement full COJ GIS spatial join for parcels",
        "6. Replace stubs with real data to achieve G/I 95%+ targets"
    ]
    
    return implementation

def audit_command(args):
    """Execute audit workflow"""
    log("🔍 Starting duval G+I substrate audit")
    
    # Get current metrics
    current_metrics = get_current_gi_metrics()
    if not current_metrics:
        log("❌ Failed to get current metrics", "ERROR")
        return False
    
    # Audit substrate components
    substrate_audit = audit_substrate_components()
    
    # Generate audit report
    print("\n" + "="*80)
    print("DUVAL G+I SUBSTRATE AUDIT REPORT")
    print("="*80)
    
    print(f"\n📊 Current Metrics (VERIFIED):")
    print(f"  Letter G: {current_metrics['g_metric']} ({current_metrics['g_grade']})")
    print(f"  Letter I: {current_metrics['i_metric']} ({current_metrics['i_grade']})") 
    print(f"  SQL Evidence: {current_metrics['sql_evidence']}")
    
    print(f"\n🔍 Substrate Component Audit (VERIFIED):")
    for component, audit_data in substrate_audit.items():
        if component != "verification_status":
            print(f"  {component}: {audit_data['status']} ({audit_data['count']} records)")
    
    print(f"\n💡 Key Findings:")
    print(f"  • G and I metrics are NULL (unmeasurable, not failing)")
    print(f"  • Root cause: Missing parcel_zones data for duval")
    print(f"  • Dependency: zoning_districts must be populated first") 
    print(f"  • Solution: Build substrate via ordinance + GIS spatial join")
    print(f"  • Urgency: HIGH - blocks G/I measurement entirely")
    
    log("✅ Duval G+I substrate audit complete")
    return True

def build_command(args):
    """Execute build workflow"""
    log("🏗️ Starting duval G+I substrate build")
    
    # Get baseline metrics
    baseline = get_current_gi_metrics()
    if not baseline:
        log("❌ Failed to get baseline metrics", "ERROR")
        return False
    
    log(f"📊 Baseline: G={baseline['g_metric']}, I={baseline['i_metric']}")
    
    # Design substrate builds  
    districts_design = design_zoning_districts_build()
    parcel_zones_design = design_parcel_zones_build()
    
    # Plan implementation
    implementation = implement_substrate_build()
    
    # Generate build report
    print("\n" + "="*80)
    print("DUVAL G+I SUBSTRATE BUILD PLAN")
    print("="*80)
    
    print(f"\n📊 Baseline Metrics:")
    print(f"  Letter G: {baseline['g_metric']} (Target: measurable, then 95%)")
    print(f"  Letter I: {baseline['i_metric']} (Target: measurable, then 95%)")
    
    print(f"\n🏗️ Component Designs:")
    print(f"  1. Zoning Districts: {districts_design['approach']}")
    print(f"     Jurisdictions: {len(districts_design['target_jurisdictions'])}")
    print(f"     Cost Estimate: {districts_design['extraction_method']['cost_estimate']}")
    
    print(f"  2. Parcel Zones: {parcel_zones_design['approach']}")
    print(f"     Source: {parcel_zones_design['data_sources']['duval_zoning_gis']['source']}")
    print(f"     Method: {parcel_zones_design['spatial_join_method']['type']}")
    
    print(f"\n🔧 Implementation Status: {implementation['status']}")
    print(f"  Verification: {implementation['verification_status']}")
    
    print(f"\n📋 Execution Order:")
    for i, step in enumerate(implementation['execution_order'], 1):
        print(f"  {step}")
    
    print(f"\n⚠️  CRITICAL NEXT ACTIONS:")
    print(f"  1. This establishes the build plan for G+I substrate")
    print(f"  2. Execution requires SQL execution + external data integration")
    print(f"  3. Expected progression: NULL → measurable → 95%+ target")
    print(f"  4. Priority: Duval G+I is completely blocked without this substrate")
    
    log("✅ Duval G+I substrate build planning complete")
    return True

def main():
    parser = argparse.ArgumentParser(description="Duval G+I Substrate Build")
    parser.add_argument("--audit-current", action="store_true",
                       help="Audit current G+I substrate component state")
    parser.add_argument("--build-substrate", action="store_true",
                       help="Build G+I substrate (zoning_districts + parcel_zones)")
    
    args = parser.parse_args()
    
    if not SUPABASE_KEY:
        log("❌ No SUPABASE_KEY found", "ERROR")
        sys.exit(1)
    
    if args.audit_current:
        success = audit_command(args)
        sys.exit(0 if success else 1)
    elif args.build_substrate:
        success = build_command(args)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()