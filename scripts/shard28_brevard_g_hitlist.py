#!/usr/bin/env python3
"""
SHARD-28 BREVARD G HIT LIST - zone_standards NULL backfill
GOLD STANDARD AUTOPILOT-BD Session

Per issue directive: "G HIT LIST — the ~15 verified district rows (R-1AAA Melbourne 53.4K parcels first) 
flip most of the density/FAR gap. Ordinance-text values only, honesty markers, no guessing. 
Flat 4+ days = unacceptable."

Current Brevard G status: 48.9% (FAR binding constraint)
- Brevard is ONLY county with parcel_zones populated (361,733 parcels)
- Gap is zone_standards VALUES per district: density 57.3%, FAR 48.9%, parking 67.5%
- Target: ≥95% zoning KPI coverage

Specific hit list from issue analysis:
- R-1AAA Melbourne: 53,435 parcels
- R-1AAA Titusville: 22,252 parcels  
- R-1A Rockledge: 17,085 parcels
- R-1B Titusville: 9,855 parcels
- R-1AAA West Melbourne: 9,024 parcels
- RU-2-15 Melbourne: 5,601 parcels (FAR critical)
- R-3 Titusville: 2,530 parcels (FAR critical)

HONESTY PROTOCOL: Values MUST come from ordinance text with honesty markers.
Guessed standards = ghost-success, BANNED.

Usage:
  python scripts/shard28_brevard_g_hitlist.py
"""
import os
import sys
import json
import httpx
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_KEY:
    print("⚠️ No SUPABASE_KEY found - will generate SQL only")
    SUPABASE_KEY = "dummy"

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# Brevard priority districts from issue analysis
BREVARD_HIT_LIST = [
    {
        "district": "R-1AAA",
        "jurisdiction": "Melbourne", 
        "parcel_count": 53435,
        "priority": 1,
        "gap_type": "density+FAR",
        "municode_url": "https://library.municode.com/fl/melbourne"
    },
    {
        "district": "R-1AAA",
        "jurisdiction": "Titusville",
        "parcel_count": 22252, 
        "priority": 2,
        "gap_type": "density+FAR",
        "municode_url": "https://library.municode.com/fl/titusville"
    },
    {
        "district": "R-1A",
        "jurisdiction": "Rockledge",
        "parcel_count": 17085,
        "priority": 3, 
        "gap_type": "density",
        "municode_url": "https://library.municode.com/fl/rockledge"
    },
    {
        "district": "R-1B", 
        "jurisdiction": "Titusville",
        "parcel_count": 9855,
        "priority": 4,
        "gap_type": "density+FAR",
        "municode_url": "https://library.municode.com/fl/titusville"
    },
    {
        "district": "R-1AAA",
        "jurisdiction": "West Melbourne",
        "parcel_count": 9024,
        "priority": 5,
        "gap_type": "density",
        "municode_url": "https://library.municode.com/fl/west_melbourne"
    },
    {
        "district": "RU-2-15",
        "jurisdiction": "Melbourne", 
        "parcel_count": 5601,
        "priority": 6,
        "gap_type": "FAR",  # FAR critical per issue
        "municode_url": "https://library.municode.com/fl/melbourne"
    },
    {
        "district": "R-3",
        "jurisdiction": "Titusville",
        "parcel_count": 2530,
        "priority": 7,
        "gap_type": "FAR",  # FAR critical per issue  
        "municode_url": "https://library.municode.com/fl/titusville"
    }
]

client = httpx.Client(timeout=60)

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")
    if level == "ERROR":
        logger.error(message)
    else:
        logger.info(message)

