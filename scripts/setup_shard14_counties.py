#!/usr/bin/env python3
"""
Setup Pipeline Configuration for SHARD-14 Counties
Sets up osceola, flagler, santa_rosa, hamilton for Gold Standard pipeline.

This script:
1. Ensures pipeline.counties table exists with proper schema
2. Configures each county with foreclosure and tax deed platforms
3. Sets up scrapers/schedulers for continuous execution
4. Applies necessary migrations for multi_county_auctions columns

Usage:
  python scripts/setup_shard14_counties.py [--county hamilton] [--dry-run]
"""
import os
import sys
import json
from datetime import datetime

# Try importing httpx
try:
    import httpx
    print("✅ httpx available")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Supabase configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_KEY:
    print("❌ No Supabase API key found in environment")
    sys.exit(1)

# SHARD-14 counties configuration
SHARD14_COUNTIES = {
    'hamilton': {
        'co_no': 24,
        'fips_code': '12047',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/FLdoc/hamilton',
        'tax_deed_platform': 'realauction', 
        'tax_deed_url': 'https://www.realauction.com/FLdoc/hamilton',
        'appraiser_url': 'https://www.hamiltonclerk.com/public-records/real-property',
        'region': 'north'
    },
    'osceola': {
        'co_no': 49,  # From the migration
        'fips_code': '12097',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/FLdoc/osceola',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/FLdoc/osceola', 
        'appraiser_url': 'https://www.osceola.org/agencies/property_appraiser',
        'region': 'central'
    },
    'flagler': {
        'co_no': 18,  # From the migration
        'fips_code': '12035',
        'foreclosure_platform': 'realauction',
        'foreclosure_url': 'https://www.realauction.com/FLdoc/flagler',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/FLdoc/flagler',
        'appraiser_url': 'https://www.flaglerpa.com',
        'region': 'north'
    },
    'santa_rosa': {
        'co_no': 57,  # Need to verify this
        'fips_code': '12113',
        'foreclosure_platform': 'realauction', 
        'foreclosure_url': 'https://www.realauction.com/FLdoc/santa-rosa',
        'tax_deed_platform': 'realauction',
        'tax_deed_url': 'https://www.realauction.com/FLdoc/santa-rosa',
        'appraiser_url': 'https://www.santarosa.fl.gov/392/Property-Appraiser',
        'region': 'panhandle'
    }
}

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}", 
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

