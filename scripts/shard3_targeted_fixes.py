#!/usr/bin/env python3
"""
SHARD-3 Targeted Fixes Based on Current Metrics
Following the brief's specific guidance for each county's failing criteria

CURRENT STATUS (from brief):
- charlotte (2/10): A✓ H✓ | B❌ C❌ D✓ E❌ F❌ G❌ I❌ J❌
- bay (1/10): A✓ | B❌ C❌ D❌ E❌ F❌ G❌ H❌ I❌ J❌
- marion (1/10): A✓ | B❌ C❌ D❌ E❌ F❌ G❌ H❌ I❌ J❌
- walton (1/10): A✓ | B❌ C❌ D❌ E❌ F❌ G❌ H❌ I❌ J❌
- jefferson (0/10): All criteria failing

PRIORITY FIXES:
1. jefferson: A-lane configuration (0→1 immediate win)
2. All counties: B verified outcomes (critical path blocker)
3. C/D parity matching (affects all except charlotte D)
4. E parcel linkage (needed for I, affects most auctions)
"""
import os
import sys
import json
import time
from datetime import datetime

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

SHARD3_COUNTIES = ['charlotte', 'bay', 'marion', 'walton', 'jefferson']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def verify_connection():
    """Verify database connection"""
    if not SUPABASE_KEY:
        log("❌ No Supabase API key found")
        return False
        
    try:
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if response.status_code == 200:
            log("✅ Database connected")
            return True
        else:
            log(f"❌ Connection failed: {response.status_code}")
            return False
    except Exception as e:
        log(f"❌ Connection error: {e}")
        return False

def check_pipeline_counties():
    """Check current pipeline.counties configuration"""
    try:
        client = httpx.Client(timeout=60)
        
        # Get all counties in our shard
        counties_filter = ','.join(f'"{c}"' for c in SHARD3_COUNTIES)
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties?county_slug=in.({counties_filter})",
            headers=sb_headers()
        )
        
        if response.status_code == 200:
            results = response.json()
            configured = {r['county_slug'] for r in results}
            missing = set(SHARD3_COUNTIES) - configured
            
            log(f"Pipeline configured: {configured}")
            log(f"Pipeline missing: {missing}")
            
            return configured, missing
        else:
            log(f"❌ Failed to check pipeline: {response.text}")
            return set(), set(SHARD3_COUNTIES)
            
    except Exception as e:
        log(f"❌ Error checking pipeline: {e}")
        return set(), set(SHARD3_COUNTIES)

def configure_jefferson_pipeline():
    """Configure jefferson county A-lane (0/10 → 1/10 quick win)"""
    log("🎯 Configuring jefferson A-lane...")
    
    # Jefferson is completely failing (0/10) - likely not in pipeline at all
    # Need to add basic pipeline configuration
    
    try:
        client = httpx.Client(timeout=60)
        
        # Add jefferson to pipeline.counties with basic realauction + tax_deed setup
        pipeline_config = {
            "county_slug": "jefferson",
            "county_name": "Jefferson",
            "state": "FL", 
            "enabled": True,
            "foreclosure_platform": "realauction",
            "tax_deed_platform": "realauction",
            "foreclosure_url": "https://www.realauction.com/",
            "tax_deed_url": "https://www.realauction.com/",
            "scraper_config": {
                "use_authenticated": True,
                "update_frequency": "daily"
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Insert pipeline configuration
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties",
            headers=sb_headers(),
            json=pipeline_config
        )
        
        if response.status_code in [200, 201]:
            log("✅ Jefferson pipeline configured")
            return True
        else:
            log(f"❌ Failed to configure jefferson: {response.text}")
            return False
            
    except Exception as e:
        log(f"❌ Error configuring jefferson: {e}")
        return False

def check_multi_county_auctions():
    """Check auction counts in multi_county_auctions for our counties"""
    try:
        client = httpx.Client(timeout=60)
        
        results = {}
        for county in SHARD3_COUNTIES:
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?select=count&county=eq.{county}",
                headers=sb_headers()
            )
            
            if response.status_code == 200:
                count_data = response.json()
                # Extract count from response
                count = len(count_data) if isinstance(count_data, list) else 0
                results[county] = count
                log(f"{county}: {count} auctions in multi_county_auctions")
            else:
                log(f"❌ Failed to check {county} auctions")
                results[county] = 0
        
        return results
        
    except Exception as e:
        log(f"❌ Error checking auction counts: {e}")
        return {}

