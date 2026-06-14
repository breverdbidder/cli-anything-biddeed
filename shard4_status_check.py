#!/usr/bin/env python3
"""
SHARD-4 County Status Check - citrus, clay, martin, washington, lafayette
Verifies database connectivity and checks current status per ULTRALOOP protocol
"""
import sys
import os
import json

# Add the shared module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))

# SHARD-4 assigned counties from the issue
SHARD_COUNTIES = ['citrus', 'clay', 'martin', 'washington', 'lafayette']

def main():
    print("🔍 SHARD-4 Gold Standard Status Check")
    print(f"Counties: {', '.join(SHARD_COUNTIES)}")
    print("=" * 60)
    
    try:
        from cli_anything_shared.supabase import get_client, health_check
        print("✅ Shared supabase module imported successfully")
        
        # Test health check
        if health_check():
            print("✅ Database health check passed")
        else:
            print("❌ Database health check failed")
            return 1
            
        # Get client and query gold_standard_county_status
        client = get_client()
        print("✅ Supabase client created successfully")
        
        # Query for SHARD-4 counties
        result = client.table('gold_standard_county_status').select('*').in_('county_slug', SHARD_COUNTIES).execute()
        
        if not result.data:
            print("❌ No data found for SHARD-4 counties in gold_standard_county_status")
            return 1
            
        print(f"\n📊 Found {len(result.data)} counties in database")
        print("\nCurrent Status:")
        print("-" * 60)
        
        for county_data in result.data:
            county = county_data.get('county_slug', 'Unknown')
            total_pass = county_data.get('total_passing_criteria', 0)
            print(f"{county:12}: {total_pass}/10 criteria passing")
            
            # Show individual letter metrics for failing ones
            letters = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
            failing_letters = []
            
            for letter in letters:
                letter_field = f"letter_{letter}_status"
                if county_data.get(letter_field) != 'PASS':
                    metric_field = f"letter_{letter}_metric"
                    metric_val = county_data.get(metric_field)
                    failing_letters.append(f"{letter.upper()}={metric_val}")
            
            if failing_letters:
                print(f"{'':12}  FAILING: {', '.join(failing_letters)}")
                
        print("\n🎯 PRIORITY ANALYSIS:")
        print("-" * 60)
        
        # Analyze priority based on issue brief
        critical_letters = ['b', 'i', 'j']  # Critical three per brief
        leverage_analysis = {}
        
        for county_data in result.data:
            county = county_data.get('county_slug', 'Unknown')
            
            # Check critical letters first
            critical_fails = []
            for letter in critical_letters:
                letter_field = f"letter_{letter}_status"
                if county_data.get(letter_field) != 'PASS':
                    critical_fails.append(letter.upper())
            
            if critical_fails:
                leverage_analysis[county] = f"Critical fails: {', '.join(critical_fails)}"
            else:
                # Count other failing letters
                other_fails = 0
                for letter in ['a', 'c', 'd', 'e', 'f', 'g', 'h']:
                    letter_field = f"letter_{letter}_status"
                    if county_data.get(letter_field) != 'PASS':
                        other_fails += 1
                leverage_analysis[county] = f"Non-critical fails: {other_fails}"
        
        for county, analysis in leverage_analysis.items():
            print(f"{county:12}: {analysis}")
            
        # Additional context for specific counties mentioned in brief
        print("\n📋 SPECIFIC COUNTY NOTES:")
        print("-" * 60)
        for county_data in result.data:
            county = county_data.get('county_slug', 'Unknown')
            if county == 'lafayette':
                print(f"{county:12}: Per brief - 0/10 criteria, needs full setup")
            elif county in ['citrus', 'clay', 'martin', 'washington']:
                passes = county_data.get('total_passing_criteria', 0)
                if passes == 1:
                    print(f"{county:12}: Single PASS county - focus on high-leverage fixes")
                elif passes == 2:
                    print(f"{county:12}: Two PASS county - check A,H letters per pattern")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())