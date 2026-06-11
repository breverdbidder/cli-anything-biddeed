#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-10 Autonomous Improvements
Target counties: manatee, alachua, martin, franklin, union
6-hour session with ship-to-main mandate

Based on issue metrics:
- manatee (2/10): A✅ H✅ B❌ C❌(14.5%) D❌(35.2%) E❌(91.4%) F❌(9.4%) G❌ I❌ J❌(0.0%)
- alachua (1/10): A✅ B❌ C❌(10.9%) D❌(50.3%) E❌(77.4%) F❌(0.0%) G❌ H❌(343h) I❌ J❌(0.0%)
- martin (1/10): A✅ B❌ C❌(11.4%) D❌(72.3%) E❌(34.8%) F❌(0.0%) G❌ H❌(222.9h) I❌ J❌(0.0%)
- franklin (0/10): All letters FAIL (no data ingested)
- union (0/10): All letters FAIL (no data ingested)

Priority improvements:
1. franklin/union Letter A (dual-product coverage) - run county ingestion
2. martin Letter E (parcel linkage 34.8% -> 95%+) - highest leverage existing county
3. manatee Letter E (parcel linkage 91.4% -> 95%+) - closest to threshold
4. alachua/martin Letter H (freshness SLA) - scraper configuration
5. All counties Letter B (verified outcomes) - independent data sources
"""
import os
import sys
import json
import requests
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import subprocess

# Supabase configuration 
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    print("Available env vars:", [k for k in os.environ.keys() if 'SUPABASE' in k or 'API' in k])
    sys.exit(1)

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

# SHARD-10 target counties
TARGET_COUNTIES = ['manatee', 'alachua', 'martin', 'franklin', 'union']

# County DOR numbers from fl_counties_manifest.yml
COUNTY_DOR_NUMBERS = {
    'manatee': 51,
    'alachua': 11,  
    'martin': 53,
    'franklin': 29,
    'union': 73
}

def log(msg):
    """Log message with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def supabase_get(table: str, params: str = "", limit: int = 1000) -> List[Dict]:
    """Get data from Supabase table"""
    try:
        url = f"{BASE}/{table}?limit={limit}&{params}"
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            log(f"❌ Error fetching from {table}: {response.status_code} - {response.text[:200]}")
            return []
    except Exception as e:
        log(f"❌ Error fetching from {table}: {e}")
        return []

