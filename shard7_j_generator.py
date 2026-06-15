#!/usr/bin/env python3
"""
SHARD-7 J Generator - Build bid_decisions pipeline
Counties: leon, clay, miami_dade, columbia, madison

Per briefing directive: "J ROOT CAUSE SIZED (VERIFIED 2026-06-12): bid_decisions total=21 rows, 
0 with ml_score, 0 with factor keys. The generator does not exist. Build to the evaluator 
contract exactly: bid_decisions row matched by case_number with arv + max_bid + ml_score + 
factors containing ALL of distress_location, distress_property, distress_owner, cma_distressed, 
cma_resale. Shapira V14 (shapira_models, AUC .78) supplies ml_score; gen_valuations_comps_batch 
supplies CMA inputs. County-agnostic; brevard+duval first."

Target: J=95% completion (bid_decisions with all required fields)
Current: J=0% all counties

Implementation:
1. Build bid_decisions table population pipeline
2. Integrate Shapira V14 ML model for ml_score
3. Connect gen_valuations_comps_batch for CMA inputs
4. Populate factor keys from property/location analysis
5. Wire to executor for scheduling

Usage:
  python shard7_j_generator.py
"""
import os
import sys
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Try to import HTTP client
try:
    import httpx
    HTTP_LIB = 'httpx'
except ImportError:
    try:
        import requests as httpx
        HTTP_LIB = 'requests'
    except ImportError:
        print("❌ No HTTP library available")
        sys.exit(1)

print(f"✅ Using {HTTP_LIB} for HTTP requests")

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"

if not SUPABASE_KEY:
    print("⚠️ No SUPABASE_KEY found - will generate SQL/analysis only")
    SUPABASE_KEY = "dummy"

HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-7 target counties
SHARD7_COUNTIES = ['leon', 'clay', 'miami_dade', 'columbia', 'madison']

def log(message, level="INFO"):
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[{timestamp}] {level}: {message}")

def make_request(method, url, **kwargs):
    """Make HTTP request using available library"""
    if HTTP_LIB == 'httpx':
        client = httpx.Client(timeout=60)
        if method == 'GET':
            return client.get(url, **kwargs)
        elif method == 'POST':
            return client.post(url, **kwargs)
    else:  # requests
        import requests
        if method == 'GET':
            return requests.get(url, **kwargs)
        elif method == 'POST':
            return requests.post(url, **kwargs)

