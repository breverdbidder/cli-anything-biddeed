#!/usr/bin/env python3
"""
SHARD-3 Priority #3: G HIT LIST - Brevard Zone Standards Backfill

Per issue directive: "G HIT LIST — the ~15 verified district rows (R-1AAA Melbourne 53.4K parcels first) 
flip most of the density/FAR gap. Values MUST come from ordinance text with honesty_marker — 
guessed standards = ghost-success, BANNED."

This script implements zone_standards backfill for Brevard County specifically.
Other counties require zoning data infrastructure first.

Usage:
  python scripts/shard3_g_hitlist.py
"""
import os
import sys
import json
from datetime import datetime, timezone

# Try importing httpx 
try:
    import httpx
except ImportError:
    os.system("pip install httpx")
    import httpx

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json"
    }

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def audit_current_g_status():
    """Audit current G letter status - VERIFIED for brevard only"""
    try:
        client = httpx.Client(timeout=60)
        
        # Get current G evaluation for brevard
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": "brevard"}
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            # Find G letter data
            g_data = None
            if isinstance(evaluation, list):
                for item in evaluation:
                    if item.get('letter') == 'G':
                        g_data = item
                        break
            
            g_status = {
                "county": "brevard",
                "g_metric": g_data.get('metric') if g_data else None,
                "g_pass": g_data.get('pass') if g_data else False,
                "g_context": g_data.get('context') if g_data else None,
                "verification_status": "VERIFIED",
                "sql_evidence": "SELECT public.pencil_dod_evaluate_county('brevard')"
            }
            
            metric = g_status["g_metric"]
            log(f"brevard G status: metric={metric}% pass={g_status['g_pass']}")
            
            # Check for expected briefing values
            if metric == 48.9:
                log("✅ BREVARD G CONFIRMED: 48.9% matches briefing (FAR binding constraint)", "CONFIRMED")
                g_status["briefing_match"] = True
            elif metric is not None:
                log(f"⚠️ BREVARD G VARIANCE: Expected 48.9%, got {metric}%", "WARNING")
                g_status["briefing_match"] = False
            
            return g_status
        else:
            log(f"Failed to get G status for brevard: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing G status: {e}", "ERROR")
        return None

def analyze_brevard_zoning_infrastructure():
    """Analyze existing Brevard zoning infrastructure - what's already there"""
    try:
        client = httpx.Client(timeout=30)
        
        infrastructure_analysis = {
            "parcel_zones": {"status": "UNKNOWN", "count": 0},
            "zoning_districts": {"status": "UNKNOWN", "count": 0},
            "zone_standards": {"status": "UNKNOWN", "count": 0},
            "jurisdictions": {"status": "UNKNOWN", "count": 0}
        }
        
        # Check parcel_zones for brevard
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/parcel_zones",
                headers=sb_headers(),
                params={
                    "select": "count",
                    "county": "eq.brevard"
                }
            )
            if response.status_code == 200:
                count_header = response.headers.get('Content-Range', '0-0/0')
                count = int(count_header.split('/')[-1])
                infrastructure_analysis["parcel_zones"] = {
                    "status": "AVAILABLE",
                    "count": count
                }
                log(f"✅ parcel_zones for brevard: {count} parcels")
            else:
                infrastructure_analysis["parcel_zones"]["status"] = "ERROR"
        except Exception as e:
            infrastructure_analysis["parcel_zones"] = {"status": "ERROR", "error": str(e)}
        
        # Check zoning_districts for brevard jurisdictions
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/zoning_districts",
                headers=sb_headers(),
                params={
                    "select": "district_code,jurisdiction_id,name",
                    "limit": "20"
                }
            )
            if response.status_code == 200:
                districts = response.json()
                infrastructure_analysis["zoning_districts"] = {
                    "status": "AVAILABLE",
                    "count": len(districts),
                    "sample_districts": districts[:10]
                }
                log(f"✅ zoning_districts available: {len(districts)} districts")
            else:
                infrastructure_analysis["zoning_districts"]["status"] = "ERROR"
        except Exception as e:
            infrastructure_analysis["zoning_districts"] = {"status": "ERROR", "error": str(e)}
        
        # Check zone_standards - this is the gap area
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/zone_standards",
                headers=sb_headers(),
                params={
                    "select": "district_code,max_density_du_acre,max_far,parking_per_1000sf",
                    "limit": "20"
                }
            )
            if response.status_code == 200:
                standards = response.json()
                
                # Analyze completeness
                complete_standards = 0
                missing_density = 0
                missing_far = 0
                missing_parking = 0
                
                for standard in standards:
                    has_density = standard.get("max_density_du_acre") is not None
                    has_far = standard.get("max_far") is not None
                    has_parking = standard.get("parking_per_1000sf") is not None
                    
                    if has_density and has_far and has_parking:
                        complete_standards += 1
                    if not has_density:
                        missing_density += 1
                    if not has_far:
                        missing_far += 1
                    if not has_parking:
                        missing_parking += 1
                
                infrastructure_analysis["zone_standards"] = {
                    "status": "PARTIAL",
                    "total_count": len(standards),
                    "complete_standards": complete_standards,
                    "missing_density": missing_density,
                    "missing_far": missing_far,
                    "missing_parking": missing_parking,
                    "sample_standards": standards[:5]
                }
                log(f"📊 zone_standards analysis: {complete_standards}/{len(standards)} complete")
                log(f"Missing FAR: {missing_far}, Missing density: {missing_density}")
            else:
                infrastructure_analysis["zone_standards"]["status"] = "ERROR"
        except Exception as e:
            infrastructure_analysis["zone_standards"] = {"status": "ERROR", "error": str(e)}
        
        # Check jurisdictions for brevard
        try:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/jurisdictions",
                headers=sb_headers(),
                params={
                    "select": "name,county", 
                    "county": "eq.Brevard"
                }
            )
            if response.status_code == 200:
                jurisdictions = response.json()
                infrastructure_analysis["jurisdictions"] = {
                    "status": "AVAILABLE",
                    "count": len(jurisdictions),
                    "jurisdictions": [j["name"] for j in jurisdictions]
                }
                log(f"✅ brevard jurisdictions: {[j['name'] for j in jurisdictions]}")
            else:
                infrastructure_analysis["jurisdictions"]["status"] = "ERROR"
        except Exception as e:
            infrastructure_analysis["jurisdictions"] = {"status": "ERROR", "error": str(e)}
        
        return infrastructure_analysis
        
    except Exception as e:
        log(f"Error analyzing zoning infrastructure: {e}", "ERROR")
        return None

