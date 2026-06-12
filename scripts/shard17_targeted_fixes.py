#!/usr/bin/env python3
"""
Shard 17 Gold Standard Targeted Fixes
charlotte, citrus, broward counties

Priority order based on CRITERION-PARALLEL PIVOT:
1. B - Verified outcomes via clerk sources (HIGH LEVERAGE)
2. E - Parcel linkage via property appraiser GIS 
3. C/D - Parity reconciliation
4. F - Tier1 sold amount verification
5. I/J - Property cards and deal thesis

SHIP-TO-MAIN mandate: Direct commits, no PRs, execute and verify live metrics
"""

import sys
import os
import json
import httpx
from datetime import datetime, timezone

# Add shared utilities to path
sys.path.append('./shared')

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

ASSIGNED_COUNTIES = ['charlotte', 'citrus', 'broward']

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def execute_sql(query, params=None):
    """Execute SQL via RPC call"""
    try:
        client = httpx.Client(timeout=120)  # Extended timeout for heavy queries
        
        payload = {"query": query}
        if params:
            payload["params"] = params
            
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/execute_sql",
            headers=sb_headers(),
            json=payload
        )
        
        if r.status_code == 200:
            return r.json()
        else:
            print(f"SQL Error: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"SQL Execution Error: {e}")
        return None

def verify_county_metrics(county_slug):
    """Get current metrics for a county using pencil_dod_evaluate_county"""
    try:
        client = httpx.Client(timeout=60)
        
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            return r.json()
        else:
            print(f"County evaluation error for {county_slug}: {r.status_code}")
            return None
    except Exception as e:
        print(f"Error evaluating {county_slug}: {e}")
        return None

class VerifiedOutcomesBuilder:
    """Priority Fix B: Build independent verified outcomes for clerk sources"""
    
    def __init__(self):
        self.counties_config = {
            'charlotte': {
                'clerk_url': 'https://www.charlotteclerk.com',
                'records_search': 'https://www.charlotteclerk.com/records/search',
                'foreclosure_platform': 'clerk_html',  # Need to verify
                'co_no': 9
            },
            'citrus': {
                'clerk_url': 'https://www.citrusclerk.org',
                'records_search': 'https://www.citrusclerk.org/records', 
                'foreclosure_platform': 'clerk_html',
                'co_no': 17
            },
            'broward': {
                'clerk_url': 'https://browardclerk.org',
                'records_search': 'https://browardclerk.org/records',
                'foreclosure_platform': 'realauction',  # Major county, likely standard
                'co_no': 11
            }
        }
    
    def discover_clerk_endpoints(self, county):
        """Discover actual clerk record search endpoints"""
        config = self.counties_config.get(county)
        if not config:
            return None
            
        print(f"Discovering clerk endpoints for {county}...")
        
        # Check if clerk has online records search
        try:
            client = httpx.Client(timeout=30, follow_redirects=True)
            r = client.get(config['clerk_url'])
            
            if r.status_code == 200:
                # Look for common patterns in clerk websites
                content = r.text.lower()
                if 'official records' in content or 'document search' in content:
                    print(f"✅ {county} clerk has online records")
                    return True
                else:
                    print(f"⚠️ {county} clerk website found but no clear records search")
                    return False
            else:
                print(f"❌ {county} clerk website not accessible")
                return False
                
        except Exception as e:
            print(f"Error checking {county} clerk: {e}")
            return False
    
    def build_outcomes_scraper(self, county):
        """Build or extend outcomes scraper for county"""
        print(f"Building verified outcomes scraper for {county}...")
        
        # For now, create a framework that can be extended
        # The issue notes that Duval has a working acclaim pipeline we can port
        
        scraper_config = {
            'county': county,
            'data_source': f'clerk_{county}:SHARD17-V1',
            'outcome_types': ['foreclosure', 'tax_deed'],
            'target_tables': ['foreclosure_outcomes', 'tax_deed_outcomes'],
            'verification_level': 'independent'
        }
        
        return scraper_config

class ParcelLinker:
    """Priority Fix E: Link auctions to parcel_id via property appraiser GIS"""
    
    def __init__(self):
        self.appraiser_endpoints = {
            'charlotte': {
                'base_url': 'https://www.ccappraiser.com',
                'search_url': 'https://www.ccappraiser.com/search',
                'gis_url': None  # To be discovered
            },
            'citrus': {
                'base_url': 'https://www.citruspa.org', 
                'search_url': 'https://www.citruspa.org/search',
                'gis_url': None
            },
            'broward': {
                'base_url': 'https://www.bcpa.net',
                'search_url': 'https://www.bcpa.net/search', 
                'gis_url': 'https://gis.bcpa.net'  # Major county likely has GIS
            }
        }
    
    def discover_gis_endpoints(self, county):
        """Discover ArcGIS REST endpoints for property data"""
        print(f"Discovering GIS endpoints for {county}...")
        
        appraiser = self.appraiser_endpoints.get(county, {})
        base_url = appraiser.get('base_url')
        
        if not base_url:
            return None
            
        # Common ArcGIS patterns to check
        potential_endpoints = [
            f"{base_url}/arcgis/rest/services",
            f"{base_url}/gis/arcgis/rest/services", 
            f"https://gis.{base_url.split('//')[1]}/arcgis/rest/services",
            f"https://maps.{base_url.split('//')[1]}/arcgis/rest/services"
        ]
        
        client = httpx.Client(timeout=30)
        for endpoint in potential_endpoints:
            try:
                r = client.get(endpoint)
                if r.status_code == 200 and 'services' in r.text.lower():
                    print(f"✅ Found GIS endpoint for {county}: {endpoint}")
                    return endpoint
            except:
                continue
                
        print(f"⚠️ No GIS endpoint found for {county}")
        return None
    
    def link_parcels_batch(self, county, batch_size=1000):
        """Link unlinked auctions to parcel_id in batches"""
        print(f"Linking parcels for {county} auctions...")
        
        # Get unlinked auctions for county
        query = """
        SELECT id, case_number, property_address, legal_description
        FROM multi_county_auctions 
        WHERE county = %s AND parcel_id IS NULL
        LIMIT %s
        """
        
        result = execute_sql(query, [county, batch_size])
        if not result:
            return 0
            
        print(f"Found {len(result)} unlinked auctions for {county}")
        
        # This would need actual GIS endpoint integration
        # For now, return count for tracking
        return len(result)

class ParityReconciler:
    """Priority Fix C/D: Improve parity matching rates"""
    
    def reconcile_county_parity(self, county):
        """Improve parity matching for county"""
        print(f"Reconciling parity for {county}...")
        
        # Check current parity rates
        query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN parity_status = 'matched_clean' THEN 1 END) as clean_matches,
            COUNT(CASE WHEN parity_status IN ('matched_clean', 'matched_divergent') THEN 1 END) as any_matches
        FROM multi_county_auctions 
        WHERE county = %s AND source_platform IS NOT NULL
        """
        
        result = execute_sql(query, [county])
        if result and len(result) > 0:
            row = result[0]
            total = row.get('total', 0)
            clean = row.get('clean_matches', 0)  
            any_match = row.get('any_matches', 0)
            
            clean_pct = (clean / total * 100) if total > 0 else 0
            any_pct = (any_match / total * 100) if total > 0 else 0
            
            print(f"{county} parity: {clean}/{total} clean ({clean_pct:.1f}%), {any_match}/{total} any ({any_pct:.1f}%)")
            
            return {
                'total': total,
                'clean_matches': clean,
                'any_matches': any_match,
                'clean_pct': clean_pct,
                'any_pct': any_pct
            }
        
        return None

def main():
    """Execute targeted fixes for shard 17 counties"""
    print("=== SHARD 17 GOLD STANDARD TARGETED FIXES ===")
    print(f"Counties: {', '.join(ASSIGNED_COUNTIES)}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY required")
        sys.exit(1)
    
    # Get baseline metrics for all counties
    baseline_metrics = {}
    print("\n=== BASELINE METRICS ===")
    for county in ASSIGNED_COUNTIES:
        metrics = verify_county_metrics(county)
        baseline_metrics[county] = metrics
        if metrics:
            pass_count = sum(1 for m in metrics if m.get('pass', False))
            print(f"{county}: {pass_count}/10 passing")
    
    # Initialize fix builders
    outcomes_builder = VerifiedOutcomesBuilder()
    parcel_linker = ParcelLinker()
    parity_reconciler = ParityReconciler()
    
    print("\n=== PRIORITY FIX B: VERIFIED OUTCOMES ===")
    for county in ASSIGNED_COUNTIES:
        outcomes_builder.discover_clerk_endpoints(county)
        scraper_config = outcomes_builder.build_outcomes_scraper(county)
        print(f"Created scraper config for {county}: {scraper_config['data_source']}")
    
    print("\n=== PRIORITY FIX E: PARCEL LINKAGE ===") 
    for county in ASSIGNED_COUNTIES:
        gis_endpoint = parcel_linker.discover_gis_endpoints(county)
        if gis_endpoint:
            linked_count = parcel_linker.link_parcels_batch(county)
            print(f"Would link {linked_count} parcels for {county}")
    
    print("\n=== PRIORITY FIX C/D: PARITY RECONCILIATION ===")
    for county in ASSIGNED_COUNTIES:
        parity_stats = parity_reconciler.reconcile_county_parity(county)
        if parity_stats:
            print(f"{county} needs parity improvement: C={parity_stats['clean_pct']:.1f}% D={parity_stats['any_pct']:.1f}%")
    
    print("\n=== SUMMARY ===")
    print("Created framework for shard 17 fixes. Next steps:")
    print("1. Implement actual clerk scraping endpoints")  
    print("2. Integrate with discovered GIS services")
    print("3. Run parity improvement algorithms")
    print("4. Schedule and wire new scrapers")
    print("5. Verify metrics movement via pencil_dod_evaluate_county")

if __name__ == "__main__":
    main()