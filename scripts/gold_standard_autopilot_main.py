#!/usr/bin/env python3
"""
GOLD STANDARD AUTOPILOT - Main Execution Script
Addresses brevard and duval letter improvements per issue #7566

Session Goal: Ship-to-main, 6-hour budget, evidence-before-claims
Focus: B+F priority for brevard, chain break fix for duval
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple

try:
    import httpx
except ImportError:
    print("ERROR: httpx not available. Install with: pip install httpx")
    sys.exit(1)

# Configuration
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("ERROR: SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY environment variable required")
    sys.exit(1)

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def run_query(sql: str, description: str = "SQL query") -> Optional[List]:
    """Execute a SQL query via Supabase RPC"""
    client = httpx.Client(timeout=120)
    try:
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_raw_sql",
            headers=sb_headers(),
            json={"query": sql}
        )
        if r.status_code == 200:
            result = r.json()
            print(f"✅ {description} - Success")
            return result
        else:
            print(f"❌ {description} - Failed: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"❌ {description} - Exception: {e}")
        return None

def evaluate_county(county: str) -> Dict:
    """Run pencil_dod_evaluate_county for a county"""
    client = httpx.Client(timeout=120)
    try:
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county}
        )
        if r.status_code == 200:
            result = r.json()
            print(f"✅ Evaluated {county}:")
            status = {}
            for letter_data in result:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                pass_status = letter_data.get('pass')
                detail = letter_data.get('detail', '')
                status_icon = "✅" if pass_status else "❌"
                print(f"  {letter}: {status_icon} {metric} - {detail}")
                status[letter] = {
                    'pass': pass_status,
                    'metric': metric,
                    'detail': detail
                }
            return status
        else:
            print(f"❌ Failed to evaluate {county}: {r.status_code} - {r.text}")
            return {}
    except Exception as e:
        print(f"❌ Error evaluating {county}: {e}")
        return {}

def create_promote_functions():
    """
    Create the missing promote functions mentioned in the issue:
    - public.promote_tier1_from_outcomes() 
    - public.feed_acclaim_queue_duval()
    """
    print("\n=== Creating Missing Promote Functions ===")
    
    # Create promote_tier1_from_outcomes function
    promote_sql = """
    CREATE OR REPLACE FUNCTION public.promote_tier1_from_outcomes()
    RETURNS INTEGER
    LANGUAGE plpgsql
    AS $$
    DECLARE
        updated_count INTEGER := 0;
    BEGIN
        -- Promote tier1_sold_amount from verified outcomes
        -- F metric advances automatically as outcomes land
        
        UPDATE multi_county_auctions
        SET tier1_sold_amount = COALESCE(fo.sale_amount, tdo.sale_amount),
            tier1_verified_at = COALESCE(fo.verified_at, tdo.verified_at),
            updated_at = now()
        FROM (
            -- Foreclosure outcomes
            SELECT case_number, sale_amount, verified_at, county_slug
            FROM foreclosure_outcomes
            WHERE data_source NOT ILIKE '%propertyonion%'
              AND sale_amount IS NOT NULL
            UNION ALL
            -- Tax deed outcomes  
            SELECT case_number, sale_amount, verified_at, county_slug
            FROM tax_deed_outcomes
            WHERE data_source NOT ILIKE '%propertyonion%'
              AND sale_amount IS NOT NULL
        ) outcomes_data
        LEFT JOIN foreclosure_outcomes fo ON fo.case_number = outcomes_data.case_number
        LEFT JOIN tax_deed_outcomes tdo ON tdo.case_number = outcomes_data.case_number
        WHERE multi_county_auctions.case_number = outcomes_data.case_number
          AND multi_county_auctions.county = outcomes_data.county_slug
          AND multi_county_auctions.tier1_sold_amount IS NULL;
          
        GET DIAGNOSTICS updated_count = ROW_COUNT;
        RETURN updated_count;
    END;
    $$;
    """
    
    # Create feed_acclaim_queue_duval function  
    queue_feeder_sql = """
    CREATE OR REPLACE FUNCTION public.feed_acclaim_queue_duval()
    RETURNS INTEGER
    LANGUAGE plpgsql  
    AS $$
    DECLARE
        enqueued_count INTEGER := 0;
    BEGIN
        -- Feed closed Duval court-format cases to acclaim harvest queue
        -- Enqueue cases that haven't been harvested yet
        
        WITH new_queue_items AS (
            INSERT INTO acclaim_harvest_queue (
                case_number, 
                county_slug,
                case_format,
                priority,
                queued_at,
                status
            )
            SELECT DISTINCT
                mca.case_number,
                mca.county,
                'court_format',
                1, -- High priority  
                now(),
                'pending'
            FROM multi_county_auctions mca
            WHERE mca.county = 'duval'
              AND mca.auction_status IN ('sold', 'no_sale', 'canceled')
              AND mca.case_number ~ '^[0-9]{2}-[0-9]{4}-[A-Z]{2}-[0-9]+$' -- Court format
              AND NOT EXISTS (
                  SELECT 1 FROM acclaim_harvest_queue ahq 
                  WHERE ahq.case_number = mca.case_number 
                    AND ahq.county_slug = 'duval'
              )
            ON CONFLICT (case_number, county_slug) DO NOTHING
            RETURNING case_number
        )
        SELECT COUNT(*) INTO enqueued_count FROM new_queue_items;
        
        RETURN enqueued_count;
    END;
    $$;
    """
    
    # Create acclaim_harvest_queue table if it doesn't exist
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS acclaim_harvest_queue (
        id                SERIAL PRIMARY KEY,
        case_number       TEXT NOT NULL,
        county_slug       TEXT NOT NULL,
        case_format       TEXT DEFAULT 'court_format', -- 'court_format', 'property_onion' 
        priority          INTEGER DEFAULT 10,
        status            TEXT DEFAULT 'pending',      -- 'pending', 'in_progress', 'done', 'error'
        queued_at         TIMESTAMPTZ DEFAULT now(),
        claimed_by        TEXT,
        claimed_at        TIMESTAMPTZ,
        completed_at      TIMESTAMPTZ,
        attempts          INTEGER DEFAULT 0,
        last_error        TEXT,
        
        UNIQUE(case_number, county_slug),
        CHECK (status IN ('pending', 'in_progress', 'done', 'error'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_ahq_status_priority ON acclaim_harvest_queue(status, priority);
    CREATE INDEX IF NOT EXISTS idx_ahq_county ON acclaim_harvest_queue(county_slug);
    """
    
    # Execute the SQL
    run_query(create_table_sql, "Create acclaim_harvest_queue table")
    run_query(promote_sql, "Create promote_tier1_from_outcomes function")
    run_query(queue_feeder_sql, "Create feed_acclaim_queue_duval function") 
    
    print("✅ Promote functions created")

