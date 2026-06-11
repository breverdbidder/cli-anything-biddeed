#!/usr/bin/env python3
"""
GOLD STANDARD SHARD-6 Status Verification
Check current metrics for highlands, sumter, jackson, calhoun, liberty counties
"""
import os
import sys
import json
import httpx
from datetime import datetime

# SHARD-6 assigned counties
ASSIGNED_COUNTIES = ['highlands', 'sumter', 'jackson', 'calhoun', 'liberty']

# Database connection 
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY, 
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

def verify_county_status(county_slug):
    """Run fresh county evaluation using pencil_dod_evaluate_county"""
    try:
        client = httpx.Client(timeout=60)
        
        print(f"\n📊 Evaluating {county_slug}...")
        
        # Call the RPC function
        r = client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
            headers=sb_headers(),
            json={"county_slug_arg": county_slug}
        )
        
        if r.status_code == 200:
            result = r.json()
            
            if isinstance(result, list) and len(result) > 0:
                pass_count = 0
                total_letters = len(result)
                
                print(f"  Results for {county_slug}:")
                for letter_data in result:
                    letter = letter_data.get('letter', '?')
                    metric = letter_data.get('metric')
                    pass_status = letter_data.get('pass', False)
                    detail = letter_data.get('detail', '')
                    
                    if pass_status:
                        pass_count += 1
                        status_symbol = "✅"
                    else:
                        status_symbol = "❌"
                    
                    # Format metric for display
                    if metric is not None:
                        if isinstance(metric, (int, float)) and metric != int(metric):
                            metric_str = f"{metric:.1f}"
                        else:
                            metric_str = str(metric)
                    else:
                        metric_str = "null"
                    
                    print(f"    {letter} {status_symbol} metric={metric_str} [{detail}]")
                
                print(f"  Score: {pass_count}/{total_letters}")
                return result, pass_count, total_letters
            else:
                print(f"  No evaluation data returned for {county_slug}")
                return None, 0, 0
                
        else:
            print(f"  ❌ Failed to evaluate {county_slug}: {r.status_code} - {r.text}")
            return None, 0, 0
            
    except Exception as e:
        print(f"  ❌ Error evaluating {county_slug}: {e}")
        return None, 0, 0

def main():
    print("=" * 80)
    print("GOLD STANDARD SHARD-6 STATUS VERIFICATION")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Counties: {', '.join(ASSIGNED_COUNTIES)}")
    print("")
    
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found. Cannot proceed.")
        return False
    
    print("🔍 Running fresh evaluations for all assigned counties...")
    
    overall_results = {}
    total_counties = len(ASSIGNED_COUNTIES)
    counties_with_data = 0
    
    for county in ASSIGNED_COUNTIES:
        result, pass_count, total_letters = verify_county_status(county)
        overall_results[county] = {
            'pass_count': pass_count,
            'total_letters': total_letters,
            'data': result
        }
        
        if result is not None:
            counties_with_data += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    print(f"Counties evaluated: {counties_with_data}/{total_counties}")
    print("")
    
    # Sort by pass count descending to show best performers first
    sorted_counties = sorted(
        overall_results.items(), 
        key=lambda x: x[1]['pass_count'], 
        reverse=True
    )
    
    for county, data in sorted_counties:
        pass_count = data['pass_count']
        total_letters = data['total_letters']
        if total_letters > 0:
            percentage = (pass_count / total_letters) * 100
            print(f"{county:12s} {pass_count:2d}/{total_letters} ({percentage:4.1f}%)")
        else:
            print(f"{county:12s} No data")
    
    print("")
    print("PRIORITY RECOMMENDATIONS:")
    print("-" * 40)
    
    # Prioritize counties with some progress but room for improvement
    priority_counties = []
    for county, data in sorted_counties:
        pass_count = data['pass_count']
        total_letters = data['total_letters']
        if 0 < pass_count < total_letters:
            priority_counties.append((county, pass_count, total_letters))
    
    if priority_counties:
        print("Focus on counties with existing progress:")
        for county, pass_count, total_letters in priority_counties[:3]:
            percentage = (pass_count / total_letters) * 100
            print(f"  • {county} ({pass_count}/{total_letters}, {percentage:.1f}%) - highest leverage")
    else:
        # If no counties have partial progress, focus on highest data volume
        print("Focus on building baseline data for:")
        for county, data in sorted_counties[:2]:
            print(f"  • {county} - establish foundation")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)