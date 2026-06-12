#!/usr/bin/env python3
"""
DUVAL CASE NUMBER REPAIR SYSTEM
High-priority fix for Gold Standard Letters C & D

ROOT CAUSE: 8,979 of 9,336 closed Duval rows have PropertyOnion IDs (PO-xxxxxx) 
instead of court case numbers. This prevents matching with official records.

SOLUTION: Lookup court case numbers via Duval clerk tax-deed file by parcel_id + sale date.

According to issue: "18,156 PO rows have parcel_id" - this is our repair pathway.
"""
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No SUPABASE_KEY found in environment")
    exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def sb_get(endpoint, params=""):
    """Make a GET request to Supabase"""
    url = f"{BASE}/{endpoint}"
    if params:
        url += f"?{params}"
    
    req = urllib.request.Request(url)
    for k, v in sb_headers().items():
        req.add_header(k, v)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.status, response.read().decode()
    except Exception as e:
        return 0, str(e)

def sb_rpc(func_name, params=None):
    """Call a Supabase RPC function"""
    payload = json.dumps(params or {}).encode()
    req = urllib.request.Request(f"{BASE}/rpc/{func_name}", data=payload, method="POST")
    for k, v in sb_headers().items():
        req.add_header(k, v)
    
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, response.read().decode()
    except Exception as e:
        return 0, str(e)

def analyze_duval_case_numbers():
    """Analyze Duval case number patterns to confirm the scope"""
    print("🔍 ANALYZING DUVAL CASE NUMBER PATTERNS")
    print("-" * 50)
    
    # Get total Duval auctions
    status, result = sb_get("multi_county_auctions", 
                           "select=count&county=eq.duval")
    
    if status == 200:
        try:
            total_duval = len(json.loads(result))
            print(f"Total Duval auctions: {total_duval}")
        except:
            print("Could not parse total count")
    
    # Get PropertyOnion case patterns
    status, result = sb_get("multi_county_auctions", 
                           "select=case_number&county=eq.duval&case_number=like.PO-%25&limit=10")
    
    if status == 200:
        try:
            po_samples = json.loads(result)
            print(f"PropertyOnion case number samples: {len(po_samples)}")
            for sample in po_samples[:5]:
                print(f"  {sample.get('case_number', 'N/A')}")
        except:
            print("Could not parse PO samples")
    
    # Get court case patterns 
    status, result = sb_get("multi_county_auctions", 
                           "select=case_number&county=eq.duval&case_number=not.like.PO-%25&limit=10")
    
    if status == 200:
        try:
            court_samples = json.loads(result)
            print(f"Court case number samples: {len(court_samples)}")
            for sample in court_samples[:5]:
                print(f"  {sample.get('case_number', 'N/A')}")
        except:
            print("Could not parse court samples")
    
    # Count PO cases with parcel_id (repair candidates)
    status, result = sb_get("multi_county_auctions", 
                           "select=count&county=eq.duval&case_number=like.PO-%25&parcel_id=not.is.null")
    
    if status == 200:
        try:
            repair_candidates = len(json.loads(result))
            print(f"PO cases with parcel_id (repair candidates): {repair_candidates}")
        except:
            print("Could not count repair candidates")
    
    return True

def create_case_repair_function():
    """Create the SQL function to repair Duval case numbers"""
    
    repair_function_sql = """
-- Function to repair Duval PropertyOnion case numbers using parcel lookup
CREATE OR REPLACE FUNCTION public.repair_duval_case_numbers(limit_rows INTEGER DEFAULT 100)
RETURNS TABLE(
  po_case_number TEXT,
  court_case_number TEXT,
  parcel_id TEXT,
  auction_date DATE,
  repair_method TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
  repair_rec RECORD;
  repaired_count INTEGER := 0;
BEGIN
  -- Create temp table for results
  CREATE TEMP TABLE IF NOT EXISTS repair_results (
    po_case_number TEXT,
    court_case_number TEXT, 
    parcel_id TEXT,
    auction_date DATE,
    repair_method TEXT
  );
  
  -- Repair strategy 1: Direct parcel_id + auction_date lookup
  -- Look for court-format cases with same parcel_id and similar auction_date
  FOR repair_rec IN
    SELECT 
      po.case_number as po_case,
      court.case_number as court_case,
      po.parcel_id,
      po.auction_date,
      'parcel_date_match' as method
    FROM multi_county_auctions po
    JOIN multi_county_auctions court ON 
      court.county = 'duval'
      AND court.parcel_id = po.parcel_id  
      AND court.case_number NOT LIKE 'PO-%'
      AND ABS(EXTRACT(days FROM court.auction_date - po.auction_date)) <= 30
    WHERE 
      po.county = 'duval'
      AND po.case_number LIKE 'PO-%'
      AND po.parcel_id IS NOT NULL
    LIMIT limit_rows
  LOOP
    -- Insert to temp results
    INSERT INTO pg_temp.repair_results VALUES (
      repair_rec.po_case,
      repair_rec.court_case, 
      repair_rec.parcel_id,
      repair_rec.auction_date,
      repair_rec.method
    );
    
    repaired_count := repaired_count + 1;
  END LOOP;
  
  -- Return results
  RETURN QUERY SELECT * FROM pg_temp.repair_results;
  
END;
$$;

-- Function to apply case number repairs
CREATE OR REPLACE FUNCTION public.apply_duval_case_repairs()
RETURNS INTEGER
LANGUAGE plpgsql  
AS $$
DECLARE
  repair_rec RECORD;
  applied_count INTEGER := 0;
BEGIN
  -- Apply repairs found by repair function
  FOR repair_rec IN
    SELECT * FROM public.repair_duval_case_numbers(1000)
  LOOP
    -- Update the PropertyOnion case to use court case number
    UPDATE multi_county_auctions
    SET 
      case_number = repair_rec.court_case_number,
      updated_at = now(),
      case_number_source = 'repaired_from_' || repair_rec.po_case_number
    WHERE 
      county = 'duval'
      AND case_number = repair_rec.po_case_number;
      
    IF FOUND THEN
      applied_count := applied_count + 1;
    END IF;
  END LOOP;
  
  RETURN applied_count;
END;
$$;

-- Function to check repair progress
CREATE OR REPLACE FUNCTION public.duval_case_repair_status()
RETURNS TABLE(
  total_duval INTEGER,
  po_cases INTEGER,
  court_cases INTEGER,
  po_with_parcel INTEGER,
  repair_candidates INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number LIKE 'PO-%'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number NOT LIKE 'PO-%'),
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions WHERE county = 'duval' AND case_number LIKE 'PO-%' AND parcel_id IS NOT NULL),
    -- Estimate repair candidates
    (SELECT COUNT(*)::INTEGER FROM multi_county_auctions po 
     WHERE po.county = 'duval' AND po.case_number LIKE 'PO-%' AND po.parcel_id IS NOT NULL
     AND EXISTS (
       SELECT 1 FROM multi_county_auctions court 
       WHERE court.county = 'duval' 
         AND court.parcel_id = po.parcel_id
         AND court.case_number NOT LIKE 'PO-%'
         AND ABS(EXTRACT(days FROM court.auction_date - po.auction_date)) <= 30
     ));
END;
$$;

COMMENT ON FUNCTION public.repair_duval_case_numbers(INTEGER) IS 'Identifies PropertyOnion cases that can be repaired with court case numbers via parcel matching';
COMMENT ON FUNCTION public.apply_duval_case_repairs() IS 'Applies case number repairs to fix Duval C/D parity issues';
COMMENT ON FUNCTION public.duval_case_repair_status() IS 'Reports progress on Duval case number repair initiative';
"""
    
    return repair_function_sql