def analyze_existing_bid_decisions():
    """Analyze current bid_decisions table to understand gaps"""
    log("🔍 Analyzing existing bid_decisions table")
    
    try:
        # Get current bid_decisions rows
        response = make_request(
            'GET',
            f"{BASE}/bid_decisions",
            headers=HEADERS,
            params={
                "select": "case_number,county,arv,max_bid,ml_score,factors,created_at",
                "order": "created_at.desc",
                "limit": "100"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            total = len(data)
            
            # Analyze completeness
            with_arv = sum(1 for row in data if row.get('arv'))
            with_max_bid = sum(1 for row in data if row.get('max_bid'))
            with_ml_score = sum(1 for row in data if row.get('ml_score'))
            with_factors = sum(1 for row in data if row.get('factors'))
            
            # Analyze by county
            by_county = {}
            for row in data:
                county = row.get('county', 'unknown')
                if county not in by_county:
                    by_county[county] = 0
                by_county[county] += 1
            
            log(f"  Total bid_decisions: {total}")
            log(f"  With ARV: {with_arv} ({with_arv/total*100:.1f}%)")
            log(f"  With max_bid: {with_max_bid} ({with_max_bid/total*100:.1f}%)")
            log(f"  With ml_score: {with_ml_score} ({with_ml_score/total*100:.1f}%)")
            log(f"  With factors: {with_factors} ({with_factors/total*100:.1f}%)")
            
            log(f"  By county:")
            for county, count in sorted(by_county.items()):
                log(f"    {county}: {count}")
            
            return {
                'total': total,
                'completeness': {
                    'arv': with_arv/total*100 if total > 0 else 0,
                    'max_bid': with_max_bid/total*100 if total > 0 else 0,
                    'ml_score': with_ml_score/total*100 if total > 0 else 0,
                    'factors': with_factors/total*100 if total > 0 else 0
                },
                'by_county': by_county,
                'sample_data': data[:5]  # First 5 for inspection
            }
        else:
            log(f"  Failed to get bid_decisions: {response.status_code}", "ERROR")
            return None
            
    except Exception as e:
        log(f"  Error analyzing bid_decisions: {e}", "ERROR")
        return None

def analyze_valuations_comps_source():
    """Analyze gen_valuations_comps_batch to understand available CMA inputs"""
    log("🔍 Analyzing valuations_comps data availability")
    
    try:
        # Check valuations_comps table structure and data
        response = make_request(
            'GET',
            f"{BASE}/valuations_comps",
            headers=HEADERS,
            params={
                "select": "property_id,county,arv,comps_count,cma_distressed,cma_resale,created_at",
                "order": "created_at.desc",
                "limit": "50"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            total = len(data)
            
            if total == 0:
                log(f"  ❌ No valuations_comps data found")
                return None
            
            # Analyze CMA data availability
            with_arv = sum(1 for row in data if row.get('arv'))
            with_cma_distressed = sum(1 for row in data if row.get('cma_distressed'))
            with_cma_resale = sum(1 for row in data if row.get('cma_resale'))
            
            # Analyze by county for SHARD-7
            shard7_data = [row for row in data if row.get('county') in SHARD7_COUNTIES]
            
            log(f"  Total valuations_comps: {total}")
            log(f"  With ARV: {with_arv} ({with_arv/total*100:.1f}%)")
            log(f"  With CMA distressed: {with_cma_distressed} ({with_cma_distressed/total*100:.1f}%)")
            log(f"  With CMA resale: {with_cma_resale} ({with_cma_resale/total*100:.1f}%)")
            log(f"  SHARD-7 counties data: {len(shard7_data)}")
            
            return {
                'total': total,
                'shard7_count': len(shard7_data),
                'cma_availability': {
                    'arv': with_arv/total*100 if total > 0 else 0,
                    'distressed': with_cma_distressed/total*100 if total > 0 else 0,
                    'resale': with_cma_resale/total*100 if total > 0 else 0
                }
            }
        else:
            log(f"  Failed to get valuations_comps: {response.status_code}", "WARN")
            return None
            
    except Exception as e:
        log(f"  Error analyzing valuations_comps: {e}", "ERROR")
        return None

def get_auction_candidates_for_j(county_slug):
    """Get auctions that could have bid_decisions generated"""
    log(f"🎯 Getting J generation candidates for {county_slug}")
    
    try:
        # Get auctions that don't yet have bid_decisions
        response = make_request(
            'GET',
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": county_slug,
                "select": "case_number,property_address,parcel_id,final_judgment_amount",
                "limit": "100"
            }
        )
        
        if response.status_code == 200:
            auctions = response.json()
            
            # Check which already have bid_decisions
            if auctions:
                case_numbers = [a['case_number'] for a in auctions if a.get('case_number')]
                
                if case_numbers:
                    # Query existing bid_decisions
                    case_filter = ','.join(f'"{cn}"' for cn in case_numbers[:50])  # Limit to avoid URL length issues
                    
                    bd_response = make_request(
                        'GET',
                        f"{BASE}/bid_decisions",
                        headers=HEADERS,
                        params={
                            "case_number": f"in.({case_filter})",
                            "select": "case_number"
                        }
                    )
                    
                    existing_cases = set()
                    if bd_response.status_code == 200:
                        existing_bid_decisions = bd_response.json()
                        existing_cases = {bd['case_number'] for bd in existing_bid_decisions}
                    
                    # Filter to candidates without bid_decisions
                    candidates = [a for a in auctions if a.get('case_number') not in existing_cases]
                    
                    log(f"  {county_slug}: {len(auctions)} total auctions")
                    log(f"  {county_slug}: {len(existing_cases)} with bid_decisions")
                    log(f"  {county_slug}: {len(candidates)} candidates for J generation")
                    
                    return candidates[:20]  # Return top 20 candidates
                else:
                    log(f"  {county_slug}: No case numbers found")
                    return []
            else:
                log(f"  {county_slug}: No auctions found")
                return []
        else:
            log(f"  {county_slug}: Failed to get auctions - {response.status_code}", "ERROR")
            return []
            
    except Exception as e:
        log(f"  {county_slug}: Error getting candidates - {e}", "ERROR")
        return []

def generate_bid_decision_sql(county_slug, candidates):
    """Generate SQL to populate bid_decisions for candidates"""
    log(f"📝 Generating bid_decisions SQL for {county_slug}")
    
    if not candidates:
        log(f"  {county_slug}: No candidates to process")
        return None
    
    # Generate INSERT statements
    timestamp = datetime.now(timezone.utc).isoformat()
    sql_statements = []
    
    sql_statements.append(f"-- SHARD-7 J Generator: {county_slug} bid_decisions population")
    sql_statements.append(f"-- Generated: {timestamp}")
    sql_statements.append(f"-- Candidates: {len(candidates)}")
    sql_statements.append("")
    
    # Create template bid_decisions rows
    for candidate in candidates:
        case_number = candidate.get('case_number')
        if not case_number:
            continue
            
        # Generate placeholder values (would be replaced with real ML/CMA data)
        insert_sql = f"""INSERT INTO bid_decisions (
    case_number,
    county, 
    property_address,
    parcel_id,
    arv,
    max_bid,
    ml_score,
    factors,
    data_source,
    created_at
) VALUES (
    '{case_number}',
    '{county_slug}',
    {repr(candidate.get('property_address', ''))},
    {repr(candidate.get('parcel_id', ''))},
    NULL,  -- ARV to be populated by CMA analysis
    NULL,  -- max_bid to be calculated by Shapira formula  
    NULL,  -- ml_score from Shapira V14 model
    jsonb_build_object(
        'distress_location', NULL,    -- Property location distress factors
        'distress_property', NULL,    -- Property condition factors  
        'distress_owner', NULL,       -- Owner distress factors
        'cma_distressed', NULL,       -- Distressed comparable sales
        'cma_resale', NULL            -- Market resale comparables
    ),
    'shard7_j_generator:v1',
    '{timestamp}'
);"""
        sql_statements.append(insert_sql)
    
    full_sql = "\n".join(sql_statements)
    
    # Save to file
    filename = f"shard7_{county_slug}_j_generation.sql"
    with open(filename, 'w') as f:
        f.write(full_sql)
    
    log(f"  {county_slug}: SQL saved to {filename}")
    return filename

def create_j_generator_migration():
    """Create migration to set up bid_decisions population pipeline"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    migration_file = f"migrations/{timestamp}_shard7_j_generator.sql"
    
    migration_sql = f"""-- SHARD-7 J Generator Migration
-- Created: {datetime.now(timezone.utc).isoformat()}
-- Purpose: Set up bid_decisions population pipeline for SHARD-7 counties

-- Ensure bid_decisions table exists with proper schema
CREATE TABLE IF NOT EXISTS bid_decisions (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county TEXT NOT NULL,
    property_address TEXT,
    parcel_id TEXT,
    arv NUMERIC,
    max_bid NUMERIC, 
    ml_score NUMERIC,
    factors JSONB DEFAULT '{{}}',
    data_source TEXT DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_bid_decisions_case_number ON bid_decisions(case_number);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_county ON bid_decisions(county);
CREATE INDEX IF NOT EXISTS idx_bid_decisions_created_at ON bid_decisions(created_at);

-- Function to populate bid_decisions for a county
CREATE OR REPLACE FUNCTION populate_bid_decisions_for_county(county_slug_arg TEXT)
RETURNS TABLE(
    case_number TEXT,
    arv NUMERIC,
    max_bid NUMERIC,
    status TEXT
) AS $$
BEGIN
    -- Insert bid_decisions for auctions without them
    INSERT INTO bid_decisions (
        case_number,
        county,
        property_address,
        parcel_id,
        data_source
    )
    SELECT 
        mca.case_number,
        mca.county,
        mca.property_address,
        mca.parcel_id,
        'auto_generator:shard7_j'
    FROM multi_county_auctions mca
    LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number
    WHERE mca.county = county_slug_arg
      AND bd.case_number IS NULL
      AND mca.case_number IS NOT NULL
      AND mca.case_number != '';

    -- Return summary
    RETURN QUERY
    SELECT 
        bd.case_number,
        bd.arv,
        bd.max_bid,
        CASE 
            WHEN bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL THEN 'complete'
            WHEN bd.arv IS NOT NULL OR bd.max_bid IS NOT NULL OR bd.ml_score IS NOT NULL THEN 'partial'
            ELSE 'skeleton'
        END as status
    FROM bid_decisions bd
    WHERE bd.county = county_slug_arg
    ORDER BY bd.created_at DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to evaluate J criteria for a county  
CREATE OR REPLACE FUNCTION evaluate_j_criteria(county_slug_arg TEXT)
RETURNS TABLE(
    total_auctions BIGINT,
    with_bid_decisions BIGINT,
    complete_bid_decisions BIGINT,
    percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(mca.case_number) as total_auctions,
        COUNT(bd.case_number) as with_bid_decisions,
        COUNT(CASE WHEN bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL 
                   AND bd.factors->>'distress_location' IS NOT NULL
                   AND bd.factors->>'distress_property' IS NOT NULL  
                   AND bd.factors->>'distress_owner' IS NOT NULL
                   AND bd.factors->>'cma_distressed' IS NOT NULL
                   AND bd.factors->>'cma_resale' IS NOT NULL
              THEN 1 END) as complete_bid_decisions,
        CASE WHEN COUNT(mca.case_number) > 0 THEN
            ROUND(COUNT(CASE WHEN bd.arv IS NOT NULL AND bd.max_bid IS NOT NULL AND bd.ml_score IS NOT NULL 
                             AND bd.factors->>'distress_location' IS NOT NULL
                             AND bd.factors->>'distress_property' IS NOT NULL  
                             AND bd.factors->>'distress_owner' IS NOT NULL
                             AND bd.factors->>'cma_distressed' IS NOT NULL
                             AND bd.factors->>'cma_resale' IS NOT NULL
                        THEN 1 END) * 100.0 / COUNT(mca.case_number), 1)
        ELSE 0
        END as percentage
    FROM multi_county_auctions mca
    LEFT JOIN bid_decisions bd ON mca.case_number = bd.case_number
    WHERE mca.county = county_slug_arg;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION populate_bid_decisions_for_county IS 'SHARD-7 J Generator: Populate skeleton bid_decisions for a county';
COMMENT ON FUNCTION evaluate_j_criteria IS 'SHARD-7 J Generator: Evaluate J completion percentage for a county';
"""
    
    # Ensure migrations directory exists
    os.makedirs("migrations", exist_ok=True)
    
    with open(migration_file, 'w') as f:
        f.write(migration_sql)
    
    log(f"📄 Migration created: {migration_file}")
    return migration_file

def main():
    """Main execution - build J generator for SHARD-7 counties"""
    log("🎯 SHARD-7 J GENERATOR - Building bid_decisions pipeline")
    log(f"Counties: {', '.join(SHARD7_COUNTIES)}")
    
    # Analyze existing state
    log(f"\n{'='*60}")
    log("PHASE 1: Analyze existing bid_decisions state")
    
    existing_analysis = analyze_existing_bid_decisions()
    cma_analysis = analyze_valuations_comps_source()
    
    # Get candidates for each county
    log(f"\n{'='*60}")
    log("PHASE 2: Identify J generation candidates")
    
    all_candidates = {}
    for county in SHARD7_COUNTIES:
        candidates = get_auction_candidates_for_j(county)
        all_candidates[county] = candidates
    
    # Generate SQL for each county
    log(f"\n{'='*60}")
    log("PHASE 3: Generate bid_decisions SQL")
    
    sql_files = []
    for county, candidates in all_candidates.items():
        if candidates:
            sql_file = generate_bid_decision_sql(county, candidates)
            if sql_file:
                sql_files.append(sql_file)
    
    # Create migration
    log(f"\n{'='*60}")
    log("PHASE 4: Create J generator migration")
    
    migration_file = create_j_generator_migration()
    
    # Summary report
    log(f"\n{'='*60}")
    log("📊 SHARD-7 J GENERATOR SUMMARY")
    
    total_candidates = sum(len(candidates) for candidates in all_candidates.values())
    log(f"Total candidates identified: {total_candidates}")
    
    for county, candidates in all_candidates.items():
        log(f"  {county}: {len(candidates)} candidates")
    
    log(f"SQL files generated: {len(sql_files)}")
    for sql_file in sql_files:
        log(f"  {sql_file}")
    
    log(f"Migration file: {migration_file}")
    
    # Next steps
    log(f"\n🚀 NEXT STEPS:")
    log(f"1. Apply migration: supabase db push")  
    log(f"2. Populate skeleton bid_decisions: SELECT populate_bid_decisions_for_county('<county>')")
    log(f"3. Integrate Shapira V14 ML scoring")
    log(f"4. Connect CMA data from gen_valuations_comps_batch")
    log(f"5. Wire to scheduled executor")
    log(f"6. Verify J metrics: SELECT evaluate_j_criteria('<county>')")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)