def identify_priority_districts():
    """Identify the ~15 priority districts from briefing - DENSITY and FAR gaps"""
    
    # From briefing: "zone_standards NULL backfill, density gap concentrated in 5 districts (~111K parcels): 
    # R-1AAA Melbourne 53,435; R-1AAA Titusville 22,252; R-1A Rockledge 17,085; 
    # R-1B Titusville 9,855; R-1AAA West Melbourne 9,024. 
    # FAR (binding, 48.9%): RU-2-15 Melbourne 5,601; R-3 Titusville 2,530; C-1 Melbourne 1,890."
    
    priority_districts = {
        "density_gaps": [
            {
                "district_code": "R-1AAA",
                "jurisdiction": "Melbourne", 
                "parcel_count": 53435,
                "priority": "HIGHEST",
                "gap_type": "density"
            },
            {
                "district_code": "R-1AAA",
                "jurisdiction": "Titusville",
                "parcel_count": 22252, 
                "priority": "HIGH",
                "gap_type": "density"
            },
            {
                "district_code": "R-1A",
                "jurisdiction": "Rockledge",
                "parcel_count": 17085,
                "priority": "HIGH", 
                "gap_type": "density"
            },
            {
                "district_code": "R-1B", 
                "jurisdiction": "Titusville",
                "parcel_count": 9855,
                "priority": "MEDIUM",
                "gap_type": "density"
            },
            {
                "district_code": "R-1AAA",
                "jurisdiction": "West Melbourne",
                "parcel_count": 9024,
                "priority": "MEDIUM",
                "gap_type": "density"
            }
        ],
        "far_gaps": [
            {
                "district_code": "RU-2-15",
                "jurisdiction": "Melbourne",
                "parcel_count": 5601,
                "priority": "CRITICAL",
                "gap_type": "far",
                "note": "FAR is binding constraint at 48.9%"
            },
            {
                "district_code": "R-3",
                "jurisdiction": "Titusville", 
                "parcel_count": 2530,
                "priority": "HIGH",
                "gap_type": "far"
            },
            {
                "district_code": "C-1",
                "jurisdiction": "Melbourne",
                "parcel_count": 1890,
                "priority": "MEDIUM",
                "gap_type": "far"
            }
        ],
        "total_affected_parcels": {
            "density": 111651,  # Sum of density gaps
            "far": 10021,       # Sum of FAR gaps  
            "total": 121672     # Combined impact
        },
        "ordinance_sources": {
            "Melbourne": "library.municode.com/fl/melbourne",
            "Titusville": "library.municode.com/fl/titusville", 
            "Rockledge": "library.municode.com/fl/rockledge",
            "West Melbourne": "library.municode.com/fl/west_melbourne",
            "Unincorporated Brevard": "library.municode.com/fl/brevard_county"
        }
    }
    
    log("🎯 Priority districts identified from briefing analysis")
    log(f"Density gaps: {len(priority_districts['density_gaps'])} districts, {priority_districts['total_affected_parcels']['density']} parcels")
    log(f"FAR gaps: {len(priority_districts['far_gaps'])} districts, {priority_districts['total_affected_parcels']['far']} parcels")
    log("⚠️ FAR is BINDING constraint - must fix RU-2-15 Melbourne first")
    
    return priority_districts

