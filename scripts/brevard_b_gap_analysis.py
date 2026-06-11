#!/usr/bin/env python3
"""
Brevard Letter B Gap Analysis
Diagnose why Brevard B metric is still 7.7% despite AcclaimWeb pipeline

Usage:
  python scripts/brevard_b_gap_analysis.py
"""
import os
import requests
import json
from datetime import datetime

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}", 
    "Content-Type": "application/json"
}

def run_sql_query(sql):
    """Run SQL query via RPC"""
    try:
        response = requests.post(
            f"{BASE}/rpc/execute_sql",
            headers=HEADERS,
            json={"sql_query": sql},
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"SQL query failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"SQL query error: {e}")
        return None

def run_simple_query(table, params=None, rpc=None):
    """Run simple table query or RPC"""
    try:
        if rpc:
            response = requests.post(f"{BASE}/rpc/{rpc}", headers=HEADERS, json=params or {}, timeout=30)
        else:
            response = requests.get(f"{BASE}/{table}", headers=HEADERS, params=params or {}, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Query failed {table}: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Query error {table}: {e}")
        return None

def analyze_brevard_b_status():
    """Analyze Brevard Letter B status comprehensively"""
    print("🔍 BREVARD LETTER B GAP ANALYSIS")
    print("=" * 60)
    
    # 1. Get current Letter B evaluation
    print("\n1. Current Letter B Status:")
    evaluation = run_simple_query(None, {"county_slug_arg": "brevard"}, "pencil_dod_evaluate_county")
    if evaluation:
        for item in evaluation:
            if item.get('letter') == 'B':
                metric = item.get('metric')
                passed = item.get('pass', False)
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"   Letter B: {status} (metric={metric})")
                break
    
    # 2. Count total closed auctions for Brevard
    print("\n2. Total Closed Auctions (denominator):")
    closed_auctions = run_simple_query("multi_county_auctions", {
        "county": "eq.brevard",
        "select": "count",
        "auction_status": "in.(sold,no_sale,canceled)"
    })
    total_closed = len(closed_auctions) if closed_auctions else 0
    print(f"   Total closed Brevard auctions: {total_closed}")
    
    # 3. Count verified outcomes from independent sources
    print("\n3. Verified Outcomes (numerator):")
    
    # Foreclosure outcomes
    fc_outcomes = run_simple_query("foreclosure_outcomes", {
        "county": "eq.brevard",
        "select": "count,data_source"
    })
    fc_count = len(fc_outcomes) if fc_outcomes else 0
    print(f"   Foreclosure outcomes: {fc_count}")
    if fc_outcomes and fc_count > 0:
        # Group by data_source
        sources = {}
        for outcome in fc_outcomes:
            source = outcome.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        for source, count in sources.items():
            print(f"     {source}: {count}")
    
    # Tax deed outcomes  
    td_outcomes = run_simple_query("tax_deed_outcomes", {
        "county": "eq.brevard", 
        "select": "count,data_source"
    })
    td_count = len(td_outcomes) if td_outcomes else 0
    print(f"   Tax deed outcomes: {td_count}")
    if td_outcomes and td_count > 0:
        sources = {}
        for outcome in td_outcomes:
            source = outcome.get('data_source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        for source, count in sources.items():
            print(f"     {source}: {count}")
    
    total_verified = fc_count + td_count
    print(f"   Total verified outcomes: {total_verified}")
    
    # 4. Check AcclaimWeb pipeline status
    print("\n4. AcclaimWeb Pipeline Status:")
    
    # Check recent AcclaimWeb data
    recent_acclaim = run_simple_query("foreclosure_outcomes", {
        "county": "eq.brevard",
        "data_source": "like.*acclaim*",
        "order": "enriched_at.desc",
        "limit": "10"
    })
    acclaim_count = len(recent_acclaim) if recent_acclaim else 0
    print(f"   Recent AcclaimWeb outcomes: {acclaim_count}")
    if recent_acclaim:
        latest = recent_acclaim[0] if recent_acclaim else {}
        latest_date = latest.get('enriched_at', 'unknown')
        print(f"   Latest AcclaimWeb enriched_at: {latest_date}")
    
    # 5. Check PropertyOnion exclusion
    print("\n5. PropertyOnion Data Exclusion Check:")
    po_outcomes = run_simple_query("foreclosure_outcomes", {
        "county": "eq.brevard",
        "data_source": "like.*propertyonion*",
        "select": "count"
    })
    po_count = len(po_outcomes) if po_outcomes else 0
    print(f"   PropertyOnion outcomes (should be excluded): {po_count}")
    
    # 6. Calculate actual verification percentage
    print("\n6. Gap Analysis:")
    if total_closed > 0:
        verification_pct = (total_verified * 100.0) / total_closed
        print(f"   Calculated verification rate: {verification_pct:.2f}%")
        print(f"   Target threshold: 95%")
        gap = max(0, 0.95 * total_closed - total_verified)
        print(f"   Gap to close: {gap:.0f} additional verified outcomes needed")
    else:
        print("   No closed auctions found - cannot calculate rate")
    
    # 7. Next steps analysis
    print("\n7. Next Steps Analysis:")
    if acclaim_count == 0:
        print("   🔥 CRITICAL: AcclaimWeb pipeline not producing outcomes")
        print("   → Run acclaim_ct_sweep.py immediately")
    elif total_verified < 0.95 * total_closed:
        print("   ⚡ Need more verified outcomes")
        print("   → Check if AcclaimWeb covers all Brevard case types")
        print("   → Verify AcclaimWeb data quality and completeness")
    else:
        print("   ✅ Should already pass - check evaluation logic")
    
    return {
        'total_closed': total_closed,
        'total_verified': total_verified,
        'verification_rate': verification_pct if total_closed > 0 else 0,
        'acclaim_count': acclaim_count,
        'gap': gap if total_closed > 0 else 0
    }

if __name__ == "__main__":
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found")
        exit(1)
    
    results = analyze_brevard_b_status()
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Closed auctions: {results['total_closed']}")
    print(f"Verified outcomes: {results['total_verified']}")
    print(f"Verification rate: {results['verification_rate']:.2f}%")
    print(f"Gap to close: {results['gap']:.0f} outcomes")