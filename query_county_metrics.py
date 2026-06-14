#!/usr/bin/env python3
"""
Query current gold standard county metrics for SHARD-13 counties
"""
import os
import sys
import json
from typing import Dict, Any

# Set up environment
os.chdir('/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')
sys.path.insert(0, '/home/runner/work/cli-anything-biddeed/cli-anything-biddeed')

# Try to import shared Supabase client
try:
    from shared.cli_anything_shared.supabase import get_client, query_table
except ImportError:
    print("❌ Failed to import Supabase client")
    sys.exit(1)

# Set Supabase credentials from CLAUDE.md
os.environ['SUPABASE_URL'] = 'https://mocerqjnksmhcjzxrewo.supabase.co'
if 'SUPABASE_KEY' not in os.environ:
    print("❌ SUPABASE_KEY environment variable not set")
    sys.exit(1)

SHARD_13_COUNTIES = ['suwannee', 'jackson', 'santa_rosa', 'gulf']

def evaluate_county(county_slug: str) -> Dict[str, Any]:
    """Evaluate a single county using pencil_dod_evaluate_county function"""
    try:
        client = get_client()
        
        # Call the evaluation function
        result = client.rpc('pencil_dod_evaluate_county', {'county_slug': county_slug}).execute()
        
        if result.data:
            return result.data
        else:
            print(f"❌ No data returned for county: {county_slug}")
            return {}
            
    except Exception as e:
        print(f"❌ Error evaluating county {county_slug}: {e}")
        return {'error': str(e)}

def main():
    print("🔍 Querying Gold Standard metrics for SHARD-13 counties...")
    print(f"Counties: {', '.join(SHARD_13_COUNTIES)}")
    print("=" * 60)
    
    all_results = {}
    
    for county in SHARD_13_COUNTIES:
        print(f"\n📊 Evaluating {county}...")
        result = evaluate_county(county)
        all_results[county] = result
        
        if 'error' not in result and result:
            # Display the metrics in the format from the issue
            print(f"Results for {county}:")
            if isinstance(result, list) and len(result) > 0:
                metrics = result[0]
                print(json.dumps(metrics, indent=2))
            else:
                print(json.dumps(result, indent=2))
        else:
            print(f"❌ Failed to get metrics for {county}")
            if 'error' in result:
                print(f"Error: {result['error']}")
    
    # Save results for session tracking
    with open('current_county_metrics.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n✅ Metrics query completed. Results saved to current_county_metrics.json")
    return all_results

if __name__ == "__main__":
    main()