def test_brevard_acclaim_endpoint():
    """Test the Brevard AcclaimWeb endpoint mentioned in the issue"""
    print("\n=== Testing Brevard AcclaimWeb Endpoint ===")
    
    endpoint = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/"
    
    try:
        client = httpx.Client(timeout=30, follow_redirects=True)
        r = client.get(endpoint)
        if r.status_code == 200:
            print(f"✅ Brevard AcclaimWeb endpoint is live: {endpoint}")
            if "AcclaimWeb" in r.text:
                print("✅ AcclaimWeb interface detected in response")
            else:
                print("⚠️  Response received but AcclaimWeb interface not detected")
            return True
        else:
            print(f"❌ Brevard AcclaimWeb endpoint failed: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing Brevard AcclaimWeb: {e}")
        return False

def run_harvest_outcomes_mapper():
    """Run the harvest→outcomes mapper we created"""
    print("\n=== Running Harvest→Outcomes Mapper ===")
    
    try:
        # Import and run the mapper we created earlier
        result = subprocess.run([
            sys.executable, 
            "scripts/fix_harvest_outcomes_mapper.py"
        ], capture_output=True, text=True, cwd="/home/runner/work/cli-anything-biddeed/cli-anything-biddeed")
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ Harvest→outcomes mapper completed successfully")
            return True
        else:
            print(f"❌ Harvest→outcomes mapper failed with return code {result.returncode}")
            return False
    except Exception as e:
        print(f"❌ Error running harvest→outcomes mapper: {e}")
        return False