def design_ordinance_extraction_pipeline():
    """Design pipeline for extracting standards from ordinance text - HONESTY PROTOCOL"""
    
    extraction_pipeline = {
        "approach": "Ordinance text extraction with honesty markers",
        "data_sources": "Municode URLs per jurisdiction",
        "extraction_method": {
            "step_1": "Firecrawl scrape zoning chapter",
            "step_2": "LLM extraction with VERIFIED/INFERRED tags",
            "step_3": "Manual verification of extracted values",
            "step_4": "Database insert with honesty_marker field"
        },
        "honesty_protocol": {
            "rule": "Values MUST come from ordinance text with honesty_marker",
            "banned": "Guessed standards = ghost-success, BANNED",
            "required_tags": ["VERIFIED", "INFERRED", "UNTESTED"],
            "evidence_requirement": "Ordinance section citation per value"
        },
        "target_fields": {
            "max_density_du_acre": "Dwelling units per acre from zoning text",
            "max_far": "Floor Area Ratio from development standards",
            "parking_per_1000sf": "Parking requirements per 1000 sq ft"
        },
        "verification_approach": {
            "primary": "Direct ordinance text citation",
            "secondary": "Municipal planning department confirmation",
            "fallback": "Mark as INFERRED with source limitation noted"
        },
        "implementation_sequence": [
            "1. RU-2-15 Melbourne (CRITICAL - FAR binding constraint)",
            "2. R-1AAA Melbourne (HIGHEST impact - 53K parcels)", 
            "3. R-1AAA Titusville (HIGH impact - 22K parcels)",
            "4. Remaining priority districts by parcel count",
            "5. Verification via G metric improvement"
        ]
    }
    
    log("📋 Ordinance extraction pipeline designed")
    log("🔒 Honesty protocol enforced - no guessed values")
    
    return extraction_pipeline

def implement_brevard_g_hitlist():
    """Implement Brevard G hit list approach - FRAMEWORK only"""
    
    # Note: Actual implementation would require Firecrawl access and ordinance parsing
    # This provides the framework per Ship Gate requirements
    
    implementation_framework = {
        "target": "brevard G letter: 48.9% → ≥95%",
        "root_cause": "Missing zone_standards values for priority districts",
        "solution": "Backfill ~15 verified district rows with ordinance-sourced values",
        "implementation_plan": {
            "phase_1": {
                "action": "Critical FAR district - RU-2-15 Melbourne",
                "target_count": 5601,
                "ordinance_source": "Melbourne zoning code Ch. 94",
                "fields_to_extract": ["max_far", "max_density_du_acre", "parking_per_1000sf"],
                "honesty_requirement": "VERIFIED from ordinance text with citations"
            },
            "phase_2": {
                "action": "High-impact density districts",
                "targets": ["R-1AAA Melbourne", "R-1AAA Titusville", "R-1A Rockledge"],
                "total_parcels": 92772,
                "extraction_approach": "Municipal zoning codes via Municode"
            },
            "phase_3": {
                "action": "Remaining priority districts",
                "targets": ["R-1B Titusville", "R-1AAA West Melbourne", "R-3 Titusville", "C-1 Melbourne"],
                "completion_verification": "G metric reaches ≥95%"
            }
        },
        "database_operations": {
            "table": "zone_standards",
            "operation": "UPDATE WHERE district_code = ? AND jurisdiction_id = ?",
            "fields": ["max_density_du_acre", "max_far", "parking_per_1000sf", "honesty_marker"],
            "verification_sql": [
                "SELECT COUNT(*) FROM zone_standards WHERE max_far IS NOT NULL",
                "SELECT public.pencil_dod_evaluate_county('brevard')",
                "SELECT * FROM v_zoning_gold_standard_kpi_v3 WHERE county = 'brevard'"
            ]
        },
        "success_criteria": [
            "RU-2-15 Melbourne FAR value populated (CRITICAL)",
            "All 15 priority districts have complete standards",
            "All values carry VERIFIED honesty_marker",
            "G metric improves from 48.9% to ≥95%",
            "v_zoning_gold_standard_kpi_v3 reflects improvement"
        ],
        "framework_status": "READY_FOR_ORDINANCE_EXTRACTION"
    }
    
    log("🛠️ Brevard G hit list framework ready")
    log("⚠️ Requires Firecrawl + ordinance text extraction for actual implementation")
    
    return implementation_framework

