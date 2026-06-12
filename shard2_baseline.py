#!/usr/bin/env python3
"""
Quick baseline check for SHARD-2 counties using environment Supabase connection
"""
import os
import json
import httpx
from datetime import datetime

# Configuration from environment/secrets (CLAUDE.md shows these are available)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://mocerqjnksmhcjzxrewo.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_SERVICE_KEY", "")

BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

SHARD2_COUNTIES = ['citrus', 'pinellas', 'collier', 'santa_rosa', 'holmes']

def test_connection():
    """Test basic connectivity"""
    try:
        client = httpx.Client(timeout=10)
        response = client.get(f"{BASE}/fl_counties?select=count&limit=1", headers=HEADERS)
        return response.status_code == 200
    except:
        return False

def get_county_metrics(county):
    """Get basic metrics for a county"""
    metrics = {}
    client = httpx.Client(timeout=30)
    
    try:
        # Total auctions
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={'county': f'eq.{county}', 'select': 'case_number'},
            timeout=20
        )
        
        if response.status_code == 200:
            auctions = response.json()
            metrics['total_auctions'] = len(auctions) if isinstance(auctions, list) else 0
        
        # Foreclosure vs Tax Deed breakdown (Letter A)
        for auction_type in ['fc', 'td']:
            response = client.get(
                f"{BASE}/multi_county_auctions",
                headers=HEADERS,
                params={
                    'county': f'eq.{county}',
                    'auction_type': f'eq.{auction_type}',
                    'select': 'case_number'
                },
                timeout=20
            )
            
            if response.status_code == 200:
                auctions = response.json()
                count = len(auctions) if isinstance(auctions, list) else 0
                metrics[f'{auction_type}_count'] = count
        
        # Closed auctions
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                'county': f'eq.{county}',
                'auction_status': 'in.(sold,no_sale,canceled)',
                'select': 'case_number'
            },
            timeout=20
        )
        
        if response.status_code == 200:
            closed = response.json()
            metrics['closed_sold'] = len(closed) if isinstance(closed, list) else 0
        
        # Parcel linked (Letter E)
        response = client.get(
            f"{BASE}/multi_county_auctions",
            headers=HEADERS,
            params={
                'county': f'eq.{county}',
                'parcel_id': 'not.is.null',
                'select': 'case_number'
            },
            timeout=20
        )
        
        if response.status_code == 200:
            linked = response.json()
            metrics['parcel_linked'] = len(linked) if isinstance(linked, list) else 0
        
        # Verified outcomes (Letter B)
        verified_count = 0
        for table in ['foreclosure_outcomes', 'tax_deed_outcomes']:
            try:
                response = client.get(
                    f"{BASE}/{table}",
                    headers=HEADERS,
                    params={
                        'county_slug': f'eq.{county}',
                        'data_source': 'not.ilike.*propertyonion*',
                        'select': 'case_number'
                    },
                    timeout=20
                )
                
                if response.status_code == 200:
                    outcomes = response.json()
                    count = len(outcomes) if isinstance(outcomes, list) else 0
                    verified_count += count
                    
            except Exception as e:
                print(f"Warning: Failed to query {table} for {county}: {e}")
        
        metrics['verified'] = verified_count
        
        # Calculate percentages
        if metrics.get('total_auctions', 0) > 0:
            metrics['parcel_linkage_pct'] = (metrics.get('parcel_linked', 0) * 100.0) / metrics['total_auctions']
        
        if metrics.get('closed_sold', 0) > 0:
            metrics['verification_pct'] = (verified_count * 100.0) / metrics['closed_sold']
        
        # Letter grades based on issue description
        metrics['grade_a'] = 'PASS' if metrics.get('fc_count', 0) > 0 and metrics.get('td_count', 0) > 0 else 'FAIL'
        metrics['grade_b'] = 'PASS' if metrics.get('verification_pct', 0) >= 95 else 'FAIL'
        metrics['grade_e'] = 'PASS' if metrics.get('parcel_linkage_pct', 0) >= 95 else 'FAIL'
        
        # Pass count
        grades = ['grade_a', 'grade_b', 'grade_e']
        metrics['pass_count'] = sum(1 for grade in grades if metrics.get(grade) == 'PASS')
        
    except Exception as e:
        print(f"Error getting metrics for {county}: {e}")
        metrics['error'] = str(e)
    
    finally:
        client.close()
    
    return metrics

def main():
    print("🔍 SHARD-2 BASELINE CHECK")
    print(f"Counties: {', '.join(SHARD2_COUNTIES)}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Check credentials
    if not SUPABASE_KEY:
        print("❌ No Supabase API key found in environment")
        print("Available env vars:", [k for k in os.environ.keys() if 'SUPABASE' in k or 'DB' in k])
        return
    
    # Test connection
    if not test_connection():
        print("❌ Database connection failed")
        return
    
    print("✅ Database connected\n")
    
    # Get metrics for each county
    county_data = {}
    for county in SHARD2_COUNTIES:
        print(f"📊 {county.upper()}")
        metrics = get_county_metrics(county)
        county_data[county] = metrics
        
        # Display key metrics from issue description
        total = metrics.get('total_auctions', 0)
        fc = metrics.get('fc_count', 0)
        td = metrics.get('td_count', 0)
        verified = metrics.get('verified', 0)
        closed = metrics.get('closed_sold', 0)
        linked = metrics.get('parcel_linked', 0)
        parcel_pct = metrics.get('parcel_linkage_pct', 0)
        pass_count = metrics.get('pass_count', 0)
        
        print(f"    A: {metrics.get('grade_a', 'UNK')} [fc={fc} td={td}]")
        print(f"    B: {metrics.get('grade_b', 'UNK')} [verified={verified} closed_sold={closed}]")
        print(f"    E: {metrics.get('grade_e', 'UNK')} [parcel_linked={linked} of {total} ({parcel_pct:.1f}%)]")
        print(f"    Score: {pass_count}/10\n")
    
    # Priority analysis
    print("🎯 PRIORITY ANALYSIS:")
    priorities = []
    for county, metrics in county_data.items():
        if metrics.get('error'):
            print(f"{county}: ❌ ERROR - {metrics['error']}")
            continue
        
        total = metrics.get('total_auctions', 0)
        pass_count = metrics.get('pass_count', 0)
        
        # Holmes priority boost for being empty
        if county == 'holmes' and total == 0:
            priority_score = 10
            reason = "Empty county - needs bootstrap"
        else:
            priority_score = pass_count + (1 if total > 1000 else 0)  # Boost for volume
            reason = f"{pass_count}/10 pass, {total} auctions"
        
        priorities.append({
            'county': county,
            'score': priority_score,
            'reason': reason
        })
    
    priorities.sort(key=lambda x: x['score'], reverse=True)
    
    for i, p in enumerate(priorities, 1):
        print(f"{i}. {p['county'].upper()} (score: {p['score']}) - {p['reason']}")
    
    print(f"\n🎯 RECOMMENDED: Start with {priorities[0]['county'].upper()}")
    print("Focus: B (verified outcomes) → E (parcel linkage) → I (property cards)")

if __name__ == "__main__":
    main()