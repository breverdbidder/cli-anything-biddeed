#!/usr/bin/env python3
"""
GOLD STANDARD WAVE2-SHARD-7 Autonomous Session
Counties: alachua, gilchrist, miami_dade, walton, gadsden, lafayette, wakulla

Ship-to-main mandate: Work directly on main branch, commit frequently
6-hour budget: Prioritize highest-leverage failing letters
"""
import os
import sys
import json
import subprocess
from datetime import datetime
import httpx

# Supabase connection
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

# My assigned counties for this shard (from fl_counties_manifest.yml)
SHARD_COUNTIES = [
    {'name': 'Alachua', 'co_no': 11, 'slug': 'alachua'},
    {'name': 'Gilchrist', 'co_no': 31, 'slug': 'gilchrist'},
    {'name': 'Miami-Dade', 'co_no': 23, 'slug': 'miami_dade'},
    {'name': 'Walton', 'co_no': 76, 'slug': 'walton'},
    {'name': 'Gadsden', 'co_no': 30, 'slug': 'gadsden'},
    {'name': 'Lafayette', 'co_no': 44, 'slug': 'lafayette'},
    {'name': 'Wakulla', 'co_no': 75, 'slug': 'wakulla'}
]

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def test_supabase_connection():
    """Verify we can connect to Supabase"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(f"{SUPABASE_URL}/rest/v1/fl_counties?select=count&limit=1", headers=sb_headers())
        if r.status_code == 200:
            print("✅ Supabase connection verified")
            return True
        else:
            print(f"❌ Supabase connection failed: {r.status_code} - {r.text}")
            return False
    except Exception as e:
        print(f"❌ Supabase connection error: {e}")
        return False

def evaluate_county(county_slug):
    """Run pencil_dod_evaluate_county for a specific county"""
    try:
        client = httpx.Client(timeout=60)
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            return result
        else:
            print(f"❌ Failed to evaluate county {county_slug}: {r.status_code} - {r.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return None

def get_county_pipeline_status(county_slug):
    """Check pipeline configuration for a county"""
    try:
        client = httpx.Client(timeout=30)
        
        # Check if county exists in pipeline.counties
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/pipeline_counties?county_slug=eq.{county_slug}&select=*",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            results = r.json()
            return results[0] if results else None
        else:
            print(f"❌ Failed to get pipeline status for {county_slug}: {r.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting pipeline status for {county_slug}: {e}")
        return None

def check_auction_data(county_slug):
    """Check if county has auction data in multi_county_auctions"""
    try:
        client = httpx.Client(timeout=30)
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/multi_county_auctions?county=eq.{county_slug}&select=count",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            count = len(r.json())
            return count
        else:
            print(f"❌ Failed to get auction count for {county_slug}")
            return 0
            
    except Exception as e:
        print(f"❌ Error getting auction count for {county_slug}: {e}")
        return 0

def run_county_ingestion(co_no, name):
    """Run county ingestion for counties with no data"""
    print(f"\n📥 Starting ingestion for {name} (CO_NO={co_no})...")
    
    try:
        # First count parcels
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no)
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Count failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Count completed for {name}")
        print(result.stdout)
        
        # Then full ingestion
        print(f"📦 Starting full ingestion for {name}...")
        result = subprocess.run([
            'python3', 'scripts/ingest_county.py', '--county', str(co_no), '--full'
        ], capture_output=True, text=True, timeout=3600)
        
        if result.returncode != 0:
            print(f"❌ Full ingestion failed for {name}: {result.stderr}")
            return False
        
        print(f"✅ Full ingestion completed for {name}")
        print(result.stdout)
        return True
        
    except subprocess.TimeoutExpired:
        print(f"⏰ Ingestion timed out for {name}")
        return False
    except Exception as e:
        print(f"❌ Error running ingestion for {name}: {e}")
        return False

def analyze_county_priorities():
    """Analyze all assigned counties and determine priority work"""
    print("="*80)
    print("WAVE2-SHARD-7 COUNTY ANALYSIS")
    print("="*80)
    
    county_analysis = []
    
    for county in SHARD_COUNTIES:
        slug = county['slug']
        name = county['name']
        co_no = county['co_no']
        
        print(f"\n🔍 Analyzing {name} ({slug})...")
        
        # Get current evaluation
        evaluation = evaluate_county(slug)
        pipeline_status = get_county_pipeline_status(slug)
        auction_count = check_auction_data(slug)
        
        analysis = {
            'county': county,
            'evaluation': evaluation,
            'pipeline_status': pipeline_status,
            'auction_count': auction_count,
            'needs_ingestion': auction_count == 0,
            'priority_score': 0
        }
        
        # Calculate priority score based on current status and volume
        if evaluation:
            pass_count = sum(1 for letter in evaluation if letter.get('pass', False))
            analysis['pass_count'] = pass_count
            analysis['priority_score'] = auction_count / 1000 + (10 - pass_count)  # Volume + gaps
        else:
            analysis['pass_count'] = 0
            analysis['priority_score'] = 1000 if auction_count == 0 else auction_count / 1000
        
        county_analysis.append(analysis)
        
        # Print summary
        if evaluation:
            print(f"  Current: {analysis['pass_count']}/10 pass")
            for letter in evaluation:
                status = "✅" if letter.get('pass', False) else "❌"
                metric = letter.get('metric', 'N/A')
                print(f"    {letter.get('letter', '?')}: {status} {metric}")
        else:
            print(f"  ❌ No evaluation data available")
        
        print(f"  Auction count: {auction_count:,}")
        print(f"  Pipeline configured: {pipeline_status is not None}")
        print(f"  Priority score: {analysis['priority_score']:.1f}")
    
    # Sort by priority score (highest first)
    county_analysis.sort(key=lambda x: x['priority_score'], reverse=True)
    
    print(f"\n📊 PRIORITY RANKING:")
    for i, analysis in enumerate(county_analysis, 1):
        county = analysis['county']
        print(f"  {i}. {county['name']:15s} | "
              f"Pass: {analysis['pass_count']:2d}/10 | "
              f"Auctions: {analysis['auction_count']:>8,} | "
              f"Score: {analysis['priority_score']:>6.1f}")
    
    return county_analysis

def work_letter_b_verified_outcomes(county_slug):
    """Work on Letter B - verified independent outcomes"""
    print(f"\n🔍 Working on Letter B (verified outcomes) for {county_slug}...")
    
    # Check if we have a verified outcomes scraper for this county
    # Letter B requires INDEPENDENT data_source (not PropertyOnion-derived)
    try:
        client = httpx.Client(timeout=30)
        
        # Check current outcomes for this county
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/tax_deed_outcomes?county=eq.{county_slug}&select=count,data_source",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            outcomes = r.json()
            print(f"  Current tax_deed_outcomes: {len(outcomes)}")
            data_sources = set(o.get('data_source', 'unknown') for o in outcomes)
            print(f"  Data sources: {data_sources}")
        
        r = client.get(
            f"{SUPABASE_URL}/rest/v1/foreclosure_outcomes?county=eq.{county_slug}&select=count,data_source",
            headers=sb_headers()
        )
        
        if r.status_code == 200:
            outcomes = r.json()
            print(f"  Current foreclosure_outcomes: {len(outcomes)}")
            data_sources = set(o.get('data_source', 'unknown') for o in outcomes)
            print(f"  Data sources: {data_sources}")
        
        # For now, log this as needing manual scraper setup
        print(f"  📋 Letter B for {county_slug} requires clerk-source outcome scraper")
        return False
        
    except Exception as e:
        print(f"❌ Error checking Letter B for {county_slug}: {e}")
        return False

def work_letter_c_d_parity(county_slug):
    """Work on Letter C/D - parity clean/any"""
    print(f"\n🔍 Working on Letter C/D (parity) for {county_slug}...")
    
    try:
        # Run customized SHARD-7 parity improvement script
        result = subprocess.run([
            'python3', 'scripts/wave2_shard7_parity_improvements.py', '--county', county_slug
        ], capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            print(f"✅ Parity improvement completed for {county_slug}")
            print(result.stdout)
            return True
        else:
            print(f"❌ Parity improvement failed for {county_slug}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error improving parity for {county_slug}: {e}")
        return False

def work_letter_e_parcel_linkage(county_slug, co_no):
    """Work on Letter E - parcel linkage"""
    print(f"\n🔍 Working on Letter E (parcel linkage) for {county_slug}...")
    
    try:
        # Try to run parcel linkage via property appraiser ArcGIS
        # This would need county-specific implementation
        print(f"📋 Letter E for {county_slug} requires county property appraiser integration")
        return False
        
    except Exception as e:
        print(f"❌ Error with parcel linkage for {county_slug}: {e}")
        return False

def work_letter_i_property_cards(county_slug):
    """Work on Letter I - property card completion"""
    print(f"\n🔍 Working on Letter I (property cards) for {county_slug}...")
    
    try:
        # Run customized SHARD-7 property card enrichment script
        result = subprocess.run([
            'python3', 'scripts/wave2_shard7_property_cards.py', '--county', county_slug
        ], capture_output=True, text=True, timeout=1800)
        
        if result.returncode == 0:
            print(f"✅ Property card enrichment completed for {county_slug}")
            print(result.stdout)
            return True
        else:
            print(f"❌ Property card enrichment failed for {county_slug}: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error enriching property cards for {county_slug}: {e}")
        return False

def main():
    print("GOLD STANDARD WAVE2-SHARD-7 AUTONOMOUS SESSION")
    print("=" * 80)
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"Counties: {', '.join([c['slug'] for c in SHARD_COUNTIES])}")
    print("=" * 80)
    
    if not SUPABASE_KEY:
        print("❌ SUPABASE_KEY environment variable not set")
        sys.exit(1)
    
    if not test_supabase_connection():
        sys.exit(1)
    
    # Analyze all counties and prioritize
    county_analysis = analyze_county_priorities()
    
    # Work on highest priority counties first
    session_results = {}
    
    for analysis in county_analysis[:4]:  # Focus on top 4 for 6-hour session
        county = analysis['county']
        slug = county['slug']
        name = county['name']
        co_no = county['co_no']
        
        print(f"\n{'='*60}")
        print(f"WORKING ON: {name} ({slug})")
        print(f"{'='*60}")
        
        county_results = {
            'initial_pass_count': analysis['pass_count'],
            'work_attempted': [],
            'final_pass_count': None
        }
        
        if analysis['needs_ingestion']:
            print(f"🚀 County {name} needs basic setup and ingestion first")
            # Use the specialized setup script
            result = subprocess.run([
                'python3', 'scripts/wave2_shard7_county_setup.py', '--county', slug
            ], capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0:
                print(f"✅ County setup completed for {name}")
                print(result.stdout)
                county_results['work_attempted'].append('county_setup')
            else:
                print(f"❌ County setup failed for {name}: {result.stderr}")
        
        # Work on specific letters based on current failures
        if analysis['evaluation']:
            for letter_data in analysis['evaluation']:
                letter = letter_data.get('letter', '').upper()
                is_pass = letter_data.get('pass', False)
                
                if not is_pass:
                    if letter == 'B':
                        if work_letter_b_verified_outcomes(slug):
                            county_results['work_attempted'].append('letter_b')
                    elif letter in ['C', 'D']:
                        if work_letter_c_d_parity(slug):
                            county_results['work_attempted'].append('letter_c_d')
                    elif letter == 'E':
                        if work_letter_e_parcel_linkage(slug, co_no):
                            county_results['work_attempted'].append('letter_e')
                    elif letter == 'I':
                        if work_letter_i_property_cards(slug):
                            county_results['work_attempted'].append('letter_i')
        
        # Re-evaluate county after work
        print(f"\n🔍 Re-evaluating {name} after work...")
        final_evaluation = evaluate_county(slug)
        if final_evaluation:
            final_pass_count = sum(1 for letter in final_evaluation if letter.get('pass', False))
            county_results['final_pass_count'] = final_pass_count
            
            print(f"📊 {name} Results:")
            print(f"  Before: {analysis['pass_count']}/10")
            print(f"  After:  {final_pass_count}/10")
            
            if final_pass_count > analysis['pass_count']:
                print(f"✅ Improvement: +{final_pass_count - analysis['pass_count']} letters!")
            else:
                print("⚠️ No improvement detected - may need different approach")
        
        session_results[slug] = county_results
    
    # Final session summary
    print(f"\n{'='*80}")
    print("SESSION SUMMARY")
    print(f"{'='*80}")
    print(f"End time: {datetime.now().isoformat()}")
    
    for slug, results in session_results.items():
        county_name = next(c['name'] for c in SHARD_COUNTIES if c['slug'] == slug)
        print(f"\n{county_name}:")
        print(f"  Initial: {results['initial_pass_count']}/10")
        if results['final_pass_count'] is not None:
            print(f"  Final:   {results['final_pass_count']}/10")
            delta = results['final_pass_count'] - results['initial_pass_count']
            print(f"  Delta:   {'+' if delta > 0 else ''}{delta}")
        print(f"  Work:    {', '.join(results['work_attempted']) or 'None'}")
    
    print(f"\n📋 Next steps:")
    print(f"  1. Commit all changes to main branch")
    print(f"  2. Run verification: SELECT public.gold_standard_loop();")
    print(f"  3. Check updated scoreboard")
    
    return session_results

if __name__ == "__main__":
    main()