def main():
    print("🔧 DUVAL CASE NUMBER REPAIR SYSTEM")
    print("=" * 60)
    print(f"Timestamp: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print()
    print("OBJECTIVE: Repair PropertyOnion case numbers to enable C/D parity matching")
    print()
    
    # Analyze current state
    analyze_duval_case_numbers()
    
    # Check if repair functions exist
    print("\n🔨 CHECKING REPAIR FUNCTIONS")
    print("-" * 30)
    
    status, result = sb_rpc("duval_case_repair_status")
    
    if status == 200:
        print("✅ Repair functions are available")
        try:
            data = json.loads(result)[0]  # Single row result
            total = data.get('total_duval', 0)
            po_cases = data.get('po_cases', 0)
            court_cases = data.get('court_cases', 0)
            po_with_parcel = data.get('po_with_parcel', 0)
            repair_candidates = data.get('repair_candidates', 0)
            
            print(f"   Total Duval auctions: {total}")
            print(f"   PropertyOnion cases: {po_cases}")
            print(f"   Court cases: {court_cases}")  
            print(f"   PO cases with parcel_id: {po_with_parcel}")
            print(f"   Repair candidates (matching pairs): {repair_candidates}")
            
            repair_pct = (repair_candidates * 100.0 / po_cases) if po_cases > 0 else 0
            print(f"   Repair potential: {repair_pct:.1f}% of PO cases")
            
        except Exception as e:
            print(f"   Raw result: {result}")
    else:
        print(f"⚠️ Repair functions not found: {status} - {result}")
        print("   Functions need to be created via migration")
        
        # Write the migration  
        print("\n📝 CREATING REPAIR MIGRATION")
        repair_sql = create_case_repair_function()
        
        with open("migrations/20260612_duval_case_repair.sql", "w") as f:
            f.write("-- DUVAL CASE NUMBER REPAIR\n")
            f.write("-- Migration to repair PropertyOnion case numbers for C/D parity\n\n")
            f.write(repair_sql)
        
        print("✅ Created migration: 20260612_duval_case_repair.sql")
    
    # Run repair analysis if functions exist
    if status == 200:
        print("\n🔍 ANALYZING REPAIR OPPORTUNITIES")
        print("-" * 30)
        
        status, result = sb_rpc("repair_duval_case_numbers", {"limit_rows": 10})
        
        if status == 200:
            try:
                repairs = json.loads(result)
                print(f"Found {len(repairs)} repair opportunities (sample):")
                
                for repair in repairs:
                    po_case = repair.get('po_case_number', 'N/A')
                    court_case = repair.get('court_case_number', 'N/A')  
                    parcel = repair.get('parcel_id', 'N/A')
                    method = repair.get('repair_method', 'N/A')
                    print(f"   {po_case} → {court_case} (parcel: {parcel}, method: {method})")
                    
            except:
                print(f"   Raw result: {result}")
    
    # Summary
    print("\n" + "=" * 60)
    print("DUVAL CASE REPAIR ANALYSIS COMPLETE")
    print("=" * 60)
    
    print("NEXT STEPS:")
    if status != 200:
        print("1. Apply migration: 20260612_duval_case_repair.sql")
        print("2. Run repair analysis with: SELECT * FROM repair_duval_case_numbers(100);")
        print("3. Apply repairs with: SELECT apply_duval_case_repairs();")
    else:
        print("1. Execute repairs: SELECT apply_duval_case_repairs();")
        print("2. Verify C/D improvements: SELECT pencil_dod_evaluate_county('duval');")
    
    print("4. Monitor parity improvements in Gold Standard metrics")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)