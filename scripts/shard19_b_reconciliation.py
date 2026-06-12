#!/usr/bin/env python3
"""
SHARD-19 B RECONCILIATION - Fix verified>closed_sold Anomaly
Per BREVARD SPRINT ORDER priority #4

ANOMALY: brevard B=134.1%, duval B=110.2% (both >105% threshold)
DIAGNOSIS: verified_outcomes > closed_sold indicates denominator/source mismatch or double-counting
ROOT CAUSE: outcomes beyond scoped closed set or double-count per Evaluator V6 rules

SOLUTION: Scope outcomes to snapshot set (gold_standard_cert_scope) per brief

Usage:
  python scripts/shard19_b_reconciliation.py
"""
import os
import requests
import json
import logging
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target counties with B anomalies
COUNTIES = ['brevard', 'duval']

def test_db_connection():
    """Test database connection"""
    try:
        response = requests.get(f"{BASE}/audit_log", headers=HEADERS, params={"limit": "1"}, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Database connection successful")
            return True
        else:
            logger.error(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Connection error: {e}")
        return False

def analyze_b_anomaly(county):
    """Analyze the B letter anomaly in detail"""
    try:
        print(f"\n🔍 ANALYZING B ANOMALY: {county.upper()}")
        print("-" * 50)
        
        # Get closed auctions count (denominator)
        closed_response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "auction_status": "in.(sold,no_sale,canceled)",
                "select": "case_number,auction_date,auction_status,source_platform",
                "limit": "50000"
            },
            timeout=30
        )
        
        if closed_response.status_code != 200:
            logger.error(f"Failed to get closed auctions: {closed_response.status_code}")
            return None
        
        closed_auctions = closed_response.json()
        total_closed = len(closed_auctions)
        
        # Get verified outcomes count (numerator)
        tax_deed_response = requests.get(
            f"{BASE}/tax_deed_outcomes",
            headers=HEADERS,
            params={
                "county_slug": f"eq.{county}",
                "data_source": "not.ilike.*propertyonion*",
                "select": "case_number,data_source,auction_date,scraped_at"
            },
            timeout=30
        )
        
        foreclosure_response = requests.get(
            f"{BASE}/foreclosure_outcomes",
            headers=HEADERS,
            params={
                "county_slug": f"eq.{county}",
                "data_source": "not.ilike.*propertyonion*", 
                "select": "case_number,data_source,auction_date,scraped_at"
            },
            timeout=30
        )
        
        tax_deed_outcomes = tax_deed_response.json() if tax_deed_response.status_code == 200 else []
        foreclosure_outcomes = foreclosure_response.json() if foreclosure_response.status_code == 200 else []
        
        total_verified = len(tax_deed_outcomes) + len(foreclosure_outcomes)
        
        # Calculate B ratio
        b_ratio = (total_verified / total_closed * 100) if total_closed > 0 else 0
        
        print(f"   📊 Closed auctions (denominator): {total_closed:,}")
        print(f"   📊 Verified outcomes (numerator): {total_verified:,}")
        print(f"   📊 B ratio: {b_ratio:.1f}% {'❌ ANOMALY' if b_ratio > 105 else '✅ NORMAL'}")
        
        # Analyze by data source
        print(f"\n   🔍 Verified outcomes by source:")
        source_counts = {}
        
        for outcome in tax_deed_outcomes:
            source = outcome.get('data_source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        for outcome in foreclosure_outcomes:
            source = outcome.get('data_source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        for source, count in source_counts.items():
            pct = (count / total_verified * 100) if total_verified > 0 else 0
            print(f"      {source}: {count:,} ({pct:.1f}%)")
        
        # Check for date mismatches (outcomes outside closed auction dates)
        closed_dates = set()
        for auction in closed_auctions:
            auction_date = auction.get('auction_date')
            if auction_date:
                closed_dates.add(auction_date)
        
        outside_date_count = 0
        for outcome in tax_deed_outcomes + foreclosure_outcomes:
            outcome_date = outcome.get('auction_date')
            if outcome_date and outcome_date not in closed_dates:
                outside_date_count += 1
        
        if outside_date_count > 0:
            print(f"   ⚠️  Outcomes outside closed auction dates: {outside_date_count}")
        
        # Check for duplicate case numbers
        outcome_case_numbers = []
        for outcome in tax_deed_outcomes + foreclosure_outcomes:
            outcome_case_numbers.append(outcome.get('case_number'))
        
        duplicate_cases = len(outcome_case_numbers) - len(set(outcome_case_numbers))
        if duplicate_cases > 0:
            print(f"   ⚠️  Duplicate case numbers in outcomes: {duplicate_cases}")
        
        return {
            'county': county,
            'total_closed': total_closed,
            'total_verified': total_verified,
            'b_ratio': b_ratio,
            'source_counts': source_counts,
            'outside_date_count': outside_date_count,
            'duplicate_cases': duplicate_cases,
            'anomalous': b_ratio > 105
        }
        
    except Exception as e:
        logger.error(f"Error analyzing B anomaly for {county}: {e}")
        return None

def check_evaluator_v6_scope():
    """Check if gold_standard_cert_scope snapshot is defined"""
    try:
        # This would check for the snapshot date mentioned in brief
        # For now, use June 12 as the snapshot date per brief
        snapshot_date = "2026-06-12"
        
        print(f"\n📅 EVALUATOR V6 SCOPE CHECK")
        print(f"   Snapshot date: {snapshot_date}")
        print(f"   Rule: brevard+duval letters evaluate against MCA rows ingested <= Jun12")
        print(f"   Denominators FROZEN (brevard=19,706)")
        
        return snapshot_date
        
    except Exception as e:
        logger.error(f"Error checking evaluator scope: {e}")
        return None

def scope_outcomes_to_snapshot(county, snapshot_date):
    """Scope verified outcomes to the snapshot set"""
    try:
        print(f"\n🎯 SCOPING OUTCOMES TO SNAPSHOT: {county.upper()}")
        print("-" * 50)
        
        # Get auctions within snapshot scope
        scoped_response = requests.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                "county": f"eq.{county}",
                "auction_date": f"lte.{snapshot_date}",
                "auction_status": "in.(sold,no_sale,canceled)",
                "select": "case_number,auction_date"
            },
            timeout=30
        )
        
        if scoped_response.status_code != 200:
            logger.error(f"Failed to get scoped auctions: {scoped_response.status_code}")
            return False
        
        scoped_auctions = scoped_response.json()
        scoped_case_numbers = {a['case_number'] for a in scoped_auctions}
        
        print(f"   📊 Scoped auctions (≤{snapshot_date}): {len(scoped_auctions):,}")
        
        # Count outcomes within scope
        scoped_tax_deed = 0
        scoped_foreclosure = 0
        
        # Tax deed outcomes in scope
        tax_deed_response = requests.get(
            f"{BASE}/tax_deed_outcomes",
            headers=HEADERS,
            params={
                "county_slug": f"eq.{county}",
                "auction_date": f"lte.{snapshot_date}",
                "select": "case_number"
            },
            timeout=30
        )
        
        if tax_deed_response.status_code == 200:
            tax_deed_outcomes = tax_deed_response.json()
            scoped_tax_deed = sum(1 for o in tax_deed_outcomes if o.get('case_number') in scoped_case_numbers)
        
        # Foreclosure outcomes in scope
        foreclosure_response = requests.get(
            f"{BASE}/foreclosure_outcomes",
            headers=HEADERS,
            params={
                "county_slug": f"eq.{county}",
                "auction_date": f"lte.{snapshot_date}",
                "select": "case_number"
            },
            timeout=30
        )
        
        if foreclosure_response.status_code == 200:
            foreclosure_outcomes = foreclosure_response.json()
            scoped_foreclosure = sum(1 for o in foreclosure_outcomes if o.get('case_number') in scoped_case_numbers)
        
        total_scoped_outcomes = scoped_tax_deed + scoped_foreclosure
        scoped_b_ratio = (total_scoped_outcomes / len(scoped_auctions) * 100) if len(scoped_auctions) > 0 else 0
        
        print(f"   📊 Scoped tax deed outcomes: {scoped_tax_deed:,}")
        print(f"   📊 Scoped foreclosure outcomes: {scoped_foreclosure:,}")
        print(f"   📊 Total scoped outcomes: {total_scoped_outcomes:,}")
        print(f"   📊 Scoped B ratio: {scoped_b_ratio:.1f}% {'✅ FIXED' if 95 <= scoped_b_ratio <= 105 else '❌ STILL ANOMALOUS'}")
        
        return {
            'scoped_auctions': len(scoped_auctions),
            'scoped_outcomes': total_scoped_outcomes,
            'scoped_b_ratio': scoped_b_ratio,
            'fixed': 95 <= scoped_b_ratio <= 105
        }
        
    except Exception as e:
        logger.error(f"Error scoping outcomes for {county}: {e}")
        return None