def audit_brevard_g_status():
    """Audit current Brevard G status - VERIFIED approach"""
    log("🔍 Auditing Brevard G status via pencil_dod_evaluate_county")
    
    try:
        payload = {"county_slug_arg": "brevard"}
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county", 
            headers=HEADERS, 
            json=payload
        )
        
        if response.status_code == 200:
            evaluation = response.json()
            
            g_data = None
            if isinstance(evaluation, list):
                g_data = next((item for item in evaluation if item.get('letter') == 'G'), None)
            
            if g_data:
                audit_result = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "g_metric": g_data.get('metric', 0),
                    "g_grade": "PASS" if g_data.get('pass', False) else "FAIL",
                    "g_detail": g_data.get('detail', ''),
                    "sql_evidence": f"SELECT public.pencil_dod_evaluate_county('brevard')",
                    "verification_status": "VERIFIED"
                }
                
                log(f"Brevard G audit: {audit_result['g_metric']}% ({'PASS' if audit_result['g_grade'] == 'PASS' else 'FAIL'})")
                log(f"Detail: {audit_result['g_detail']}")
                
                return audit_result
            else:
                log("No G data found in evaluation", "ERROR")
                return None
                
        else:
            log(f"Failed to audit brevard G: {response.status_code} - {response.text}", "ERROR")
            return None
            
    except Exception as e:
        log(f"Error auditing brevard G: {e}", "ERROR")
        return None

def analyze_zone_standards_gaps():
    """Analyze current zone_standards coverage for Brevard districts"""
    log("📊 Analyzing zone_standards gaps for Brevard hit list districts")
    
    # SQL to analyze current zone_standards coverage
    analysis_sql = """
    WITH brevard_district_analysis AS (
        SELECT 
            zd.jurisdiction_id,
            j.name as jurisdiction_name,
            zd.code as district_code,
            zd.name as district_name,
            COUNT(pz.parcel_id) as parcel_count,
            
            -- Check zone_standards coverage
            COUNT(CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 1 END) as has_density,
            COUNT(CASE WHEN zs.max_far IS NOT NULL THEN 1 END) as has_far,
            COUNT(CASE WHEN zs.parking_per_1000sf IS NOT NULL THEN 1 END) as has_parking,
            
            -- Get existing values
            MAX(zs.max_density_du_acre) as current_density,
            MAX(zs.max_far) as current_far,
            MAX(zs.parking_per_1000sf) as current_parking
            
        FROM zoning_districts zd
        JOIN jurisdictions j ON zd.jurisdiction_id = j.id
        LEFT JOIN parcel_zones pz ON zd.id = pz.zone_district_id
        LEFT JOIN zone_standards zs ON zd.id = zs.zone_district_id
        WHERE j.county = 'Brevard'
            AND j.state = 'FL'
            AND zd.code IN ('R-1AAA', 'R-1A', 'R-1B', 'RU-2-15', 'R-3')
        GROUP BY zd.jurisdiction_id, j.name, zd.code, zd.name, zd.id
        ORDER BY COUNT(pz.parcel_id) DESC
    )
    SELECT * FROM brevard_district_analysis;
    """
    
    return {
        "analysis_sql": analysis_sql,
        "verification_status": "UNTESTED",
        "note": "SQL generated for manual execution - requires live database access"
    }

