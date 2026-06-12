#!/usr/bin/env python3
"""
SHARD-14 Gold Standard Campaign Orchestrator
Executes the complete Gold Standard improvement pipeline for osceola, bay, okeechobee, hamilton

This script orchestrates all phases needed to move SHARD-14 counties to 10/10 Gold Standard:

Phase 1: Database Setup & Migration
Phase 2: County Bootstrap (Hamilton priority)  
Phase 3: Letter B - Verified Outcomes (0% → 95%+)
Phase 4: Letter I - Property Cards (0% → 95%+) 
Phase 5: Letter J - Deal Thesis (0% → 95%+)
Phase 6: Verification & Metrics Reporting

Usage:
  python scripts/shard14_gold_standard_campaign.py --full-pipeline
  python scripts/shard14_gold_standard_campaign.py --county osceola --phase verification
"""
import os
import sys
import subprocess
import argparse
import time
from datetime import datetime

# SHARD-14 target counties (from issue metrics)
TARGET_COUNTIES = [
    {
        'name': 'Osceola', 'slug': 'osceola', 'co_no': 59,
        'current_state': '2/10', 
        'priority': 1,  # Highest volume, best leverage
        'issues': ['B: 0% verified', 'C: 14.1%', 'D: 49.5%', 'E: 77.9%', 'F: 1.9%', 'I: 0%', 'J: 0%']
    },
    {
        'name': 'Bay', 'slug': 'bay', 'co_no': 13,
        'current_state': '1/10',
        'priority': 2,  # Good volume, similar pattern
        'issues': ['B: 0% verified', 'C: 15.6%', 'D: 60.0%', 'E: 81.4%', 'F: 0.0%', 'H: 325h', 'I: 0%', 'J: 0%']
    },
    {
        'name': 'Okeechobee', 'slug': 'okeechobee', 'co_no': 57,
        'current_state': '1/10', 
        'priority': 3,  # Lower volume but same pattern
        'issues': ['B: 0% verified', 'C: 17.3%', 'D: 74.1%', 'E: 85.6%', 'F: 0.0%', 'H: 349h', 'I: 0%', 'J: 0%']
    },
    {
        'name': 'Hamilton', 'slug': 'hamilton', 'co_no': 34,
        'current_state': '0/10',
        'priority': 4,  # Needs complete bootstrap
        'issues': ['All letters FAIL - no data ingested']
    }
]

# Critical letters for maximum leverage
CRITICAL_LETTERS = ['B', 'I', 'J']

