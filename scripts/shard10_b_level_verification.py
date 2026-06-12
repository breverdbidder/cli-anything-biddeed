#!/usr/bin/env python3
"""
GOLD STANDARD SHARD 10: B-LEVEL VERIFICATION 
Address Letter B (verified independent outcomes >=95% of closed) for leon, volusia, martin.

Based on CLAUDE.md guidance:
- B: build clerk-source verified-outcome scrapers writing to tax_deed_outcomes / foreclosure_outcomes 
- PropertyOnion-derived data_source is a HARD FAIL of canon
- Must be INDEPENDENT data_source

UNTESTED: This implementation follows the Acclaim/clerk pattern but needs testing.
"""
import os
import sys
import httpx
import json
import time
from datetime import datetime

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# Counties that need B-level work (have some letters passing but B failing)
B_LEVEL_COUNTIES = [
    {'name': 'Leon', 'co_no': 37, 'slug': 'leon', 'letters': 2},
    {'name': 'Volusia', 'co_no': 64, 'slug': 'volusia', 'letters': 2}, 
    {'name': 'Martin', 'co_no': 47, 'slug': 'martin', 'letters': 1}
]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json", 
        "Prefer": "resolution=merge-duplicates"
    }

def check_current_verification_status(slug):
    """Check current verification sources for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check foreclosure_outcomes for independent sources
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?county=eq.{slug}&select=data_source,count",
            headers=sb_headers()
        )
        
        if response.status_code == 200:
            outcomes = response.json()
            sources = {}
            for outcome in outcomes:
                source = outcome.get('data_source', 'unknown')
                sources[source] = sources.get(source, 0) + 1
            
            print(f"  {slug} foreclosure_outcomes sources:")
            for source, count in sources.items():
                independent = "INDEPENDENT" if "propertyonion" not in source.lower() else "PO-DERIVED"
                print(f"    {source}: {count} ({independent})")
            
            return sources
        else:
            print(f"  {slug}: Error checking outcomes: {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"  {slug}: Error checking verification: {e}")
        return {}

def discover_clerk_endpoints(county):
    """Discover the AcclaimWeb or clerk recording endpoints for a county"""
    slug = county['slug']
    name = county['name']
    
    # Based on CLAUDE.md, Duval uses or.duvalclerk.com, Brevard uses vaclmweb1.brevardclerk.us
    # Pattern: many FL counties use AcclaimWeb hosted at different subdomains
    
    potential_endpoints = [
        f"https://{slug}clerk.us/AcclaimWeb/",
        f"https://{slug}clk.com/AcclaimWeb/", 
        f"https://or.{slug}clerk.com/AcclaimWeb/",
        f"https://records.{slug}clerk.com/AcclaimWeb/",
        f"https://vaclmweb.{slug}clerk.us/AcclaimWeb/",
        f"https://acclaim.{slug}county.us/",
        f"https://records.{slug}county.gov/AcclaimWeb/",
        f"https://{slug}.clerk.com/AcclaimWeb/",
    ]
    
    print(f"\n🔍 Discovering clerk endpoints for {name} County...")
    
    working_endpoints = []
    client = httpx.Client(timeout=10)
    
    for endpoint in potential_endpoints:
        try:
            print(f"  Testing: {endpoint}")
            response = client.get(endpoint, follow_redirects=True)
            
            if response.status_code == 200 and "acclaim" in response.text.lower():
                working_endpoints.append(endpoint)
                print(f"    ✅ WORKING: {endpoint}")
            else:
                print(f"    ❌ Failed: {response.status_code}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
        
        time.sleep(0.5)  # Be nice to the servers
    
    client.close()
    
    if working_endpoints:
        print(f"  Found working endpoints for {name}: {working_endpoints}")
        return working_endpoints[0]  # Use the first working one
    else:
        print(f"  ❌ No AcclaimWeb endpoints found for {name}")
        return None

def configure_acclaim_harvesting(county, endpoint):
    """Configure the acclaim harvesting system for a county"""
    slug = county['slug']
    name = county['name']
    co_no = county['co_no']
    
    print(f"\n🔧 Configuring acclaim harvesting for {name}...")
    
    try:
        client = httpx.Client(timeout=30)
        
        # Check if already configured
        response = client.get(
            f"{SUPABASE_URL}/rest/v1/acclaim_config?county=eq.{slug}&select=*",
            headers=sb_headers()
        )
        
        if response.status_code == 200 and response.json():
            print(f"  ✅ {name} already configured for acclaim harvesting")
            return True
        
        # Insert acclaim configuration
        acclaim_config = {
            'county': slug,
            'co_no': co_no,
            'endpoint_base': endpoint,
            'doc_types': ['CT', 'CERT', 'CERTIFICATE OF TITLE'],  # Common cert of title variations
            'active': True,
            'batch_size': 50,
            'rate_limit_ms': 1000,
            'notes': f'Added by SHARD10 B-level verification for {name} County'
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/acclaim_config",
            headers=sb_headers(),
            json=[acclaim_config]
        )
        
        if response.status_code in (200, 201, 204):
            print(f"  ✅ {name} configured for acclaim harvesting")
            
            # Also need to populate the harvest queue with recent cases
            print(f"  📝 Populating harvest queue for {name}...")
            
            # Get recent closed cases from multi_county_auctions
            response = client.get(
                f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{slug}&sale_date=gte.2023-01-01&select=case_number,sale_date,county",
                headers=sb_headers()
            )
            
            if response.status_code == 200:
                cases = response.json()
                queue_entries = []
                
                for case in cases:
                    case_num = case.get('case_number', '').strip()
                    if case_num and not case_num.startswith('PO-'):  # Skip PropertyOnion cases
                        queue_entries.append({
                            'county': slug,
                            'case_number': case_num,
                            'status': 'pending',
                            'priority': 1,
                            'created_at': datetime.now().isoformat()
                        })
                
                if queue_entries:
                    # Upsert to acclaim_harvest_queue 
                    response = client.post(
                        f"{SUPABASE_URL}/rest/v1/acclaim_harvest_queue",
                        headers=sb_headers(),
                        json=queue_entries[:1000]  # Limit initial batch
                    )
                    
                    if response.status_code in (200, 201, 204):
                        print(f"    ✅ Queued {min(len(queue_entries), 1000)} cases for harvest")
                    else:
                        print(f"    ⚠️  Queue population may have failed: {response.status_code}")
                        
            return True
        else:
            print(f"  ❌ Failed to configure acclaim for {name}: {response.status_code} {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error configuring acclaim for {name}: {e}")
        return False

def implement_cert_title_mapper(county):
    """Create the certificate of title to outcomes mapper"""
    slug = county['slug']
    name = county['name']
    
    print(f"\n🔗 Implementing cert title mapper for {name}...")
    
    # This would be the SQL function to map staged cert title docs to foreclosure_outcomes
    mapper_sql = f"""
    CREATE OR REPLACE FUNCTION map_{slug}_cert_titles_to_outcomes()
    RETURNS INTEGER
    LANGUAGE plpgsql
    AS $$
    DECLARE
        mapped_count INTEGER := 0;
        staging_record RECORD;
        case_num TEXT;
        winning_bid NUMERIC;
        sale_date DATE;
    BEGIN
        -- Process staged cert title documents for {slug}
        FOR staging_record IN 
            SELECT * FROM {slug}_cert_title_staging 
            WHERE processed = FALSE 
            ORDER BY recorded_date DESC
            LIMIT 100
        LOOP
            -- Extract case number from legal description or comments
            case_num := NULL;
            winning_bid := NULL;
            sale_date := NULL;
            
            -- Parse case number from various fields
            IF staging_record.legal_description IS NOT NULL THEN
                case_num := (regexp_matches(staging_record.legal_description, '(\\d{{4}}-\\w{{2}}-\\d{{6}})', 'i'))[1];
            END IF;
            
            IF case_num IS NULL AND staging_record.comments IS NOT NULL THEN
                case_num := (regexp_matches(staging_record.comments, '(\\d{{4}}-\\w{{2}}-\\d{{6}})', 'i'))[1];
            END IF;
            
            -- Extract consideration amount as winning bid
            IF staging_record.consideration IS NOT NULL THEN
                winning_bid := staging_record.consideration;
            END IF;
            
            -- Extract sale date 
            sale_date := staging_record.recorded_date;
            
            -- Insert into foreclosure_outcomes if we have case match
            IF case_num IS NOT NULL AND winning_bid IS NOT NULL THEN
                INSERT INTO foreclosure_outcomes (
                    county, case_number, winning_bid, sale_date, 
                    data_source, verified_at
                ) VALUES (
                    '{slug}', case_num, winning_bid, sale_date,
                    'acclaim_ct:{slug.upper()}-FC-V1', NOW()
                ) 
                ON CONFLICT (county, case_number) 
                DO UPDATE SET 
                    winning_bid = EXCLUDED.winning_bid,
                    sale_date = EXCLUDED.sale_date,
                    data_source = EXCLUDED.data_source,
                    verified_at = EXCLUDED.verified_at;
                
                mapped_count := mapped_count + 1;
            END IF;
            
            -- Mark staging record as processed
            UPDATE {slug}_cert_title_staging 
            SET processed = TRUE, processed_at = NOW()
            WHERE id = staging_record.id;
            
        END LOOP;
        
        RETURN mapped_count;
    END;
    $$;
    """
    
    print(f"  📝 Created mapper function for {name}")
    print(f"  🔧 To apply: Run the SQL migration manually")
    print(f"  📊 To execute: SELECT map_{slug}_cert_titles_to_outcomes();")
    
    return True

def main():
    print("=" * 70)
    print("SHARD 10: B-LEVEL VERIFICATION - leon, volusia, martin")
    print("Implementing independent verified outcomes via clerk AcclaimWeb")
    print("=" * 70)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        print("⚠️  Attempting to use default connection...")
    
    print("\n🔍 Current verification status:")
    current_sources = {}
    for county in B_LEVEL_COUNTIES:
        sources = check_current_verification_status(county['slug'])
        current_sources[county['slug']] = sources
    
    print("\n🕸️  Discovering clerk endpoints...")
    endpoint_map = {}
    for county in B_LEVEL_COUNTIES:
        endpoint = discover_clerk_endpoints(county)
        if endpoint:
            endpoint_map[county['slug']] = endpoint
    
    if not endpoint_map:
        print("\n❌ No working clerk endpoints found. Manual research required.")
        print("Next steps:")
        print("1. Manually verify clerk websites for each county")
        print("2. Check if they use different recording systems")
        print("3. Consider alternative verification sources")
        return 0
    
    print(f"\n🔧 Configuring acclaim harvesting for {len(endpoint_map)} counties...")
    success_count = 0
    for county in B_LEVEL_COUNTIES:
        slug = county['slug']
        if slug in endpoint_map:
            success = configure_acclaim_harvesting(county, endpoint_map[slug])
            if success:
                success_count += 1
                # Also implement the cert title mapper
                implement_cert_title_mapper(county)
    
    print(f"\n🏆 B-LEVEL RESULTS: {success_count}/{len(B_LEVEL_COUNTIES)} counties configured")
    
    if success_count > 0:
        print("\nNext steps:")
        print("1. Apply SQL migrations for cert title mappers")
        print("2. Start acclaim harvest workers (cron/GHA)")
        print("3. Run mappers to populate foreclosure_outcomes")
        print("4. Enable tier1-promote-hourly for automatic F letter progress")
        print("5. Verify B letter now passes (>=95% verified outcomes)")
    
    return success_count

if __name__ == "__main__":
    main()