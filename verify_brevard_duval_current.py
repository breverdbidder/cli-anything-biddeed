#!/usr/bin/env python3
"""
GOLD STANDARD AUTOPILOT: Verify current brevard and duval county status
Run pencil_dod_evaluate_county for both counties and show live metrics
"""
import os
import sys
import json
from datetime import datetime

# Import httpx 
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Setup Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Target counties for SHARD 29
TARGET_COUNTIES = ['brevard', 'duval']

def sb_headers():
    """Supabase request headers"""
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_connection():
    """Test basic connection to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Database connection successful")
            return True
        else:
            print(f"❌ Database connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def evaluate_county_live(county_slug):
    """Run pencil_dod_evaluate_county function for live metrics"""
    try:
        client = httpx.Client(timeout=60)
        
        print(f"🔍 Evaluating {county_slug} with pencil_dod_evaluate_county...")
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"✅ Live evaluation for {county_slug.upper()}:")
            
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                total_letters = len(result)
                
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    passed = letter_data.get('pass', False)
                    threshold = letter_data.get('threshold')
                    
                    if passed:
                        pass_count += 1
                    
                    status_emoji = "✅" if passed else "❌"
                    metric_str = f"{metric:.1f}" if isinstance(metric, (int, float)) and metric is not None else str(metric) if metric is not None else "NULL"
                    threshold_str = f" (threshold: {threshold})" if threshold else ""
                    
                    print(f"  {letter}: {status_emoji} {metric_str}{threshold_str}")
                
                print(f"  SCORE: {pass_count}/{total_letters}")
                return result, pass_count, total_letters
            else:
                print(f"  No evaluation data returned")
                return None, 0, 0
        else:
            print(f"❌ Failed to evaluate {county_slug}: {r.status_code} - {r.text}")
            return None, 0, 0
            
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None, 0, 0

def get_basic_counts():
    """Get basic row counts for key tables"""
    try:
        client = httpx.Client(timeout=30)
        
        print("\n📊 Basic table counts:")
        
        # multi_county_auctions for both counties
        for county in TARGET_COUNTIES:
            r = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county}&select=case_number",
                headers=sb_headers()
            )
            if r.status_code == 200:
                count = len(r.json())
                print(f"  {county} auctions: {count:,}")
        
        # Check verified outcomes
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?select=case_number&limit=1000",
            headers=sb_headers()
        )
        if r.status_code == 200:
            foreclosure_count = len(r.json())
            print(f"  foreclosure_outcomes: {foreclosure_count:,}")
        
        # Check bid_decisions
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/bid_decisions?select=case_number&limit=1000",
            headers=sb_headers()
        )
        if r.status_code == 200:
            bid_decisions_count = len(r.json())
            print(f"  bid_decisions: {bid_decisions_count:,}")
            
    except Exception as e:
        print(f"❌ Error getting counts: {e}")

def main():
    print("=" * 60)
    print("GOLD STANDARD AUTOPILOT - BREVARD & DUVAL VERIFICATION")
    print(f"Dispatch: db82988c-3cdf-45e2-a4ac-c4a100157b80")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"API Key present: {bool(SUPABASE_KEY)}")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        print("Expected: SUPABASE_KEY or SUPABASE_SERVICE_KEY")
        sys.exit(1)
    
    if not test_connection():
        sys.exit(1)
    
    # Get current live metrics
    print("\n=== LIVE COUNTY EVALUATIONS ===")
    
    total_score = 0
    total_possible = 0
    
    for county in TARGET_COUNTIES:
        print(f"\n--- {county.upper()} ---")
        result, pass_count, total_letters = evaluate_county_live(county)
        total_score += pass_count
        total_possible += total_letters
    
    print(f"\n🎯 COMBINED SCORE: {total_score}/{total_possible}")
    
    # Get basic counts
    get_basic_counts()
    
    print(f"\n✅ Verification complete at {datetime.now().isoformat()}")
    print("\nNext: Start ULTRALOOP protocol with target selection")

if __name__ == "__main__":
    main()