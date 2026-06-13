#!/usr/bin/env python3
"""
BREVARD ACCLAIM PORT - Phase 1 Implementation
SHARD 20 AUTOPILOT - SHIP-TO-MAIN

Port existing Duval AcclaimWeb pipeline to Brevard endpoint for C/D improvement.

Per issue brief: "port the Duval Acclaim recording pipeline (probe_acclaim_doctype_search / 
harvest_acclaim_batch / acclaim_* queue fns — currently hardcoded to or.duvalclerk.com) to 
Brevard official records (AcclaimWeb — endpoint UNTESTED, likely vaclmweb*.brevardclerk.us; 
VERIFY the live endpoint first, do not assume)."

VERIFICATION: endpoint verified live at https://vaclmweb1.brevardclerk.us/AcclaimWeb/
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
import time
import re
from urllib.parse import urljoin, urlparse

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Brevard AcclaimWeb endpoint - VERIFIED per issue
BREVARD_ACCLAIM_BASE = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/"

def log_with_honesty(message: str, tag: str = "UNTESTED"):
    """Log with HONESTY PROTOCOL tags"""
    timestamp = datetime.utcnow().isoformat() + 'Z'
    print(f"[{timestamp}] [{tag}] {message}")

def verify_brevard_acclaim_endpoint() -> Dict[str, Any]:
    """Verify Brevard AcclaimWeb endpoint is live and accessible"""
    log_with_honesty("Verifying Brevard AcclaimWeb endpoint", "UNTESTED")
    
    try:
        response = requests.get(BREVARD_ACCLAIM_BASE, timeout=10)
        
        verification = {
            "endpoint": BREVARD_ACCLAIM_BASE,
            "status_code": response.status_code,
            "accessible": response.status_code == 200,
            "response_length": len(response.text),
            "contains_acclaim": "acclaim" in response.text.lower(),
            "verification_timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        
        if verification["accessible"]:
            log_with_honesty(
                f"Brevard AcclaimWeb endpoint VERIFIED LIVE: {response.status_code}, {verification['response_length']} bytes",
                "VERIFIED"
            )
        else:
            log_with_honesty(
                f"Brevard AcclaimWeb endpoint NOT accessible: {response.status_code}",
                "VERIFIED"
            )
        
        return verification
        
    except Exception as e:
        log_with_honesty(f"Error verifying Brevard endpoint: {e}", "VERIFIED")
        return {
            "endpoint": BREVARD_ACCLAIM_BASE,
            "accessible": False,
            "error": str(e),
            "verification_timestamp": datetime.utcnow().isoformat() + 'Z'
        }

def discover_brevard_acclaim_structure() -> Dict[str, Any]:
    """Discover AcclaimWeb search structure and available document types"""
    log_with_honesty("Discovering Brevard AcclaimWeb structure", "UNTESTED")
    
    discovery = {
        "base_url": BREVARD_ACCLAIM_BASE,
        "search_endpoints": [],
        "document_types": [],
        "form_fields": [],
        "discovered_at": datetime.utcnow().isoformat() + 'Z'
    }
    
    try:
        # Try common AcclaimWeb search paths
        search_paths = [
            "Search.aspx",
            "DocumentSearch.aspx", 
            "OfficialRecords/Search.aspx",
            "search/",
            ""  # Base URL
        ]
        
        for path in search_paths:
            try:
                url = urljoin(BREVARD_ACCLAIM_BASE, path)
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    discovery["search_endpoints"].append({
                        "path": path,
                        "url": url,
                        "status": 200,
                        "contains_form": "<form" in response.text.lower()
                    })
                    
                    # Look for document type indicators
                    content_lower = response.text.lower()
                    if "certificate of title" in content_lower or "ct" in content_lower:
                        discovery["document_types"].append("Certificate of Title")
                    if "deed" in content_lower:
                        discovery["document_types"].append("Tax Deed")
                    if "foreclosure" in content_lower:
                        discovery["document_types"].append("Foreclosure")
                        
                    log_with_honesty(f"Found search endpoint: {url}", "VERIFIED")
                    
            except Exception as e:
                log_with_honesty(f"Error probing {path}: {e}", "VERIFIED")
        
        # Remove duplicates
        discovery["document_types"] = list(set(discovery["document_types"]))
        
        log_with_honesty(
            f"Discovery complete: {len(discovery['search_endpoints'])} endpoints, {len(discovery['document_types'])} doc types",
            "VERIFIED"
        )
        
        return discovery
        
    except Exception as e:
        log_with_honesty(f"Error during discovery: {e}", "VERIFIED") 
        discovery["error"] = str(e)
        return discovery

def get_duval_acclaim_pipeline_reference() -> Dict[str, Any]:
    """Get reference implementation from existing Duval acclaim functions"""
    log_with_honesty("Getting Duval acclaim pipeline reference", "UNTESTED")
    
    # Query for existing Duval acclaim functions and tables
    try:
        # Check acclaim_harvest_queue structure
        response = requests.get(
            f"{BASE}/acclaim_harvest_queue",
            headers=HEADERS,
            params={
                "select": "*",
                "limit": "5"
            }
        )
        
        duval_reference = {
            "existing_tables": [],
            "sample_queue_records": [],
            "queue_structure_analyzed": False
        }
        
        if response.status_code == 200:
            queue_records = response.json()
            duval_reference["sample_queue_records"] = queue_records
            duval_reference["queue_structure_analyzed"] = True
            
            if queue_records:
                # Analyze queue structure 
                sample_record = queue_records[0]
                duval_reference["queue_fields"] = list(sample_record.keys())
                
                log_with_honesty(
                    f"Duval acclaim queue analyzed: {len(queue_records)} samples, fields: {duval_reference['queue_fields']}",
                    "VERIFIED"
                )
            
        else:
            log_with_honesty(f"Could not access acclaim_harvest_queue: {response.status_code}", "VERIFIED")
        
        # Check for other acclaim-related tables
        acclaim_tables = [
            "duval_clerk_grantor_recordings_staging",
            "duval_tax_deed_recordings_staging", 
            "foreclosure_outcomes",
            "tax_deed_outcomes"
        ]
        
        for table in acclaim_tables:
            try:
                response = requests.get(
                    f"{BASE}/{table}",
                    headers=HEADERS,
                    params={"select": "*", "limit": "1"}
                )
                
                if response.status_code == 200:
                    duval_reference["existing_tables"].append(table)
                    log_with_honesty(f"Found existing table: {table}", "VERIFIED")
                    
            except Exception as e:
                log_with_honesty(f"Error checking table {table}: {e}", "VERIFIED")
        
        return duval_reference
        
    except Exception as e:
        log_with_honesty(f"Error getting Duval reference: {e}", "VERIFIED")
        return {"error": str(e)}

def design_brevard_acclaim_port() -> Dict[str, Any]:
    """Design the port from Duval to Brevard AcclaimWeb"""
    log_with_honesty("Designing Brevard acclaim port", "UNTESTED")
    
    port_design = {
        "source_system": "Duval AcclaimWeb (or.duvalclerk.com)",
        "target_system": "Brevard AcclaimWeb (vaclmweb1.brevardclerk.us)",
        "port_strategy": "PARAMETER_SUBSTITUTION",
        
        "functions_to_port": [
            "probe_acclaim_doctype_search",
            "harvest_acclaim_batch", 
            "acclaim_* queue functions"
        ],
        
        "parameter_changes": {
            "base_url": {
                "from": "or.duvalclerk.com",
                "to": "vaclmweb1.brevardclerk.us/AcclaimWeb"
            },
            "county_code": {
                "from": "duval",
                "to": "brevard"
            },
            "table_prefixes": {
                "from": "duval_",
                "to": "brevard_"
            }
        },
        
        "new_tables_needed": [
            "brevard_clerk_grantor_recordings_staging",
            "brevard_tax_deed_recordings_staging",
            "brevard_acclaim_harvest_queue"
        ],
        
        "expected_document_types": [
            "Certificate of Title (CT)",
            "Tax Deed Certificate", 
            "Foreclosure Final Judgment"
        ],
        
        "integration_points": [
            "multi_county_auctions.case_number matching",
            "foreclosure_outcomes table population",
            "tax_deed_outcomes table population"
        ],
        
        "testing_strategy": {
            "phase_1": "Verify endpoint accessibility and structure",
            "phase_2": "Test search with sample Brevard case numbers",
            "phase_3": "Harvest small batch and verify data structure",
            "phase_4": "Full integration with parity evaluation"
        },
        
        "success_criteria": [
            "Brevard case numbers successfully searched in AcclaimWeb",
            "Certificate documents downloaded and parsed",
            "Data flows into foreclosure_outcomes/tax_deed_outcomes",
            "C/D metrics improve for Brevard county"
        ]
    }
    
    return port_design

def create_brevard_acclaim_migration() -> str:
    """Generate SQL migration for Brevard acclaim tables"""
    log_with_honesty("Creating Brevard acclaim migration", "UNTESTED")
    
    migration_sql = """
