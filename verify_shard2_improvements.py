#!/usr/bin/env python3
"""
SHARD-2 Verification Script
Checks improvements after migration application
"""
import os
import sys
import json
from datetime import datetime

# Add shared module to path
sys.path.append('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed/shared')

def verify_shard2_improvements():
    """Verify SHARD-2 improvements using direct SQL"""
    try:
        from cli_anything_shared.supabase import get_client
        
        client = get_client("shard2")
        
        # Query verification function
        result = client.rpc("shard2_verification_summary").execute()
        
        if result.data:
            print("SHARD-2 VERIFICATION RESULTS")
            print("=" * 50)
            
            for county_data in result.data:
                county = county_data['county_slug']
                auctions = county_data['auction_count']
                decisions = county_data['bid_decisions_count'] 
                clean = county_data['parity_clean_count']
                any_match = county_data['parity_any_count']
                
                # Calculate metrics
                j_coverage = (decisions / auctions * 100) if auctions > 0 else 0
                c_coverage = (clean / auctions * 100) if auctions > 0 else 0  
                d_coverage = (any_match / auctions * 100) if auctions > 0 else 0
                
                print(f"{county}:")
                print(f"  Auctions: {auctions}")
                print(f"  J (bid_decisions): {decisions} ({j_coverage:.1f}%)")
                print(f"  C (parity_clean): {clean} ({c_coverage:.1f}%)")
                print(f"  D (parity_any): {any_match} ({d_coverage:.1f}%)")
                print()
                
            return True
        else:
            print("❌ No verification data returned")
            return False
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def run_live_evaluations():
    """Run live county evaluations"""
    try:
        from cli_anything_shared.supabase import get_client
        
        client = get_client("shard2")
        counties = ['broward', 'baker', 'leon', 'st_lucie', 'holmes']
        
        print("LIVE COUNTY EVALUATIONS")
        print("=" * 50)
        
        for county in counties:
            try:
                result = client.rpc("pencil_dod_evaluate_county", {"county_slug_arg": county}).execute()
                
                if result.data:
                    print(f"\n{county}:")
                    for letter_data in result.data:
                        letter = letter_data.get('letter', '?')
                        metric = letter_data.get('metric')
                        passed = letter_data.get('pass', False)
                        status = "✅ PASS" if passed else "❌ FAIL"
                        print(f"  {letter}: {status} metric={metric}")
                else:
                    print(f"\n{county}: No evaluation data")
                    
            except Exception as e:
                print(f"\n{county}: Error - {e}")
        
        return True
                
    except Exception as e:
        print(f"❌ Live evaluations failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 SHARD-2 Post-Migration Verification")
    print(f"Session: claude/issue-7749-20260614-1601")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    success = True
    
    if not verify_shard2_improvements():
        success = False
    
    if not run_live_evaluations():
        success = False
    
    sys.exit(0 if success else 1)