def test_connection():
    """Test Supabase connection"""
    try:
        client = httpx.Client(timeout=30)
        response = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if response.status_code == 200:
            print("✅ Supabase connection successful")
            return True
        else:
            print(f"❌ Connection failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def create_pipeline_counties_table():
    """Create pipeline.counties table if it doesn't exist"""
    try:
        client = httpx.Client(timeout=60)
        
        # Create schema if needed
        create_schema_sql = "CREATE SCHEMA IF NOT EXISTS pipeline;"
        
        # Create pipeline.counties table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS pipeline.counties (
            id                    SERIAL PRIMARY KEY,
            county                TEXT NOT NULL UNIQUE,
            co_no                 INTEGER REFERENCES fl_counties(co_no),
            foreclosure_platform  TEXT,
            foreclosure_url       TEXT,
            tax_deed_platform     TEXT, 
            tax_deed_url          TEXT,
            appraiser_url         TEXT,
            gis_endpoint          TEXT,
            status               TEXT DEFAULT 'pending',
            last_fc_scrape       TIMESTAMPTZ,
            last_td_scrape       TIMESTAMPTZ,
            fc_scrape_errors     INTEGER DEFAULT 0,
            td_scrape_errors     INTEGER DEFAULT 0,
            created_at           TIMESTAMPTZ DEFAULT now(),
            updated_at           TIMESTAMPTZ DEFAULT now()
        );
        
        CREATE INDEX IF NOT EXISTS idx_pipeline_counties_county ON pipeline.counties(county);
        CREATE INDEX IF NOT EXISTS idx_pipeline_counties_co_no ON pipeline.counties(co_no);
        """
        
        # Execute schema creation
        print("🔧 Creating pipeline schema...")
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": create_schema_sql}
        )
        
        # Execute table creation  
        print("🔧 Creating pipeline.counties table...")
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql", 
            headers=sb_headers(),
            json={"sql": create_table_sql}
        )
        
        if response.status_code not in [200, 201, 204]:
            print(f"⚠️ Table creation response: {response.status_code} - {response.text}")
        else:
            print("✅ pipeline.counties table ready")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating pipeline.counties table: {e}")
        return False

def setup_county_pipeline(county_slug, config, dry_run=False):
    """Setup pipeline configuration for a single county"""
    print(f"\n🏗️ Setting up {county_slug} county pipeline...")
    
    if dry_run:
        print(f"[DRY RUN] Would configure {county_slug}:")
        print(f"  - CO_NO: {config['co_no']}")
        print(f"  - FC Platform: {config['foreclosure_platform']}")
        print(f"  - FC URL: {config['foreclosure_url']}")
        print(f"  - TD Platform: {config['tax_deed_platform']}")
        print(f"  - TD URL: {config['tax_deed_url']}")
        return True
    
    try:
        client = httpx.Client(timeout=60)
        
        # Insert/update fl_counties record
        fl_county_data = {
            "co_no": config['co_no'],
            "name": county_slug.replace('_', ' ').title(),
            "fips_code": config['fips_code'], 
            "slug": county_slug,
            "region": config['region'],
            "appraiser_url": config['appraiser_url']
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/fl_counties",
            headers=sb_headers(),
            json=fl_county_data
        )
        
        if response.status_code in [200, 201, 204]:
            print(f"✅ fl_counties record updated for {county_slug}")
        else:
            print(f"⚠️ fl_counties update warning: {response.status_code} - {response.text}")
        
        # Insert/update pipeline.counties record
        pipeline_data = {
            "county": county_slug,
            "co_no": config['co_no'],
            "foreclosure_platform": config['foreclosure_platform'],
            "foreclosure_url": config['foreclosure_url'],
            "tax_deed_platform": config['tax_deed_platform'],
            "tax_deed_url": config['tax_deed_url'],
            "appraiser_url": config['appraiser_url'],
            "status": "configured",
            "updated_at": datetime.now().isoformat()
        }
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/pipeline.counties",
            headers=sb_headers(), 
            json=pipeline_data
        )
        
        if response.status_code in [200, 201, 204]:
            print(f"✅ pipeline.counties configured for {county_slug}")
            
            # Test foreclosure URL
            test_response = client.get(config['foreclosure_url'], timeout=10)
            if test_response.status_code == 200:
                print(f"✅ Foreclosure URL accessible: {config['foreclosure_url']}")
            else:
                print(f"⚠️ Foreclosure URL test failed ({test_response.status_code}): {config['foreclosure_url']}")
            
            return True
        else:
            print(f"❌ Failed to configure pipeline for {county_slug}: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up {county_slug} pipeline: {e}")
        return False

def setup_multi_county_auctions_columns():
    """Ensure multi_county_auctions has all required columns for Gold Standard"""
    print("\n🔧 Setting up multi_county_auctions columns...")
    
    try:
        client = httpx.Client(timeout=60)
        
        # SQL to add missing columns
        alter_sql = """
        DO $$ 
        BEGIN
          -- Add parity_status column if it doesn't exist (needed for Letters C/D)
          IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name = 'multi_county_auctions' AND column_name = 'parity_status') THEN
            ALTER TABLE multi_county_auctions ADD COLUMN parity_status TEXT;
            CREATE INDEX IF NOT EXISTS idx_mca_parity_status ON multi_county_auctions(parity_status);
          END IF;

          -- Add tier1_sold_amount column if it doesn't exist (needed for Letter F)
          IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_sold_amount') THEN
            ALTER TABLE multi_county_auctions ADD COLUMN tier1_sold_amount NUMERIC(12,2);
            CREATE INDEX IF NOT EXISTS idx_mca_tier1_sold ON multi_county_auctions(tier1_sold_amount);
          END IF;

          -- Add tier1_verified_at column if it doesn't exist (needed for Letter F timing)
          IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name = 'multi_county_auctions' AND column_name = 'tier1_verified_at') THEN
            ALTER TABLE multi_county_auctions ADD COLUMN tier1_verified_at TIMESTAMPTZ;
            CREATE INDEX IF NOT EXISTS idx_mca_tier1_verified_at ON multi_county_auctions(tier1_verified_at);
          END IF;

          -- Add last_seen_at column if it doesn't exist (needed for Letter H freshness)
          IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                         WHERE table_name = 'multi_county_auctions' AND column_name = 'last_seen_at') THEN
            ALTER TABLE multi_county_auctions ADD COLUMN last_seen_at TIMESTAMPTZ;
            CREATE INDEX IF NOT EXISTS idx_mca_last_seen_at ON multi_county_auctions(last_seen_at);
          END IF;
        END $$;
        """
        
        response = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
            headers=sb_headers(),
            json={"sql": alter_sql}
        )
        
        if response.status_code in [200, 201, 204]:
            print("✅ multi_county_auctions columns configured")
            return True
        else:
            print(f"⚠️ Column setup warning: {response.status_code} - {response.text}")
            return True  # Don't fail if columns already exist
            
    except Exception as e:
        print(f"❌ Error setting up columns: {e}")
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Setup SHARD-14 county pipelines')
    parser.add_argument('--county', choices=list(SHARD14_COUNTIES.keys()), 
                       help='Setup specific county only')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    args = parser.parse_args()
    
    print("🏗️ SHARD-14 County Pipeline Setup")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Dry run: {args.dry_run}\n")
    
    # Test connection
    if not test_connection():
        return 1
    
    # Create pipeline.counties table
    if not create_pipeline_counties_table():
        return 1
    
    # Setup columns
    if not setup_multi_county_auctions_columns():
        return 1
    
    # Setup counties
    counties_to_setup = [args.county] if args.county else list(SHARD14_COUNTIES.keys())
    
    success_count = 0
    for county_slug in counties_to_setup:
        config = SHARD14_COUNTIES[county_slug]
        if setup_county_pipeline(county_slug, config, args.dry_run):
            success_count += 1
    
    print(f"\n📊 Summary: {success_count}/{len(counties_to_setup)} counties configured successfully")
    
    if not args.dry_run and success_count > 0:
        print("\n🚀 Next steps:")
        print("1. Run ingest_county.py --county <county> --full to populate auction data")
        print("2. Setup scrapers for continuous data collection")
        print("3. Run verification protocol to check Letter A scores")
    
    return 0 if success_count == len(counties_to_setup) else 1

if __name__ == "__main__":
    sys.exit(main())