#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-7 Autonomous Session: manatee, flagler, okaloosa, columbia, madison
6-hour autonomous execution targeting highest-leverage failing criteria

Session targets:
- columbia, madison: 0/10 -> criterion A setup (dual product coverage)  
- manatee: 2/10 -> criterion B,C,D,E,F,G,I,J fixes
- flagler: 1/10 -> criterion B,C,D,E,F,G,H,I,J fixes
- okaloosa: 1/10 -> criterion B,C,D,E,F,G,H,I,J fixes

Usage:
  python scripts/shard7_gold_standard_autonomous.py
"""
import os
import sys
import subprocess
import httpx
import json
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-7 assigned counties with co_no mappings
SHARD_COUNTIES = [
    {'name': 'Manatee', 'co_no': 41, 'slug': 'manatee', 'current_score': '2/10', 'priority': 'medium'},
    {'name': 'Flagler', 'co_no': 18, 'slug': 'flagler', 'current_score': '1/10', 'priority': 'medium'},
    {'name': 'Okaloosa', 'co_no': 46, 'slug': 'okaloosa', 'current_score': '1/10', 'priority': 'medium'},
    {'name': 'Columbia', 'co_no': 12, 'slug': 'columbia', 'current_score': '0/10', 'priority': 'high'},
    {'name': 'Madison', 'co_no': 40, 'slug': 'madison', 'current_score': '0/10', 'priority': 'high'}
]

def log_with_timestamp(message):
    """Add timestamp to all log messages"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

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
        log_with_timestamp("✅ Supabase connection verified")
        client.close()
        return True
    except Exception as e:
        log_with_timestamp(f"❌ Supabase connection failed: {e}")
        return False

def evaluate_county_status(county_slug):
    """Evaluate current Gold Standard status for a county"""
    try:
        client = httpx.Client(timeout=60)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Call the evaluation function
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=headers,
            json={"county_slug_arg": county_slug}
        )
        
        if response.status_code == 200:
            results = response.json()
            log_with_timestamp(f"📊 {county_slug.upper()} status:")
            
            letter_results = {}
            for result in results:
                letter = result.get('letter', 'UNKNOWN')
                pass_status = result.get('pass', False)
                metric = result.get('metric', 0)
                detail = result.get('detail', '')
                
                status_icon = "✅" if pass_status else "❌"
                if letter != 'ERROR':
                    log_with_timestamp(f"    {letter} {status_icon} metric={metric} [{detail}]")
                    letter_results[letter] = {
                        'pass': pass_status,
                        'metric': metric,
                        'detail': detail
                    }
                else:
                    log_with_timestamp(f"    ERROR: {detail}")
                    
            client.close()
            return letter_results
            
        else:
            log_with_timestamp(f"❌ Error evaluating {county_slug}: {response.status_code} {response.text}")
            client.close()
            return None
            
    except Exception as e:
        log_with_timestamp(f"❌ Error evaluating {county_slug}: {e}")
        return None

def check_county_ingestion_status(co_no, name, slug):
    """Check current data ingestion status for a county"""
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
        
        # Check multi_county_auctions
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&select=count",
            headers=headers
        )
        auction_count = len(response.json()) if response.status_code == 200 else 0
        
        # Check pipeline.counties configuration
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties?slug=eq.{slug}&select=*",
            headers=headers
        )
        pipeline_config = response.json()[0] if response.status_code == 200 and response.json() else None
        
        status = {
            'county': name,
            'co_no': co_no,
            'slug': slug,
            'fl_county_exists': fl_county is not None,
            'total_parcels': fl_county.get('total_parcels', 0) if fl_county else 0,
            'auctions': auction_count,
            'pipeline_configured': pipeline_config is not None,
            'pipeline_config': pipeline_config,
            'needs_basic_setup': auction_count == 0
        }
        
        client.close()
        return status
        
    except Exception as e:
        log_with_timestamp(f"❌ Error checking {name} ingestion status: {e}")
        return None