def check_verified_outcomes():
    """Check verified outcomes for each county (Letter B analysis)"""
    try:
        client = httpx.Client(timeout=60)
        
        # Check foreclosure_outcomes and tax_deed_outcomes for our counties
        for county in SHARD3_COUNTIES:
            log(f"Checking verified outcomes for {county}...")
            
            # Check foreclosure outcomes
            fc_response = client.get(
                f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?select=count&county=eq.{county}",
                headers=sb_headers()
            )
            
            # Check tax deed outcomes  
            td_response = client.get(
                f"{SUPABASE_URL}/rest/v1/tax_deed_outcomes?select=count&county=eq.{county}",
                headers=sb_headers()
            )
            
            fc_count = len(fc_response.json()) if fc_response.status_code == 200 else 0
            td_count = len(td_response.json()) if td_response.status_code == 200 else 0
            
            log(f"  {county}: {fc_count} FC outcomes, {td_count} TD outcomes")
            
            if fc_count == 0 and td_count == 0:
                log(f"  ⚠️ {county} has no verified outcomes - Letter B blocker")
        
        return True
        
    except Exception as e:
        log(f"❌ Error checking verified outcomes: {e}")
        return False

def run_verification_check():
    """Run verification for all SHARD-3 counties"""
    try:
        client = httpx.Client(timeout=120)  # Longer timeout for evaluations
        
        log("🔍 Running fresh evaluations for SHARD-3...")
        
        for county in SHARD3_COUNTIES:
            log(f"\nEvaluating {county}...")
            
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=sb_headers(),
                json={"county_slug_arg": county}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    passed = sum(1 for item in result if item.get('pass', False))
                    log(f"  ✅ {county}: {passed}/10 letters passing")
                    
                    # Show failing letters
                    failing = [item['letter'] for item in result if not item.get('pass', False)]
                    if failing:
                        log(f"     Failing: {', '.join(failing)}")
                else:
                    log(f"  ❌ {county}: No evaluation data")
            else:
                log(f"  ❌ {county}: Evaluation failed - {response.text}")
        
        return True
        
    except Exception as e:
        log(f"❌ Error in verification: {e}")
        return False

def main():
    """Main execution following brief priorities"""
    log("🚀 SHARD-3 Targeted Fixes Starting")
    log(f"Target counties: {', '.join(SHARD3_COUNTIES)}")
    
    # Step 1: Verify connection
    if not verify_connection():
        return False
    
    # Step 2: Check pipeline configuration
    log("\n📋 Checking pipeline configuration...")
    configured, missing = check_pipeline_counties()
    
    # Step 3: Quick win - configure jefferson if missing (0/10 → 1/10)
    if 'jefferson' in missing:
        log("\n🎯 PRIORITY: Configuring jefferson (0/10 → 1/10 quick win)")
        configure_jefferson_pipeline()
    
    # Step 4: Check auction data availability
    log("\n📊 Checking auction data availability...")
    auction_counts = check_multi_county_auctions()
    
    # Step 5: Analyze verified outcomes (Letter B blocker)
    log("\n🔍 Analyzing verified outcomes (Letter B)...")
    check_verified_outcomes()
    
    # Step 6: Run fresh verification
    log("\n✅ Running verification check...")
    run_verification_check()
    
    log(f"\n🏁 SHARD-3 analysis completed at {datetime.now().strftime('%H:%M:%S')}")
    log("See output above for specific fixes needed per county")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)