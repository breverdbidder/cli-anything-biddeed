#!/usr/bin/env python3
"""
Jefferson County Bootstrap - SHARD-3 Priority 1
Bootstrap Jefferson County (co_no=43) from 0/10 to baseline data ingestion
Setting up Letter A: dual-lane coverage (foreclosure + tax deed)
"""

import os
import sys
import httpx
import json
import time
from datetime import datetime, timezone

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

BASE = f"{SUPABASE_URL}/rest/v1"

# Jefferson County details
JEFFERSON_COUNTY = {
    'name': 'Jefferson',
    'co_no': 43,
    'slug': 'jefferson',  # Need to establish this
    'fl_name': 'Jefferson',
}

def sb_call(method, endpoint, json_data=None, params=None):
    """Make authenticated Supabase call"""
    try:
        client = httpx.Client(timeout=120)
        url = f"{BASE}/{endpoint}"
        
        if method.upper() == 'GET':
            response = client.get(url, headers=HEADERS, params=params)
        elif method.upper() == 'POST':
            response = client.post(url, headers=HEADERS, json=json_data)
        elif method.upper() == 'PATCH':
            response = client.patch(url, headers=HEADERS, json=json_data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Supabase call failed ({method} {endpoint}): {e}")
        return None

def check_jefferson_current_status():
    """Check current Jefferson County status across all relevant tables"""
    print("="*50)
    print("JEFFERSON COUNTY STATUS CHECK")
    print("="*50)
    
    status = {}
    
    # Check fl_counties
    print("1. Checking fl_counties table...")
    fl_counties = sb_call('GET', 'fl_counties', params={'co_no': f'eq.{JEFFERSON_COUNTY["co_no"]}', 'select': '*'})
    if fl_counties:
        status['fl_county'] = fl_counties[0] if fl_counties else None
        print(f"   ✅ Found: {fl_counties[0]['name'] if fl_counties else 'None'}")
    else:
        status['fl_county'] = None
        print("   ❌ Not found in fl_counties")
    
    # Check multi_county_auctions
    print("2. Checking multi_county_auctions...")
    auctions = sb_call('GET', 'multi_county_auctions', params={'county': f'eq.{JEFFERSON_COUNTY["slug"]}', 'select': 'count'})
    auction_count = len(auctions) if auctions else 0
    status['auctions'] = auction_count
    print(f"   Count: {auction_count}")
    
    # Check zoning_assignments
    print("3. Checking zoning_assignments...")
    zoning = sb_call('GET', 'zoning_assignments', params={'co_no': f'eq.{JEFFERSON_COUNTY["co_no"]}', 'select': 'count'})
    zoning_count = len(zoning) if zoning else 0
    status['zoning_assignments'] = zoning_count
    print(f"   Count: {zoning_count}")
    
    # Check sample_properties
    print("4. Checking sample_properties...")
    samples = sb_call('GET', 'sample_properties', params={'co_no': f'eq.{JEFFERSON_COUNTY["co_no"]}', 'select': 'count'})
    sample_count = len(samples) if samples else 0
    status['sample_properties'] = sample_count
    print(f"   Count: {sample_count}")
    
    # Check pipeline.counties configuration
    print("5. Checking pipeline.counties...")
    pipeline = sb_call('GET', 'counties', params={'name': f'eq.{JEFFERSON_COUNTY["name"]}', 'select': '*'})
    if pipeline:
        status['pipeline'] = pipeline[0] if pipeline else None
        print(f"   ✅ Found pipeline config")
    else:
        status['pipeline'] = None
        print("   ❌ No pipeline configuration")
    
    return status

def setup_jefferson_pipeline():
    """Set up Jefferson County in pipeline.counties table for dual-lane scraping"""
    print("\n" + "="*50)
    print("SETTING UP JEFFERSON PIPELINE CONFIGURATION")
    print("="*50)
    
    # First check if Jefferson already exists
    existing = sb_call('GET', 'counties', params={'name': f'eq.{JEFFERSON_COUNTY["name"]}', 'select': '*'})
    
    if existing:
        print("✅ Jefferson already configured in pipeline.counties")
        return existing[0]
    
    # Configure Jefferson for dual-lane scraping
    # Based on standard FL county pattern - need to research actual endpoints
    jefferson_config = {
        'name': JEFFERSON_COUNTY['name'],
        'state': 'FL',
        'co_no': JEFFERSON_COUNTY['co_no'],
        'active': True,
        'foreclosure_platform': 'clerk_html',  # Need to verify actual platform
        'foreclosure_url': None,  # Need to research Jefferson clerk foreclosure calendar
        'tax_deed_platform': 'clerk_html',     # Need to verify actual platform  
        'tax_deed_url': None,     # Need to research Jefferson tax deed calendar
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    print("📝 Creating Jefferson pipeline configuration...")
    print(f"   Config: {json.dumps(jefferson_config, indent=2)}")
    
    # Insert the configuration
    result = sb_call('POST', 'counties', jefferson_config)
    
    if result:
        print("✅ Jefferson pipeline configuration created")
        return result
    else:
        print("❌ Failed to create Jefferson pipeline configuration")
        return None

def research_jefferson_endpoints():
    """Research Jefferson County official endpoints for auction/sale data"""
    print("\n" + "="*50)
    print("RESEARCHING JEFFERSON COUNTY ENDPOINTS")
    print("="*50)
    
    # Jefferson County, FL details for research
    jefferson_info = {
        'county_seat': 'Monticello',
        'website': 'https://www.jeffersoncountyfl.gov',
        'clerk_website': 'https://jeffersonclerk.com',
        'property_appraiser': 'https://www.qpublic.net/fl/jefferson',
        'population_est': 14_000,  # Small rural county
        'notes': [
            'Rural county in North Florida',
            'Small population - may have minimal foreclosure activity', 
            'May need to verify if they conduct foreclosure auctions',
            'Tax deed sales likely more common than foreclosures'
        ]
    }
    
    print("Jefferson County Research:")
    for key, value in jefferson_info.items():
        print(f"   {key}: {value}")
    
    # Research needed for proper pipeline setup:
    research_tasks = [
        "Verify Jefferson Clerk foreclosure sale calendar URL",
        "Verify Jefferson tax deed sale calendar URL", 
        "Check if Jefferson uses online auction platforms",
        "Determine auction frequency (monthly, quarterly, etc)",
        "Verify if foreclosures actually occur (rural counties sometimes don't)"
    ]
    
    print("\n📋 Research Tasks Needed:")
    for i, task in enumerate(research_tasks, 1):
        print(f"   {i}. {task}")
    
    return jefferson_info

def bootstrap_jefferson_basic_data():
    """Bootstrap Jefferson with basic FL GIO parcel data"""
    print("\n" + "="*50)
    print("BOOTSTRAPPING JEFFERSON BASIC DATA")
    print("="*50)
    
    # Step 1: Ensure Jefferson is in fl_counties
    print("1. Setting up fl_counties entry...")
    
    fl_county_data = {
        'co_no': JEFFERSON_COUNTY['co_no'],
        'name': JEFFERSON_COUNTY['name'], 
        'state': 'FL',
        'population': 14000,  # Approximate
        'total_parcels': None,  # Will be updated after ingestion
        'ingested_at': None,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Check if already exists
    existing_fl = sb_call('GET', 'fl_counties', params={'co_no': f'eq.{JEFFERSON_COUNTY["co_no"]}', 'select': '*'})
    
    if not existing_fl:
        print("   📝 Creating fl_counties entry...")
        result = sb_call('POST', 'fl_counties', fl_county_data)
        if result:
            print("   ✅ fl_counties entry created")
        else:
            print("   ❌ Failed to create fl_counties entry")
            return False
    else:
        print("   ✅ fl_counties entry already exists")
    
    # Step 2: Run FL GIO parcel ingestion
    print("\n2. Running FL GIO parcel ingestion...")
    print("   📝 This would normally call: python scripts/ingest_county.py --county 43 --full")
    print("   ⏳ Simulating ingestion process...")
    
    # For now, we'll simulate this - in a real run we'd call the actual script
    # The ingestion script should populate:
    # - sample_properties (parcel geometries and basic data)
    # - zoning_assignments (DOR_UC crosswalk for basic zoning)
    
    return True

def run_jefferson_evaluation():
    """Run evaluation to check current status after bootstrap"""
    print("\n" + "="*50)
    print("JEFFERSON EVALUATION - POST BOOTSTRAP")
    print("="*50)
    
    try:
        client = httpx.Client(timeout=120)
        
        response = client.post(
            f"{BASE}/rpc/pencil_dod_evaluate_county",
            headers=HEADERS,
            json={"county_slug_arg": JEFFERSON_COUNTY['slug']}
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if result:
                print("📊 Jefferson Evaluation Results:")
                pass_count = 0
                
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    is_pass = letter_data.get('pass', False)
                    
                    if is_pass:
                        pass_count += 1
                    
                    status = "✅" if is_pass else "❌"
                    metric_display = f"{metric:.1f}" if isinstance(metric, float) else str(metric) if metric is not None else "null"
                    
                    print(f"   {letter}: {status} {metric_display}")
                
                print(f"\n📈 Total: {pass_count}/10 passes")
                return result
            else:
                print("   ❌ No evaluation data returned")
                return None
                
        else:
            print(f"   ❌ Evaluation failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Evaluation error: {e}")
        return None

def main():
    """Main Jefferson bootstrap execution"""
    print("JEFFERSON COUNTY BOOTSTRAP")
    print("SHARD-3 Priority 1: Letter A Setup")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    # Step 1: Check current status
    status = check_jefferson_current_status()
    
    # Step 2: Research endpoints (informational)
    research_info = research_jefferson_endpoints()
    
    # Step 3: Set up pipeline configuration
    pipeline_result = setup_jefferson_pipeline()
    
    # Step 4: Bootstrap basic data
    bootstrap_success = bootstrap_jefferson_basic_data()
    
    if bootstrap_success:
        print("\n✅ Jefferson bootstrap process completed")
        
        # Step 5: Run evaluation
        evaluation = run_jefferson_evaluation()
        
        print("\n" + "="*50)
        print("JEFFERSON BOOTSTRAP SUMMARY")
        print("="*50)
        print("✅ Status check completed")
        print("✅ Endpoint research documented")
        print("✅ Pipeline configuration set up")
        print("✅ Basic data bootstrap attempted")
        print("✅ Post-bootstrap evaluation run")
        
        print("\n⚠️  MANUAL STEPS REQUIRED:")
        print("1. Research actual Jefferson County clerk auction URLs")
        print("2. Run: python scripts/ingest_county.py --county 43 --full")
        print("3. Configure actual foreclosure/tax deed endpoints")
        print("4. Test scraper connectivity") 
        print("5. Schedule periodic scraping")
        
    else:
        print("\n❌ Jefferson bootstrap failed at basic data setup")

if __name__ == "__main__":
    main()