#!/usr/bin/env python3
"""
SHARD-9 MASTER EXECUTOR
Purpose: Coordinate all shard-9 county fixes in priority order
Counties: osceola (2/10), duval (1/10), okaloosa (1/10), dixie (0/10), taylor (0/10)

Execution priority per brief and leverage analysis:
1. DUVAL B reconciliation + J generator (closest to gold)
2. OSCEOLA B fix + J generator (2/10 base)
3. DIXIE/TAYLOR county setup (A letter infrastructure)
4. OKALOOSA B fix (similar to osceola pattern)
"""
import os
import subprocess
import sys
from datetime import datetime

def run_script(script_name, description):
    """Run a shard-9 script and capture results"""
    print(f"\n{'='*60}")
    print(f"🎯 EXECUTING: {description}")
    print(f"📄 Script: {script_name}")
    print(f"⏰ Started: {datetime.now().strftime('%H:%M:%S')}")
    print('='*60)
    
    try:
        # Run the Python script
        result = subprocess.run([
            sys.executable, script_name
        ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
        
        print(result.stdout)
        
        if result.stderr:
            print("⚠️ STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - COMPLETED")
            return True
        else:
            print(f"❌ {description} - FAILED (exit code {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (>5 minutes)")
        return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def execute_shard9_pipeline():
    """Execute the complete shard-9 pipeline"""
    print("🚀 SHARD-9 MASTER EXECUTOR")
    print("Counties: osceola, duval, okaloosa, dixie, taylor")
    print("Budget: 6h autonomous session")
    print("Target: Move highest-leverage metrics for gold standard certification")
    
    start_time = datetime.now()
    results = {}
    
    # Phase 1: DUVAL (highest priority - closest to gold)
    print(f"\n🎯 PHASE 1: DUVAL FIXES (Priority 1 - closest to gold)")
    
    # 1.1: DUVAL B reconciliation (fix >100% anomaly)
    results['duval_b_reconciliation'] = run_script(
        'shard9_duval_b_reconciliation.py',
        'DUVAL B Reconciliation (110.2% -> 95-105%)'
    )
    
    # 1.2: DUVAL J generator (0.0% -> 95%)
    results['duval_j_generator'] = run_script(
        'shard9_duval_j_generator.py',
        'DUVAL J Generator (bid_decisions pipeline)'
    )
    
    # Phase 2: OSCEOLA (2/10 base, good foundation)
    print(f"\n🎯 PHASE 2: OSCEOLA FIXES (Priority 2 - 2/10 base)")
    
    # 2.1: OSCEOLA B fix (null -> 95%)
    results['osceola_b_fix'] = run_script(
        'shard9_osceola_b_fix.py',
        'OSCEOLA B Fix (null -> 95%)'
    )
    
    # Phase 3: DIXIE & TAYLOR (0/10, need basic infrastructure)
    print(f"\n🎯 PHASE 3: DIXIE & TAYLOR SETUP (Priority 3 - basic infrastructure)")
    
    # 3.1: County setup (A letter dual-product coverage)
    results['dixie_taylor_setup'] = run_script(
        'shard9_dixie_taylor_county_setup.py',
        'DIXIE & TAYLOR County Setup (A letter infrastructure)'
    )
    
    # Phase 4: Verification and summary
    print(f"\n🎯 PHASE 4: VERIFICATION")
    results['verification'] = run_script(
        'verify_shard9_status.py',
        'SHARD-9 Status Verification (final metrics check)'
    )
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n{'='*60}")
    print("📋 SHARD-9 EXECUTION SUMMARY")
    print(f"⏰ Total Duration: {duration}")
    print(f"📊 Results:")
    
    success_count = 0
    for task, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {task}: {status}")
        if success:
            success_count += 1
    
    print(f"\n🎯 Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
    
    # Next steps based on results
    print(f"\n📋 NEXT STEPS:")
    
    if results.get('duval_b_reconciliation') and results.get('duval_j_generator'):
        print("1. ✅ DUVAL ready for gold certification check")
    else:
        print("1. ⚠️ DUVAL needs manual review - B or J fixes failed")
    
    if results.get('osceola_b_fix'):
        print("2. ✅ OSCEOLA B fixed - add J generator for higher score")
    else:
        print("2. ⚠️ OSCEOLA B fix needs manual review")
    
    if results.get('dixie_taylor_setup'):
        print("3. ✅ DIXIE/TAYLOR basic infrastructure complete")
        print("   - Wire scrapers to GitHub Actions workflows")
        print("   - Monitor A metric improvement in next 24h")
    else:
        print("3. ⚠️ DIXIE/TAYLOR setup failed - manual intervention needed")
    
    print(f"\n📈 EXPECTED IMPROVEMENTS:")
    print("- DUVAL: 1/10 -> 3-4/10 (B fix + J generator)")
    print("- OSCEOLA: 2/10 -> 3/10 (B fix)")
    print("- DIXIE/TAYLOR: 0/10 -> 1/10 (A letter)")
    print("- Total shard improvement: 4-6 letter fixes across 5 counties")
    
    return results

if __name__ == "__main__":
    print("🎯 GOLD STANDARD SHARD-9 AUTONOMOUS EXECUTION")
    print(f"Started: {datetime.now()}")
    print("="*60)
    
    # Check if we're in the right directory
    if not os.path.exists('shard9_duval_b_reconciliation.py'):
        print("❌ Shard-9 scripts not found in current directory")
        print("Expected files:")
        print("  - shard9_duval_b_reconciliation.py")
        print("  - shard9_duval_j_generator.py") 
        print("  - shard9_osceola_b_fix.py")
        print("  - shard9_dixie_taylor_county_setup.py")
        print("  - verify_shard9_status.py")
        sys.exit(1)
    
    # Execute the pipeline
    results = execute_shard9_pipeline()
    
    # Exit with appropriate code
    all_success = all(results.values())
    sys.exit(0 if all_success else 1)