def main():
    log_with_timestamp("=" * 80)
    log_with_timestamp("GOLD STANDARD SHARD-7 AUTONOMOUS SESSION")
    log_with_timestamp("Counties: manatee, flagler, okaloosa, columbia, madison")
    log_with_timestamp("Budget: 6 hours | Mode: Ship-to-main")
    log_with_timestamp("=" * 80)
    
    if not SUPABASE_KEY:
        log_with_timestamp("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not check_supabase_connection():
        log_with_timestamp("❌ Database connection failed - cannot proceed")
        sys.exit(1)
    
    log_with_timestamp("\n🔍 PHASE 1: Current Status Analysis")
    log_with_timestamp("-" * 50)
    
    zero_state_counties = []
    active_counties = []
    
    for county in SHARD_COUNTIES:
        log_with_timestamp(f"\n📋 Analyzing {county['name']} ({county['slug']})...")
        
        # Check ingestion status
        ingestion_status = check_county_ingestion_status(
            county['co_no'], county['name'], county['slug']
        )
        
        if ingestion_status:
            log_with_timestamp(f"  📊 Parcels: {ingestion_status['total_parcels']:,} | "
                              f"Auctions: {ingestion_status['auctions']} | "
                              f"Pipeline: {'✅' if ingestion_status['pipeline_configured'] else '❌'}")
            
            if ingestion_status['needs_basic_setup']:
                zero_state_counties.append(county)
                log_with_timestamp(f"  🎯 ZERO STATE: Priority criterion A setup")
            else:
                # Evaluate Gold Standard status
                letter_results = evaluate_county_status(county['slug'])
                if letter_results:
                    county['letter_results'] = letter_results
                    active_counties.append(county)
                    
                    # Count passing letters
                    passing_letters = sum(1 for result in letter_results.values() if result['pass'])
                    log_with_timestamp(f"  🏆 Current score: {passing_letters}/10")
    
    # Prioritize work based on analysis
    log_with_timestamp(f"\n🎯 PRIORITY TARGETING:")
    log_with_timestamp(f"  Zero-state counties (criterion A): {len(zero_state_counties)}")
    for county in zero_state_counties:
        log_with_timestamp(f"    - {county['name']}: needs dual-product coverage setup")
    
    log_with_timestamp(f"  Active counties (letters B-J): {len(active_counties)}")
    for county in active_counties:
        if 'letter_results' in county:
            failing_letters = [letter for letter, result in county['letter_results'].items() 
                             if not result['pass'] and letter != 'ERROR']
            log_with_timestamp(f"    - {county['name']}: failing {', '.join(failing_letters)}")
    
    # EXECUTION PHASE: Start with highest leverage
    log_with_timestamp(f"\n🚀 PHASE 2: Execution (Ship-to-main)")
    log_with_timestamp("-" * 50)
    
    if zero_state_counties:
        log_with_timestamp("🥇 PRIORITY: Zero-state county setup (criterion A)")
        for county in zero_state_counties:
            log_with_timestamp(f"\n🔧 Setting up {county['name']} for criterion A...")
            # This would call the appropriate setup scripts
            log_with_timestamp(f"  TODO: Configure pipeline lanes for {county['slug']}")
            log_with_timestamp(f"  TODO: Run county ingestion (CO_NO={county['co_no']})")
    
    if active_counties:
        log_with_timestamp("\n🥈 ACTIVE: Letter-specific fixes")
        for county in active_counties:
            if 'letter_results' in county:
                log_with_timestamp(f"\n🔧 Working on {county['name']}...")
                # Analyze failing letters and prioritize fixes
                failing_letters = [(letter, result) for letter, result in county['letter_results'].items() 
                                 if not result['pass'] and letter != 'ERROR']
                
                # Sort by impact/difficulty
                priority_order = ['B', 'I', 'J', 'E', 'C', 'D', 'F', 'G', 'H']  # Critical three first
                failing_letters.sort(key=lambda x: priority_order.index(x[0]) if x[0] in priority_order else 99)
                
                for letter, result in failing_letters[:3]:  # Top 3 priorities
                    log_with_timestamp(f"  🎯 Letter {letter}: {result['detail']} (metric: {result['metric']})")
    
    log_with_timestamp(f"\n✨ Session planning complete. Ready for implementation.")
    log_with_timestamp("Next: Implement fixes and run verification protocol")

if __name__ == "__main__":
    main()