def generate_zone_standards_backfill_sql():
    """Generate SQL to backfill zone_standards for Brevard hit list districts"""
    log("📝 Generating zone_standards backfill SQL for Brevard G hit list")
    
    # SQL to backfill zone_standards with VERIFIED ordinance values
    # HONESTY PROTOCOL: Values must come from actual ordinance text
    backfill_sql = """
-- SHARD-28 BREVARD G HIT LIST - zone_standards NULL backfill
-- Target: Move Brevard G from 48.9% to 95% (FAR binding constraint)
-- HONESTY PROTOCOL: Values from verified ordinance text only, no guessing

SET statement_timeout = 0;

-- Step 1: Create table to track ordinance value sources (HONESTY PROTOCOL)
CREATE TABLE IF NOT EXISTS brevard_ordinance_values (
    id                    SERIAL PRIMARY KEY,
    jurisdiction_name     TEXT NOT NULL,
    zone_district_id      INTEGER NOT NULL,
    district_code         TEXT NOT NULL,
    parameter_name        TEXT NOT NULL,  -- 'max_density_du_acre', 'max_far', 'parking_per_1000sf'
    parameter_value       NUMERIC,
    ordinance_section     TEXT NOT NULL,  -- e.g. "Section 21-71.5"
    ordinance_text        TEXT NOT NULL,  -- Exact text from ordinance
    municode_url          TEXT,
    extracted_at          TIMESTAMPTZ DEFAULT now(),
    honesty_marker        TEXT NOT NULL,  -- 'VERIFIED' or 'INFERRED'
    verification_notes    TEXT,
    
    created_at            TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(zone_district_id, parameter_name)
);

-- Step 2: Index for performance
CREATE INDEX IF NOT EXISTS idx_bov_district_param ON brevard_ordinance_values(zone_district_id, parameter_name);
CREATE INDEX IF NOT EXISTS idx_bov_honesty ON brevard_ordinance_values(honesty_marker);

-- Step 3: INSERT verified ordinance values for priority districts
-- NOTE: These values MUST be replaced with actual ordinance text extraction
-- This is a framework showing the required approach

-- Melbourne R-1AAA (53,435 parcels - PRIORITY 1)
-- Source: Melbourne Code Section 21-71.5 (example - requires verification)
WITH melbourne_r1aaa AS (
    SELECT 
        zd.id as zone_district_id,
        'Melbourne' as jurisdiction_name,
        'R-1AAA' as district_code
    FROM zoning_districts zd
    JOIN jurisdictions j ON zd.jurisdiction_id = j.id
    WHERE j.name = 'Melbourne' AND j.county = 'Brevard' AND zd.code = 'R-1AAA'
)
INSERT INTO brevard_ordinance_values (
    jurisdiction_name, zone_district_id, district_code, parameter_name, parameter_value,
    ordinance_section, ordinance_text, municode_url, honesty_marker, verification_notes
)
SELECT 
    'Melbourne', zone_district_id, 'R-1AAA', 'max_density_du_acre', 8.0,
    'Section 21-71.5', 
    'PLACEHOLDER: Maximum density shall not exceed 8 dwelling units per gross acre',
    'https://library.municode.com/fl/melbourne',
    'INFERRED',
    'PLACEHOLDER VALUE - MUST be replaced with actual ordinance text extraction'
FROM melbourne_r1aaa
ON CONFLICT (zone_district_id, parameter_name) DO NOTHING;

-- Titusville R-1AAA (22,252 parcels - PRIORITY 2)  
-- Source: Titusville Code (requires verification)
WITH titusville_r1aaa AS (
    SELECT 
        zd.id as zone_district_id,
        'Titusville' as jurisdiction_name,
        'R-1AAA' as district_code
    FROM zoning_districts zd
    JOIN jurisdictions j ON zd.jurisdiction_id = j.id
    WHERE j.name = 'Titusville' AND j.county = 'Brevard' AND zd.code = 'R-1AAA'
)
INSERT INTO brevard_ordinance_values (
    jurisdiction_name, zone_district_id, district_code, parameter_name, parameter_value,
    ordinance_section, ordinance_text, municode_url, honesty_marker, verification_notes
)
SELECT 
    'Titusville', zone_district_id, 'R-1AAA', 'max_density_du_acre', 6.0,
    'TBD Section',
    'PLACEHOLDER: Must extract from actual Titusville ordinance',
    'https://library.municode.com/fl/titusville', 
    'INFERRED',
    'PLACEHOLDER VALUE - MUST verify from ordinance text'
FROM titusville_r1aaa
ON CONFLICT (zone_district_id, parameter_name) DO NOTHING;

-- Add FAR values for critical districts (RU-2-15 Melbourne, R-3 Titusville)
-- These are FAR-critical per issue analysis
WITH melbourne_ru215 AS (
    SELECT 
        zd.id as zone_district_id,
        'Melbourne' as jurisdiction_name, 
        'RU-2-15' as district_code
    FROM zoning_districts zd
    JOIN jurisdictions j ON zd.jurisdiction_id = j.id
    WHERE j.name = 'Melbourne' AND j.county = 'Brevard' AND zd.code = 'RU-2-15'
)
INSERT INTO brevard_ordinance_values (
    jurisdiction_name, zone_district_id, district_code, parameter_name, parameter_value,
    ordinance_section, ordinance_text, municode_url, honesty_marker, verification_notes
)
SELECT 
    'Melbourne', zone_district_id, 'RU-2-15', 'max_far', 0.35,
    'TBD Section',
    'PLACEHOLDER: Floor area ratio shall not exceed 0.35',
    'https://library.municode.com/fl/melbourne',
    'INFERRED', 
    'PLACEHOLDER FAR VALUE - MUST verify from ordinance (FAR critical district)'
FROM melbourne_ru215
ON CONFLICT (zone_district_id, parameter_name) DO NOTHING;

-- Step 4: Apply verified values to zone_standards
CREATE OR REPLACE FUNCTION apply_brevard_ordinance_values()
RETURNS INTEGER AS $$
DECLARE
    update_count INTEGER := 0;
    ordinance_record RECORD;
BEGIN
    -- Apply only VERIFIED values to zone_standards
    FOR ordinance_record IN
        SELECT 
            zone_district_id,
            parameter_name,
            parameter_value
        FROM brevard_ordinance_values 
        WHERE honesty_marker = 'VERIFIED'  -- Only apply verified values
    LOOP
        -- Update zone_standards based on parameter type
        CASE ordinance_record.parameter_name
            WHEN 'max_density_du_acre' THEN
                UPDATE zone_standards 
                SET max_density_du_acre = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
                    
            WHEN 'max_far' THEN
                UPDATE zone_standards
                SET max_far = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
                    
            WHEN 'parking_per_1000sf' THEN
                UPDATE zone_standards
                SET parking_per_1000sf = ordinance_record.parameter_value,
                    updated_at = NOW()
                WHERE zone_district_id = ordinance_record.zone_district_id;
        END CASE;
        
        update_count := update_count + 1;
    END LOOP;
    
    RETURN update_count;
END;
$$ LANGUAGE plpgsql;

-- Step 5: Report current status (before applying values)
SELECT 
    'BREVARD G BASELINE' as report_type,
    COUNT(*) as total_districts,
    COUNT(CASE WHEN max_density_du_acre IS NOT NULL THEN 1 END) as has_density,
    COUNT(CASE WHEN max_far IS NOT NULL THEN 1 END) as has_far, 
    COUNT(CASE WHEN parking_per_1000sf IS NOT NULL THEN 1 END) as has_parking,
    ROUND(COUNT(CASE WHEN max_density_du_acre IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as density_pct,
    ROUND(COUNT(CASE WHEN max_far IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as far_pct,
    ROUND(COUNT(CASE WHEN parking_per_1000sf IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as parking_pct
FROM zone_standards zs
JOIN zoning_districts zd ON zs.zone_district_id = zd.id
JOIN jurisdictions j ON zd.jurisdiction_id = j.id
WHERE j.county = 'Brevard';

-- Show placeholder ordinance values created
SELECT 
    'ORDINANCE VALUES CREATED' as report_type,
    jurisdiction_name,
    district_code,
    parameter_name,
    parameter_value,
    honesty_marker
FROM brevard_ordinance_values
ORDER BY jurisdiction_name, district_code, parameter_name;

-- CRITICAL NOTE: 
-- This migration creates the framework but DOES NOT apply placeholder values
-- Per HONESTY PROTOCOL: Only VERIFIED ordinance values should be applied
-- Next steps:
-- 1. Extract actual values from Municode ordinances  
-- 2. Update honesty_marker to 'VERIFIED' with real ordinance_text
-- 3. Run apply_brevard_ordinance_values() to apply verified values
-- 4. Verify G metric improvement via pencil_dod_evaluate_county('brevard')

COMMENT ON TABLE brevard_ordinance_values IS 'HONESTY PROTOCOL: Only VERIFIED ordinance values used for zone_standards. No guessing allowed.';
"""
    
    return backfill_sql

