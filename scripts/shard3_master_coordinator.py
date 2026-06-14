#!/usr/bin/env python3
"""
SHARD-3 Master Coordinator: charlotte, bay, marion, walton, jefferson
Gold Standard Campaign - 6h autonomous session

Executes fixes for failing criteria following the brief playbooks:
- A: dual-product coverage configuration 
- B: verified independent outcomes (≥95% of closed)
- C/D: parity matching improvements
- E: parcel linkage via county GIS
- F: tier1 sold verification
- G: zoning KPI (min density/FAR/pk1000 ≥95%)
- H: freshness ≤48h
- I: property card completion ≥95%
- J: Shapira deal thesis pipeline

Priority: jefferson (0/10) -> bay/marion/walton (1/10) -> charlotte (2/10)
"""
import os
import sys
import json
import time
from datetime import datetime
import traceback

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import httpx
except ImportError:
    print("❌ httpx not available - installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# SHARD-3 counties
SHARD3_COUNTIES = ['charlotte', 'bay', 'marion', 'walton', 'jefferson']

def sb_headers():
    """Get Supabase headers"""
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def log(message: str):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def test_connection():
    """Test Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1",
            headers=sb_headers()
        )
        if response.status_code == 200:
            log("✅ Database connection successful")
            return True
        else:
            log(f"❌ Database connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}")
        return False

def evaluate_county(county_slug: str) -> dict:
    """Run pencil_dod_evaluate_county for a county"""
    try:
        client = httpx.Client(timeout=60)
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if response.status_code == 200:
            result = response.json()
            log(f"✅ Evaluated {county_slug}")
            return result
        else:
            log(f"❌ Failed to evaluate {county_slug}: {response.status_code} - {response.text}")
            return []
            
    except Exception as e:
        log(f"❌ Error evaluating {county_slug}: {e}")
        return []

def get_county_status(county_slug: str) -> dict:
    """Get current county status summary"""
    evaluation = evaluate_county(county_slug)
    if not evaluation:
        return {"county": county_slug, "pass_count": 0, "letters": {}}
    
    letters = {}
    pass_count = 0
    
    for letter_data in evaluation:
        letter = letter_data.get('letter', '?')
        metric = letter_data.get('metric')
        passed = letter_data.get('pass', False)
        
        letters[letter] = {
            "metric": metric,
            "pass": passed,
            "status": "✅" if passed else "❌"
        }
        
        if passed:
            pass_count += 1
    
    return {
        "county": county_slug,
        "pass_count": pass_count,
        "letters": letters
    }

def configure_a_lane(county_slug: str) -> bool:
    """Configure A-lane (dual-product coverage) for county"""
    log(f"Configuring A-lane for {county_slug}...")
    
    # Check if county exists in pipeline.counties
    try:
        client = httpx.Client(timeout=60)
        
        # Check existing configuration
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties?county_slug=eq.{county_slug}",
            headers=sb_headers()
        )
        
        if response.status_code == 200:
            results = response.json()
            if results:
                log(f"✅ {county_slug} already configured in pipeline.counties")
                return True
            else:
                log(f"⚠️ {county_slug} not found in pipeline.counties - needs configuration")
                # This would typically involve:
                # 1. Adding county to pipeline.counties with realauction + tax_deed platforms
                # 2. Setting foreclosure_url and tax_deed_url appropriately
                # 3. Configuring scraper lanes
                return False
        else:
            log(f"❌ Failed to check pipeline configuration: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Error configuring A-lane: {e}")
        return False

def fix_letter_b(county_slug: str) -> bool:
    """Fix Letter B - verified independent outcomes"""
    log(f"Working on Letter B for {county_slug}...")
    
    # Letter B requires independent data source for verified outcomes
    # This typically involves setting up scrapers for clerk records
    # For now, log the requirement
    log(f"⚠️ Letter B fix requires independent outcome verification setup for {county_slug}")
    log(f"   - Need clerk recording scraper or equivalent independent source")
    log(f"   - Cannot use PropertyOnion as source (must be independent)")
    
    return False  # Placeholder - real implementation needed

def fix_letter_e(county_slug: str) -> bool:
    """Fix Letter E - parcel linkage via county GIS"""
    log(f"Working on Letter E for {county_slug}...")
    
    # Letter E requires linking auction records to parcels via county property appraiser
    # This involves spatial queries or parcel ID matching
    log(f"⚠️ Letter E fix requires parcel linkage implementation for {county_slug}")
    log(f"   - Need county property appraiser GIS integration")
    log(f"   - Spatial matching or parcel ID resolution")
    
    return False  # Placeholder - real implementation needed

def process_county(county_slug: str) -> dict:
    """Process a single county through the improvement pipeline"""
    log(f"\n{'='*50}")
    log(f"PROCESSING: {county_slug.upper()}")
    log(f"{'='*50}")
    
    # Get initial status
    initial_status = get_county_status(county_slug)
    log(f"Initial status: {initial_status['pass_count']}/10 letters passing")
    
    improvements = []
    
    # Process failing letters in order of priority
    for letter, data in initial_status['letters'].items():
        if not data['pass']:
            log(f"\nProcessing failing letter {letter}...")
            
            if letter == 'A':
                success = configure_a_lane(county_slug)
                improvements.append(f"A-lane: {'✅' if success else '❌'}")
            elif letter == 'B':
                success = fix_letter_b(county_slug)
                improvements.append(f"B verified outcomes: {'✅' if success else '❌'}")
            elif letter == 'E':
                success = fix_letter_e(county_slug)
                improvements.append(f"E parcel linkage: {'✅' if success else '❌'}")
            else:
                log(f"⚠️ No specific handler for letter {letter} yet")
                improvements.append(f"{letter}: handler needed")
    
    # Get final status
    final_status = get_county_status(county_slug)
    improvement = final_status['pass_count'] - initial_status['pass_count']
    
    return {
        "county": county_slug,
        "initial_pass": initial_status['pass_count'],
        "final_pass": final_status['pass_count'],
        "improvement": improvement,
        "improvements": improvements,
        "final_status": final_status
    }

def main():
    """Main execution"""
    log("🚀 SHARD-3 Master Coordinator Starting")
    log(f"Counties: {', '.join(SHARD3_COUNTIES)}")
    
    # Test database connection
    if not SUPABASE_KEY:
        log("❌ No Supabase API key found")
        return False
    
    if not test_connection():
        log("❌ Database connection failed")
        return False
    
    # Process each county
    results = []
    total_initial_pass = 0
    total_final_pass = 0
    
    for county in SHARD3_COUNTIES:
        try:
            result = process_county(county)
            results.append(result)
            total_initial_pass += result['initial_pass']
            total_final_pass += result['final_pass']
        except Exception as e:
            log(f"❌ Error processing {county}: {e}")
            traceback.print_exc()
    
    # Summary
    log(f"\n{'='*50}")
    log("SHARD-3 SESSION SUMMARY")
    log(f"{'='*50}")
    
    for result in results:
        county = result['county']
        initial = result['initial_pass']
        final = result['final_pass']
        improvement = result['improvement']
        
        status_icon = "✅" if improvement > 0 else "🔄" if improvement == 0 else "❌"
        log(f"{status_icon} {county}: {initial}/10 → {final}/10 (+{improvement})")
        
        for imp in result['improvements']:
            log(f"   {imp}")
    
    log(f"\nTotal progress: {total_initial_pass}/50 → {total_final_pass}/50 (+{total_final_pass - total_initial_pass})")
    log(f"Session completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("Session interrupted by user")
        sys.exit(1)
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)