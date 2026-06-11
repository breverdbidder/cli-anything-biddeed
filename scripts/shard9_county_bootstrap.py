#!/usr/bin/env python3
"""
SHARD 9 County Bootstrap: dixie, taylor (and verify leon, washington, marion)
Ensures baseline data ingestion for assigned counties before Letter work

This addresses the 0/10 scores for dixie and taylor by:
1. Running county ingestion (FL GIO parcels → zoning_assignments)
2. Verifying slug assignment in multi_county_auctions
3. Setting up scraper configurations

Usage:
  python scripts/shard9_county_bootstrap.py
"""
import os
import sys
import subprocess
import httpx
import json
from datetime import datetime
from typing import Dict, List, Optional

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD 9 assigned counties with metadata from fl_counties_manifest.yml
TARGET_COUNTIES = [
    {'name': 'Leon', 'co_no': 47, 'slug': 'leon'},
    {'name': 'Washington', 'co_no': 77, 'slug': 'washington'},
    {'name': 'Marion', 'co_no': 52, 'slug': 'marion'}, 
    {'name': 'Dixie', 'co_no': 25, 'slug': 'dixie'},
    {'name': 'Taylor', 'co_no': 72, 'slug': 'taylor'}
]

def check_supabase_connection():
    """Verify we can connect to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=headers)
        response.raise_for_status()
        print("✅ Supabase connection verified")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

def check_county_status(co_no, name, slug):
    """Check current ingestion status for a county"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check fl_counties
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?co_no=eq.{co_no}&select=*",
            headers=headers
        )
        fl_county = response.json()[0] if response.status_code == 200 and response.json() else None
        
        # Check zoning_assignments  
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/zoning_assignments?co_no=eq.{co_no}&select=count",
            headers=headers
        )
        zoning_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check multi_county_auctions
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check gold_standard_county_status
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/gold_standard_county_status?county_slug=eq.{slug}&select=score,metrics",
            headers=headers
        )
        gs_status = response.json()[0] if response.status_code == 200 and response.json() else None
        
        status = {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'zoning_assignments': zoning_count,
            'auctions': auction_count,
            'gold_standard_score': gs_status.get('score', 0) if gs_status else 0,
            'needs_ingestion': zoning_count == 0,
            'needs_auction_slug': auction_count == 0
        }
        
        return status
        
    except Exception as e:
        print(f"❌ Error checking {name} status: {e}")
        return None

def run_county_ingestion(co_no, name):
    """Run the county ingestion script for a specific county"""
    print(f"\n📥 Starting ingestion for {name} (CO_NO={co_no})...")
    
    try:
        # First, just count parcels
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Count failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        print(result.stdout[-500:])  # Last 500 chars
        
        # Then do full ingestion  
        print(f"📦 Starting full ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
        
        if result.returncode != 0:
            print(f"❌ Full ingestion failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Full ingestion completed for {name}")
        print(result.stdout[-500:])  # Last 500 chars
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Ingestion timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running ingestion for {name}: {e}")
        return False

def ensure_slug_in_auctions(slug: str, co_no: int) -> bool:
    """Ensure the county slug exists in multi_county_auctions"""
    try:
        client = httpx.Client(timeout=30)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Check if slug already exists
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count&limit=1",
            headers=headers
        )
        
        if response.status_code == 200 and response.json():
            print(f"✅ {slug} already has auction records")
            return True
        
        print(f"ℹ️  {slug} has no auction records - may need scraper execution")
        return False
        
    except Exception as e:
        print(f"❌ Error checking auction slug for {slug}: {e}")
        return False

def evaluate_county_live(slug: str) -> Optional[Dict]:
    """Run live county evaluation via pencil_dod_evaluate_county"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result:
                print(f"📊 Live evaluation for {slug}:")
                score = 0
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric', 'null')
                    passing = letter_data.get('pass', False)
                    status = "✅" if passing else "❌"
                    if passing:
                        score += 1
                    print(f"  {letter}: {status} {metric}")
                print(f"  Score: {score}/10")
                return {'score': score, 'letters': result}
            else:
                print(f"📊 {slug}: No evaluation data (needs setup)")
                return None
        else:
            print(f"❌ Failed to evaluate {slug}: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error evaluating {slug}: {e}")
        return None

def main():
    print("=" * 80)
    print("SHARD 9 COUNTY BOOTSTRAP")
    print("Assigned: leon, washington, marion, dixie, taylor")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        sys.exit(1)
    
    print("\n🔍 Checking current county status...")
    
    counties_status = []
    for county in TARGET_COUNTIES:
        status = check_county_status(county['co_no'], county['name'], county['slug'])
        if status:
            counties_status.append(status)
            print(f"  {status['county']:12s} | "
                  f"GS Score: {status['gold_standard_score']:>2}/10 | "
                  f"Parcels: {status['total_parcels']:>8,} | " 
                  f"Zoning: {status['zoning_assignments']:>6} | "
                  f"Auctions: {status['auctions']:>5} | "
                  f"Status: {'NEEDS_INGESTION' if status['needs_ingestion'] else 'READY'}")
    
    # Identify counties that need ingestion
    counties_to_ingest = [s for s in counties_status if s['needs_ingestion']]
    
    if counties_to_ingest:
        print(f"\n📋 Counties needing ingestion: {len(counties_to_ingest)}")
        for county in counties_to_ingest:
            print(f"  - {county['county']} (CO_NO={county['co_no']})")
        
        # Run ingestion for counties that need it
        for county in counties_to_ingest:
            success = run_county_ingestion(county['co_no'], county['county'])
            if success:
                print(f"✅ {county['county']} ingestion completed successfully")
            else:
                print(f"❌ {county['county']} ingestion failed - manual intervention required")
    else:
        print("\n✅ All counties have baseline parcel data!")
    
    # Check auction slug status
    print("\n🔍 Checking auction slug status...")
    for county in TARGET_COUNTIES:
        ensure_slug_in_auctions(county['slug'], county['co_no'])
    
    # Run live evaluations
    print("\n📊 Running live county evaluations...")
    for county in TARGET_COUNTIES:
        print(f"\n--- {county['slug']} ---")
        evaluate_county_live(county['slug'])
    
    print("\n🏆 Bootstrap complete!")
    print("\nNext steps:")
    print("  1. Execute verified outcomes scraper: python scripts/shard9_verified_outcomes.py --all-counties")
    print("  2. Fix parcel linkage (Letter E) for better C/D/F scores")
    print("  3. Address Letter G/I zoning completeness")
    print("  4. Implement Letter H freshness automation")

if __name__ == "__main__":
    main()