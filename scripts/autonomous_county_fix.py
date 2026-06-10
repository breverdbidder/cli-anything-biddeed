#!/usr/bin/env python3
"""
Autonomous County Fix Script - Execute via Python import without bash
For Gold Standard Wave2-Shard-5 session
"""
import os
import sys
import json
import subprocess
from datetime import datetime, timezone

# Install httpx if needed
try:
    import httpx
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# GitHub Actions secrets should be available as environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_db_connection():
    """Test Supabase connection"""
    print("🔌 Testing database connection...")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found")
        # Try to get from environment in GitHub Actions
        github_env = os.environ.get('GITHUB_ACTIONS')
        if github_env:
            print("  📝 Running in GitHub Actions - checking for secrets...")
        return False
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1",
                headers=get_headers()
            )
            
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print("✅ Database connection successful")
                return True
            else:
                print(f"❌ Database error: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

def evaluate_county_status(county_slug):
    """Get current status for a county via pencil_dod_evaluate_county"""
    print(f"📊 Evaluating {county_slug}...")
    
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=get_headers(),
                json={"county_slug_arg": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if isinstance(result, list):
                    evaluation = {}
                    for item in result:
                        letter = item.get('letter', '?')
                        metric = item.get('metric')
                        passed = item.get('pass', False)
                        evaluation[letter] = {'metric': metric, 'pass': passed}
                        
                        status_icon = "✅" if passed else "❌"
                        print(f"  {letter}: {status_icon} {metric}")
                    
                    return evaluation
                else:
                    print(f"  ⚠️ Unexpected result format: {result}")
                    return None
            else:
                print(f"❌ Evaluation failed: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ Error evaluating {county_slug}: {e}")
        return None

def check_county_data_status(county_slug):
    """Check basic data availability for a county"""
    print(f"🔍 Checking data status for {county_slug}...")
    
    try:
        with httpx.Client(timeout=30) as client:
            # Check auction data
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count",
                headers=get_headers()
            )
            
            auction_count = len(response.json()) if response.status_code == 200 else 0
            print(f"  Auction records: {auction_count}")
            
            # Check if county exists in fl_counties
            county_co_map = {
                'volusia': 30, 'escambia': 22, 'lee': 36, 'santa_rosa': 69,
                'dixie': 21, 'holmes': 36, 'taylor': 75
            }
            
            co_no = county_co_map.get(county_slug)
            if co_no:
                response = client.get(
                    f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
                    headers=get_headers()
                )
                
                fl_county_data = response.json()[0] if response.status_code == 200 and response.json() else None
                if fl_county_data:
                    total_parcels = fl_county_data.get('total_parcels', 0)
                    print(f"  Total parcels: {total_parcels}")
                else:
                    print(f"  ⚠️ No fl_counties record for CO_NO={co_no}")
            
            return {
                'auction_count': auction_count,
                'co_no': co_no,
                'has_fl_county_record': fl_county_data is not None if co_no else False
            }
            
    except Exception as e:
        print(f"❌ Error checking data for {county_slug}: {e}")
        return None

def main():
    """Main execution function"""
    print("=" * 70)
    print("GOLD STANDARD WAVE2-SHARD-5 AUTONOMOUS SESSION")
    print("Counties: volusia, escambia, lee, santa_rosa, dixie, holmes, taylor")
    print("=" * 70)
    
    # Test connection first
    if not test_db_connection():
        print("\n❌ Cannot proceed without database connection")
        return False
    
    # Process assigned counties
    shard_counties = ['volusia', 'escambia', 'lee', 'santa_rosa', 'dixie', 'holmes', 'taylor']
    
    county_statuses = {}
    
    for county_slug in shard_counties:
        print(f"\n{'='*50}")
        print(f"PROCESSING: {county_slug.upper()}")
        print(f"{'='*50}")
        
        # Check data status
        data_status = check_county_data_status(county_slug)
        
        # Get evaluation
        evaluation = evaluate_county_status(county_slug)
        
        county_statuses[county_slug] = {
            'data_status': data_status,
            'evaluation': evaluation
        }
    
    # Summary
    print(f"\n{'='*70}")
    print("SESSION SUMMARY")
    print(f"{'='*70}")
    
    for county_slug, status in county_statuses.items():
        evaluation = status.get('evaluation', {})
        data_status = status.get('data_status', {})
        
        pass_count = sum(1 for letter_data in evaluation.values() if letter_data.get('pass', False)) if evaluation else 0
        
        print(f"\n{county_slug:12s}: {pass_count}/10 pass")
        print(f"  Auction records: {data_status.get('auction_count', 'unknown') if data_status else 'unknown'}")
        
        if evaluation:
            critical_letters = ['B', 'I', 'J']
            failing_critical = [letter for letter in critical_letters if not evaluation.get(letter, {}).get('pass', False)]
            
            if failing_critical:
                print(f"  Critical failures: {', '.join(failing_critical)}")
    
    print(f"\nTime: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("\n✅ Diagnostic session completed")
    print("\nNext actions required:")
    print("  1. Implement auction data ingestion for 0/10 counties")
    print("  2. Build verified outcomes scrapers (Letter B)")
    print("  3. Property card enrichment pipeline (Letter I)")
    print("  4. Shapira deal thesis pipeline (Letter J)")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)