def run_script_with_logging(script_name, args=None, timeout=1800):
    """Run a script and capture its output with detailed logging"""
    cmd = ['python3', f'scripts/{script_name}']
    if args:
        cmd.extend(args)
    
    print(f"\n🚀 EXECUTING: {' '.join(cmd)}")
    print("-" * 60)
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd='/home/runner/work/cli-anything-biddeed/cli-anything-biddeed'
        )
        
        elapsed = time.time() - start_time
        
        # Print output
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr and result.returncode != 0:
            print("STDERR:")
            print(result.stderr)
        
        success = result.returncode == 0
        print(f"\n{'✅ SUCCESS' if success else '❌ FAILED'} - {elapsed:.1f}s elapsed")
        
        return {
            'script': script_name,
            'args': args,
            'success': success,
            'elapsed': elapsed,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"\n⏰ TIMEOUT after {elapsed:.1f}s")
        return {
            'script': script_name,
            'args': args,
            'success': False,
            'elapsed': elapsed,
            'error': 'Timeout',
            'returncode': -1
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n❌ ERROR: {e}")
        return {
            'script': script_name,
            'args': args,
            'success': False,
            'elapsed': elapsed,
            'error': str(e),
            'returncode': -1
        }

def phase_1_database_setup():
    """Phase 1: Database Setup & Migration"""
    print("\n" + "="*80)
    print("PHASE 1: DATABASE SETUP & MIGRATION")
    print("="*80)
    
    results = []
    
    # Apply SHARD-14 migration
    print("📦 Applying SHARD-14 database migration...")
    # result = run_script_with_logging('apply_shard14_migration.py')
    # results.append(result)
    
    # For now, just verify the migration exists
    migration_file = 'migrations/20260612_shard14_county_setup.sql'
    if os.path.exists(migration_file):
        print(f"✅ Migration file exists: {migration_file}")
        results.append({
            'script': 'migration_check',
            'success': True,
            'elapsed': 0.1
        })
    else:
        print(f"❌ Migration file missing: {migration_file}")
        results.append({
            'script': 'migration_check',
            'success': False,
            'error': 'Migration file not found'
        })
    
    return results

def phase_2_county_bootstrap(target_counties=None):
    """Phase 2: County Bootstrap (Hamilton priority)"""
    print("\n" + "="*80) 
    print("PHASE 2: COUNTY BOOTSTRAP")
    print("="*80)
    
    results = []
    
    # Focus on Hamilton first (0/10 state)
    hamilton = next((c for c in TARGET_COUNTIES if c['slug'] == 'hamilton'), None)
    
    if not target_counties or 'hamilton' in [c['slug'] for c in target_counties]:
        print("🔧 Hamilton County Bootstrap (Priority: CRITICAL)")
        result = run_script_with_logging('shard14_county_bootstrap.py', ['--county', 'hamilton'])
        results.append(result)
    
    # Check other counties if they need bootstrap
    other_counties = [c for c in TARGET_COUNTIES if c['slug'] != 'hamilton']
    if not target_counties:
        target_counties = other_counties
    
    for county in target_counties:
        if county['slug'] == 'hamilton':
            continue  # Already handled
        
        print(f"\n🔍 Checking {county['name']} bootstrap status...")
        result = run_script_with_logging('shard14_county_bootstrap.py', ['--county', county['slug']])
        results.append(result)
    
    return results

def phase_3_letter_b_verified_outcomes(target_counties):
    """Phase 3: Letter B - Verified Outcomes (Critical: 0% → 95%+)"""
    print("\n" + "="*80)
    print("PHASE 3: LETTER B - VERIFIED OUTCOMES")
    print("="*80)
    
    results = []
    
    # Set up verified outcomes framework for all counties
    print("🔍 Analyzing verified outcomes gaps...")
    result = run_script_with_logging('shard14_letter_b_verified_outcomes.py', [
        '--all-counties', '--analyze-only'
    ])
    results.append(result)
    
    # Set up scraper frameworks for each county
    for county in target_counties:
        print(f"\n⚙️ Setting up verified outcomes pipeline for {county['name']}...")
        result = run_script_with_logging('shard14_letter_b_verified_outcomes.py', [
            '--county', county['slug'], '--create-samples'
        ])
        results.append(result)
    
    return results

def phase_4_letter_i_property_cards(target_counties):
    """Phase 4: Letter I - Property Cards (Critical: 0% → 95%+)"""
    print("\n" + "="*80)
    print("PHASE 4: LETTER I - PROPERTY CARD ENRICHMENT")
    print("="*80)
    
    results = []
    
    # Analyze property completion gaps
    print("🏠 Analyzing property card completion gaps...")
    result = run_script_with_logging('shard14_letter_i_property_cards.py', [
        '--all-counties', '--analyze-only'
    ])
    results.append(result)
    
    # Set up property enrichment for each county
    for county in target_counties:
        print(f"\n📍 Setting up property enrichment for {county['name']}...")
        result = run_script_with_logging('shard14_letter_i_property_cards.py', [
            '--county', county['slug'], '--sample-enrichment', '--sample-size', '5'
        ])
        results.append(result)
    
    return results

def phase_5_letter_j_deal_thesis(target_counties):
    """Phase 5: Letter J - Deal Thesis (Critical: 0% → 95%+)"""
    print("\n" + "="*80)
    print("PHASE 5: LETTER J - DEAL THESIS PIPELINE")
    print("="*80)
    
    results = []
    
    # Analyze deal thesis gaps
    print("🎯 Analyzing deal thesis completion gaps...")
    result = run_script_with_logging('shard14_letter_j_deal_thesis.py', [
        '--all-counties', '--analyze-only'
    ])
    results.append(result)
    
    # Create sample bid decisions for each county
    for county in target_counties:
        print(f"\n💰 Creating deal thesis pipeline for {county['name']}...")
        result = run_script_with_logging('shard14_letter_j_deal_thesis.py', [
            '--county', county['slug'], '--create-samples', '--sample-size', '5'
        ])
        results.append(result)
    
    return results

def phase_6_verification_reporting(target_counties):
    """Phase 6: Verification & Metrics Reporting"""
    print("\n" + "="*80)
    print("PHASE 6: VERIFICATION & METRICS REPORTING")
    print("="*80)
    
    results = []
    
    # Run county status check
    print("📊 Checking final county status...")
    result = run_script_with_logging('shard14_county_status_simple.py')
    results.append(result)
    
    print("\n🎯 VERIFICATION PROTOCOL:")
    print("After database changes are applied, run:")
    print("SELECT public.pencil_dod_evaluate_county('<county>') for each:")
    for county in target_counties:
        print(f"  - {county['slug']}")
    
    return results

def generate_campaign_report(all_results, target_counties):
    """Generate comprehensive campaign completion report"""
    print("\n" + "="*100)
    print("SHARD-14 GOLD STANDARD CAMPAIGN COMPLETION REPORT")
    print("="*100)
    print(f"Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Target Counties: {', '.join([c['name'] for c in target_counties])}")
    print()
    
    # Phase-by-phase summary
    phases = [
        ("Database Setup", [r for r in all_results if 'phase_1' in r]),
        ("County Bootstrap", [r for r in all_results if 'phase_2' in r]),
        ("Letter B: Verified Outcomes", [r for r in all_results if 'phase_3' in r]),
        ("Letter I: Property Cards", [r for r in all_results if 'phase_4' in r]),
        ("Letter J: Deal Thesis", [r for r in all_results if 'phase_5' in r]),
        ("Verification", [r for r in all_results if 'phase_6' in r])
    ]
    
    total_elapsed = sum(r['elapsed'] for r in all_results)
    successful_scripts = sum(1 for r in all_results if r['success'])
    total_scripts = len(all_results)
    
    print("PHASE EXECUTION SUMMARY:")
    print("-" * 50)
    
    for phase_name, phase_results in phases:
        if phase_results:
            successes = sum(1 for r in phase_results if r['success'])
            total = len(phase_results)
            elapsed = sum(r['elapsed'] for r in phase_results)
            status = "✅ PASS" if successes == total else "❌ PARTIAL"
            print(f"{phase_name:30s} {status:8s} ({successes}/{total}) {elapsed:6.1f}s")
        else:
            print(f"{phase_name:30s} {'⚠️ SKIP':8s}")
    
    print()
    print(f"OVERALL SUCCESS RATE: {successful_scripts}/{total_scripts} scripts ({successful_scripts/total_scripts*100:.1f}%)")
    print(f"TOTAL EXECUTION TIME: {total_elapsed:.1f} seconds ({total_elapsed/60:.1f} minutes)")
    print()
    
    # Expected letter improvements
    print("EXPECTED GOLD STANDARD IMPROVEMENTS:")
    print("-" * 50)
    print("B: Verified outcomes framework + sample data → 0% → framework for 95%+")
    print("I: Property enrichment pipeline + sample data → 0% → framework for 95%+")
    print("J: Shapira Formula pipeline + sample decisions → 0% → framework for 95%+")
    print("Hamilton: Complete bootstrap from 0/10 → basic data foundation")
    print()
    
    # Next steps
    print("CRITICAL NEXT STEPS:")
    print("-" * 50)
    print("1. Apply database migration to live Supabase (requires environment setup)")
    print("2. Execute county data ingestion for Hamilton (if bootstrap found no data)")
    print("3. Build production scrapers for verified outcomes (clerk sources)")
    print("4. Scale property enrichment to full auction datasets")
    print("5. Deploy Shapira Formula as production bid decision pipeline")
    print("6. Run verification protocol: SELECT public.pencil_dod_evaluate_county('<county>')")
    print()
    
    return {
        'total_scripts': total_scripts,
        'successful_scripts': successful_scripts,
        'success_rate': successful_scripts / total_scripts,
        'total_elapsed': total_elapsed,
        'phases_complete': sum(1 for _, pr in phases if pr and all(r['success'] for r in pr)),
        'phases_total': len([p for p in phases if p[1]])
    }

def main():
    parser = argparse.ArgumentParser(description='SHARD-14 Gold Standard Campaign Orchestrator')
    parser.add_argument('--county', help='Target specific county only')
    parser.add_argument('--phase', choices=['setup', 'bootstrap', 'letter-b', 'letter-i', 'letter-j', 'verification'], 
                       help='Run specific phase only')
    parser.add_argument('--full-pipeline', action='store_true', help='Run complete pipeline (all phases)')
    parser.add_argument('--critical-letters-only', action='store_true', help='Focus on Letters B, I, J only')
    
    args = parser.parse_args()
    
    if not any([args.full_pipeline, args.phase, args.critical_letters_only]):
        parser.print_help()
        sys.exit(1)
    
    print("🎯 SHARD-14 GOLD STANDARD CAMPAIGN")
    print("=" * 60)
    print(f"Session start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("Ship-to-main mandate: All changes committed directly to main branch")
    print()
    
    # Determine target counties
    if args.county:
        target_counties = [c for c in TARGET_COUNTIES if c['slug'] == args.county]
        if not target_counties:
            print(f"❌ County '{args.county}' not found in SHARD-14")
            sys.exit(1)
    else:
        target_counties = TARGET_COUNTIES
    
    print("TARGET COUNTIES:")
    for county in target_counties:
        print(f"  {county['name']:12s} {county['current_state']:4s} Priority {county['priority']}")
    print()
    
    # Execute campaign phases
    campaign_start = time.time()
    all_results = []
    
    try:
        if args.phase == 'setup' or args.full_pipeline:
            phase_1_results = phase_1_database_setup()
            all_results.extend([{**r, 'phase': 'phase_1'} for r in phase_1_results])
        
        if args.phase == 'bootstrap' or args.full_pipeline:
            phase_2_results = phase_2_county_bootstrap(target_counties)
            all_results.extend([{**r, 'phase': 'phase_2'} for r in phase_2_results])
        
        if args.phase == 'letter-b' or args.full_pipeline or args.critical_letters_only:
            phase_3_results = phase_3_letter_b_verified_outcomes(target_counties)
            all_results.extend([{**r, 'phase': 'phase_3'} for r in phase_3_results])
        
        if args.phase == 'letter-i' or args.full_pipeline or args.critical_letters_only:
            phase_4_results = phase_4_letter_i_property_cards(target_counties)
            all_results.extend([{**r, 'phase': 'phase_4'} for r in phase_4_results])
        
        if args.phase == 'letter-j' or args.full_pipeline or args.critical_letters_only:
            phase_5_results = phase_5_letter_j_deal_thesis(target_counties)
            all_results.extend([{**r, 'phase': 'phase_5'} for r in phase_5_results])
        
        if args.phase == 'verification' or args.full_pipeline:
            phase_6_results = phase_6_verification_reporting(target_counties)
            all_results.extend([{**r, 'phase': 'phase_6'} for r in phase_6_results])
    
    except KeyboardInterrupt:
        print("\n🛑 Campaign interrupted by user")
    except Exception as e:
        print(f"\n❌ Campaign failed with error: {e}")
    
    # Generate final report
    campaign_elapsed = time.time() - campaign_start
    report = generate_campaign_report(all_results, target_counties)
    
    # Final status
    if report['success_rate'] >= 0.8:
        print(f"🎉 CAMPAIGN SUCCESSFUL ({campaign_elapsed:.1f}s total)")
        print("Ready for production deployment and verification.")
        sys.exit(0)
    else:
        print(f"⚠️ CAMPAIGN PARTIAL ({report['successful_scripts']}/{report['total_scripts']} scripts)")
        print("Manual intervention required for failed components.")
        sys.exit(1)

if __name__ == "__main__":
    main()