def supabase_post(table: str, data: List[Dict], batch_size: int = 500) -> int:
    """Insert/upsert data to Supabase table in batches"""
    if not data:
        return 0
    
    total_inserted = 0
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        try:
            response = requests.post(f"{BASE}/{table}", headers=HEADERS, json=batch, timeout=30)
            if response.status_code in [200, 201, 204]:
                total_inserted += len(batch)
                log(f"✅ Upserted batch {i//batch_size + 1}: {len(batch)} records to {table}")
            else:
                log(f"❌ Error upserting batch to {table}: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            log(f"❌ Error upserting batch to {table}: {e}")
        
        time.sleep(0.5)  # Rate limiting
    
    return total_inserted

def supabase_rpc(function_name: str, params: Dict = None) -> any:
    """Call Supabase RPC function"""
    try:
        response = requests.post(f"{BASE}/rpc/{function_name}", headers=HEADERS, json=params or {}, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            log(f"❌ RPC {function_name} failed: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        log(f"❌ RPC {function_name} error: {e}")
        return None

def evaluate_county(county_slug: str) -> Dict:
    """Evaluate a county using pencil_dod_evaluate_county"""
    log(f"Evaluating county: {county_slug}")
    result = supabase_rpc("pencil_dod_evaluate_county", {"county_slug_arg": county_slug})
    
    if result:
        pass_count = 0
        log(f"📊 {county_slug.upper()} evaluation:")
        
        if isinstance(result, list):
            for letter_data in result:
                letter = letter_data.get('letter', '?')
                metric = letter_data.get('metric')
                is_pass = letter_data.get('pass', False)
                if is_pass:
                    pass_count += 1
                status = "✅ PASS" if is_pass else "❌ FAIL"
                log(f"    {letter}: {status} metric={metric}")
        
        log(f"    TOTAL: {pass_count}/10")
        return {'county': county_slug, 'evaluation': result, 'pass_count': pass_count}
    
    return {'county': county_slug, 'evaluation': None, 'pass_count': 0}

def check_county_basic_data(county_slug: str) -> Dict:
    """Check if county has basic auction data ingested"""
    log(f"Checking basic data for {county_slug}")
    
    # Check multi_county_auctions
    auctions = supabase_get("multi_county_auctions", f"county=eq.{county_slug}&select=count", limit=1)
    auction_count = len(auctions)
    
    # Check sample_properties with CO_NO
    co_no = COUNTY_DOR_NUMBERS.get(county_slug)
    if co_no:
        properties = supabase_get("sample_properties", f"co_no=eq.{co_no}&select=count", limit=1)
        property_count = len(properties)
    else:
        property_count = 0
    
    log(f"  {county_slug}: {auction_count} auctions, {property_count} sample properties")
    return {
        'county': county_slug,
        'auction_count': auction_count,
        'property_count': property_count,
        'has_basic_data': auction_count > 0 or property_count > 0
    }

def run_county_ingestion(county_slug: str) -> bool:
    """Run county ingestion using ingest_county.py script"""
    co_no = COUNTY_DOR_NUMBERS.get(county_slug)
    if not co_no:
        log(f"❌ No CO_NO found for {county_slug}")
        return False
    
    log(f"Running county ingestion for {county_slug} (CO_NO={co_no})")
    
    # First, try a count to see how many parcels we're dealing with
    try:
        result = subprocess.run([
            sys.executable, "scripts/ingest_county.py", 
            "--county", str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            log(f"✅ Count successful for {county_slug}")
            log(result.stdout[-500:])  # Show last 500 chars of output
            
            # Now run full ingestion
            log(f"Running full ingestion for {county_slug}")
            result_full = subprocess.run([
                sys.executable, "scripts/ingest_county.py",
                "--county", str(co_no), "--full"
            ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
            
            if result_full.returncode == 0:
                log(f"✅ Full ingestion successful for {county_slug}")
                log(result_full.stdout[-500:])
                return True
            else:
                log(f"❌ Full ingestion failed for {county_slug}: {result_full.stderr}")
                return False
        else:
            log(f"❌ Count failed for {county_slug}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log(f"❌ County ingestion timeout for {county_slug}")
        return False
    except Exception as e:
        log(f"❌ County ingestion error for {county_slug}: {e}")
        return False

def improve_parcel_linkage(county_slug: str) -> bool:
    """Improve parcel linkage (Letter E) for a county"""
    log(f"Improving parcel linkage for {county_slug}")
    
    # This would involve running parcel linking scripts
    # For now, we'll check current status and identify the gaps
    
    co_no = COUNTY_DOR_NUMBERS.get(county_slug)
    if not co_no:
        return False
    
    # Check current linkage status
    auctions_total = supabase_get("multi_county_auctions", f"county=eq.{county_slug}&select=count")
    auctions_linked = supabase_get("multi_county_auctions", f"county=eq.{county_slug}&parcel_id=not.is.null&select=count")
    
    total_count = len(auctions_total) if auctions_total else 0
    linked_count = len(auctions_linked) if auctions_linked else 0
    
    if total_count > 0:
        linkage_pct = (linked_count / total_count) * 100
        log(f"  Current linkage: {linked_count}/{total_count} = {linkage_pct:.1f}%")
        
        if linkage_pct >= 95.0:
            log(f"✅ {county_slug} already has sufficient parcel linkage")
            return True
    
    # TODO: Implement actual parcel linking logic here
    # This would involve calling county property appraiser APIs
    # or running existing parcel linking scripts
    
    log(f"🚧 Parcel linkage improvement needed for {county_slug} (TODO)")
    return False

def improve_freshness(county_slug: str) -> bool:
    """Improve data freshness (Letter H) for a county"""
    log(f"Improving freshness for {county_slug}")
    
    # Check current freshness
    # TODO: Check last_seen timestamps and configure scrapers
    
    log(f"🚧 Freshness improvement needed for {county_slug} (TODO)")
    return False

def main():
    """Main execution function"""
    start_time = datetime.now()
    log("🚀 Starting SHARD-10 Gold Standard Improvements")
    log(f"Target counties: {', '.join(TARGET_COUNTIES)}")
    
    # Phase 1: Evaluate all counties to get baseline
    log("\n=== PHASE 1: Baseline Evaluation ===")
    baseline_evaluations = {}
    for county in TARGET_COUNTIES:
        baseline_evaluations[county] = evaluate_county(county)
        time.sleep(1)
    
    # Phase 2: Check basic data status
    log("\n=== PHASE 2: Basic Data Check ===")
    data_status = {}
    for county in TARGET_COUNTIES:
        data_status[county] = check_county_basic_data(county)
        time.sleep(1)
    
    # Phase 3: Prioritized improvements
    log("\n=== PHASE 3: Prioritized Improvements ===")
    
    # Priority 1: Counties with no data (franklin, union)
    zero_data_counties = [c for c in TARGET_COUNTIES 
                         if not data_status[c]['has_basic_data']]
    
    for county in zero_data_counties:
        log(f"\n🎯 PRIORITY 1: Setting up {county} (Letter A)")
        if run_county_ingestion(county):
            log(f"✅ County ingestion completed for {county}")
            # Re-evaluate after ingestion
            evaluate_county(county)
        else:
            log(f"❌ County ingestion failed for {county}")
    
    # Priority 2: Improve parcel linkage for counties close to threshold
    high_linkage_counties = ['manatee']  # 91.4% - closest to 95% threshold
    
    for county in high_linkage_counties:
        log(f"\n🎯 PRIORITY 2: Improving parcel linkage for {county} (Letter E)")
        if improve_parcel_linkage(county):
            log(f"✅ Parcel linkage improved for {county}")
            evaluate_county(county)
    
    # Priority 3: Address freshness issues
    stale_counties = ['alachua', 'martin']  # H failures due to staleness
    
    for county in stale_counties:
        log(f"\n🎯 PRIORITY 3: Improving freshness for {county} (Letter H)")
        if improve_freshness(county):
            log(f"✅ Freshness improved for {county}")
            evaluate_county(county)
    
    # Phase 4: Final verification
    log("\n=== PHASE 4: Final Verification ===")
    final_evaluations = {}
    for county in TARGET_COUNTIES:
        final_evaluations[county] = evaluate_county(county)
        time.sleep(1)
    
    # Summary
    log("\n=== SUMMARY ===")
    total_time = datetime.now() - start_time
    log(f"Total execution time: {total_time}")
    
    for county in TARGET_COUNTIES:
        baseline_pass = baseline_evaluations[county]['pass_count']
        final_pass = final_evaluations[county]['pass_count']
        improvement = final_pass - baseline_pass
        log(f"{county}: {baseline_pass}/10 → {final_pass}/10 ({improvement:+d})")

if __name__ == "__main__":
    main()