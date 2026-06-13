#!/usr/bin/env python3
"""
Quick query script to check current status of SHARD-4 assigned counties.
Counties: broward, sarasota, indian_river, washington, lafayette
"""
import httpx
import json
import os

# Supabase connection
SUPABASE_URL = "https://mocerqjnksmhcjzxrewo.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Our assigned counties from issue description
ASSIGNED_COUNTIES = {
    'broward': {'current_status': '2/10 (A,H)'},
    'sarasota': {'current_status': '2/10 (A,H)'},
    'indian_river': {'current_status': '1/10 (A)'},
    'washington': {'current_status': '1/10 (A)'},
    'lafayette': {'current_status': '0/10'}
}

def query_county_status(county_slug: str) -> dict:
    """Query current status for a county"""
    if not SUPABASE_KEY:
        print(f"ERROR: SUPABASE_ANON_KEY environment variable not found")
        return {}
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            # Query pencil_dod_evaluate_county function
            response = client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/pencil_dod_evaluate_county",
                headers=headers,
                json={"county_slug": county_slug}
            )
            
            if response.status_code == 200:
                result = response.json()
                status = {}
                for row in result:
                    letter = row.get('letter', '').upper()
                    status[letter] = {
                        'pass': row.get('pass', False),
                        'metric': row.get('metric', 'null'),
                        'detail': row.get('detail', ''),
                        'threshold': row.get('threshold', '')
                    }
                return status
            else:
                print(f"{county_slug}: Query failed - {response.status_code}")
                return {}
    except Exception as e:
        print(f"{county_slug}: Error - {e}")
        return {}

def main():
    print("GOLD STANDARD SHARD-4 CURRENT STATUS")
    print("=" * 50)
    
    for county_slug, info in ASSIGNED_COUNTIES.items():
        print(f"\n{county_slug.upper()} (expected {info['current_status']}):")
        status = query_county_status(county_slug)
        
        if status:
            pass_count = sum(1 for v in status.values() if v.get('pass', False))
            print(f"  Current: {pass_count}/10 letters passing")
            
            # Show failing letters with highest potential
            failing_letters = []
            for letter, data in status.items():
                if not data.get('pass', False):
                    failing_letters.append({
                        'letter': letter,
                        'metric': data.get('metric', 'null'),
                        'detail': data.get('detail', '')
                    })
            
            if failing_letters:
                print("  Priority failing letters:")
                for fail in failing_letters[:5]:  # Top 5
                    print(f"    {fail['letter']}: {fail['metric']} - {fail['detail'][:50]}...")
        else:
            print("  ERROR: Could not query status")

if __name__ == "__main__":
    main()