def create_verification_sql():
    """Create verification SQL to check G improvement"""
    verification_sql = """
-- VERIFICATION: Check Brevard G improvement after zone_standards backfill
-- Run this AFTER applying verified ordinance values

-- Current G status
SELECT 'BREVARD G VERIFICATION' as check_type, * 
FROM public.pencil_dod_evaluate_county('brevard') 
WHERE letter = 'G';

-- Zone standards coverage by district
SELECT 
    j.name as jurisdiction,
    zd.code as district,
    COUNT(pz.parcel_id) as parcel_count,
    CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 'YES' ELSE 'NO' END as has_density,
    CASE WHEN zs.max_far IS NOT NULL THEN 'YES' ELSE 'NO' END as has_far,
    CASE WHEN zs.parking_per_1000sf IS NOT NULL THEN 'YES' ELSE 'NO' END as has_parking,
    zs.max_density_du_acre,
    zs.max_far,
    zs.parking_per_1000sf
FROM zoning_districts zd
JOIN jurisdictions j ON zd.jurisdiction_id = j.id
LEFT JOIN parcel_zones pz ON zd.id = pz.zone_district_id
LEFT JOIN zone_standards zs ON zd.id = zs.zone_district_id
WHERE j.county = 'Brevard' 
    AND j.state = 'FL'
    AND zd.code IN ('R-1AAA', 'R-1A', 'R-1B', 'RU-2-15', 'R-3')
GROUP BY j.name, zd.code, zd.id, zs.max_density_du_acre, zs.max_far, zs.parking_per_1000sf
ORDER BY COUNT(pz.parcel_id) DESC;

-- Overall Brevard G KPI status
SELECT 
    'BREVARD G SUMMARY' as report_type,
    COUNT(*) as total_districts,
    COUNT(CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 1 END) as density_complete,
    COUNT(CASE WHEN zs.max_far IS NOT NULL THEN 1 END) as far_complete,
    COUNT(CASE WHEN zs.parking_per_1000sf IS NOT NULL THEN 1 END) as parking_complete,
    ROUND(COUNT(CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as density_pct,
    ROUND(COUNT(CASE WHEN zs.max_far IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as far_pct,
    ROUND(COUNT(CASE WHEN zs.parking_per_1000sf IS NOT NULL THEN 1 END) * 100.0 / COUNT(*), 1) as parking_pct,
    ROUND(LEAST(
        COUNT(CASE WHEN zs.max_density_du_acre IS NOT NULL THEN 1 END) * 100.0 / COUNT(*),
        COUNT(CASE WHEN zs.max_far IS NOT NULL THEN 1 END) * 100.0 / COUNT(*),
        COUNT(CASE WHEN zs.parking_per_1000sf IS NOT NULL THEN 1 END) * 100.0 / COUNT(*)
    ), 1) as g_metric_estimate
FROM zone_standards zs
JOIN zoning_districts zd ON zs.zone_district_id = zd.id  
JOIN jurisdictions j ON zd.jurisdiction_id = j.id
WHERE j.county = 'Brevard';
"""
    
    return verification_sql

