#!/usr/bin/env python3
"""
Bootstrap Zero Counties: Letter A Fix for dixie, holmes, taylor
Implements dual-product coverage by configuring both foreclosure and tax_deed auction lanes
"""
import os
import sys
import httpx
import json
from datetime import datetime, timezone

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def get_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def bootstrap_county_letter_a(county_slug):
    """Call the database function to bootstrap Letter A for a county"""
    print(f"🚀 Bootstrapping Letter A for {county_slug}...")
    
    try:
        with httpx.Client(timeout=60) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/bootstrap_county_letter_a",
                headers=get_headers(),
                json={"county_slug_arg": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ {county_slug}: {result}")
                return True
            else:
                print(f"❌ Failed to bootstrap {county_slug}: {response.status_code} - {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error bootstrapping {county_slug}: {e}")
        return False

def check_auction_data_count(county_slug):
    """Check current auction data count for a county"""
    try:
        with httpx.Client(timeout=30) as client:
            # Check total auctions
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count",
                headers=get_headers()
            )
            
            total_count = len(response.json()) if response.status_code == 200 else 0
            
            # Check by sale type
            fc_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&sale_type=eq.foreclosure&select=count",
                headers=get_headers()
            )
            fc_count = len(fc_response.json()) if fc_response.status_code == 200 else 0
            
            td_response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&sale_type=eq.tax_deed&select=count",
                headers=get_headers()
            )
            td_count = len(td_response.json()) if td_response.status_code == 200 else 0
            
            print(f"  {county_slug}: Total={total_count}, FC={fc_count}, TD={td_count}")
            
            # Letter A requires both sale types present
            dual_product = fc_count > 0 and td_count > 0
            
            return {
                'total': total_count,
                'foreclosure': fc_count,
                'tax_deed': td_count,
                'dual_product': dual_product
            }
            
    except Exception as e:
        print(f"❌ Error checking {county_slug}: {e}")
        return None

def log_session_action(session_id, county_slug, action_type, action_detail, success=True):
    """Log an action to the session log"""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/log_gold_standard_session",
                headers=get_headers(),
                json={
                    "session_id": session_id,
                    "county_slug_arg": county_slug,
                    "action_type": action_type,
                    "action_detail": action_detail,
                    "success": success
                }
            )
            
            if response.status_code != 200:
                print(f"⚠️ Failed to log session action: {response.status_code}")
                
    except Exception as e:
        print(f"⚠️ Error logging session action: {e}")

def main():
    """Bootstrap zero counties for Letter A compliance"""
    print("=" * 60)
    print("BOOTSTRAP ZERO COUNTIES - LETTER A FIX")
    print("Counties: dixie, holmes, taylor")
    print("Goal: Dual-product coverage (foreclosure + tax_deed)")
    print("=" * 60)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY not found")
        return False
    
    session_id = f"wave2-shard5-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    zero_counties = ['dixie', 'holmes', 'taylor']
    
    # Check current status
    print("\n📊 Current auction data status:")
    county_status = {}
    for county in zero_counties:
        status = check_auction_data_count(county)
        county_status[county] = status
        
        if status and status['dual_product']:
            print(f"✅ {county} already has dual product coverage")
        elif status and status['total'] > 0:
            print(f"⚠️ {county} has {status['total']} auctions but missing dual product")
        else:
            print(f"❌ {county} has no auction data")
    
    # Bootstrap counties that need it
    print("\n🔧 Bootstrapping counties...")
    for county in zero_counties:
        status = county_status.get(county, {})
        
        if not status or not status.get('dual_product', False):
            print(f"\n🏗️ Bootstrapping {county}...")
            
            # Call bootstrap function
            success = bootstrap_county_letter_a(county)
            
            # Log the action
            if success:
                log_session_action(
                    session_id, county, 'bootstrap_letter_a',
                    f"Configured dual-product coverage pipeline for {county}",
                    True
                )
            else:
                log_session_action(
                    session_id, county, 'bootstrap_letter_a',
                    f"Failed to configure pipeline for {county}",
                    False
                )
        else:
            print(f"⏭️ {county} already configured")
            log_session_action(
                session_id, county, 'bootstrap_letter_a',
                f"{county} already has dual-product coverage",
                True
            )
    
    # Final verification
    print("\n🔍 Post-bootstrap verification:")
    all_configured = True
    for county in zero_counties:
        status = check_auction_data_count(county)
        if status and status.get('dual_product', False):
            print(f"✅ {county}: Letter A ready")
        else:
            print(f"⚠️ {county}: Still needs auction data ingestion")
            all_configured = False
    
    # Summary
    print(f"\n🏆 Bootstrap Summary:")
    if all_configured:
        print("✅ All zero counties configured for dual-product coverage")
    else:
        print("⚠️ Counties configured but need auction data ingestion to run")
        print("   Next: Execute auction scraping pipeline for configured counties")
    
    log_session_action(
        session_id, 'ALL', 'bootstrap_complete',
        f"Bootstrap phase completed. All_configured={all_configured}",
        all_configured
    )
    
    return all_configured

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)