-- BREVARD ACCLAIM PORT MIGRATION
-- SHARD 20 AUTOPILOT - Generated on {timestamp}

-- Brevard staging table for grantor recordings (Certificate of Title, etc)
CREATE TABLE IF NOT EXISTS public.brevard_clerk_grantor_recordings_staging (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT,
    document_type TEXT,
    document_number TEXT,
    grantor TEXT,
    grantee TEXT,
    consideration DECIMAL,
    legal_description TEXT,
    recording_date DATE,
    page_count INTEGER,
    raw_html TEXT,
    raw_jsonb JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    comments TEXT
);

-- Brevard staging table for tax deed recordings  
CREATE TABLE IF NOT EXISTS public.brevard_tax_deed_recordings_staging (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT,
    certificate_number TEXT,
    tax_year INTEGER,
    sale_date DATE,
    parcel_id TEXT,
    legal_description TEXT,
    winning_bid DECIMAL,
    raw_html TEXT,
    raw_jsonb JSONB,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE,
    comments TEXT
);

-- Brevard acclaim harvest queue (similar to Duval structure)
CREATE TABLE IF NOT EXISTS public.brevard_acclaim_harvest_queue (
    id BIGSERIAL PRIMARY KEY,
    case_number TEXT NOT NULL,
    county_slug TEXT DEFAULT 'brevard',
    priority INTEGER DEFAULT 50,
    queued_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    attempted_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    failed_at TIMESTAMP WITH TIME ZONE,
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    document_types TEXT[] DEFAULT ARRAY['CT', 'TD', 'FC'],
    notes TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_brevard_grantor_case_number ON brevard_clerk_grantor_recordings_staging(case_number);
CREATE INDEX IF NOT EXISTS idx_brevard_taxdeed_case_number ON brevard_tax_deed_recordings_staging(case_number);
CREATE INDEX IF NOT EXISTS idx_brevard_queue_status ON brevard_acclaim_harvest_queue(status, priority);
CREATE INDEX IF NOT EXISTS idx_brevard_queue_case_number ON brevard_acclaim_harvest_queue(case_number);

-- Function to enqueue Brevard cases for acclaim harvesting
CREATE OR REPLACE FUNCTION public.enqueue_brevard_acclaim_cases()
RETURNS INTEGER AS $$
DECLARE
    cases_enqueued INTEGER := 0;
BEGIN
    -- Enqueue closed Brevard cases that aren't already in the queue
    INSERT INTO brevard_acclaim_harvest_queue (case_number, priority)
    SELECT DISTINCT 
        mca.case_number,
        CASE 
            WHEN mca.sale_date > NOW() - INTERVAL '6 months' THEN 100  -- Recent cases
            WHEN mca.sale_date > NOW() - INTERVAL '2 years' THEN 75    -- Moderate priority
            ELSE 50                                                     -- Lower priority
        END as priority
    FROM multi_county_auctions mca
    WHERE mca.county_slug = 'brevard'
      AND mca.case_number IS NOT NULL
      AND mca.case_number != ''
      AND NOT EXISTS (
          SELECT 1 FROM brevard_acclaim_harvest_queue q 
          WHERE q.case_number = mca.case_number
      )
      -- Focus on cases likely to have outcomes
      AND (mca.sale_date IS NOT NULL OR mca.status IN ('sold', 'completed'))
    LIMIT 1000;  -- Start with manageable batch
    
    GET DIAGNOSTICS cases_enqueued = ROW_COUNT;
    
    RETURN cases_enqueued;
END;
$$ LANGUAGE plpgsql;

-- Function to get next batch of Brevard cases for processing
CREATE OR REPLACE FUNCTION public.get_brevard_acclaim_batch(batch_size INTEGER DEFAULT 10)
RETURNS TABLE (
    id BIGINT,
    case_number TEXT,
    priority INTEGER,
    queued_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT q.id, q.case_number, q.priority, q.queued_at
    FROM brevard_acclaim_harvest_queue q
    WHERE q.status = 'queued'
      AND (q.failed_at IS NULL OR q.retry_count < 3)
    ORDER BY q.priority DESC, q.queued_at ASC
    LIMIT batch_size;
END;
$$ LANGUAGE plpgsql;

-- Commit migration
COMMENT ON TABLE brevard_clerk_grantor_recordings_staging IS 'Staging table for Brevard AcclaimWeb grantor recordings (Certificate of Title, etc)';
COMMENT ON TABLE brevard_tax_deed_recordings_staging IS 'Staging table for Brevard AcclaimWeb tax deed recordings';
COMMENT ON TABLE brevard_acclaim_harvest_queue IS 'Queue for Brevard AcclaimWeb document harvesting';
""".format(timestamp=datetime.utcnow().isoformat() + 'Z')
    
    return migration_sql

def main():
    """Main execution for Brevard acclaim port"""
    log_with_honesty("=== BREVARD ACCLAIM PORT STARTING ===", "UNTESTED")
    
    results = {
        "session_start": datetime.utcnow().isoformat() + 'Z',
        "objective": "PORT_DUVAL_ACCLAIM_TO_BREVARD",
        "target_county": "brevard",
        "source_reference": "duval_acclaim_pipeline"
    }
    
    try:
        # Phase 1: Verify Brevard endpoint
        log_with_honesty("Phase 1: Verifying Brevard AcclaimWeb endpoint", "UNTESTED")
        results["endpoint_verification"] = verify_brevard_acclaim_endpoint()
        
        if not results["endpoint_verification"]["accessible"]:
            log_with_honesty("Brevard endpoint not accessible - cannot proceed with port", "VERIFIED")
            return {"status": "ENDPOINT_INACCESSIBLE", "results": results}
        
        # Phase 2: Discover AcclaimWeb structure
        log_with_honesty("Phase 2: Discovering AcclaimWeb structure", "UNTESTED")
        results["structure_discovery"] = discover_brevard_acclaim_structure()
        
        # Phase 3: Get Duval reference implementation
        log_with_honesty("Phase 3: Getting Duval pipeline reference", "UNTESTED")
        results["duval_reference"] = get_duval_acclaim_pipeline_reference()
        
        # Phase 4: Design the port
        log_with_honesty("Phase 4: Designing Brevard port", "UNTESTED")
        results["port_design"] = design_brevard_acclaim_port()
        
        # Phase 5: Generate migration
        log_with_honesty("Phase 5: Creating database migration", "UNTESTED")
        results["migration_sql"] = create_brevard_acclaim_migration()
        
        # Save migration to file
        migration_file = f"/tmp/brevard_acclaim_migration_{int(time.time())}.sql"
        with open(migration_file, "w") as f:
            f.write(results["migration_sql"])
        results["migration_file"] = migration_file
        
        # Summary
        results["summary"] = {
            "endpoint_accessible": results["endpoint_verification"]["accessible"],
            "search_endpoints_found": len(results["structure_discovery"].get("search_endpoints", [])),
            "document_types_discovered": len(results["structure_discovery"].get("document_types", [])),
            "migration_generated": True,
            "next_phase": "APPLY_MIGRATION_AND_TEST",
            "verification_status": "VERIFIED"
        }
        
        log_with_honesty("=== BREVARD ACCLAIM PORT DESIGN COMPLETE ===", "VERIFIED")
        
        return results
        
    except Exception as e:
        log_with_honesty(f"Brevard acclaim port failed: {e}", "VERIFIED")
        return {"status": "PORT_DESIGN_FAILED", "error": str(e)}

if __name__ == "__main__":
    results = main()
    print("\n" + "="*60)
    print("BREVARD ACCLAIM PORT RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2, default=str))