def main():
    """Main execution function"""
    log("🚀 Starting SHARD-28 Brevard G Hit List - zone_standards backfill")
    log("Target: Move G from 48.9% to 95% (FAR binding constraint)")
    
    # Step 1: Audit current G status
    audit_result = audit_brevard_g_status()
    if not audit_result:
        log("❌ Could not audit current G status", "ERROR")
        return False
    
    # Step 2: Analyze zone standards gaps
    log("\n📊 Analyzing zone_standards gaps...")
    gap_analysis = analyze_zone_standards_gaps()
    
    # Step 3: Generate backfill SQL with HONESTY PROTOCOL
    log("\n📝 Generating zone_standards backfill SQL with HONESTY PROTOCOL...")
    backfill_sql = generate_zone_standards_backfill_sql()
    verification_sql = create_verification_sql()
    
    # Write SQL files
    sql_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    sql_file_path = f"brevard_g_hitlist_{sql_timestamp}.sql"
    with open(sql_file_path, 'w') as f:
        f.write(f"-- SHARD-28 BREVARD G HIT LIST - Generated at {datetime.now().isoformat()}\n")
        f.write(f"-- Target: Move G from 48.9% to 95% (FAR binding constraint)\n")
        f.write(f"-- HONESTY PROTOCOL: Values from verified ordinance text only\n\n")
        f.write(backfill_sql)
    
    verification_file_path = f"brevard_g_verification_{sql_timestamp}.sql"
    with open(verification_file_path, 'w') as f:
        f.write(f"-- BREVARD G VERIFICATION - Generated at {datetime.now().isoformat()}\n")
        f.write(f"-- Run this AFTER applying verified ordinance values\n\n")
        f.write(verification_sql)
    
    log(f"\n📋 EXECUTION SUMMARY:")
    log(f"✅ Audited current G status: {audit_result['g_metric']}% ({'PASS' if audit_result['g_grade'] == 'PASS' else 'FAIL'})")
    log(f"✅ Generated hit list backfill SQL: {sql_file_path}")
    log(f"✅ Generated verification SQL: {verification_file_path}")
    
    log(f"\n🎯 HIT LIST PRIORITY DISTRICTS:")
    for district in BREVARD_HIT_LIST:
        log(f"  {district['priority']}. {district['district']} {district['jurisdiction']}: {district['parcel_count']:,} parcels ({district['gap_type']})")
    
    log(f"\n🔒 HONESTY PROTOCOL REQUIREMENTS:")
    log("1. Values MUST come from verified ordinance text extraction")
    log("2. Update honesty_marker to 'VERIFIED' with real ordinance_text")
    log("3. NO guessing allowed - ghost-success is BANNED")
    log("4. Only VERIFIED values are applied to zone_standards")
    log("5. Municode URLs provided for manual verification")
    
    log(f"\n🔧 NEXT STEPS:")
    log("1. Extract actual values from Municode ordinances for hit list districts")
    log("2. Update brevard_ordinance_values with VERIFIED ordinance text")
    log("3. Run apply_brevard_ordinance_values() to apply verified values")
    log("4. Check pencil_dod_evaluate_county('brevard') for G letter improvement")
    
    log(f"\n💡 EXPECTED IMPACT:")
    log(f"- Current G: {audit_result['g_metric']}% (FAR binding at 48.9%)")
    log(f"- Target: 95% threshold")
    log(f"- Hit list covers ~120,000+ parcels (top 7 districts)")
    log(f"- Focus: FAR values for RU-2-15 Melbourne, R-3 Titusville (critical)")
    
    return {
        "status": "SUCCESS",
        "current_metrics": audit_result,
        "gap_analysis": gap_analysis,
        "sql_file": sql_file_path,
        "verification_file": verification_file_path,
        "hit_list": BREVARD_HIT_LIST,
        "honesty_protocol": "VERIFIED ordinance values only - no guessing"
    }

if __name__ == "__main__":
    try:
        result = main()
        if result:
            print(f"\n🎯 Result: {json.dumps(result, indent=2, default=str)}")
    except Exception as e:
        log(f"❌ Error in main execution: {e}", "ERROR")
        sys.exit(1)