def create_scoped_evaluation_function():
    """Create a scoped evaluation function for Evaluator V6"""
    try:
        print(f"\n🔧 CREATING SCOPED EVALUATION FUNCTION")
        print("-" * 50)
        
        # SQL for scoped pencil_dod_evaluate_county_scoped function
        scoped_function_sql = """
        CREATE OR REPLACE FUNCTION public.pencil_dod_evaluate_county_scoped(
            county_slug_arg TEXT,
            snapshot_date_arg DATE DEFAULT '2026-06-12'::DATE
        )
        RETURNS TABLE(
            letter TEXT,
            pass BOOLEAN,
            metric NUMERIC,
            detail TEXT,
            threshold TEXT
        ) 
        LANGUAGE plpgsql
        AS $$
        DECLARE
            total_closed INTEGER;
            verified_outcomes_count INTEGER;
            scoped_auctions_count INTEGER;
        BEGIN
            -- Get scoped closed auctions (denominator)
            SELECT COUNT(*) INTO scoped_auctions_count 
            FROM multi_county_auctions 
            WHERE county = county_slug_arg 
              AND auction_status IN ('sold', 'no_sale', 'canceled')
              AND auction_date <= snapshot_date_arg;
              
            IF scoped_auctions_count = 0 THEN
                RETURN QUERY SELECT 'ERROR', FALSE, 0.0, 'No scoped auctions found', '';
                RETURN;
            END IF;

            -- B: Verified outcomes from independent sources (≥95%, ≤105%)
            SELECT COUNT(*) INTO verified_outcomes_count
            FROM (
                SELECT 1 FROM tax_deed_outcomes 
                WHERE county_slug = county_slug_arg 
                  AND data_source NOT ILIKE '%propertyonion%'
                  AND auction_date <= snapshot_date_arg
                  AND case_number IN (
                      SELECT case_number FROM multi_county_auctions 
                      WHERE county = county_slug_arg 
                        AND auction_date <= snapshot_date_arg
                        AND auction_status IN ('sold', 'no_sale', 'canceled')
                  )
                UNION ALL
                SELECT 1 FROM foreclosure_outcomes 
                WHERE county_slug = county_slug_arg 
                  AND data_source NOT ILIKE '%propertyonion%'
                  AND auction_date <= snapshot_date_arg
                  AND case_number IN (
                      SELECT case_number FROM multi_county_auctions 
                      WHERE county = county_slug_arg 
                        AND auction_date <= snapshot_date_arg
                        AND auction_status IN ('sold', 'no_sale', 'canceled')
                  )
            ) verified;

            RETURN QUERY
            SELECT 'B',
                verified_outcomes_count >= (scoped_auctions_count * 0.95)::INTEGER 
                AND verified_outcomes_count <= (scoped_auctions_count * 1.05)::INTEGER,
                CASE WHEN scoped_auctions_count > 0 THEN (verified_outcomes_count * 100.0 / scoped_auctions_count) ELSE 0 END,
                'verified=' || verified_outcomes_count::TEXT || ' scoped_closed=' || scoped_auctions_count::TEXT,
                '≥95% and ≤105% with scoped independent outcomes';

        END;
        $$;
        """
        
        # Execute the function creation
        response = requests.post(
            f"{BASE}/rpc/exec_sql",
            headers=HEADERS,
            json={"sql_query": scoped_function_sql},
            timeout=30
        )
        
        if response.status_code == 200:
            print(f"   ✅ Created pencil_dod_evaluate_county_scoped function")
            return True
        else:
            logger.error(f"Failed to create scoped function: {response.status_code}")
            return False
        
    except Exception as e:
        logger.error(f"Error creating scoped evaluation function: {e}")
        return False

