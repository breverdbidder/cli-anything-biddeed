#!/usr/bin/env python3
"""
SHARD-3 County Status Verification for Gold Standard Campaign  
Check current A-J letter grades for brevard, putnam, hernando, walton, jefferson

Usage:
  python shard3_status_check.py
"""
import os
import sys
import json

# Try importing httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available - installing...")
    os.system("pip install httpx")
    import httpx

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

print(f"Using Supabase URL: {SUPABASE_URL}")
print(f"API Key present: {bool(SUPABASE_KEY)}")

# SHARD-3 assigned counties
SHARD3_COUNTIES = ['brevard', 'putnam', 'hernando', 'walton', 'jefferson']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        return False
        
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        print(f"Connection status: {r.status_code}")
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_current(county_slug):
    """Run the pencil_dod_evaluate_county function for a single county"""
    try:
        client = httpx.Client(timeout=60)
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ County evaluation for {county_slug}:")
            if isinstance(result, list) and len(result) > 0:
                pass_count = sum(1 for item in result if item.get('pass', False))
                print(f"  Overall: {pass_count}/10")
                
                # Sort by letter for consistent output
                sorted_results = sorted(result, key=lambda x: x.get('letter', 'Z'))
                for letter_data in sorted_results:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    status = "✅ PASS" if letter_data.get('pass') else "❌ FAIL"
                    metric_str = f"metric={metric}" if metric is not None else "metric=null"
                    
                    # Extract context for failed letters
                    context = ""
                    if not letter_data.get('pass') and 'context' in letter_data:
                        ctx = letter_data['context']
                        if isinstance(ctx, dict):
                            # Extract key metrics
                            ctx_parts = []
                            for key in ['fc', 'td', 'verified', 'closed_sold', 'matched_clean', 'matched_any', 'parcel_linked', 'tier1_sold']:
                                if key in ctx:
                                    ctx_parts.append(f"{key}={ctx[key]}")
                            if ctx_parts:
                                context = f" [{' '.join(ctx_parts)}]"
                    
                    print(f"  {letter}: {status} {metric_str}{context}")
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_multi_county_audit_count(county):
    """Get count of multi_county_auctions for verification"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions",
            headers=sb_headers(),
            params={
                "select": "count",
                "county": f"eq.{county}"
            }
        )
        
        if r.status_code == 200:
            count_header = r.headers.get('Content-Range', '0-0/0')
            # Parse count from header like "0-99/245123"
            total_count = int(count_header.split('/')[-1])
            return total_count
        else:
            print(f"⚠️ Failed to get auction count for {county}")
            return None
    except Exception as e:
        print(f"⚠️ Error getting auction count for {county}: {e}")
        return None

if __name__ == "__main__":
    print("🔍 SHARD-3 County Status Verification - Gold Standard Campaign")
    print(f"Target counties: {', '.join(SHARD3_COUNTIES)}")
    
    print("\n=== Database Connectivity Test ===")
    if not test_connection():
        sys.exit(1)
    
    print("\n=== Fresh County Evaluations ===")
    county_results = {}
    
    for county in SHARD3_COUNTIES:
        print(f"\n{'='*50}")
        print(f"COUNTY: {county.upper()}")
        print('='*50)
        
        # Get live evaluation
        evaluation = evaluate_county_current(county)
        county_results[county] = evaluation
        
        # Get auction count for context
        auction_count = get_multi_county_audit_count(county)
        if auction_count:
            print(f"  Total auctions in multi_county_auctions: {auction_count}")
    
    print("\n" + "="*60)
    print("SHARD-3 SUMMARY")
    print("="*60)
    
    for county, evaluation in county_results.items():
        if evaluation and isinstance(evaluation, list):
            pass_count = sum(1 for item in evaluation if item.get('pass', False))
            print(f"{county}: {pass_count}/10")
        else:
            print(f"{county}: EVALUATION FAILED")
    
    print("\nPRIORITY ORDER (from briefing):")
    print("1. brevard C/D root cause - PropertyOnion coverage fix")  
    print("2. J generator build - bid_decisions pipeline")
    print("3. brevard G hit list - zone_standards backfill")
    print("4. brevard B reconciliation - fix 134.1% anomaly")
    print("5. Other counties following same patterns")