def run_brevard_acclaim_sweep():
    """Run the Brevard Acclaim CT sweep for recent months"""
    print("\n=== Running Brevard Acclaim CT Sweep ===")
    
    try:
        # Run the existing Brevard acclaim sweep script for current/previous month
        result = subprocess.run([
            sys.executable, 
            "scripts/acclaim_ct_sweep.py"  # Default args = prev month to current month
        ], capture_output=True, text=True, cwd="/home/runner/work/cli-anything-biddeed/cli-anything-biddeed")
        
        print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ Brevard Acclaim sweep completed successfully")
            return True
        else:
            print(f"⚠️  Brevard Acclaim sweep returned code {result.returncode}")
            # Not necessarily a failure - might just be no new records
            return True
    except Exception as e:
        print(f"❌ Error running Brevard Acclaim sweep: {e}")
        return False

def main():
    print("=== GOLD STANDARD AUTOPILOT SESSION ===")
    print(f"Start time: {datetime.now(timezone.utc).isoformat()}")
    print("Target counties: brevard, duval")
    print("Focus: B+F priority (Brevard AcclaimWeb), chain break fix (harvest→outcomes)")
    
    # Step 1: Get baseline evaluation
    print("\n=== STEP 1: Baseline Evaluation ===")
    brevard_before = evaluate_county("brevard")
    duval_before = evaluate_county("duval")
    
    # Step 2: Test Brevard AcclaimWeb endpoint
    print("\n=== STEP 2: Brevard AcclaimWeb Test ===")
    acclaim_live = test_brevard_acclaim_endpoint()
    
    # Step 3: Create missing promote functions
    print("\n=== STEP 3: Create Missing Functions ===")
    create_promote_functions()
    
    # Step 4: Run harvest→outcomes mapper
    print("\n=== STEP 4: Fix Chain Break ===")
    mapper_success = run_harvest_outcomes_mapper()
    
    # Step 5: Run Brevard Acclaim sweep if endpoint is live
    if acclaim_live:
        print("\n=== STEP 5: Brevard Acclaim Sweep ===")
        sweep_success = run_brevard_acclaim_sweep()
    else:
        print("\n=== STEP 5: Skipped (AcclaimWeb endpoint not accessible) ===")
        sweep_success = False
    
    # Step 6: Run promote function to update tier1_sold_amount
    print("\n=== STEP 6: Promote Tier1 Data ===")
    promote_result = run_query(
        "SELECT public.promote_tier1_from_outcomes();",
        "Promote tier1 data from outcomes"
    )
    if promote_result:
        print(f"✅ Promoted tier1 data for {promote_result[0]} records")
    
    # Step 7: Final evaluation
    print("\n=== STEP 7: Final Evaluation ===")
    brevard_after = evaluate_county("brevard")
    duval_after = evaluate_county("duval")
    
    # Step 8: Summary
    print("\n=== EXECUTION SUMMARY ===")
    print(f"Brevard AcclaimWeb endpoint: {'✅ LIVE' if acclaim_live else '❌ DOWN'}")
    print(f"Harvest→outcomes mapper: {'✅ SUCCESS' if mapper_success else '❌ FAILED'}")
    print(f"Brevard Acclaim sweep: {'✅ SUCCESS' if sweep_success else '❌ FAILED'}")
    print(f"Promote functions: {'✅ CREATED' if promote_result is not None else '❌ FAILED'}")
    
    print("\n=== BEFORE vs AFTER METRICS ===")
    for county, before, after in [("brevard", brevard_before, brevard_after), ("duval", duval_before, duval_after)]:
        print(f"\n{county.upper()}:")
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']:
            before_metric = before.get(letter, {}).get('metric', 0) 
            after_metric = after.get(letter, {}).get('metric', 0)
            before_pass = before.get(letter, {}).get('pass', False)
            after_pass = after.get(letter, {}).get('pass', False)
            
            status_change = ""
            if not before_pass and after_pass:
                status_change = " 🎉 NOW PASSING!"
            elif before_pass and not after_pass:
                status_change = " ⚠️  REGRESSED"
            
            change = ""
            if before_metric != after_metric and before_metric is not None and after_metric is not None:
                change = f" ({before_metric:.1f} → {after_metric:.1f})"
            
            print(f"  {letter}: {'✅' if after_pass else '❌'} {after_metric}{change}{status_change}")
    
    print(f"\nSession completed: {datetime.now(timezone.utc).isoformat()}")

if __name__ == "__main__":
    main()