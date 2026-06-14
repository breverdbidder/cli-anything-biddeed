#!/usr/bin/env python3
"""
SHARD-4 Environment Verification
Tests database access to key tables needed for B/I/J improvements
"""
import sys
import os
from datetime import datetime

# Add shared modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

SHARD_COUNTIES = ['citrus', 'clay', 'martin', 'washington', 'lafayette']

def verify_database_tables():
    """Verify critical tables exist and are accessible"""
    print("🔍 Verifying database tables...")
    
    try:
        from cli_anything_shared.supabase import get_client
        client = get_client()
        
        # Test tables needed for B/I/J improvements
        critical_tables = [
            'multi_county_auctions',
            'tax_deed_outcomes', 
            'foreclosure_outcomes',
            'bid_decisions',
            'gold_standard_county_status'
        ]
        
        for table in critical_tables:
            try:
                result = client.table(table).select('count', count='exact').limit(1).execute()
                count = result.count if hasattr(result, 'count') else 'unknown'
                print(f"✅ {table}: accessible (count={count})")
            except Exception as e:
                print(f"❌ {table}: error - {e}")
                return False
                
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

def verify_pencil_function():
    """Test pencil_dod_evaluate_county function"""
    print("\n🔍 Testing pencil_dod_evaluate_county function...")
    
    try:
        from cli_anything_shared.supabase import get_client
        client = get_client()
        
        # Test with citrus county
        result = client.rpc('pencil_dod_evaluate_county', {'county_slug': 'citrus'}).execute()
        
        if result.data:
            print(f"✅ pencil_dod_evaluate_county: working")
            print(f"   Sample result: {len(result.data)} evaluation items returned")
            
            # Show sample data structure
            if result.data:
                sample = result.data[0]
                print(f"   Sample item keys: {list(sample.keys())}")
            return True
        else:
            print("❌ pencil_dod_evaluate_county: no data returned")
            return False
            
    except Exception as e:
        print(f"❌ pencil_dod_evaluate_county: error - {e}")
        return False

def check_county_data():
    """Check basic auction data for SHARD-4 counties"""
    print("\n🔍 Checking SHARD-4 county auction data...")
    
    try:
        from cli_anything_shared.supabase import get_client
        client = get_client()
        
        for county in SHARD_COUNTIES:
            try:
                # Check auction count
                result = client.table('multi_county_auctions')\
                    .select('case_number', count='exact')\
                    .eq('county', county)\
                    .limit(1)\
                    .execute()
                    
                auction_count = result.count if hasattr(result, 'count') else 0
                
                # Check closed auctions
                closed_result = client.table('multi_county_auctions')\
                    .select('case_number', count='exact')\
                    .eq('county', county)\
                    .in_('auction_status', ['sold', 'no_sale', 'canceled'])\
                    .limit(1)\
                    .execute()
                    
                closed_count = closed_result.count if hasattr(closed_result, 'count') else 0
                
                print(f"✅ {county:12}: {auction_count:5} total auctions, {closed_count:5} closed")
                
            except Exception as e:
                print(f"❌ {county:12}: error - {e}")
                
    except Exception as e:
        print(f"❌ County data check failed: {e}")

def test_table_write_access():
    """Test if we can write to critical tables"""
    print("\n🔍 Testing table write access...")
    
    try:
        from cli_anything_shared.supabase import get_client
        client = get_client()
        
        # Test write access to tax_deed_outcomes (needed for Letter B)
        test_record = {
            'case_number': f'TEST_SHARD4_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
            'county_slug': 'test',
            'data_source': 'shard4_verification_test',
            'outcome_status': 'test_record',
            'created_at': datetime.now().isoformat()
        }
        
        result = client.table('tax_deed_outcomes').insert(test_record).execute()
        
        if result.data:
            print("✅ tax_deed_outcomes: write access confirmed")
            
            # Clean up test record
            client.table('tax_deed_outcomes')\
                .delete()\
                .eq('case_number', test_record['case_number'])\
                .execute()
            print("✅ test record cleaned up")
            return True
        else:
            print("❌ tax_deed_outcomes: write access failed")
            return False
            
    except Exception as e:
        print(f"❌ Write access test failed: {e}")
        return False

def main():
    print("SHARD-4 Environment Verification")
    print("=" * 50)
    print(f"Target counties: {', '.join(SHARD_COUNTIES)}")
    print(f"Target letters: B (verified outcomes), I (property cards), J (deal thesis)")
    print()
    
    success = True
    
    # Run all verification checks
    if not verify_database_tables():
        success = False
        
    if not verify_pencil_function():
        success = False
        
    check_county_data()  # Informational, doesn't affect success
    
    if not test_table_write_access():
        success = False
    
    print(f"\n{'='*50}")
    if success:
        print("✅ SHARD-4 environment verification PASSED")
        print("Ready for autonomous session execution")
    else:
        print("❌ SHARD-4 environment verification FAILED")
        print("Environment not ready for autonomous session")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())