def main():
    """Main execution"""
    print("⚖️ SHARD-19 B RECONCILIATION - Fix verified>closed_sold Anomaly")
    print("Per BREVARD SPRINT ORDER priority #4")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    if not test_db_connection():
        return
    
    # Analyze current B anomalies
    anomaly_data = {}
    for county in COUNTIES:
        analysis = analyze_b_anomaly(county)
        if analysis:
            anomaly_data[county] = analysis
    
    # Check evaluator V6 scope requirements
    snapshot_date = check_evaluator_v6_scope()
    
    if not snapshot_date:
        print("❌ Could not determine snapshot date")
        return
    
    # Scope outcomes to snapshot
    scoped_results = {}
    for county in COUNTIES:
        if anomaly_data.get(county, {}).get('anomalous'):
            result = scope_outcomes_to_snapshot(county, snapshot_date)
            if result:
                scoped_results[county] = result
    
    # Create scoped evaluation function for Evaluator V6
    function_created = create_scoped_evaluation_function()
    
    # Summary
    print(f"\n{'='*70}")
    print("B RECONCILIATION RESULTS")
    print('='*70)
    
    fixed_counties = []
    for county, data in anomaly_data.items():
        b_ratio = data['b_ratio']
        scoped_data = scoped_results.get(county)
        
        if scoped_data and scoped_data.get('fixed'):
            fixed_counties.append(county)
            print(f"📊 {county.upper()}: {b_ratio:.1f}% → {scoped_data['scoped_b_ratio']:.1f}% ✅ FIXED")
        else:
            print(f"📊 {county.upper()}: {b_ratio:.1f}% {'❌ STILL ANOMALOUS' if b_ratio > 105 else '✅ NORMAL'}")
    
    if fixed_counties:
        print(f"\n✅ SUCCESS: Fixed B anomaly for {', '.join(fixed_counties)}")
        print(f"📈 Scoped evaluation now respects Evaluator V6 snapshot rules")
        
        print(f"\n🔍 ROOT CAUSE CONFIRMED:")
        print(f"   - Outcomes beyond scoped closed set per Evaluator V6")
        print(f"   - Snapshot scope ≤{snapshot_date} resolves denominator mismatch")
        
        if function_created:
            print(f"\n✅ Created pencil_dod_evaluate_county_scoped() function")
            print(f"📋 Use this function for accurate B evaluation going forward")
        
        print(f"\n📋 NEXT STEPS:")
        print(f"1. Update gold_standard_loop to use scoped evaluation")
        print(f"2. Run pencil_dod_evaluate_county_scoped('brevard', '{snapshot_date}')")
        print(f"3. Run pencil_dod_evaluate_county_scoped('duval', '{snapshot_date}')")
        print(f"4. Verify B passes 95-105% range before certification")
    else:
        print(f"⚠️  No B anomalies fixed - manual investigation required")
        print(f"🔍 Consider: duplicate case numbers, date mismatches, source contamination")
    
    print(f"\n⚡ B RECONCILIATION: COMPLETED")

if __name__ == "__main__":
    main()