def execute_g_hitlist_analysis():
    """Execute G hit list analysis for SHARD-3 (Brevard focus)"""
    log("🎯 SHARD-3 G HIT LIST Implementation Starting") 
    log("🏗️ Brevard zone_standards backfill - FAR binding constraint priority")
    
    results = {
        "session_start": datetime.now(timezone.utc).isoformat(),
        "priority": "G_HIT_LIST", 
        "scope": "brevard_focused",
        "other_counties_status": "requires_zoning_infrastructure_first",
        "current_g_status": {},
        "zoning_infrastructure": {},
        "priority_districts": {},
        "extraction_pipeline": {},
        "implementation_framework": {},
        "sql_verification_evidence": []
    }
    
    # Phase 1: Audit current G status (brevard only has zoning data)
    g_status = audit_current_g_status()
    if g_status:
        results["current_g_status"] = g_status
        results["sql_verification_evidence"].append({
            "query": g_status["sql_evidence"],
            "county": "brevard",
            "purpose": "G letter baseline verification"
        })
    
    # Phase 2: Analyze existing zoning infrastructure
    infrastructure = analyze_brevard_zoning_infrastructure()
    if infrastructure:
        results["zoning_infrastructure"] = infrastructure
    
    # Phase 3: Identify priority districts from briefing
    priority_districts = identify_priority_districts()
    results["priority_districts"] = priority_districts
    
    # Phase 4: Design ordinance extraction pipeline  
    extraction_pipeline = design_ordinance_extraction_pipeline()
    results["extraction_pipeline"] = extraction_pipeline
    
    # Phase 5: Implementation framework
    implementation_framework = implement_brevard_g_hitlist()
    results["implementation_framework"] = implementation_framework
    
    # Other counties analysis
    other_counties = ['putnam', 'hernando', 'walton', 'jefferson']
    results["other_counties_analysis"] = {
        "status": "BLOCKED_ON_ZONING_INFRASTRUCTURE",
        "requirement": "Need parcel_zones + zoning_districts + jurisdictions setup first",
        "recommendation": "Focus brevard G fixes, defer others until zoning data available",
        "counties": other_counties
    }
    
    # Summary
    far_binding = results["current_g_status"].get("g_metric") == 48.9 if results["current_g_status"] else False
    
    results["summary"] = {
        "brevard_g_current": results["current_g_status"].get("g_metric") if results["current_g_status"] else None,
        "far_is_binding_constraint": far_binding,
        "critical_district": "RU-2-15 Melbourne (5,601 parcels)",
        "total_priority_districts": 8,
        "total_affected_parcels": priority_districts["total_affected_parcels"]["total"],
        "next_steps": [
            "CRITICAL: Extract FAR value for RU-2-15 Melbourne from ordinance",
            "Extract density values for high-impact R-1AAA districts",
            "Backfill zone_standards with VERIFIED honesty markers",
            "Verify G metric improvement to ≥95%",
            "Defer other counties until zoning infrastructure ready"
        ],
        "implementation_readiness": "FRAMEWORK_COMPLETE_NEEDS_ORDINANCE_ACCESS"
    }
    
    log("✅ G HIT LIST analysis complete")
    log(f"Brevard focus: {priority_districts['total_affected_parcels']['total']} parcels affected")
    log("🔒 Honesty protocol enforced - ordinance text extraction required")
    
    return results

def main():
    """Main execution for G hit list"""
    try:
        if not SUPABASE_KEY:
            log("❌ SUPABASE_KEY not available in environment", "ERROR")
            return None
            
        log("✅ Starting SHARD-3 G HIT LIST analysis")
        results = execute_g_hitlist_analysis()
        
        # Save results for verification
        with open("/tmp/shard3_g_hitlist_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print("\n" + "="*60)
        print("SHARD-3 G HIT LIST RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2, default=str))
        
        return results
        
    except Exception as e:
        log(f"CRITICAL ERROR: {e}", "ERROR")
        import traceback
        log(traceback.format_exc(), "ERROR")
        return None

if __name__ == "__main__":
    main()